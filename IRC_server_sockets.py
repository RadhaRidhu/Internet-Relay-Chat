#!/usr/bin/python
#Name: Radha Natesan
# USAGE:   IRC_server_sockets.py <PORT>
#
# EXAMPLE: IRC_server_sockets.py 8000

import socket
import sys
from IRC_utility import *
import selectors
import types
import time

user_list = {}
room_list = {}
userLimitPerRoom = 5
maxRoomCount = 10
shutDown = False

#Process request received from the clients and send response
def process(dataStr,sock):
    global userId,roomId,room_list,user_list
    data = json.loads(dataStr)
    op_code = data["Header"]["OP-CODE"]

    #If opcode is connect, validate client name and store the client name and connection address in user_list
    if (op_code == opcode.IRC_OPCODE_CONNECT):
        username = data["Payload"]
        if (not validName(username)):
            return getResponse(errorresp.IRC_ERROR_ILLEGAL_NAME)
        elif (not isNameAvailable(username)):
            return getResponse(errorresp.IRC_ERROR_NAME_ALREADY_EXISTS)
        
        user_list[username] = {"Socket":sock} 

    #If opcode is to list room, send the response with list of rooms from room_list
    elif (op_code == opcode.IRC_OPCODE_LIST_ROOM):
        roomList = list(room_list.keys())
        return makeListResponse(opcode.IRC_OPCODE_LIST_ROOM_RESP,roomList)

    #if opcode is to list users from a room, extract the list under "users" key for the roomname in room_list
    elif (op_code == opcode.IRC_OPCODE_LIST_USERS):
        if valid_payload(opcode.IRC_OPCODE_LIST_USERS,data):
            roomname = data["Payload"]["Room-Name"]
            userList = []
            if (roomname in room_list):
                userList = room_list[roomname]["users"]
                return makeListResponse(opcode.IRC_OPCODE_LIST_USER_RESP,userList) 
            else:
                return getNoRoomErrResponse(roomname)
        else:
            return malformedRequest()  

    #if opcode is join a room, validate roomname and add an entry in room_list if the join request 
    #is for a new room along with the username. If request is for an existing room, add the username to the
    #"users" list for the roomname in room_list and increment the user count value under "count" by 1 for the room
    elif (op_code == opcode.IRC_OPCODE_JOIN):
        if valid_payload(opcode.IRC_OPCODE_JOIN,data):
            roomlist = json.loads(data["Payload"]["Room-Name"])
            username = data["Payload"]["User-Name"]
            for i in range(len(roomlist)):
                roomname = roomlist[i]
                if (not validName(roomname)):
                    return getResponse(errorresp.IRC_ERROR_ILLEGAL_NAME)
                elif (isMaxRoomLimitReached(roomname)):
                    return getResponse(errorresp.IRC_ERROR_USER_LIMIT_REACHED)
            for i in range(len(roomlist)):
                roomname = roomlist[i]
                if (roomname in room_list):
                    if (username not in room_list[roomname]["users"]):
                        usersCount = room_list[roomname]["count"]
                        room_list[roomname]["count"] = usersCount + 1
                        room_list[roomname]["users"].append(username)
                else:
                    if (len(room_list.keys()) == maxRoomCount):
                        return getRoomLimitReachedResponse(roomname)
                    else:
                        room_list[roomname] = {"count" : 1,"users":[username]}
        else:
            return malformedRequest()

    #If the opcode is leave, remove entry for the username from the room_list for the corresponding roomname and decrement 
    #the user count value under "count" by 1 for the room.
    elif (op_code == opcode.IRC_OPCODE_LEAVE):
        if valid_payload(opcode.IRC_OPCODE_LEAVE,data):
            roomlist = json.loads(data["Payload"]["Room-Name"])
            username = data["Payload"]["User-Name"]
            for i in range(len(roomlist)):
                roomname = roomlist[i]
                if (roomname in list(room_list.keys())):
                    usersCount = room_list[roomname]["count"]
                    if username in room_list[roomname]["users"]:
                        room_list[roomname]["count"] = usersCount - 1
                        room_list[roomname]["users"].remove(username)

        else:
            return malformedRequest()

    #If the opcode is send message, extract Room name, user name and message details from the payload and build show message 
    #response and send to all users that are part of the room.
    elif (op_code == opcode.IRC_OPCODE_SEND_MSG):
        if valid_payload(opcode.IRC_OPCODE_SEND_MSG,data):
            forRoomlist = json.loads(data["Payload"]["Room-Name"])
            message = data["Payload"]["Message"]
            fromUser = data["Payload"]["User-Name"]
            fwdMsg = []
            for i in range(len(forRoomlist)):
                forRoom = forRoomlist[i]
                if (forRoom in list(room_list.keys())):
                    users = room_list[forRoom]["users"]
                    for i in range(len(users)):
                        fwdMsg.append(show_message(users[i],fromUser,forRoom, message,""))
            return fwdMsg
        else:
            return malformedRequest()

    #If the opcode is to send group message, extract the roomlist from the payload and send the message to all users belonging 
    #to the targeted room.
    elif (op_code == opcode.IRC_OPCODE_SEND_GROUP_MSG):
        if valid_payload(opcode.IRC_OPCODE_SEND_GROUP_MSG,data):
            roomlist = json.loads(data["Payload"]["Room-Name"])
            message = data["Payload"]["Message"]
            fromUser = data["Payload"]["User-Name"]
            fwdMsg = []
            for i in range(len(roomlist)):
                forRoom = roomlist[i]
                if (forRoom in list(room_list.keys())):
                    users = room_list[forRoom]["users"]
                    for i in range(len(users)):
                        fwdMsg.append(show_message(users[i],fromUser,forRoom, message,""))
                else:
                    return getNoRoomErrResponse(forRoom)
            return fwdMsg
        else:
            return malformedRequest()

    #if the opcode is to send private message to a user, build show message response and send the message to the specific user.
    elif (op_code == opcode.IRC_OPCODE_SEND_PRV_MSG):
        if valid_payload(opcode.IRC_OPCODE_SEND_PRV_MSG,data):
            touser = data["Payload"]["To-User"]
            message = data["Payload"]["Message"]
            fromUser = data["Payload"]["User-Name"]
            fwdMsg = []
            if touser in list(user_list.keys()):
                fwdMsg.append(show_message(touser,fromUser,"PRV MSG", message,""))
            else:
                return getNoUserErrResponse(touser)
            return fwdMsg
        else:
            return malformedRequest()

    #if opcode is to quit from IRC application, remove the corresponding user from all the participating rooms and delete the entry
    #from user_list dictionary.
    elif (op_code == opcode.IRC_OPCODE_QUIT):
        print(data)
        if valid_payload(opcode.IRC_OPCODE_QUIT,data):
            username = data["Payload"]["User-Name"]
            deleteUserData(username)
        else:
            return malformedRequest()
    else:
        return illegalRequestCode()
    return getResponse(opcode.IRC_OPCODE_OK)

#Validate Room/User name length to be between 1 and 20
def validName(name):
    if (len(name) < 1 or len(name) > 20):
        return False
    return True

#Check if the username is not already taken
def isNameAvailable(username):
    if (username in list(user_list.keys())):
        return False
    return True

#Check if the user per room limit has reached
def isMaxRoomLimitReached(roomname):
    if (roomname in room_list):
        usersCount = room_list[roomname]["count"]
        if usersCount == userLimitPerRoom:
            return True
    return False

#Propagate shut down server response to all users
def shutDownServer():
    res = []
    for key in user_list:
        res.append(serverShutdownResponse(key))
    shutDown = True
    return res

#Remove the user from all the participating rooms and delete the entry from user_list dictionary. 
def deleteUserData(username):
    global user_list,room_list
    for key in room_list:
        if username in room_list[key]["users"]:
            usersCount = room_list[key]["count"]
            room_list[key]["count"] = usersCount - 1
            room_list[key]["users"].remove(username)   
    if username in list(user_list.keys()):
        user_list.pop(username) 

#Accept connection from the socket and create inbound and outbound queues. Register the socket with selector to enable 
#non-blocking receive event
def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print('accepted connection from', addr)
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

#Perform READ and WRITE event whenever the connection is ready
def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    '''if shutDown:
        print('Shutting down')
        sel.unregister(sock)
        sock.close()   
        sel.close() '''

    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        print('received:', recv_data)
        if recv_data:
            outdata = process(decrypt(recv_data),sock)
            if (type(outdata) is list):
                for i in range(len(outdata)):
                    touser = json.loads(outdata[i])["Payload"]["User-Name"]
                    tosocket = user_list[touser]["Socket"]
                    tosocket.send(outdata[i].encode())
                    time.sleep(0.1)
            else:
                data.outb = outdata.encode() 
        else:
            #if client crashes, delete client data and close connection
            print('closing connection to', data.addr)
            for username, s in user_list.items():
                userSocket = s['Socket']
                if userSocket.getpeername() == sock.getpeername():
                    deleteUserData(username)
                    break
            sel.unregister(sock)
            sock.close()
    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print('sending', repr(data.outb), 'to', data.addr)
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]




if len(sys.argv) < 2:
    print ("USAGE:   echo_server_sockets.py <PORT>")
    sys.exit(0)

#Create socket to listen from the port
sel = selectors.DefaultSelector()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = ''
port = int(sys.argv[1])
s.bind((host, port))
s.listen()
s.setblocking(False)
sel.register(s, selectors.EVENT_READ, data=None)

#wait for selector event
while (1):
    events = sel.select(timeout=None)
    for key, mask in events:
        if key.data is None:
            accept_wrapper(key.fileobj)
        else:
            service_connection(key, mask)


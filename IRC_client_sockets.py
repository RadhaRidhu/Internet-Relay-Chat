#!/usr/bin/python
#Name: Radha Natesan
# USAGE:   IRC_client_sockets.py <HOST> <PORT>
#
# EXAMPLE: IRC_client_sockets.py localhost 8000 
import socket
import sys
from IRC_utility import *
import selectors
import types
import threading
import time	

#Global variables
roomJoinedList = []
roomPendingJoin = []
inChatRoom = False
user_name = ""
messages = []  
currentRequest = reqtype.LOGIN
runThreadRcv = False
getUserResponse = False
mainloop = True

# Create request to get the list of rooms available
def listRooms():
	global messages
	messages = [list_rooms()]
 
# Create request to get the user list of a chat room
def listUsers(roomname):
	global messages
	messages = [list_users(roomname)]

# Create request to Login user
def loginUser():
	#Get user name
	global messages,user_name
	print (bcolors.BLUE + 'Enter User name :' + bcolors.ENDC)
	user_name = input()
	messages = [connect_user(user_name)]
					
# Create request to join a room/multiple rooms
def joinRoom(roomlist):
	global messages,user_name, roomPendingJoin
	roomPendingJoin = roomlist.copy()
	messages = [join_room(roomlist,user_name)]

# Create request to leave all rooms/specific rooms
def leaveRoom(roomlist):
	global messages,user_name
	messages = [leave_room(roomlist,user_name)]

# Create request to exit from the IRC app
def quitIRC():
	global messages,user_name
	messages = [quit(user_name)]	

# Parse response from the server and wait for next command
def process_response(dataStr):
	data = json.loads(dataStr)
	op_code = data["Header"]["OP-CODE"]

	#Parse the show message response and display the message on screen
	if (op_code == opcode.IRC_OPCODE_SHOW_MSG):
		fromuser = data["Payload"]["From-User"]
		roomname = data["Payload"]["To-Room"]
		frommessage = data["Payload"]["Message"]
		print(bcolors.BOLD + fromuser + ':<' + roomname + '> ' + bcolors.BLUE + frommessage + bcolors.ENDC)

	#Illegal User/Room name. Request for a different name.
	elif (op_code == errorresp.IRC_ERROR_ILLEGAL_NAME):
		print (bcolors.RED + bcolors.BOLD  + 'Invalid name.' + bcolors.ENDC)
		if (currentRequest == reqtype.LOGIN):
			loginUser()
		else:
			getUserCommand(key)

	#User name already taken. Request for a different user name
	elif (op_code == errorresp.IRC_ERROR_NAME_ALREADY_EXISTS):
		print (bcolors.RED + bcolors.BOLD  + 'Name already exists.' + bcolors.ENDC)
		loginUser() 

	#Maximum user per room limit reached. Choose a different room
	elif (op_code == errorresp.IRC_ERROR_USER_LIMIT_REACHED):
		print (bcolors.RED + bcolors.BOLD  + 'Max User/Room limit reached for the room.' + bcolors.ENDC)
		getUserCommand(key)

	#Maximum room limit reached. Choose a different room
	elif (op_code == errorresp.IRC_ERROR_ROOM_LIMIT_REACHED):
		print (bcolors.RED + bcolors.BOLD  + 'Max Room limit reached:' + bcolors.ENDC)
		if not inChatRoom:
			getUserCommand(key)

# Start Connection with the server by registering the socket with the selector
sel = selectors.DefaultSelector()
   
def start_connections(host, port, num_conns):
	server_addr = (host, port)
	for i in range(0, num_conns):
		connid = i + 1
		#print('starting connection', connid, 'to', server_addr)
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setblocking(False)
		sock.connect_ex(server_addr)
		#sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

		events = selectors.EVENT_READ | selectors.EVENT_WRITE
		data = types.SimpleNamespace(connid=connid,
									 msg_total=sum(len(m) for m in messages),
									 recv_total=0,
									 messages=list(messages),
									 outb=b'')
		sel.register(sock, events, data=data)

# Wait for user coomand and send request to the server
def getUserCommand(key):
	global runThreadRcv,currentRequest,messages,roomJoinedList,inChatRoom	
	data = key.data

	cmd = ""
	parm = ""
	parmlist = []

	while 1:
		user_input = input('<cmd> ').strip()

		if len(user_input.split()) > 1:
			cmd, *parmlist = user_input.split()
			parm = " ".join(parmlist)
		else:
			cmd = user_input
		
		if cmd == command.LISTROOMS:
			currentRequest = reqtype.LISTROOMS
			listRooms()
			data.messages = messages
			break

		elif cmd == command.LISTUSERS:
			if (parmlist == []):
				print('Missing parameters: \\listusers <roomname>')
			else:
				roomname = parm
				currentRequest = reqtype.LISTUSERS
				listUsers(roomname)
				data.messages = messages
				break

		elif cmd == command.JOIN:
			if (parmlist == []):
				print('Missing parameters: \\join <roomname>')
			else:
				#runThreadRcv = False
				roomname = parm
				currentRequest = reqtype.JOIN
				joinRoom(parmlist)
				data.messages = messages
				break

		elif cmd == command.QUIT:
			currentRequest = reqtype.QUIT
			quitIRC()
			data.messages = messages
			runThreadRcv = False	
			break

		elif cmd == command.LEAVE:
			if roomJoinedList != []:
				time.sleep(0.1)
				if (parmlist == []):
					leaveRoom(roomJoinedList)
					roomJoinedList = []
					inChatRoom = False
				else:
					leaveRoom(parmlist)
					for room in parmlist:
						roomJoinedList.remove(room)
				if roomJoinedList == []:
					runThreadRcv = False
				currentRequest = reqtype.LEAVE
				data.messages = messages
				service_connection(key,selectors.EVENT_WRITE)
				break
			else:
				print('No rooms joined')

		elif cmd == command.MSG:
			if roomJoinedList != []:
				messages = [send_message(roomJoinedList,user_name,parm)]
				data.messages = messages
				break

		elif cmd == command.MSGROOM:
			roomCount = int(parmlist[0])
			currentRequest = reqtype.MSGROOM
			roomList = parmlist[1:roomCount+1]
			msg = " ".join(parmlist[roomCount+1:])
			messages = [send_group_message(roomList,user_name,msg)]
			data.messages = messages
			break

		elif cmd == command.PRVMSG:
			touser = parmlist[0]
			currentRequest = reqtype.PRVMSG
			msg = " ".join(parmlist[1:])
			messages = [send_private_message(touser,user_name,msg)]
			data.messages = messages
			break

# Start Connection with the server by registering the socket with the selector 
def service_connection(key, mask):
	global currentRequest,messages,runThreadRcv,getUserResponse,roomJoinedList,inChatRoom,roomPendingJoin
	sock = key.fileobj
	data = key.data
	if mask & selectors.EVENT_READ:
		recv_data = sock.recv(1024)  # Should be ready to read
		if recv_data:
			#print('received', repr(recv_data), 'from connection', data.connid)
			data.recv_total += len(recv_data)
			response = json.loads(recv_data)
			op_code = response["Header"]["OP-CODE"]

			#Process show message and display the message on screen
			if (op_code == opcode.IRC_OPCODE_SHOW_MSG):
				touser = response["Payload"]["User-Name"]
				if(touser == user_name):
					process_response(recv_data)
				else:
					messages = [recv_data]
					data.messages = messages
					service_connection(key,selectors.EVENT_WRITE)
			
			#Shut down message from server. Clost selector and quit
			elif (op_code == opcode.IRC_OPCODE_SERVER_SHUTDOWN):
				print('Server shutting down. Good Bye!')	
				sel.close()

			#Login response if successful, wait for user input
			elif (currentRequest == reqtype.LOGIN) :
				if (op_code == opcode.IRC_OPCODE_OK):
					print('Login successful')
					getUserCommand(key)
				else:
					process_response(recv_data)
					data.messages = messages
					service_connection(key,selectors.EVENT_WRITE)
			
			#Display the rooms received in the response on screen.		
			elif (currentRequest == reqtype.LISTROOMS) :
				if (op_code == opcode.IRC_OPCODE_LIST_ROOM_RESP):
					roomList = response["Payload"]["Message"]
					print (bcolors.MAGENTA + bcolors.BOLD + 'Available Rooms List :' + bcolors.ENDC)
					print ((bcolors.MAGENTA + roomList + bcolors.ENDC))
					if not inChatRoom:
						getUserCommand(key)
			
			#Display the user list received in the response on screen.	
			elif (currentRequest == reqtype.LISTUSERS) :
				if (op_code == opcode.IRC_OPCODE_LIST_USER_RESP):
					userList = response["Payload"]["Message"]
					print (bcolors.MAGENTA + bcolors.BOLD + 'Users List :' + bcolors.ENDC)
					print ((bcolors.MAGENTA + userList + bcolors.ENDC))
				elif (op_code == errorresp.IRC_ERROR_MALFORMED_REQUEST):
					print (bcolors.RED + bcolors.BOLD  + 'Invalid request received.' + bcolors.ENDC)
				elif (op_code == errorresp.IRC_ERROR_ROOM_NOT_FOUND):
					print (bcolors.RED + bcolors.BOLD  + 'Room not found.' + bcolors.ENDC)
				if not inChatRoom:
						getUserCommand(key)
			
			#Start the chat session. Create a thread to do a data receive/send in the background	
			elif (currentRequest == reqtype.JOIN) :
				if (op_code == opcode.IRC_OPCODE_OK):
					roomJoinedList = roomJoinedList + roomPendingJoin
					roomPendingJoin = []
					print (bcolors.BLUE + 'Welcome to ' + " ".join(roomJoinedList) + bcolors.ENDC)
					
					if not runThreadRcv:
						runThreadRcv = True
						response_thread = threading.Thread(target=service_response)
						response_thread.start()

					if not inChatRoom:
						inChatRoom = True
						while roomJoinedList != []:
							getUserCommand(key)
				else:
					roomPendingJoin = []
					process_response(recv_data)
					data.messages = messages
					service_connection(key,selectors.EVENT_WRITE)

			#Send message to multiple rooms
			elif (currentRequest == reqtype.MSGROOM) :
				if (op_code == errorresp.IRC_ERROR_ROOM_NOT_FOUND):
					print (bcolors.RED + bcolors.BOLD  + 'Room not found.' + bcolors.ENDC)
				if not inChatRoom:
						getUserCommand(key)

			#Send private message 
			elif (currentRequest == reqtype.PRVMSG) :
				if (op_code == errorresp.IRC_ERROR_USER_NOT_FOUND):
					print (bcolors.RED + bcolors.BOLD  + 'User not found.' + bcolors.ENDC)
				if not inChatRoom:
						getUserCommand(key)

			#Leave the room
			elif (currentRequest == reqtype.LEAVE) :
				if (op_code == errorresp.IRC_ERROR_MALFORMED_REQUEST):
					print (bcolors.RED + bcolors.BOLD  + 'Invalid request received.' + bcolors.ENDC)
				if not inChatRoom:
						getUserCommand(key)

			#Quit IRC and close selector
			elif (currentRequest == reqtype.QUIT) :
				if (op_code == opcode.IRC_OPCODE_OK):
					runThreadRcv = False
					print('Good Bye!')	
					sel.close()
				elif (op_code == errorresp.IRC_ERROR_MALFORMED_REQUEST):
					print (bcolors.RED + bcolors.BOLD  + 'Invalid request received.' + bcolors.ENDC)
					if not inChatRoom:
						getUserCommand(key)


		if not recv_data or data.recv_total == data.msg_total:
			print('IRC Server not available. Try connecting later.')
			sel.unregister(sock)
			sock.close()
			runThreadRcv = False
			print('Good Bye!')	
			sel.close()
	#If WRITE event, send message from outbound queue in the socket
	if mask & selectors.EVENT_WRITE:
		if not data.outb and data.messages:
			data.outb = data.messages.pop(0)
		if data.outb:
			#print('sending', repr(data.outb), 'to connection', data.connid)
			sent = sock.send(encrypt(data.outb))  # Should be ready to write
			data.outb = data.outb[sent:]

#This method runs in a thread and is started whenever user joins a chat room      
def service_response():

	try:
		while (runThreadRcv):
			events = sel.select(timeout=1)
			if events:
				for key, mask in events:
					service_connection(key,mask)
			# Check for a socket being monitored to continue.
			if not sel.get_map():
				break
	except ConnectionRefusedError:
            print('Server not responding. Please try connecting later.')
	except KeyboardInterrupt:
		print("caught keyboard interrupt, exiting")
	finally:
		print('closing sel')
		#sel.close()

 
print (bcolors.MAGENTA + bcolors.BOLD  + 'Internet Relay Chat Application' + bcolors.ENDC)
print (bcolors.MAGENTA + bcolors.BOLD  + 'IRC commands:' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\listrooms' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\listusers <room-name>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\join <room-list>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\leave <room-list>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\msg <message>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\msgroom <room-count> <room list> <message>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\prvmsg <user-name> <message>' + bcolors.ENDC)
print (bcolors.MAGENTA + '\\quit' + bcolors.ENDC)

if len(sys.argv) < 3:
	print ("USAGE: IRC_client_sockets.py <HOST> <PORT>")
	sys.exit(0)

#Parse host details and connect to server
host = sys.argv[1]
port = int(sys.argv[2])

loginUser()
start_connections(host,port,1)

#wait for READ/WRITE event on the connection
try:
	while True:
		events = sel.select(timeout=1)
		if events:
			for key, mask in events:
				service_connection(key,mask)
		# Check for a socket being monitored to continue.
		if not sel.get_map():
			break
except ConnectionRefusedError:
            print('Server not responding. Please try connecting later.')
except KeyboardInterrupt:
	print("caught keyboard interrupt, exiting")
finally:
	sel.close()


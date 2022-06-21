#!/usr/bin/python
#Name: Radha Natesan
# USAGE:   IRC_client_sockets.py <HOST> <PORT> <MESSAGE>
#
# EXAMPLE: IRC_client_sockets.py localhost 8000 
import sys
import json
import base64
from Crypto import Random
from Crypto.Cipher import AES

#Color codes for formatting input
class bcolors:
    MAGENTA     = '\033[95m'
    BLUE        = '\033[94m'
    GREEN       = '\033[92m'
    YELLOW      = '\033[93m'
    RED         = '\033[91m'
    CYAN        = '\033[96m'
    ENDC        = '\033[0m'
    BOLD        = '\033[1m'
    UNDERLINE   = '\033[4m'

#Request Type
class reqtype:
    LOGIN       = 1
    LISTROOMS   = 2
    JOIN        = 3
    SENDMSG     = 4
    LEAVE       = 5
    LISTUSERS   = 6
    QUIT        = 7
    MSGROOM     = 8
    PRVMSG      = 9

#User command 
class command:
    LISTROOMS = '\\listrooms'
    LISTUSERS = '\\listusers'
    JOIN = '\\join'
    LEAVE = '\\leave'
    QUIT = '\\quit'
    MSG = '\\msg'
    MSGROOM = '\\msgroom'
    PRVMSG = '\\prvmsg'

#Opcodes to construct request and responses
class opcode:
    IRC_OPCODE_CONNECT          = 1 
    IRC_OPCODE_OK               = 2
    IRC_OPCODE_JOIN             = 3
    IRC_OPCODE_SEND_MSG         = 4
    IRC_OPCODE_SHOW_MSG         = 5
    IRC_OPCODE_LIST_ROOM        = 6
    IRC_OPCODE_LIST_ROOM_RESP   = 7 
    IRC_OPCODE_LEAVE            = 8
    IRC_OPCODE_LIST_USERS       = 9
    IRC_OPCODE_LIST_USER_RESP   = 10
    IRC_OPCODE_QUIT             = 11
    IRC_OPCODE_SEND_GROUP_MSG   = 12
    IRC_OPCODE_SEND_PRV_MSG     = 13
    IRC_OPCODE_SERVER_SHUTDOWN  = 14

#Error response code
class errorresp:
    IRC_ERROR_ILLEGAL_NAME          = 201
    IRC_ERROR_NAME_ALREADY_EXISTS   = 202
    IRC_ERROR_USER_LIMIT_REACHED    = 203
    IRC_ERROR_ROOM_LIMIT_REACHED    = 204
    IRC_ERROR_MALFORMED_REQUEST     = 205
    IRC_ERROR_ILLEGAL_REQUEST       = 206
    IRC_ERROR_ROOM_NOT_FOUND        = 207
    IRC_ERROR_USER_NOT_FOUND        = 208

#Build data with header and payload tags
def build_data(op_code,payload):
    IRC_data = {"Header": {"OP-CODE":op_code,
                            "Length":sys.getsizeof(payload)},
                "Payload": payload }
    return IRC_data

def getResponse(op_code):
    return json.dumps(build_data(op_code,""))

def connect_user(username):
    return json.dumps(build_data(opcode.IRC_OPCODE_CONNECT,username))
  
def join_room(roomlist,username):
    payload = {"Room-Name":json.dumps(roomlist),"User-Name":username}
    return json.dumps(build_data(opcode.IRC_OPCODE_JOIN,payload))

def leave_room(roomlist,username):
    payload = {"Room-Name":json.dumps(roomlist),"User-Name":username}
    return json.dumps(build_data(opcode.IRC_OPCODE_LEAVE,payload))

def list_rooms():
    return json.dumps(build_data(opcode.IRC_OPCODE_LIST_ROOM,""))

def list_users(roomname):
    payload = {"Room-Name":roomname}
    return json.dumps(build_data(opcode.IRC_OPCODE_LIST_USERS,payload))

def send_message(roomlist,  fromuser, message):
    payload = {"Room-Name":json.dumps(roomlist),"User-Name":fromuser,"Message":message}
    return json.dumps(build_data(opcode.IRC_OPCODE_SEND_MSG,payload))

def send_group_message(roomlist,  fromuser, message):
    payload = {"Room-Name":json.dumps(roomlist),"User-Name":fromuser,"Message":message}
    return json.dumps(build_data(opcode.IRC_OPCODE_SEND_GROUP_MSG,payload))

def send_private_message(touser,  fromuser, message):
    payload = {"To-User":touser,"User-Name":fromuser,"Message":message}
    return json.dumps(build_data(opcode.IRC_OPCODE_SEND_PRV_MSG,payload))

def show_message(touser, fromuser, roomname, message, type):
    payload = {"User-Name":touser,"From-User":fromuser,"To-Room":roomname,"Message":message,"Type":type}
    return json.dumps(build_data(opcode.IRC_OPCODE_SHOW_MSG,payload))

def makeListResponse(op_code, listData):
    payload = {"Message":json.dumps(listData)}
    return json.dumps(build_data(op_code,payload))

def quit(username):
    payload = {"User-Name":username}
    return json.dumps(build_data(opcode.IRC_OPCODE_QUIT,payload))

def getRoomLimitReachedResponse(roomname):
    payload = {"Room-Name":roomname}
    return json.dumps(build_data(errorresp.IRC_ERROR_ROOM_LIMIT_REACHED,payload))

def getNoRoomErrResponse(roomname):
    payload = {"Room-Name":roomname}
    return json.dumps(build_data(errorresp.IRC_ERROR_ROOM_NOT_FOUND,payload))

def getNoUserErrResponse(roomname):
    payload = {"Room-Name":roomname}
    return json.dumps(build_data(errorresp.IRC_ERROR_USER_NOT_FOUND,payload))

def serverShutdownResponse(username):
    payload = {"User-Name":username}
    return json.dumps(build_data(opcode.IRC_OPCODE_SERVER_SHUTDOWN,payload))

#Check for malformed requests
def valid_payload(op_code, data):
    payload = data["Payload"]
    if (op_code == opcode.IRC_OPCODE_LIST_USERS):
        return ({"Room-Name"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_JOIN):
        return ({"Room-Name","User-Name"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_LEAVE):
        return ({"Room-Name","User-Name"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_SEND_MSG):
        return ({"Room-Name","User-Name","Message"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_SEND_GROUP_MSG):
        return ({"Room-Name","User-Name","Message"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_SEND_PRV_MSG):
        return ({"To-User","User-Name","Message"} == set(payload))
    if (op_code == opcode.IRC_OPCODE_QUIT):
        return ({"User-Name"} == set(payload))
    return True

def malformedRequest():
    return getResponse(errorresp.IRC_ERROR_MALFORMED_REQUEST)

def illegalRequestCode():
    return getResponse(errorresp.IRC_ERROR_ILLEGAL_REQUEST)


# AES Crypto for secure transfer
def encrypt(message):
    message = pad(message)
    iv = Random.new().read( AES.block_size )
    cipher = AES.new( 'This is a key123', AES.MODE_CBC, iv )
    return base64.b64encode( iv + cipher.encrypt( message ) )


def decrypt(ciphertext):
    ciphertext = base64.b64decode(ciphertext)
    iv = ciphertext[:16]
    cipher = AES.new('This is a key123', AES.MODE_CBC, iv )
    return unpad(cipher.decrypt( ciphertext[16:] ))

#Input strings must be a multiple of 16 in length
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-s[-1]]

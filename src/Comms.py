'''
Created on 20 Nov 2015

@author: Jurie
'''

import queue
from collections import deque
import socket
import select
import threading
from ctypes.wintypes import MSG
import json
from io import StringIO
from enum import Enum

class Comms(object):
    '''
    classdocs
    Base class implementation TCP socket communication
    '''


    def __init__(self, tcpIP, tcpPort):
        '''
        Constructor
        '''
        self.ipAddress = tcpIP
        self.portNumber = tcpPort
        self.transQ = queue.Queue()
        self.recvQ = queue.Queue()
        
        self.BUFFER_SIZE = 1024
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.connect((self.ipAddress, self.portNumber))
        
        self.terminate = False
        self.transmitCV = threading.Condition()
        
    def transmit(self):
        #This method will wait on condition variable, notified by a msg added to the Q. It will however only send a single msg.  It is the caller responsibility to add the loop.  Allowing expansion of the method.
        with self.transmitCV:
            print ('Entered transmit threaed') 
            while (self.transQ.empty() == True and not self.terminate):
                self.transmitCV.wait()
                
            if(self.transQ.empty() == False):
                msg = self.transQ.get_nowait()
                if(type(msg) is str):
                    msg = msg.encode()
                self.socket.send(msg)
    
    def receive(self):
        #This method waits for 1 second to receive a msg and adds it to the queue if there is.  It is the caller's responsibility to implement a loop.  This allows for expansion of the method.
        ready = select.select([self.socket],[],[],1)
        if(len(ready[0])!=0):
            data = (self.socket.recv(self.BUFFER_SIZE)).decode("utf-8").split('\n')[0]  #Read and translate received message into correct format.
            self.recvQ.put(data)
            return True
        else:
            return False
            
    def pushTransMsg(self, msg):
        #This method adds a msg to the transmit Q and notifies the thread.
        with self.transmitCV:
            self.transQ.put(msg)
            self.transmitCV.notify()
        
   
    def popRecvMsg(self):
        #Will raise Empty exception if there is no message in the Q
        return self.recvQ.get_nowait()
    
    def terminateComms(self):
        with self.transmitCV:
            self.terminate = True
            self.transmitCV.notify()

class RigComms(Comms):
    '''
    classdocs
    '''


    def __init__(self, tcpIP, tcpPort):
        '''
        Constructor
        '''
        Comms.__init__(self,tcpIP, tcpPort)
        #self.recvQ = Deque()    #Override recvQ to be a deque, allowing to peek at the first element.
        self.status = {}
        self.replies = {}
        self.ID = 0
        
        self.recvLock = threading.Lock()
        
    def receive(self):
        silenceCounter = 0
        while(self.terminate == False):
            self.recvLock.acquire()
            received = Comms.receive(self)
            if(received == False):
                silenceCounter +=1
            else:
                silenceCounter = 0
                try:
                    msgString = self.recvQ.get()
                    msg = json.loads(msgString)
                    key = next(iter(msg.keys()))
                    if(key == 'update'):
                        self.status = msg['update']
                        if(hasattr(self,'UI')):     #If attribute UI has been added by activateRigToUI(), forward the rig status
                            self.UI.pushTransMsg(msgString)
                    elif(key == 'reply'):
                        self.replies[msg['reply']['id']] = msg['reply']
                    else:
                        #Log invalid key
                        print('invalid key: ', key)
                except ValueError as e:
                    #Log invalid msg
                    print("Invalid msg")
            self.recvLock.release()
            
    def popRecvMsg(self):
        if(self.recvLock.acquire(blocking = False)==True):
            Comms.popRecvMsg(self)
            self.recvLock.release()
        else:
            raise ValueError
    
    def getStatus(self):
        return self.status
    
    def sendCmd(self, cmd): #Command is a dict of the JSON to be sent.  Excludes the ID and msg keyword
        cmd['id'] = self.ID
        self.ID +=1 #increment ID
        obj = {}
        obj['msg'] = cmd
        io = StringIO()
        json.dump(obj,io)
        msg = str.encode(io.getvalue() + '\n')
        self.pushTransMsg(msg)

        return self.ID-1 #Return ID-1 since ID has already been incremented.
    
    def getCmdReply(self,ID):
        if((ID in self.replies) == False):
            return (False,None)
        else:
            reply = self.replies[ID]
            del self.replies[ID]
            return (True,reply)
        
    def transmit(self):
        while(self.terminate != True):
            Comms.transmit(self)
            
    def activateRigToUI(self, UI):
        self.UI = UI


class UIComms(Comms):

    def __init__(self, tcpIP, tcpPort):
        self.status = {}
        self.commandsQ = queue.Queue()
        self.recvLock = threading.Lock()
        Comms.__init__(self, tcpIP, tcpPort)
        
    def receive(self):
        silenceCounter = 0
        while(self.terminate == False):
            self.recvLock.acquire()
            received = Comms.receive(self)
            if(received == False):
                silenceCounter +=1
            else:
                silenceCounter = 0
                try:
                    msgString = self.recvQ.get()
                    msg = json.loads(msgString)
                    key = next(iter(msg.keys()))
                    if(key == 'updateUI'):
                        self.status = msg['updateUI']
                        #TODO parse status to UI
                    elif(key == 'cmd'):
                        self.commandsQ.put_nowait(msg['cmd'])
                    elif(key == 'msg'):
                        if(hasattr(self,'rig')):     #If attribute rig has been added by activateUItoRig(), forward msg to rig
                            self.UI.pushTransMsg(msgString)
                    else:
                        #Log invalid key
                        print('invalid key: ', key)
                except ValueError as e:
                    #Log invalid msg
                    print("Invalid msg")
            self.recvLock.release()
        
    def getStatus(self):
        return self.status
    
    def sendReply(self, reply):
        obj = {}
        obj['reply'] = reply
        io = StringIO()
        json.dump(obj,io)
        msg = str.encode(io.getvalue() + '\n')
        self.pushTransMsg(msg)

    def getCmd(self):  #Raises and empty exception if no command
        return self.commandsQ.get_nowait()
        
    def sendAppStatus(self,status):
        obj = {}
        obj['appStatus'] = status
        io = StringIO()
        json.dump(obj,io)
        msg = str.encode(io.getvalue() + '\n')
        self.pushTransMsg(msg)
        
    def sendWarning(self,warning):
        obj = {}
        obj['warningMsg'] = warning
        io = StringIO()
        json.dump(obj,io)
        msg = str.encode(io.getvalue() + '\n')
        self.pushTransMsg(msg)
        
    def sendError(self,error):
        obj = {}
        obj['errorMsg'] = error
        io = StringIO()
        json.dump(obj,io)
        msg = str.encode(io.getvalue() + '\n')
        self.pushTransMsg(msg)
        
    def transmit(self):
        while(self.terminate != True):
            Comms.transmit(self)
        
    def activateUItoRig(self, rigComms):
        self.rig = rigComms

rigComms = RigComms('172.168.0.63',5000)

t_recv = threading.Thread(target = rigComms.receive)
t_recv.start()
t_trans = threading.Thread(target= rigComms.transmit)
t_trans.start()

uiComms = UIComms('172.168.0.63',5001)

t_recvUI = threading.Thread(target = uiComms.receive)
t_recvUI.start()
t_transUI = threading.Thread(target= uiComms.transmit)
t_transUI.start()

rigComms.activateRigToUI(uiComms)


inC = 0

while(inC != 10):
    inC = int(input('Options: \n1. SendCmd \n2. Get reply \n3. Get status \n4. SendUIcmd \n10. terminate'))
    if(inC == 1):
        print(rigComms.sendCmd({'type':'stateCmd','instr':"idle"}))
    elif(inC ==2):
        temp = int(input('Enter msg ID'))
        print(rigComms.getCmdReply(temp))
    elif(inC == 3):
        print('Rig',rigComms.getStatus())
        print('UI',uiComms.getStatus())
    elif(inC == 4):
        uiComms.sendWarning({"msg":"Dars fout"})
        
rigComms.terminateComms()
uiComms.terminateComms()
print ("Terminate called")
t_recv.join()
t_recvUI.join()
print("Recv joined")
t_trans.join()
t_transUI.join()
    
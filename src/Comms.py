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
        self.transQ = Queue()
        self.recvQ = Queue()
        
        self.BUFFER_SIZE = 1024
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.connect((self.ipAddress, self.portNumber))
        
        self.terminate = False
        self.transmitCV = threading.Condition()
        
    def transmit(self):
        with self.transmitCV:
            while (self.transQ.empty() == True and not self.terminate):
                self.transmitCV.wait()
        
        if not self.terminate:
            while(self.transQ.empty()==False):
                self.socket.send(self.transQ.get_nowait())
    
    def receive(self):
        ready = select.select([self.socket],None,None,1)
        
        if(ready[0].empty()==False):
            data = (self.socket.recv(self.BUFFER_SIZE)).decode("utf-8").split('\n')[0]  #Read and translate received message into correct format.
            self.recvQ.put(data)
            return True
        else:
            return False
            
    def pushTransMsg(self, msg):
        self.transQ.put(msg)
        self.transmitCV.notify()
        
   
    def popRecvMsg(self):
         #Will raise Empty exception if there is no message in the Q
        return self.recvQ.get_nowait()

class RigComms(Comms.Comms):
    '''
    classdocs
    '''


    def __init__(self, tcpIP, tcpPort):
        '''
        Constructor
        '''
        Comms.Comms(self,tcpIP, tcpPort)
        self.recvQ = Deque()    #Override recvQ to be a deque, allowing to peek at the first element.
        self.status = {}
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
                    msg = json.loads(self.recvQ[0])
                    key = next(iter(msg.keys()))
                    if(key == 'update'):
                        self.status = msg
                    elif(key != 'reply'):
                        self.recvQ.get()
                except ValueError as e:
                    #Log invalid msg
                    self.recvQ.get()
            self.recvLock.release()
            
        def popRecvMsg(self):
            if(self.recvLock.acquire(blocking = False)==True):
                Comms.popRecvMsg(self)
                self.recvLock.release()
            else:
                raise ValueError
            
            
            
        
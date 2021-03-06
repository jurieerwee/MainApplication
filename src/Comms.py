'''
Created on 20 Nov 2015

@author: Jurie
'''

import queue
from collections import deque
import socket
import select
from select import poll
import threading
import logging

import json
from io import StringIO
import datetime

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
		
		self.fdw = self.socket.makefile('w')
		self.fdr = self.socket.makefile('r')
		
		#self.rdPoll = poll()
		#self.rdPoll.register(self.fdr,select.POLLIN+select.POLLERR)

		
		self.terminate = False
		self.transmitCV = threading.Condition()
		
	def transmit(self):
		#This method will wait on condition variable, notified by a msg added to the Q. It will however only send a single msg.  It is the caller responsibility to add the loop.  Allowing expansion of the method.
			#print ('Entered transmit threaed') 
		try:
			msg = self.transQ.get(timeout=1)
			if(type(msg) is not str):
				#msg = msg.encode()
				msg = msg.decode("utf-8")
				
			#self.socket.send(msg) #must be encoded
			msg = msg.strip() + '\n'	#Ensures messages ends with a newline.
			try:
				self.fdw.write(msg) #must be decoded
				self.fdw.flush()
			except socket.error:
				self.terminateComms()
		except queue.Empty:
			pass
		
		#The outer trasmit will reinstantiate the function
	
	def receive(self):
		#This method waits for 1 second to receive a msg and adds it to the queue if there is.  It is the caller's responsibility to implement a loop.  This allows for expansion of the method.
		ready = select.select([self.fdr],[],[self.fdr],2)
		#print(self.ipAddress + 'sel'+ str(datetime.datetime.now()))
		if(len(ready[0])!=0):
			try:
				data = self.fdr.readline()#.strip()
				#print(self.ipAddress + 'rd'+str(datetime.datetime.now()))
				self.recvQ.put(data.strip('\x00'))
			except socket.error:
				self.recvQ.put(None)
				return False
			return True
		elif(len(ready[2])!=0):
			self.recvQ.put(None)
			return False
		else:
			return True
			
	def pushTransMsg(self, msg):
		#This method adds a msg to the transmit Q and notifies the thread.
		if(self.terminate == True):
			return False
		
		self.transQ.put(msg)
		
		return True

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
		#self.recvQ = Deque()	#Override recvQ to be a deque, allowing to peek at the first element.
		self.status = {}
		self.replies = {}
		self.ID = 0
		self.updateID = 0
		
		self.recvLock = threading.Lock()
		
	def receive(self):
		while(self.terminate == False):
			received = Comms.receive(self)
			if(received==False):
				self.terminateComms()
				
		if(not self.fdr.closed):
			self.fdr.close()
			
	def interpret(self):
		try:
			while(self.recvQ.empty()==False):
				msgString = self.recvQ.get()
				if(not msgString):
					self.terminateComms()	#Socket closed
				else:
					msg = json.loads(msgString)#,encoding='utf-8')
					#print("success msg: ", msgString)
					key = next(iter(msg.keys()))
					if(key == 'update'):
						self.status = msg['update']
						self.status.update({'id':self.updateID}) 	#Also add an ID to the update
						self.updateID +=1
						logging.debug('UpdateReceived:'+str(self.updateID-1))
					elif(key == 'reply'):
						self.replies[msg['reply']['id']] = msg['reply']
					else:
						#Log invalid key
						logging.warning('invalid key:%s' % key)
		except ValueError as e:
			#Log invalid msg
			print("Invalid msg: %s" % repr(msgString))

			
			
	def popRecvMsg(self):
		if(self.recvLock.acquire(blocking = False)==True):
			Comms.popRecvMsg(self)
			self.recvLock.release()
		else:
			raise ValueError
	
	def getStatus(self):
		return self.status
	
	def sendCmd(self, cmd): #Command is a dict of the JSON to be sent.  Excludes the ID and msg keyword
		cmd.update({'id':self.ID})
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
		
		if(not self.fdw.closed):
			self.fdw.close()
			
	def activateRigToUI(self, UI):
		self.UI = UI


class UIComms(Comms):

	def __init__(self, tcpIP, tcpPort):
		self.status = {}
		self.commandsQ = queue.Queue()
		self.recvLock = threading.Lock()
		self.promptID = 0
		self.promptReplies = {}
		Comms.__init__(self, tcpIP, tcpPort)
		
	def receive(self):
		while(self.terminate == False):
			received = Comms.receive(self)
			if(received==False):
				self.terminateComms()

		if(not self.fdr.closed):
			self.fdr.close()
			
	def interpret(self):
		try:
			while(self.recvQ.empty()==False):
				msgString = self.recvQ.get()
				if(not msgString):
					self.terminateComms()
				else:
					msg = json.loads(msgString)
					key = next(iter(msg.keys()))
					if(key == 'updateUI'):
						self.status = msg['updateUI']
						#TODO parse status to UI
					elif(key == 'cmd'):
						self.commandsQ.put_nowait(msg['cmd'])
					elif(key == 'msg'):
						if(hasattr(self,'rig')):	 #If attribute rig has been added by activateUItoRig(), forward msg to rig
							self.rig.pushTransMsg(msgString + '\n')
							logging.info('Msg forwarded')
					elif(key == 'promptReply'):
						self.promptReplies.update({msg['promptReply']['id']:msg['promptReply']})
					else:
						#Log invalid key
						logging.warning('invalid key: %s' %key)
		except ValueError as e:
			#Log invalid msg
			logging.warning("Invalid msg")
		
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
		try:
			return self.commandsQ.get_nowait()
		except:
			return None
	
	def getPromptReply(self,ref):
		if(ref in self.promptReplies):
			reply = self.promptReplies[ref]
			del self.promptReplies[ref]
			return reply
			
		else:
			return None
		
	def sendAppStatus(self,status):
		obj = {}
		obj['appStatus'] = status
		io = StringIO()
		json.dump(obj,io)
		msg = str.encode(io.getvalue() + '\n')
		self.pushTransMsg(msg)
		
	def sendRigUpdate(self,update):
		obj = {}
		obj['update'] = update
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
		
	def sendPrompt(self,prompt):
		obj = {}
		obj['prompt'] = prompt
		obj['prompt'].update({'id':self.promptID})	#Add id
		self.promptID+=1
		msg = json.dumps(obj)
		self.pushTransMsg(msg)
		
		return (self.promptID -1) #minus 1 since already incremented.
		
	def transmit(self):
		while(self.terminate != True):
			Comms.transmit(self)
		
		if(not self.fdw.closed):
			self.fdw.close()
		
	def activateUItoRig(self, rigComms):
		self.rig = rigComms



# rigComms = RigComms('172.168.0.63',5000)
# 
# t_recv = threading.Thread(target = rigComms.receive)
# t_recv.start()
# t_trans = threading.Thread(target= rigComms.transmit)
# t_trans.start()
# 
# uiComms = UIComms('172.168.0.63',5001)
# 
# t_recvUI = threading.Thread(target = uiComms.receive)
# t_recvUI.start()
# t_transUI = threading.Thread(target= uiComms.transmit)
# t_transUI.start()
# 
# rigComms.activateRigToUI(uiComms)
# 
# 
# inC = 0
# 
# while(inC != 10):
# 	inC = int(input('Options: \n1. SendCmd \n2. Get reply \n3. Get status \n4. SendUIcmd \n10. terminate'))
# 	if(inC == 1):
# 		print(rigComms.sendCmd({'type':'stateCmd','instr':"idle"}))
# 	elif(inC ==2):
# 		temp = int(input('Enter msg ID'))
# 		print(rigComms.getCmdReply(temp))
# 	elif(inC == 3):
# 		print('Rig',rigComms.getStatus())
# 		print('UI',uiComms.getStatus())
# 	elif(inC == 4):
# 		uiComms.sendWarning({"msg":"Dars fout"})
# 		
# rigComms.terminateComms()
# uiComms.terminateComms()
# print ("Terminate called")
# t_recv.join()
# t_recvUI.join()
# print("Recv joined")
# t_trans.join()
# t_transUI.join()
# 	
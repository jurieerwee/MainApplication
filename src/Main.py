'''
Created on 20 Nov 2015

@author: Jurie
'''

if __name__ == '__main__':
    pass

from Comms import *
import Control
import threading
import socket
import time
import sys
import logging

uiIP = 'localhost'
if(len(sys.argv)>1):
	uiIP = sys.argv[1]
	
rigIP = 'localhost'
if(len(sys.argv)>2):
	rigIP = sys.argv[2]
	
def initLogging():
	logging.basicConfig(filename='mainAppLog.log',filemode = 'w',level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

initLogging()

try:
	rigComms = RigComms(rigIP,5000)
except (socket.error):
	print('rigComms init failed')
	exit()
	
# class UIComms(object):
# 	def sendWarning(self,msg):
# 		print (msg)
# 		
# 	def sendError(self,msg):
# 		print(msg)
# 	
# uiComms = UIComms()
try:	
	uiComms = UIComms(uiIP,5001)
except (socket.error):
	logging.error('uiComms init failed')
	sys.exit()

rigComms.activateRigToUI(uiComms)
uiComms.activateUItoRig(rigComms)

t_recvUI = threading.Thread(target = uiComms.receive)
t_recvUI.start()
t_transUI = threading.Thread(target= uiComms.transmit)
t_transUI.start()
t_recv = threading.Thread(target = rigComms.receive)
t_recv.start()
t_trans = threading.Thread(target= rigComms.transmit)
t_trans.start()



rigComms.sendCmd({'type':'setCMD','instr':'activateUpdate'})
time.sleep(2)

i =0
while(not rigComms.getStatus() and i <10):
	time.sleep(0.5)
	i +=1

if(i==10):
	logging.error('No status...',rigComms.getStatus() )
	exit()

print(rigComms.getStatus())

ctrl = Control.Control(rigComms,uiComms)

ctrl.controlLoop()


rigComms.terminateComms()
uiComms.terminateComms()

t_trans.join()
t_recv.join()
t_recvUI.join()
t_transUI.join()
'''
Created on 20 Nov 2015

@author: Jurie
'''
from time import strftime

if __name__ == '__main__':
    pass

from Comms import *
import Control
import threading
import socket
from datetime import datetime
import sys
import time
import logging
import configparser
import os
from Results import Results


sessionDate= datetime.now()
directory = "/home/jurie/python_projects/MainApplication/outputs/"+sessionDate.strftime("%Y%m%d_%H%M")+"/"

if not os.path.exists(directory):
	os.makedirs(directory)
else:
	print("Output directory already exists...")
	exit()

os.chdir(directory)
	
def initLogging():
	logging.basicConfig(filename='mainAppLog.log',filemode = 'w',level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

def initConfig():
	config = configparser.ConfigParser()
	config.read(['ipSettings.conf','stateSettings.conf','rigID.conf'])
	return config

def initResults(config, sessionDate,coordinates):
	mqttParams = {'qos':2,'hostname':config['mqttServer'].get('ip'),'auth':{'username':config['mqttServer'].get('username',None),'password':config['mqttServer'].get('password',None)},'port':int(config['mqttServer'].get('port',1883)) }
	resultsComm = Results(mqttParams,config['mqttServer'].get('topicPrefix','waterleakage'), config.get('rigID'),sessionDate,config['mqttServer'].get('backupDir','/user/jurie/home/mqttUnsent'))
		
	return resultsComm

initLogging()
config = initConfig()
resultsComm = initResults(config, sessionDate)

'''Determine ip addresses and ports'''
if(len(sys.argv)>1):
	uiIP = sys.argv[1]
else:
	uiIP = config['ui'].get('ipaddress','localhost')
uiPort = int(config['ui'].get('port','5001'))

if(len(sys.argv)>2):
	rigIP = sys.argv[2]
else:
	rigIP = config['rig'].get('ipaddress','localhost')
rigPort = int(config['rig'].get('port','5000'))


try:
	rigComms = RigComms(rigIP,rigPort)
except (socket.error):
	print('rigComms init failed')
	exit()
	
try:	
	uiComms = UIComms(uiIP,uiPort)
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

coordinates = None
resultsComm.publishSession(coordinates,config['metadata'].get('softwareV','Undefined'),config.get('confV','Undefined'),config['metadata'].get('operator','Undefined'),float(config['metadata'].get('heightComp',0)))		


ctrl = Control.Control(rigComms,uiComms,resultsComm,config,sessionDate)

try:
	ctrl.controlLoop()
except KeyboardInterrupt:
	pass

print("Closing comms")
rigComms.terminateComms()
uiComms.terminateComms()

t_trans.join()
t_recv.join()
t_recvUI.join()
t_transUI.join()
'''
Created on 23 Nov 2015

@author: Jurie
'''


import threading
import logging
import json
from Comms import UIComms

class Control(object):
	'''
	classdocs
	'''
	rigCommands = {}
	rigCommands['prime'] = {'type':'stateCMD','instr':'prime'}
	rigCommands['idle'] = {'type':'stateCMD','instr':'idle'}
	rigCommands['fillTank'] = {'type':'stateCMD','instr':'fillTank'}
	rigCommands['forceFill'] = {'type':'stateCMD','instr':'forceFill'}
	rigCommands['startPump'] = {'type':'stateCMD','instr':'startPump'}
	rigCommands['newPressure'] = {'type':'stateCMD','instr':'newPressure'}
	rigCommands['releaseHold'] = {'type':'stateCMD','instr':'releaseHold'}
	rigCommands['clearErr'] = {'type':'stateCMD','instr':'clearErr'}
	rigCommands['override'] = {'type':'stateCMD','instr':'override'}
	rigCommands['disableOverride'] = {'type':'stateCMD','instr':'disableOverride'}
	rigCommands['terminate'] = {'type':'stateCMD','instr':'terminate'}
	rigCommands['resetCounters'] = {'type':'setCMD','instr':'resetCounters'}
	rigCommands['setPressure'] = {'type':'setCMD','instr':'setPressure'}
	rigCommands['setPumpPerc'] = {'type':'setCMD','instr':'setPumpPerc'}
	rigCommands['activateUpdate'] = {'type':'setCMD','instr':'activateUpdate'}
	rigCommands['startPumpMan'] = {'type':'manual','instr':'startPump'}
	rigCommands['stopPumpMan'] = {'type':'manual','instr':'stopPump'}
	rigCommands['openInflowVavle'] = {'type':'manual','instr':'openInflowVavle'}
	rigCommands['closeInflowVavle'] = {'type':'manual','instr':'closeInflowVavle'}
	rigCommands['openOutflowVavle'] = {'type':'manual','instr':'openOutflowVavle'}
	rigCommands['closeOutflowVavle'] = {'type':'manual','instr':'closeOutflowVavle'}
	rigCommands['openReleaseVavle'] = {'type':'manual','instr':'openReleaseVavle'}
	rigCommands['closeReleaseVavle'] = {'type':'manual','instr':'closeReleaseVavle'}
	rigCommands['error'] = {'type':'stateCMD','instr':'error'}

	def __init__(self, _rigComms, _uiComms):
		'''
		Constructor
		'''
		self.state = 'IDLE'
		self.mode = 'SINGLE_STATE'
		self.rigComms = _rigComms
		self.rigActive = True
		self.uiActive = True
		self.uiComms = _uiComms
		self.subStateStep = 1
		self.lastID = 0
		self.resetErrorID = -1 #For the reset of an error
		
		#leakageTest
		self.pressureSequence = [4,3.5,3,2.5,2]
		self.pressSeqCounter =0
		self.timer1Passed = False #Flag for use with timer1.
		self.results = [] #list of dictionaries for test results
		
		#Prompting
		self.promptID = -1
		
	def changeState(self,newState):	
		self.state = newState
		self.subStateStep =1
	
	def abort(self):
		logging.error('Abort')
		
	def nextState(self):
		logging.info('Next state')
		if(self.mode == 'SINGLE_STATE'):
			self.state = 'IDLE'
		
		self.subStateStep = 1

	def primeLoop(self):
		
		def step1():
			'''
			#Consider whether rig in the IDLE_PRES state. Issue a userWarning if not and IDLE, send primeCMD if it is.
			'''
			status = self.rigComms.getStatus()
			if(status['status']['state']=='IDLE_PRES'):
				self.lastID = self.rigComms.sendCmd(Control.rigCommands['prime'])
				self.subStateStep +=1
				logging.info('Continue from step1 to 2')
			else:
				self.uiComms.sendWarning({'id':2,'msg':'No system pressure. Returning to IDLE.'})
				logging.warning('No system pressure')
				self.changeState('IDLE')
		
		def step2():
			'''
			Wait for the primeCMD response. Abort if JSON error, IDLE if command unsuccessful, otherwise continue
			'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				logging.info('Reply received')
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':1,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					logging.info('Continue to step 3')
				else:
					self.uiComms.sendWarning({'id':1,'msg': 'Prime command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
			#TODO: Timeout on reply
		
		def step3():
			'''
			If in prime4 and stopFill instruction issured, goto IDLE. If in one of the IDLE state, go to IDLE
			''' 
			if(self.rigComms.getStatus()['status']['state']=='PRIME4'):	#TODO: add stopFill flag
				self.subStateStep = 1
				self.nextState()
			elif(self.updateIDref < self.rigComms.getStatus()['id'] and (self.rigComms.getStatus()['status']['state']=='IDLE' or (self.rigComms.getStatus()['status']['state']=='IDLE_PRES'))):
				self.subStateStep = 1
				self.nextState()
		
		
				
		stepsDict = {}
		stepsDict[1] = step1
		stepsDict[2] = step2
		stepsDict[3] = step3
		
		stepsDict[self.subStateStep]()
		
	primeLoop.stopFill = False
	
	def errorLoop(self):
		def step1():
			logging.error('In error state')
			self.subStateStep +=1
			
		def step2():
			if(self.rigComms.getStatus()['status']['state']!='ERROR'):
				self.changeState('IDLE')
		
		if(self.subStateStep ==1):
			step1()
		#elif(self.subStateStep==2):
		#	step2()
		
	def waitIsolateLoop(self):
		def step1():
			prmt = {'type':1,'msg':"Isolate pipe. YES if isolated, NO to cancel",'options':'yesno'}
			self.promptID = self.uiComms.sendPrompt(prmt)
			self.subStateStep +=1
		def step2():
			reply = self.uiComms.getPromptReply(self.promptID)
			if(reply):
				if(reply['reply']=='yes'):
					self.nextState()
				else:
					self.changeState('IDLE')
		
		if(self.subStateStep==1):
			step1()
		elif(self.subStateStep==2):
			step2()
	
	def leakTestLoop(self):
		def stopTimer1():
			''' Function used by timer time1.'''
			self.timer1Passed = True
		def step1():
			''' Send startPump command. Continue to next step'''
			self.lastID = self.rigComms.sendCmd(Control.rigCommands['startPump'])
			self.subStateStep +=1
			self.timer1Passed = False
			self.timer1 = threading.Timer(10,stopTimer1) #TODO: make settling time configurable
			self.timer1.start()
			logging.info('Step1 of leakageTest done')
			
		def step2():
			''' Wait for reply on startPump command. Continue to next step'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':2,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					logging.info('Continue to step 3')
				else:
					self.uiComms.sendWarning({'id':3,'msg': 'Start pump command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
					
		def step3():
			'''Wait for a few seconds before continuing in order for the pump to settle'''
			if(self.timer1Passed==True):
				self.subStateStep += 1
				self.updateIDref = self.rigComms.getStatus()['id']
				logging.info('Continue to step 4')
					
		def step4():
			'''Set the new pressure command.  This is also the entry point for the loop back next pressure is set'''
			setPresCMD = Control.rigCommands['setPressure']
			setPresCMD.update({'pressure':self.pressureSequence[self.pressSeqCounter]})
			self.lastID = self.rigComms.sendCmd(setPresCMD)
			self.pressSeqCounter +=1
			self.subStateStep +=1
			logging.info('Continue to step 5')
		
		def step5():
			'''Wait for reply on setPressure command. Send newPressure command.'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':3,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					self.lastID = self.rigComms.sendCmd(Control.rigCommands['newPressure'])
					logging.info('Continue to step 6')
				else:
					self.uiComms.sendWarning({'id':4,'msg': 'Set pressure command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
		
		def step6():
			'''Wait for reply on newPressure command. Start settling timer of 1minute.'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':4,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					self.timer1Passed = False
					self.timer1 = threading.Timer(60,stopTimer1) #TODO: make settling time configurable
					self.timer1.start()
					logging.info('Continue to step 7')
				else:
					self.uiComms.sendWarning({'id':5,'msg': 'New pressure command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
		
		def step7():
			'''Wait for settling period to pass.  Consider that rig in correct state. Reset the rig counters.'''
			if(self.timer1Passed == True):
				if(self.rigComms.getStatus()['status']['state']=='PRESSURE_HOLD'):
					logging.info('Settle period over.')
					self.lastID = self.rigComms.sendCmd(Control.rigCommands['resetCounters'])
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					self.timer1Passed = False
					self.timer1 = threading.Timer(30,stopTimer1)
					self.timer1.start()
					self.minMeasureTimePassed = False
				else:
					self.uiComms.sendWarning({'id':6,'msg':'Rig in wrong state after settling.'})
					self.changeState('IDLE')
					
		def step8():
			''' Wait for reply on resetCounters cmd. Continue to next step'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':5,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					logging.info('Continue to step 9')
				else:
					self.uiComms.sendWarning({'id':7,'msg': 'Reset counters command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
					
		def step9():
			'''Continue to next step once minimum measuring time has passed.  Also start the no-flow timeout'''
			if(self.timer1Passed == True): #Minimum measuring time passed.
				self.timer1Passed = False
				self.timer1 = threading.Timer(151,stopTimer1)	#Start no-flow timer
				self.subStateStep += 1
				self.updateIDref = self.rigComms.getStatus()['id']
				logging.info('Continue to step 10')
				
		def step10():	#TODO: Build in a pressure monitor for pressure changes.
			'''Take the measurings from the rig at the right time.  If no flow, stop test. '''
			status = self.rigComms.getStatus()
			if(status['setData']['flowCounter']>=3): #minimum of 3 pulses, ie, two delta
				self.timer1.cancel() #Stop no-flow timeout
				result = {'setPressure':self.pressureSequence[self.pressSeqCounter-1],'avePressure':status['setData']['pressure'],'aveFlow': status['setData']['flowRate']}
				self.results.append(result)
				logging.info('Results taken')
				
				self.updateIDref = self.rigComms.getStatus()['id']
				if(self.pressSeqCounter<len(self.pressureSequence)):
					self.subStateStep = 4 	#Jump back to set pressure step
					logging.info ('Return to step4')
				else: #Done
					self.subStateStep += 1
					logging.info('Continue to step 11')

			elif(self.timer1Passed == True): #No flow
				result =  {'setPressure':self.pressureSequence[self.pressSeqCounter-1],'avePressure':status['setData']['pressure'],'aveFlow': 0}
				self.results.append(result)
				self.updateIDref = self.rigComms.getStatus()['id']
				self.subStateStep +=1
				logging.info('Continue to step 11')
				
		def step11():
			'''Send final command for rig to IDLE'''
			self.lastID = self.rigComms.sendCmd(Control.rigCommands['idle'])
			self.updateIDref = self.rigComms.getStatus()['id']
			self.subStateStep +=1
			logging.info('Continue to step 12')
			
			
		def step12():
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':6,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.updateIDref = self.rigComms.getStatus()['id']
					self.nextState()
					self.subStateStep =1
					with open('testResults.txt','wt') as resultsFile:
						for datapoint in self.results:
							json.dump(datapoint,resultsFile,indent=4)
				else:
					self.uiComms.sendWarning({'id':8,'msg': 'Final idle command unsuccessful. Returning to IDLE'})
					self.changeState('IDLE')
					
		stepsDict = {}
		stepsDict[1] = step1
		stepsDict[2] = step2
		stepsDict[3] = step3
		stepsDict[4] = step4
		stepsDict[5] = step5
		stepsDict[6] = step6
		stepsDict[7] = step7
		stepsDict[8] = step8
		stepsDict[9] = step9
		stepsDict[10] = step10
		stepsDict[11] = step11
		stepsDict[12] = step12
		
		stepsDict[self.subStateStep]()

	def idleLoop(self):
		if(self.subStateStep == 1):
			logging.info( 'Entered idle in main.')
			self.lastID = self.rigComms.sendCmd(Control.rigCommands['idle'])
			self.updateIDref = self.rigComms.getStatus()['id']
			self.subStateStep =2
		if(self.subStateStep == 2):
			if(self.rigComms.getStatus()['id'] > self.updateIDref):
				if(self.rigComms.getStatus()['status']['state']!= 'IDLE' and self.rigComms.getStatus()['status']['state']!= 'IDLE_PRES'):
					self.subStateStep =1
				else:
					self.subStateStep =3
	
	'''Message interpret methods'''
	def enable_auto_continue(self):
		self.mode = 'AUTO_CONTINUE'
		return True
	def enable_stepthrough(self):
		self.mode = 'STEP_THROUGH'
		return True
	def enable_singlestate(self):
		self.mode = 'SINGLE_STATE'
		return True
	def startPrime(self): #For command use only
		if(self.state != 'IDLE'):
			return False
		self.changeState('PRIME')
		return True
	def startFill(self):
		if(self.state != 'IDLE'):
			return False
		self.changeState('FILL')
		return True
	def startForceFill(self):
		if(self.state != 'IDLE'):
			return False
		self.changeState('FORCEFILL')
		return True	
	def startIdle(self):	#Same as an stop command
		self.changeState('IDLE')
		return True
	def startPump(self):
		if(self.state != 'IDLE'):
			return False
		self.changeState('PUMP')
		return True
	def startSetPressure(self):
		return False	#Not yet correctly implemented.
	def startLeakageTest(self):	
		if(self.state != 'IDLE'):
			return False
		self.changeState('LEAKAGE_TEST')
		return True
	def startOverrive(self):
		if(self.state != 'IDLE'):
			return False
		self.changeState('OVERRIDE')
	def startWaitIsolate(self):
		if(self.state != 'IDLE'):
			return False
		self.changeState('WAIT_ISOLATE')
		return True
	def startIsolationTest(self):
		return False #not yet implemented
	def startDataUpload(self):
		return False #not yet implemented
	def startError(self):
		self.changeState('ERROR')
		self.rigComms.sendCmd(Control.rigCommands['error'])
	def continueCmd(self):
		self.nextState()
		return True
	def preemptCmd(self):
		self.preempt = True
		return True
	def clearError(self):
		if(self.state == 'ERROR'):
			self.rigComms.sendCmd(Control.rigCommands['clearErr'])
			self.changeState('IDLE')
			self.resetErrorID = self.rigComms.getStatus()['id']
			return True
		else:
			return False
	
	def cmdInterpret(self,cmd):		
		cmdID = None
		cmdDict = {"modeCMD":{"auto_continue":self.enable_auto_continue, "stepthrough":self.enable_stepthrough,"singlestate":self.enable_singlestate}\
				,"stateCMD":{"prime":self.startPrime,"fill":self.startFill,"forceFill":self.startForceFill,"idle":self.startIdle,"pump":self.startPump,"setPressure":self.startSetPressure\
							,"error":self.startError,"override":self.startOverrive,"leakageTest":self.startLeakageTest,"continue":self.continueCmd, "preempt":self.preemptCmd  \
								,"clearError":self.clearError, "waitIsolate":self.startWaitIsolate}
				}
		reply = {}
		
		try:
			cmdID = cmd['id']
			cmdType = cmd['type']
			instr = cmd['instr']
			response = cmdDict[cmdType][instr]()
			reply.update({'success':True,'code':response,'id':cmdID})
			logging.info('Command successfull: ' + json.dumps(cmd))
		except ValueError as e:
			if(cmdID):
				reply.update({'success':False,'id':cmdID})
			logging.error('Invalid command: '+json.dumps(cmd))
			logging.exception(e)
			raise
				
		if(reply):
			self.uiComms.sendReply(reply)
			
	def sendUpdate(self):
		self.updateTimer = threading.Timer(0.5,self.sendUpdate)
		self.updateTimer.start()
		update = {'mode':self.mode,'state':self.state,'step':self.subStateStep, 'results': self.results}
		self.uiComms.sendAppStatus(update)
	
	def controlLoop(self):
		self.stateFunctions = {'PRIME':self.primeLoop, 'IDLE':self.idleLoop, 'LEAKAGE_TEST':self.leakTestLoop, 'ERROR':self.errorLoop, 'WAIT_ISOLATE':self.waitIsolateLoop}
		logging.info('Started controlLoop')
		
		try:
			self.sendUpdate()
			
			while(True):
				if((self.resetErrorID +1 < self.rigComms.getStatus()['id']) and self.rigComms.getStatus()['status']['state']=='ERROR' and self.state != 'ERROR'):
					self.state = 'ERROR'
					self.subStateStep = 1;
					self.uiComms.sendError({'id':9,'msg':"Rig in error mode"})
				#Comms:
				if(self.rigActive == True and self.rigComms.terminate == True):
					self.rigActive = False
					self.uiComms.sendError({'id':8, 'msg':"Rig comss failed"})
					logging.error("Rig comms failed")
					self.state = 'ERROR'
					self.subStateStep = 1
				
				if(self.uiActive==True and self.uiComms.terminate == True):
					self.uiActive = False
					self.rigComms.sendCmd(Control.rigCommands['error'])
					logging.error("UI comms failed")
					self.state = 'ERROR'
					self.subStateStep = 1
				
				self.stateFunctions[self.state]()
				cmd = self.uiComms.getCmd()
				if(cmd):
					self.cmdInterpret(cmd)
		finally:
			self.updateTimer.cancel()

		
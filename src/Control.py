'''
Created on 23 Nov 2015

@author: Jurie
'''


import threading

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

	def __init__(self, _rigComms, _uiComms):
		'''
		Constructor
		'''
		self.state = 'LEAKAGE_TEST'
		self.mode = 'AUTO_CONTINUE'
		self.rigComms = _rigComms
		self.uiComms = _uiComms
		self.subStateStep = 1
		self.lastID = 0
		
		#leakageTest
		self.pressureSequence = [4,3.5,3,2.5,2]
		self.pressSeqCounter =0
		self.timer1Passed = False #Flag for use with timer1.
		self.results = [] #list of dictionaries for test results
		
		
	def abort(self):
		print('Abort')
		
	def nextState(self):
		print('Next state')
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
				print('Continue from step1 to 2')
			else:
				self.uiComms.sendWarning({'id':2,'msg':'No system pressure. Returning to IDLE.'})
				print('No system pressure')
				self.state = 'IDLE'
				self.subStateStep =1
		
		def step2():
			'''
			Wait for the primeCMD response. Abort if JSON error, IDLE if command unsuccessful, otherwise continue
			'''
			reply = self.rigComms.getCmdReply(self.lastID)
			if(reply[0]==True):
				print('Reply received')
				if(reply[1]['success'] == False):
					self.uiComms.sendError({'id':1,'msg': 'JSON error'})
					self.abort()
				elif(reply[1]['code'] == 1):
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					print('Continue to step 3')
				else:
					self.uiComms.sendWarning({'id':1,'msg': 'Prime command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
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
					print('Continue to step 3')
				else:
					self.uiComms.sendWarning({'id':3,'msg': 'Start pump command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
					
		def step3():
			'''Wait for a few seconds before continuing in order for the pump to settle'''
			if(self.timer1Passed==True):
				self.subStateStep += 1
				self.updateIDref = self.rigComms.getStatus()['id']
				print('Continue to step 4')
					
		def step4():
			'''Set the new pressure command.  This is also the entry point for the loop back next pressure is set'''
			setPresCMD = Control.rigCommands['setPressure']
			setPresCMD.update({'pressure':self.pressureSequence[self.pressSeqCounter]})
			self.lastID = self.rigComms.sendCmd(setPresCMD)
			self.pressSeqCounter +=1
			self.subStateStep +=1
			print('Continue to step 5')
		
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
					print('Continue to step 6')
				else:
					self.uiComms.sendWarning({'id':4,'msg': 'Set pressure command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
		
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
					print('Continue to step 7')
				else:
					self.uiComms.sendWarning({'id':5,'msg': 'New pressure command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
		
		def step7():
			'''Wait for settling period to pass.  Consider that rig in correct state. Reset the rig counters.'''
			if(self.timer1Passed == True):
				if(self.rigComms.getStatus()['status']['state']=='PRESSURE_HOLD'):
					print('Settle period over.')
					self.lastID = self.rigComms.sendCmd(Control.rigCommands['resetCounters'])
					self.subStateStep += 1
					self.updateIDref = self.rigComms.getStatus()['id']
					self.timer1Passed = False
					self.timer1 = threading.Timer(30,stopTimer1)
					self.timer1.start()
					self.minMeasureTimePassed = False
				else:
					self.uiComms.sendWarning({'id':6,'msg':'Rig in wrong state after settling.'})
					self.state = 'IDLE'
					self.subStateStep =1
					
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
					print('Continue to step 9')
				else:
					self.uiComms.sendWarning({'id':7,'msg': 'Reset counters command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
					
		def step9():
			'''Continue to next step once minimum measuring time has passed.  Also start the no-flow timeout'''
			if(self.timer1Passed == True): #Minimum measuring time passed.
				self.timer1Passed = False
				self.timer1 = threading.Timer(151,stopTimer1)	#Start no-flow timer
				self.subStateStep += 1
				self.updateIDref = self.rigComms.getStatus()['id']
				print('Continue to step 10')
				
		def step10():	#TODO: Build in a pressure monitor for pressure changes.
			'''Take the measurings from the rig at the right time.  If no flow, stop test. '''
			status = self.rigComms.getStatus()
			if(status['setData']['flowCounter']>=3): #minimum of 3 pulses, ie, two delta
				self.timer1.cancel() #Stop no-flow timeout
				result = {'setPressure':self.pressureSequence[self.pressSeqCounter-1],'avePressure':status['setData']['pressure'],'aveFlow': status['setData']['flowRate']}
				self.results.append(result)
				print('Results taken')
				
				self.updateIDref = self.rigComms.getStatus()['id']
				if(self.pressSeqCounter<len(self.pressureSequence)):
					self.subStateStep = 4 	#Jump back to set pressure step
					print ('Return to step4')
				else: #Done
					self.subStateStep += 1
					print('Continue to step 11')

			elif(self.timer1Passed == True): #No flow
				result =  {'setPressure':self.pressureSequence[self.pressSeqCounter-1],'avePressure':status['setData']['pressure'],'aveFlow': 0}
				self.results.append(result)
				self.updateIDref = self.rigComms.getStatus()['id']
				self.subStateStep +=1
				print('Continue to step 11')
				
		def step11():
			'''Send final command for rig to IDLE'''
			self.lastID = self.rigComms.sendCmd(Control.rigCommands['idle'])
			self.updateIDref = self.rigComms.getStatus()['id']
			self.subStateStep +=1
			print('Continue to step 12')
			
			
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
					with open('testResults.txt','wb') as resultsFile:
						for datapoint in self.results:
							resultsFile.write(datapoint)
				else:
					self.uiComms.sendWarning({'id':8,'msg': 'Final idle command unsuccessful. Returning to IDLE'})
					self.state = 'IDLE'
					self.subStateStep =1
					
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
			print( 'Entered idle in main.')
			self.lastID = self.rigComms.sendCmd(Control.rigCommands['idle'])
			self.updateIDref = self.rigComms.getStatus()['id']
			self.subStateStep =2
		if(self.subStateStep == 2):
			if(self.rigComms.getStatus()['id'] > self.updateIDref):
				if(self.rigComms.getStatus()['status']['state']!= 'IDLE' and self.rigComms.getStatus()['status']['state']!= 'IDLE_PRES'):
					self.subStateStep =1
				else:
					self.subStateStep =3
	
	def controlLoop(self):
		self.stateFunctions = {'PRIME':self.primeLoop, 'IDLE':self.idleLoop, 'LEAKAGE_TEST':self.leakTestLoop}
		print('Started controlLoop')
		
		gotCMD = False
		while(gotCMD == False):
			try:
				self.uiComms.getCmd()
				gotCMD = True
			except:
				gotCMD = False
		
		while(True):
			self.stateFunctions[self.state]()
			
			

		
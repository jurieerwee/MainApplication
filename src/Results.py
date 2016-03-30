'''
Created on 29 Mar 2016

@author: Jurie
'''
import paho.mqtt.publish as publish
import logging
import json
import datetime

class Results(object):
	'''
	classdocs sucessful 
	'''
	Results.SUCCESSFUL = 1
	Results.BACKEDUP = 2
	Results.FAILED = 0
	

	def __init__(self, _mqttPublishParams,_topicPrefix,_rigID,_sessionDate, _backupdir):
		'''
		Constructor
		'''
		self.mqttPublishParams =_mqttPublishParams
		self.topicPrefix=_topicPrefix
		self.rigID=_rigID
		self.sessionDate=_sessionDate.isoformat()[:-7]
		self.backupdir = _backupdir
		
		self.sessionStarted = False
		''' Session must be successfully published for other publishes to send'''
		
	def publishSession(self, coordinates=None,softwareV,confV,operator,heightComp):
		resultdict = {'date':self.sessionDate, 'coordinates':coordinates,'rigID':self.rigID, 'softwareV':softwareV, 'confV':confV, 'operator':operator, 'heigthCompensation':heightComp}
		
		with open('session.txt','wt') as resultsFile:
			json.dump(resultdict, resultsFile)
		
		repl =  self.publishMQTT(self.topicPrefix+'/'+self.rigID+'/session', resultdict, 'session')
		if (repl==Results.SUCCESSFUL):
			self.sessionStarted = True
		
		return repl
		
	def publishLeakTest(self,number,code,time,dataPoints):
		resultDict = {'sessionDate':self.sessionDate,'number':number,'code':code,'time':time.isoformat()[:-7],'dataPoints':dataPoints}
		
		with open('testResults'+str(number) +   '.txt','wt') as resultsFile:
				json.dump(resultDict, resultsFile)
		
		return self.publishMQTT(self.topicPrefix+'/'+self.rigID+'/leakTest',resultDict,'leakTest')
		
	def publishIsolationTest(self,number,code,time):
		resultDict = {'sessionDate':self.sessionDate,'number':number,'code':code,'time':time.isoformat()[:-7]}
		
		with open('isolationResults'+str(number) +   '.txt','wt') as resultsFile:
				json.dump(resultDict, resultsFile)
		
		return self.publishMQTT(self.topicPrefix+'/'+self.rigID+'/isoTest',resultDict,'isoTest')
	
	def publishSystemPressure(self,number,code,time,avePres,stdPred,maxPres,minPres):
		resultDict = {'sessionDate':self.sessionDate,'number':number,'code':code,'time':time.isoformat()[:-7],'avePres':avePres,'stdPred':stdPred,'maxPres':maxPres,'minPres':minPres}
		
		with open('SystemPressure'+str(number) +   '.txt','wt') as resultsFile:
				json.dump(resultDict, resultsFile)
		
		return self.publishMQTT(self.topicPrefix+'/'+self.rigID+'/sysPres',resultDict,'sysPres')
				
	def publishMQTT(self,topic,payload,msgType):
		'''Filename sould be in format msgType'''
		
		'''Transmission is only allowed if session type msg or session started activated. '''
		transmit = (self.sessionStarted == True or msgType=='session')
		if(transmit):
			repl = publish.single(topic,json.dump(payload),**self.mqttPublishParams)
		else:
			repl = [None,]
		
		if(transmit==False or repl[0]==publish.MQTT_ERR_NO_CONN):
			try:
				with open(self.backupdir+'/'+self.sessionDate+'_'+msgType+'.json','wt') as resultsFile:
					temp = {'topic':topic,'payload':payload}
					json.dump(temp, resultsFile)
				logging.warning('MQTT publish failed. File backed up: '+ topic)
				return Results.BACKEDUP
			except:
				logging.warning('MQTT publish failed. File backed up failed: '+ topic)
				return Results.FAILED
		else:
			logging.info('MQTT publish successful: '+ topic)
			return Results.SUCCESSFUL
			
		
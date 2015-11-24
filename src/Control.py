'''
Created on 23 Nov 2015

@author: Jurie
'''
from enum import Enum, unique

@unique
class States(Enum):
    IDLE, PRIME, FILL, FORCEFILL, PUMP, PRESSURE, ERROR, OVERRIDE, ISOLATION_TEST, PRESSURE_MEASURE, WAIT_USER, LEAKAGE_TEST = range(12)
@unique
class Modes(Enum):
    AUTO_CONTINUE, STEP_TROUGH, SINGLE_STATE, MANUAL = range(4)

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
        self.state = States.IDLE
        self.mode = Modes.AUTO_CONTINUE
        self.rigComms = _rigComms
        self.uiComms = _uiComms
        
    def abort(self):
        print('Abort')
        
    def nextState(self):
        print('Next state')

    def primeLoop(self):
        
        def step1():
            '''
            #Consider whether rig in the IDLE_PRES state. Issue a userWarning if not and IDLE, send primeCMD if it is.
            '''
            status = self.rigComms.getStatus()
            if(status['status']['state']=='IDLE_PRES'):
                self.primeLoop.lastID = self.rigComms.sendCmd(rigCommands['prime'])
                self.primeLoop.step +=1
                print('Continue from step1 to 2')
            else:
                self.uiComms.sendWarning('No system pressure. Returning to IDLE.')
                print('No system pressure')
                self.state = States.IDLE
                self.primeLoop.step =1
        
        def step2():
            '''
            Wait for the primeCMD response. Abort if JSON error, IDLE if command unsuccessful, otherwise continue
            '''
            reply = self.rigComms.getCmdReply(self.primeLoop.lastID)
            if(reply[0]==True):
                print('Reply received')
                if(reply[1]['success'] == False):
                    self.uiComms.sendError('JSON error')
                    self.abort()
                elif(reply[1]['code'] == 1):
                    self.primeLoop.step += 1
                    print('Continue to step 3')
                else:
                    self.uiComms.sendWarning('Prime command unsuccessful. Returning to IDLE')
                    self.state = States.IDLE
                    self.primeLoop.step =1
            #TODO: Timeout on reply
        
        def step3():
            '''
            If in prime4 and stopFill instruction issured, goto IDLE. If in one of the IDLE state, go to IDLE
            ''' 
            if(self.rigComms.getStatus()['status']['state']=='PRIME4' and self.primeLoop.stopFill == True):
                self.primeLoop.step = 1
                self.nextState()
            elif(self.rigComms.getStatus()['status']['state']=='IDLE' or (self.rigComms.getStatus()['status']['state']=='IDLE_PRES')):
                self.primeLoop.step = 1
                self.nextState()
        
        
                
        stepsDict = {}
        stepsDict[1] = step1
        stepsDict[2] = step2
        stepsDict[3] = step3
        
        stepsDict[self.primeLoop.step]()
        
    primeLoop.step = 1
    primeLoop.stopFill = False
        
    def controlLoop(self):
        while(True):
            self.primeLoop()
            
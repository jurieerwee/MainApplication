'''
Created on 20 Nov 2015

@author: Jurie
'''

if __name__ == '__main__':
    pass

from Comms import *
import Control
import threading

rigComms = RigComms('172.168.0.63',5000)
uiComms = UIComms('172.168.0.63',5001)

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

ctrl = Control.Control(rigComms,uiComms)




rigComms.terminateComms()
uiComms.terminateComms()

t_trans.join()
t_recv.join()
t_recvUI.join()
t_transUI.join()
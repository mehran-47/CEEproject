#!/usr/bin/env python3
import mimetypes, os, json, time, sys, copy
from threading import Thread, Event
from queue import Queue, Empty as QEmpty
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh, spawn, TIMEOUT
from mainLogFromCicParser import mainLogLiveParser

node_dicts = Queue(10)
updateApps = False
GUI_dict = {}
appDict = {}
callLoadDict = {}
allThreads = []
threadsRunning = Event()
upNodeCount = 0
root_dir = os.getcwd() + '/html/'
localSSHCreds = {'ip':'192.168.0.1', 'user':'mk', 'pw':'UIw0rk'}
SSHCreds = {'ip':'', 'user':'', 'pw':''}
SSHIP, SSHUser, SSHPw, fetchInterval, SSHConnectAttempts, GUIIP, GUIPort = None, None, None, None, None, None, None


def setConfigIPToActiveCIC():
    ps, ps1 = (pxssh.pxssh(),)*2 
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        ip, user, pw = configDict['ssh']['ip'], configDict['ssh']['username'], configDict['ssh']['password']
    if ps.login(ip, user, pw):
        current_cic_hostname = "".join(execute_commands(ps, ['hostname -s'])[-1].split())
        main_cic_hostname = execute_commands(ps, ['echo $(sudo crm_mon -1 | grep cmha| grep Started)'])[0].rsplit('Started')[-1]
        main_cic_hostname = "".join(main_cic_hostname.split())
        print('Main cic hostname: %s.' %(main_cic_hostname))
        if current_cic_hostname!=main_cic_hostname:
            print('Currently set IP in the \'config.json\' file does not belong to the main CIC, fetching main cic IP for GUI-config file. This might take upto 1 minute.')            
            main_cic_ip_string = execute_commands(ps, ['ssh '+user+'@'+main_cic_hostname, 'echo $(ifconfig br-ex | grep "inet addr:")', 'exit'])[-3]
            main_cic_ip_string = ["".join(s.split()) for s in re.findall(r'(?<=inet addr:)(.+)(?=Bcast)', main_cic_ip_string)][0]
            print('Main cic IP: %s' %(main_cic_ip_string))
            configDict['ssh']['ip'] = main_cic_ip_string
            with open('config.json', 'w') as conF:
                conF.write(json.dumps(configDict, indent=4, separators=(',', ':')))
        else:
            print("Config file has the main CIC IP.")
            ps.logout()


def load_config():
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        global SSHIP
        global SSHUser
        global SSHPw
        global GUIIP
        global GUIPort
        global SSHConnectAttempts
        global fetchInterval
        global SSHCreds
        global scaleAction
        SSHIP, SSHUser, SSHPw = configDict['ssh']['ip'], configDict['ssh']['username'], configDict['ssh']['password']
        SSHCreds['ip'], SSHCreds['user'], SSHCreds['pw'] = SSHIP, SSHUser, SSHPw
        SSHConnectAttempts, fetchInterval = configDict['ssh']['connectattempts'], float(configDict['ssh']['fetchinterval'])
        GUIIP, GUIPort, maxCalls = configDict['guiserver']['ip'], configDict['guiserver']['port'], configDict['guiserver']['maxcalls']
        scaleAction = configDict['scale_action']
        with open(root_dir+'gui_config.json', 'w') as guiconF:
            guiconF.write(json.dumps({'ajaxlink':'http://'+GUIIP+':'+str(GUIPort), 'maxcalls':maxCalls}))


def dictMerger(timeoutDelay=5, updateInterval=3):
    while threadsRunning.is_set():
        global GUI_dict
        global updateApps
        global callLoadDict
        global appDict
        global upNodeCount
        try:
            GUI_dict.update(node_dicts.get(True, timeout=updateInterval+timeoutDelay))
            node_dicts.task_done()
        except QEmpty:
            print("Didn't get any updated dictionary from the nodes, continuing without updating the GUI-dictionary")
        for aHost in GUI_dict:
            if aHost in mlp.appDictForGui:
                GUI_dict[aHost]['applications'] = mlp.appDictForGui[aHost]['applications']
            if GUI_dict[aHost].get('applications') is not None:
                for anApp in callLoadDict:
                    for aVm in GUI_dict[aHost]['applications']:
                        if anApp in aVm:
                            GUI_dict[aHost]['applications'][aVm]['calls'] = callLoadDict[anApp]['calls']
                            #print('GUI_dict callinfo:', GUI_dict[aHost]['applications'][aVm]['calls'])
            #print('######################updating apps####################\n', mlp.appDictForGui, '\n', GUI_dict)
        '''
        newUpNodeCount = getUpNodeCount(GUI_dict)
        if upNodeCount != newUpNodeCount: 
            updateApps = True
            upNodeCount = newUpNodeCount
        if updateApps:
            #Thread(target=update_with_oneoff_command, args=(['cat /home/mk/Documents/CM_HA_Demo/dummy_inputs/applications.txt'], appDict, localSSHCreds)).start()
            Thread(target=update_with_oneoff_command, args=(['nova list --fields host,name,state'], appDict)).start()
            updateApps=False
        reloadApps(GUI_dict, appDict)
        '''
        time.sleep(updateInterval)


def update_with_commands(commandList, queueToUpdate, parserFunction, sshInfo=SSHCreds):
    ps = pxssh.pxssh()
    global threadsRunning
    try:
        for i in range(1, SSHConnectAttempts):
            if ps.login(sshInfo['ip'], sshInfo['user'], sshInfo['pw']):
                while threadsRunning.is_set():
                    aDict = parserFunction(execute_commands(ps,commandList))
                    #print(aDict)
                    queueToUpdate.put(aDict)
                    time.sleep(fetchInterval)
            if not threadsRunning.is_set(): break
        ps.logout()
    except KeyboardInterrupt:
        print('\nSSH pull interrupted, quitting')
        ps.logout()


def update_with_call_load():
    global callLoadDict
    sshHandle = pxssh.pxssh()
    with open('config.json', 'r') as conF: 
        creds = json.loads(conF.read())['ssh_call_info']
    if sshHandle.login(creds['ip'], creds['username'], creds['password']):
        while threadsRunning.is_set():
            sshHandle.sendline(creds['command_to_send'])
            sshHandle.prompt()
            tempLines = sshHandle.before.decode('utf-8').splitlines()[-1]
            tempCallLoadDict = json.loads(tempLines) if tempLines is not None else {}
            for aVm in tempCallLoadDict:
                if aVm not in callLoadDict: callLoadDict[aVm] = {}                    
                callLoadDict[aVm]['calls'] = tempCallLoadDict[aVm]
            time.sleep(fetchInterval)
        sshHandle.logout()


def update_with_oneoff_command(commandList, dictToUpdate, sshInfo=SSHCreds):
    ps = pxssh.pxssh()    
    if ps.login(sshInfo['ip'], sshInfo['user'], sshInfo['pw']):
        extractedAppDict = app_list_to_dict(execute_commands(ps, commandList))
        exportAppListToConfigFile(extractedAppDict)
        dictToUpdate.update(extractedAppDict)
    ps.logout()


def reloadApps(dictToUpdate, source):
    for key in dictToUpdate:
        if key not in source or len(source[key]['applications'])==0:
            dictToUpdate[key]['applications'] = {}
        else:
            dictToUpdate[key]['applications'] = source[key]['applications']        


def getUpNodeCount(dictToCountFrom):
    toRet = 0
    for aNode in dictToCountFrom:
        if dictToCountFrom[aNode]['state']=='up':
            toRet += 1
    return toRet


def _reset_updateApps():
    while True:
        global updateApps
        updateApps = True
        time.sleep(60)


def button_action_reboot(hostName):
    try:
        child = spawn('ssh '+SSHUser+'@'+SSHIP)
        child.expect(SSHUser+"@"+SSHIP+"'s password:")
        child.sendline(SSHPw)
        child.sendline('echo "nova host-action --action reboot '+hostName+'">tempRebootCommand')
        child.sendline('exit')
    except TIMEOUT:
        print('Failed to execute reboot action on '+hostName)
        return


def button_action_scale(scriptPath, actionType):
    ps = pxssh.pxssh()
    if ps.login(scaleAction['ip'], scaleAction['user'], scaleAction['pw']):
        ps.sendline('echo "~/CSCF_SCALE.sh 5 '+actionType+'">~/tempScaleAction')
    ps.logout()


class GUIHandler(BaseHTTPRequestHandler):
    '''Small class to define HTTP handler of the front end of the GUI'''
    error_message_format = '<h1>404: File not found </h1>'
    
    def do_GET(self):
        mime = {"html":"text/html", "css":"text/css", "png":"image/png", "jpg":"image/jpg", "js":"application/javascript", "json":"application/json"}
        RequestedFileType = mimetypes.guess_type(self.path)[0] if mimetypes.guess_type(self.path)[0]!=None else 'text/html'
        aJSON = "{}"
        try:
            if self.path == '/':
                self.path = self.path+'index.html'
            if self.path == '/getOverviewData':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                global GUI_dict                
                print(json.dumps(GUI_dict))
                self.wfile.write(bytes(json.dumps(GUI_dict), 'UTF-8'))
                return
            elif os.path.isfile(root_dir + self.path):
                self.send_response(200)
                self.send_header("Content-type", RequestedFileType)
                self.end_headers()
                fp = open(root_dir + self.path, 'rb')
                self.wfile.write(fp.read())
                fp.close()
                return
            elif len(self.path.split('reboot--'))>1:
                Thread(target=button_action_reboot, args=(self.path.split('reboot--')[1],)).start()
                return
            elif len(self.path.split('actionScaleIn'))>1:
                Thread(target=button_action_scale, args=(scaleAction['scriptpath'],'in')).start()
                return
            elif len(self.path.split('actionScaleOut'))>1:
                Thread(target=button_action_scale, args=(scaleAction['scriptpath'],'out')).start()
                return
            else:
                self.send_response(404, 'File not found')
                self.send_header("Content-type", 'text/html')
                self.end_headers()
                self.wfile.write(bytes('File not found', 'UTF-8'))
                return
        except BrokenPipeError:
            print('Failed to complete request')
        except KeyboardInterrupt:
            print('KeyboardInterrupt received, quitting.') 
            return
    
    def log_message(self, format, *args):
        return







if __name__ == '__main__':
    qwrs_2 = {'vmUnavailable':\
                {'regexes':\
                    {'matcher':r'VM Unavailable;',\
                    'finder':[ \
                                [r'\{.+\}', lambda x: json.loads(x)['host'], 'host'], \
                                [r'(?<=VM\=)(.+)(?=; major_type)', lambda x: x, 'vm'], \
                                [r'(?<=active_severity\:)(\s+\d)', lambda x: int("".join(x.split())), 'activeSeverity'] \
                            ] \
                    },\
                'valueQ': Queue()\
                }\
            }
    #setConfigIPToActiveCIC()
    print('alert: "setConfigIPToActiveCIC" is disabled')
    load_config()
    mlp = mainLogLiveParser(threadsRunning)
    threadsRunning.set()    
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = Thread(target=GUIserver.serve_forever, name="GUIserverThread")
    #serviceListPullThread = Thread(target = update_with_commands, args=(['cat /home/mk/Documents/CM_HA_Demo/dummy_inputs/service_list.txt'], node_dicts, service_list_to_dict, localSSHCreds))
    serviceListPullThread = Thread(target = update_with_commands, args=(['nova service-list'], node_dicts, service_list_to_dict), name='serviceListPullThread')    
    dictMergerThread = Thread(target=dictMerger, args=(5, fetchInterval), name="dictMergerThread")
    callLoadGetterThread = Thread(target=update_with_call_load, name="callLoadGetterThread")
    appPutterThread = Thread(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha/main.log | grep -v DEBUG'], qwrs_2), name="appPutterThread")
    appGetterThread = Thread(target=mlp.startMappingEventsLive, args=(qwrs_2,), name="appGetterThread")
    allThreads += [serviceListPullThread, GUIserverThread, dictMergerThread, callLoadGetterThread, appPutterThread, appGetterThread]
    try:
        print('GUI running at %s:%d/index.html' %(GUIIP, GUIPort))
        for aThread in allThreads: aThread.start()              
    except KeyboardInterrupt:
        print("\nStopping GUI server and SSH-pulling.")
        threadsRunning.clear()
        node_dicts.join()
        try:
            while any([aThread.is_alive() for aThread in allThreads]):
                for aThread in allThreads:
                    if aThread.is_alive():
                        aThread.join(0.1)
        except KeyboardInterrupt:
            print('Stopping all')
        sys.exit()
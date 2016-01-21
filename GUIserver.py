#!/usr/bin/env python3
import mimetypes, os, json, time, sys, copy
from threading import Thread, Event
from queue import Queue
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh

node_dicts = Queue(10)
updateApps = True
GUI_dict = {}
appDict = {}
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
        SSHIP, SSHUser, SSHPw = configDict['ssh']['ip'], configDict['ssh']['username'], configDict['ssh']['password']
        SSHCreds['ip'], SSHCreds['user'], SSHCreds['pw'] = SSHIP, SSHUser, SSHPw
        SSHConnectAttempts, fetchInterval = configDict['ssh']['connectattempts'], float(configDict['ssh']['fetchinterval'])
        GUIIP, GUIPort = configDict['guiserver']['ip'], configDict['guiserver']['port']
        with open(root_dir+'gui_config.json', 'w') as guiconF:
            guiconF.write(json.dumps({'ajaxlink':'http://'+GUIIP+':'+str(GUIPort)}))

def dictMerger(timeoutDelay=5, updateInterval=3):
    while threadsRunning.is_set():
        global GUI_dict
        global updateApps
        global appDict
        global upNodeCount
        GUI_dict.update(node_dicts.get(True, timeout=updateInterval+timeoutDelay))
        node_dicts.task_done()
        newUpNodeCount = getUpNodeCount(GUI_dict)
        if upNodeCount != newUpNodeCount: 
            updateApps = True
            upNodeCount = newUpNodeCount
        if updateApps:
            #Thread(target=update_with_oneoff_command, args=(['cat /home/mk/Documents/CM_HA_Demo/dummy_inputs/applications.txt'], appDict, localSSHCreds)).start()
            Thread(target=update_with_oneoff_command, args=(['nova list --fields host,name,state'], appDict)).start()
            updateApps=False
        reloadApps(GUI_dict, appDict)
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


def exportAppListToConfigFile(toExport):
    dictToWrite = {}
    if os.path.isfile('html/appViewConfig.json'):
        with open('html/appViewConfig.json','r') as appViewFile:
            dictToWrite = json.loads(appViewFile.read())
    for key in toExport:
        for appName in toExport[key]['applications']:
            if appName not in dictToWrite:
                dictToWrite[appName] = {'visibility':True, 'isDemoCase': False}        
    with open('html/appViewConfig.json', 'w') as appViewFile: 
        appViewFile.write(json.dumps(dictToWrite, sort_keys=True, indent=4, separators=(',', ':')))


def _reset_updateApps():
    while True:
        global updateApps
        updateApps = True
        time.sleep(60)


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
    setConfigIPToActiveCIC()
    load_config()
    threadsRunning.set()
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = Thread(target=GUIserver.serve_forever)
    #serviceListPullThread = Thread(target = update_with_commands, args=(['cat /home/mk/Documents/CM_HA_Demo/dummy_inputs/service_list.txt'], node_dicts, service_list_to_dict, localSSHCreds))
    serviceListPullThread = Thread(target = update_with_commands, args=(['nova service-list'], node_dicts, service_list_to_dict))    
    dictMergerThread = Thread(target=dictMerger, args=(5, fetchInterval))
    allThreads += [serviceListPullThread, GUIserverThread, dictMergerThread]
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
#!/usr/bin/env python3
import mimetypes, os, json, time, sys
from threading import Thread, Event
from queue import Queue
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh

node_dicts = Queue(10)
updateApps = False
GUI_dict = {}
appDict = {}
allThreads = []
threadsRunning = Event()
upNodeCount = 0
root_dir = os.getcwd() + '/html/'
localSSHCreds = {'ip':'192.168.0.1', 'user':'mk', 'pw':'UIw0rk'}
SSHCreds = {'ip':'', 'user':'', 'pw':''}
SSHIP, SSHUser, SSHPw, fetchInterval, SSHConnectAttempts, GUIIP, GUIPort = None, None, None, None, None, None, None

def load_config():
    conF = open('config.json', 'r')
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
        print('\nLagging by %d entries\n' %(node_dicts.qsize()))
        GUI_dict.update(node_dicts.get(True, timeout=updateInterval+timeoutDelay))
        node_dicts.task_done()
        newUpNodeCount = getUpNodeCount(GUI_dict)
        if upNodeCount != newUpNodeCount: 
            updateApps = True
            upNodeCount = newUpNodeCount
        if updateApps:
            #Thread(target=update_with_oneoff_command, args=(['cat /home/mk/Documents/ceeprojSandbox/dummy_outputs/applications.txt'], appDict, localSSHCreds)).start()
            Thread(target=update_with_oneoff_command, args=(['nova list --fields host,name,state'], appDict)).start()
            updateApps=False
        deepUpdate(GUI_dict, appDict)
        time.sleep(updateInterval)


def update_with_commands(commandList, queueToUpdate, parserFunction, sshInfo=SSHCreds):
    ps = pxssh.pxssh()
    global node_dicts
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
        dictToUpdate.update(app_list_to_dict(execute_commands(ps, commandList)))
    ps.logout()


def deepUpdate(dictToUpdate, source):
    for key in source:
        if key in dictToUpdate:
            dictToUpdate[key].update(source[key])
        else:
            dictToUpdate[key] = source[key]

def getUpNodeCount(dictToCountFrom):
    toRet = 0
    for aNode in dictToCountFrom:
        if dictToCountFrom[aNode]['state']=='up':
            toRet += 1
    return toRet


class GUIHandler(BaseHTTPRequestHandler):
    '''Small class to define HTTP handler of the front end of the GUI'''
    error_message_format = '<h1>404: File not found </h1>'
    
    def do_GET(self):
        mime = {"html":"text/html", "css":"text/css", "png":"image/png", "jpg":"image/jpg", "js":"application/javascript", "json":"application/json"}
        RequestedFileType = mimetypes.guess_type(self.path)[0] if mimetypes.guess_type(self.path)[0]!=None else 'text/html'
        aJSON = "{}"
        try:
            if self.path == '/':
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
    load_config()
    threadsRunning.set()
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = Thread(target=GUIserver.serve_forever)
    #serviceListPullThread = Thread(target = update_with_commands, args=(['cat /home/mk/Documents/ceeprojSandbox/dummy_outputs/service_list.txt'], node_dicts, service_list_to_dict, localSSHCreds))
    serviceListPullThread = Thread(target = update_with_commands, args=(['nova service-list'], node_dicts, service_list_to_dict))
    dictMergerThread = Thread(target=dictMerger, args=(5, fetchInterval))
    allThreads += [serviceListPullThread, GUIserverThread, dictMergerThread]
    try:
        #update_with_commands(['nova service-list'])
        print('GUI running at %s:%d/index.html' %(GUIIP, GUIPort))
        for aThread in allThreads: aThread.start()              
    except KeyboardInterrupt:
        print("\nStopping GUI server and SSH-pulling.")
        threadsRunning.clear()
        while any([aThread.is_alive() for aThread in allThreads]):
            for aThread in allThreads:
                if aThread.is_alive():
                    aThread.join(0.1)
        node_dicts.join()
        sys.exit()
#!/usr/bin/env python3
import mimetypes, os, json, time, sys, copy, logging, datetime 
from threading import Thread, Event
from queue import Queue, Empty as QEmpty
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh, spawn, TIMEOUT
from mainLogFromCicParser import mainLogLiveParser
from multiprocessing import Process as mProcess

LOG_LEVELS = { 'debug':logging.DEBUG,
            'info':logging.INFO,
            'warning':logging.WARNING,
            'error':logging.ERROR,
            'critical':logging.CRITICAL,
            }
node_dicts = Queue(10)
updateApps = False
GUI_dict = {}
appDict = {}
callLoadDict = {}
allThreads = []
threadsRunning = Event()
upNodeCount = 0
root_dir = os.getcwd() + '/html/'
#localSSHCreds = {'ip':'192.168.0.1', 'user':'mk', 'pw':'UIw0rk'}
SSHCreds = {'ip':'', 'user':'', 'pw':''}
SSHIP, SSHUser, SSHPw, fetchInterval, SSHConnectAttempts, GUIIP, GUIPort = None, None, None, None, None, None, None


def setConfigIPToActiveCIC():
    ps, ps1 = (pxssh.pxssh(),)*2 
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        ip, user, pw = configDict['ssh']['ip'], configDict['ssh']['username'], configDict['ssh']['password']
    if ps.login(ip, user, pw):
        current_cic_hostname = "".join(execute_commands(ps, ['hostname -s'])[-1].split())+'.domain.tld'
        main_cic_hostname = execute_commands(ps, ['echo $(sudo crm_mon -1 | grep cmha| grep Started)'])[0].rsplit('Started')[-1]
        main_cic_hostname = "".join(main_cic_hostname.split())
        log.info('Main cic hostname: "%s"' %(main_cic_hostname))
        log.debug('Current cic hostname: "%s"' %(current_cic_hostname))
        if current_cic_hostname!=main_cic_hostname:
            log.info('Currently set IP in the \'config.json\' file does not belong to the main CIC, fetching main cic IP for GUI-config file. This might take upto 1 minute.')            
            main_cic_ip_string = execute_commands(ps, ['ssh '+user+'@'+main_cic_hostname, pw ,'echo $(ifconfig br-ex | grep "inet addr:")'])[-2]
            log.debug('main cic ip string %s' %(main_cic_ip_string))
            execute_commands(ps, ['exit'])
            main_cic_ip_string = ["".join(s.split()) for s in re.findall(r'(?<=inet addr:)(.+)(?=Bcast)', main_cic_ip_string)][0]
            log.info('Main cic IP: %s' %(main_cic_ip_string))
            configDict['ssh']['ip'] = main_cic_ip_string
            with open('config.json', 'w') as conF:
                conF.write(json.dumps(configDict, indent=4, separators=(',', ':'), sort_keys=True))
        else:
            log.info("Config file has the main CIC IP.")
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
            log.warning("Didn't get any updated dictionary from the nodes, continuing without updating the GUI-dictionary")
        for aHost in GUI_dict:
            if aHost in mlp.appDictForGui:
                GUI_dict[aHost]['applications'] = mlp.appDictForGui[aHost]['applications']
            if GUI_dict[aHost].get('applications') is not None:
                for anApp in callLoadDict:
                    for aVm in GUI_dict[aHost]['applications']:
                        if anApp in aVm:
                            GUI_dict[aHost]['applications'][aVm]['calls'] = callLoadDict[anApp]['calls']                            
        time.sleep(updateInterval)


def update_with_commands(commandList, queueToUpdate, parserFunction, sshInfo=SSHCreds):
    ps = pxssh.pxssh()
    global threadsRunning
    try:
        for i in range(1, SSHConnectAttempts):
            if ps.login(sshInfo['ip'], sshInfo['user'], sshInfo['pw']):
                while threadsRunning.is_set():
                    aDict = parserFunction(execute_commands(ps,commandList))
                    queueToUpdate.put(aDict)
                    time.sleep(fetchInterval)
            if not threadsRunning.is_set(): break
        ps.logout()
    except KeyboardInterrupt:
        log.info('SSH pull interrupted, quitting')
        ps.logout()


def __update_with_call_load(appName, creds):
    global callLoadDict
    sshHandle = pxssh.pxssh()   
    try:
        if sshHandle.login(creds['ip'], creds['username'], creds['password']):
            while threadsRunning.is_set():
                sshHandle.sendline(creds['command_to_send'])
                sshHandle.prompt()
                tempLines = sshHandle.before.decode('utf-8').splitlines()[-1]
                try:
                    tempCallLoadDict = json.loads(tempLines) if tempLines is not None else {}
                except ValueError:
                    log.error("Invalid call info received, setting call info to 'None' for this dictionary")
                    tempCallLoadDict = {}
                tempCallLoadDict = {appName+'-'+k:v for k, v in tempCallLoadDict.items()}
                for aVm in tempCallLoadDict:
                    if aVm not in callLoadDict: callLoadDict[aVm] = {}                    
                    callLoadDict[aVm]['calls'] = tempCallLoadDict[aVm]
                time.sleep(fetchInterval)
            sshHandle.logout()
    except IndexError:
        log.error('"IndexError" while updating with call info. Porbable cause : Error in communication with %s' %(creds['ip']))
        return


def update_with_call_load():
    global callLoadDict
    callCreds = {}
    with open('config.json', 'r') as conF: 
        callCreds = json.loads(conF.read())['ssh_call_info']
    for anApp in callCreds:
        ThreadInterruptable(target=__update_with_call_load, args=(anApp, callCreds[anApp]), name='call_load_updater_thread__'+ anApp).start()


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
        #child.sendline('echo "nova host-action --action reboot '+hostName+'">tempRebootCommand')
        child.sendline('ssh '+hostName+' reboot')        
        child.sendline('exit')
    except TIMEOUT:
        log.error('Failed to execute reboot action on %s' %(hostName))
        return


def button_action_scale(scriptPath, actionType):
    ps = pxssh.pxssh()
    if ps.login(scaleAction['ip'], scaleAction['user'], scaleAction['pw']):
        ps.sendline('echo "~/CSCF_SCALE.sh 5 '+actionType+'">~/tempScaleAction')
    ps.logout()


def killThreads(tl):
    for aThread in tl:
        aThread._tstate_lock = None
        aThread._stop()


class ThreadInterruptable(Thread):
    def join(self, timeout=0.1):
        try:            
            super(ThreadInterruptable, self).join(timeout)
        except KeyboardInterrupt:
            log.info('Stopping thread %r' %(self.name))
            try:
                self._tstate_lock = None
                self._stop()
                threadsRunning.clear()
                global allThreads
                killThreads(allThreads)
                log.info('Stopping all threads to exit program.')
            except AssertionError:
                log.warning('Ignored AssertionError in parent (threading.Thread) class.')


class GUIHandler(BaseHTTPRequestHandler):
    '''class to define HTTP handler of the front end of the GUI'''
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
                log.debug(json.dumps(GUI_dict))
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
                log.debug('Got command to reboot %r' %(self.path.split('reboot--')[1]))
                return
            elif len(self.path.split('actionScaleIn'))>1:
                Thread(target=button_action_scale, args=(scaleAction['scriptpath'],'in')).start()
                log.debug('Got command to scale-in')
                return
            elif len(self.path.split('actionScaleOut'))>1:
                Thread(target=button_action_scale, args=(scaleAction['scriptpath'],'out')).start()
                log.debug('Got command to scale-out')
                return
            else:
                self.send_response(404, 'File not found')
                self.send_header("Content-type", 'text/html')
                self.end_headers()
                self.wfile.write(bytes('File not found', 'UTF-8'))
                return
        except BrokenPipeError:
            log.error('Failed to complete request in "do_GET"')
        except KeyboardInterrupt:
            log.info('KeyboardInterrupt received, quitting.') 
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
                                [r'(?<=active_severity\:)(\s+\d)', lambda x: int("".join(x.split())), 'activeSeverity'], \
                                [r'(\d{4}\-\d{2}\-\d{2}\s\d{2}\:\d{2}\:\d{2})(?=\s)', lambda x: datetime.datetime.strptime(x[-1], "%Y-%m-%d %H:%M:%S") if len(x)>0 else None, 'eventTime']
                            ] \
                    },\
                'valueQ': Queue()\
                }\
            }
    log = logging.getLogger('GUIserver')
    if argv[1:]:
        log.setLevel(LOG_LEVELS.get(argv[1], logging.NOTSET))        
    else:
        log.setLevel(logging.INFO)
    fh = logging.FileHandler('gui_events.log')    
    sh = logging.StreamHandler()
    sh.setLevel(LOG_LEVELS.get(argv[1]) if argv[1:] else logging.INFO)
    fh.setLevel(logging.DEBUG)
    logFormatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(logFormatter)
    sh.setFormatter(logFormatter)
    log.addHandler(fh)
    log.addHandler(sh)
    setConfigIPToActiveCIC()
    #log.warning('"setConfigIPToActiveCIC" is disabled')
    load_config()
    mlp = mainLogLiveParser(threadsRunning, logger=log)
    threadsRunning.set()    
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = ThreadInterruptable(target=GUIserver.serve_forever, name="GUIserverThread")
    #serviceListPullThread = Thread(target = update_with_commands, args=(['cat /home/mk/Documents/CM_HA_Demo/dummy_inputs/service_list.txt'], node_dicts, service_list_to_dict, localSSHCreds))
    serviceListPullThread = ThreadInterruptable(target = update_with_commands, args=(['nova service-list'], node_dicts, service_list_to_dict), name='serviceListPullThread')    
    dictMergerThread = ThreadInterruptable(target=dictMerger, args=(5, fetchInterval), name="dictMergerThread")
    callLoadGetterThread = ThreadInterruptable(target=update_with_call_load, name="callLoadGetterThread")
    appPutterThread = ThreadInterruptable(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha/main.log | grep -v DEBUG'], qwrs_2), name="appPutterThread")
    appGetterThread = ThreadInterruptable(target=mlp.startMappingEventsLive, args=(qwrs_2,), name="appGetterThread")
    allThreads += [serviceListPullThread, GUIserverThread, dictMergerThread, callLoadGetterThread, appPutterThread, appGetterThread]
    try:
        log.info('GUI running at %s:%d' %(GUIIP, GUIPort))
        for aThread in allThreads: aThread.start()
    except KeyboardInterrupt:
        log.info('Stopping GUI server and SSH-pulling.')
        threadsRunning.clear()
        for aThread in allThreads: 
            aThread._stop()
        node_dicts.join()      
        sys.exit()
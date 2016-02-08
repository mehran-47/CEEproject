#!/usr/bin/env python3
import mimetypes, os, json, time, sys, copy, logging, datetime 
from threading import Thread, Event
from queue import Queue, Empty as QEmpty
from sys import argv
from http.server import BaseHTTPRequestHandler, HTTPServer
from sshfetch import *
from pexpect import pxssh, spawn, TIMEOUT, EOF as pexpectEndOfFile
from mainLogFromCicParser import mainLogLiveParser
from multiprocessing import Process as mProcess

LOG_LEVELS = { 'debug':logging.DEBUG,
            'info':logging.INFO,
            'warning':logging.WARNING,
            'error':logging.ERROR,
            'critical':logging.CRITICAL,
            }
frontEndEventStack = []
node_dicts = Queue(10)
updateApps = False
GUI_dict = {}
appDict = {}
callLoadDict = {}
allThreads = []
threadsRunning = Event()
upNodeCount = 0
root_dir = os.getcwd() + '/html/'
SSHCreds = {'ip':'', 'user':'', 'pw':''}
SSHIP, SSHUser, SSHPw, fetchInterval, SSHConnectAttempts, GUIIP, GUIPort = None, None, None, None, None, None, None
qwrs_2 = {'vmUnavailable':\
                {'regexes':\
                    {'matcher':r'VM Unavailable;',\
                    'finder':[ \
                                [r'\{.+\}', lambda x: json.loads(x)['host'], 'host'], \
                                [r'(?<=VM\=)(.+)(?=; major_type)', lambda x: x, 'vm'], \
                                [r'(?<=active_severity\:)(\s+\d)', lambda x: int("".join(x.split())), 'activeSeverity'], \
                                [r'(\d{4}\-\d{2}\-\d{2}\s\d{2}\:\d{2}\:\d{2})(?=\s)', lambda x: x, 'eventTime']
                            ] \
                    },\
                'valueQ': Queue()\
                }\
            }
extraVerbose = False
latestScaleAction = {'scale':None, 'vm':None}


def __sendDummyEventsToGUI():
    dummySend = True
    while dummySend:
        toSend = input('type dummy event to send: >\n')
        try:
            if toSend.split('#')[1]=='stop': 
                dummySend=False
                continue
            frontEndEventStack.append(toSend)
        except IndexError:
            print('invalid dummy input!')


def setConfigIPToActiveCIC():
    ps, ps1 = (pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile":"/dev/null"}),)*2 
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
        GUIIP, GUIPort = configDict['guiserver']['ip'], configDict['guiserver']['port'] 
        scaleAction = configDict['scale_action']
        with open(root_dir+'gui_config.json', 'w') as guiconF:
            guiconF.write(json.dumps({'ajaxlink':'http://'+GUIIP+':'+str(GUIPort), 'maxcalls':configDict['guiserver']['maxcalls'], 'refreshinterval':configDict['guiserver']['refreshInterval'] }))


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
            elif 'applications' in GUI_dict[aHost]:
                del GUI_dict[aHost]['applications']
            if GUI_dict[aHost].get('applications') is not None:
                for anApp in callLoadDict:
                    for aVm in GUI_dict[aHost]['applications']:
                        if anApp in aVm:
                            GUI_dict[aHost]['applications'][aVm]['calls'] = callLoadDict[anApp]['calls']
        time.sleep(updateInterval)


def update_with_commands(commandList, queueToUpdate, parserFunction, sshInfo=SSHCreds):
    ps = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile":"/dev/null"})
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
        log.info('SSH pull interrupted, stopped checking node/blade availability.')
        ps.logout()


def __update_with_call_load(appName, creds):
    global callLoadDict
    sshHandle = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile":"/dev/null"})   
    try:
        if sshHandle.login(creds['ip'], creds['username'], creds['password']):
            while threadsRunning.is_set():
                sshHandle.sendline(creds['command_to_send'])
                sshHandle.prompt()
                tempLines = sshHandle.before.decode('utf-8').splitlines()[-1]
                try:
                    tempCallLoadDict = json.loads(tempLines) if tempLines is not None else {}
                except ValueError:
                    log.warning("Invalid call info received, error in output of %s:%s. Provided output:\n\t%s " %(creds['ip'], creds['command_to_send'], tempLines))
                    tempCallLoadDict = {}
                tempCallLoadDict = {appName+'-'+k:v for k, v in tempCallLoadDict.items()}
                for aVm in tempCallLoadDict:
                    if aVm not in callLoadDict: callLoadDict[aVm] = {}                    
                    callLoadDict[aVm]['calls'] = tempCallLoadDict[aVm]
                #Ugly fix for confirming evacuation is 'actually' complete. Sorry. :(
                if mlp.evacuatingVm !='' and mlp.evacuatingVm in tempCallLoadDict and tempCallLoadDict[mlp.evacuatingVm]>0:
                    frontEndEventStack.append('Server-response: VM is operational. Evacuation complete'+'#{"evacuation":"stop"}')
                    mlp.evacuatingVm = ''
                time.sleep(fetchInterval)
            sshHandle.logout()
    except IndexError:
        log.error('"IndexError" while updating with call info. Porbable cause : Error in communication with %s' %(creds['ip']))
        return
    except pexpectEndOfFile:
        log.critical('pexpect: end-of-file exception; Failed to read call information. Failed to log in to %s. Running GUI without call-info. Restart program if necessary.' %(creds['ip']))


def update_with_call_load():
    global callLoadDict
    callCreds = {}
    with open('config.json', 'r') as conF: 
        callCreds = json.loads(conF.read())['ssh_call_info']
    for anApp in callCreds:
        updateWithCallLoadPrivateThread = ThreadInterruptable(target=__update_with_call_load, args=(anApp, callCreds[anApp]), name='call_load_updater_thread__'+ anApp)
        if not updateWithCallLoadPrivateThread.is_alive(): updateWithCallLoadPrivateThread.start()
        allThreads.append(updateWithCallLoadPrivateThread)


def button_action_reboot(hostName):
    ps = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile":"/dev/null"})
    try:
        if ps.login(SSHIP, SSHUser, SSHPw):
            execute_commands(ps, ['ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '+hostName+' reboot'])
            ps.logout()
    except pexpectEndOfFile:
        log.error('Failed to execute reboot action on %s' %(hostName))
        return


def __refreshApps(delay):
    time.sleep(delay)
    mlp.refreshVmIdToNameMap()
    log.info('Refreshed app-map post scaling')
    frontEndEventStack.append('Server-response: Scaling action complete #{}')
    log.debug('App-dict for GUI (mlp.appDictForGui):\n%r\n' %(mlp.appDictForGui))
    log.debug('GUI_dict:\n%r\n' %(GUI_dict))


def __scaleInPrep(appName, payLoad, delay):
    with open('config.json', 'r') as conF: 
        callCreds = json.loads(conF.read())['ssh_call_info'][appName]
    try:
        child = spawn('ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '+callCreds['username']+'@'+callCreds['ip']+' -t -s cli', timeout=15)
        child.expect('Password:')
        child.sendline(callCreds['password'])
        child.sendline('configure')
        child.sendline('no ManagedElement=1,SystemFunctions=1,SysM=1,CrM=1,ComputeResourceRole='+payLoad+',provides')
        child.sendline('commit')
        child.sendline('exit')
        if extraVerbose: 
            log.debug('Providing output while executing:"no ManagedElement=1,SystemFunctions=1,SysM=1,CrM=1,ComputeResourceRole=PL-5,provides"')
            for line in child:
                log.debug(line.decode('utf-8'))
        child.close()
        log.info('Prepared for scaling in')
        frontEndEventStack.append('Server-response: Cleanup complete; prepared for scaling in #{}')
        time.sleep(delay)
    except TIMEOUT:
        log.warning('SSH timeout executing "scaleInPrep"')
        time.sleep(delay)


def button_action_scale(actionType):
    with open('config.json', 'r') as conF: 
        callCreds = json.loads(conF.read())['ssh_call_info']['CSCF']
    ps = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile":"/dev/null"}, timeout=60)
    if ps.login(scaleAction['ip'], scaleAction['user'], scaleAction['pw']):
        apploadDelay = 40
        lastPL = max(int(vm[-1]) for vm in mlp.latestApps if 'PL' in vm)
        try:
            if actionType=='out':
                if lastPL>70:
                    log.info('Cannot scale out beyond PL-%d' %(lastPL))
                    return
                ps.sendline(scaleAction['scriptpath']+' '+str(lastPL+1)+' out &')
                ps.sendline('echo "'+scaleAction['scriptpath']+' '+str(lastPL+1)+' out">dispatchedCommand')
                latestScaleAction['scale'], latestScaleAction['vm'] = 'out', 'CSCF-PL-'+str(lastPL+1)
                log.info('Scaling out PL-%d' %(lastPL+1))
                frontEndEventStack.append('Server-response: Scaling out PL-'+str(lastPL+1)+'#{"scaling":"start"}')
                scaleActionCompletionChecker = ThreadInterruptable(target = checkScalingActionCompletion)
                scaleActionCompletionChecker.start()
                allThreads.append(scaleActionCompletionChecker)
            if actionType=='in':
                if lastPL<5:
                    log.info('Cannot scale in once reached PL-4')
                    return
                __scaleInPrep('CSCF', 'PL-'+str(lastPL) ,15)
                ps.sendline(scaleAction['scriptpath']+' '+str(lastPL)+' in &')
                latestScaleAction['scale'], latestScaleAction['vm'] = 'in', 'CSCF-PL-'+str(lastPL)
                ps.sendline('echo "'+scaleAction['scriptpath']+' '+str(lastPL)+' in">dispatchedCommand')
                log.info('Scaling in PL-%d' %(lastPL))
                frontEndEventStack.append('Server-response: Scaling in PL-'+ str(lastPL)+'#{"scaling":"start"}')
                scaleActionCompletionChecker = ThreadInterruptable(target = checkScalingActionCompletion)
                scaleActionCompletionChecker.start()
                allThreads.append(scaleActionCompletionChecker)
                apploadDelay = 20
            appreloaderThread = ThreadInterruptable(target=__refreshApps, args=(apploadDelay,), name='appreloaderThread')
            appreloaderThread.start()
            allThreads.append(appreloaderThread)
            ps.logout()
            return            
        except pexpectEndOfFile:
            log.error('Error scaling %s PL-%d' %(actionType, lastPL))
            return

def __filler_messages(vmName):
    messages = [vmName+' has been booted up successfully #{}',vmName+' is registered to the cluster #{}', vmName+' is being enabled #{}' , vmName+' is being prepared for traffic handling #{}']
    for aMessage in messages:
        time.sleep(60)
        frontEndEventStack.append(aMessage)        
 
def checkScalingActionCompletion():
    if latestScaleAction['scale']=='out':
        __fillerMessagesThread = ThreadInterruptable(target=__filler_messages, args=(latestScaleAction['vm'], ))
        __fillerMessagesThread.start()
        allThreads.append(__fillerMessagesThread)
    while threadsRunning.is_set():
        if latestScaleAction['scale']=='out' and latestScaleAction['vm'] in callLoadDict:
            if callLoadDict[latestScaleAction['vm']]['calls'] > 0:
                log.info('Scaling out %s complete' %(latestScaleAction['vm']))
                frontEndEventStack.append('Server-response: Scaling action complete #{"scaling":"stop"}')
                return
        elif latestScaleAction['scale']=='in' and latestScaleAction['vm'] not in mlp.latestApps:
            frontEndEventStack.append('Server-response: Scaling action complete #{"scaling":"stop"}')
            log.info('Scaling in %s complete' %(latestScaleAction['vm']))
            return
        time.sleep(fetchInterval)


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
                #The avalanche effect: one 'KeyboardInterrupt' to kill them all.
                global allThreads
                self.killThreads(allThreads)
                log.info('Stopping all threads to exit program.')
            except AssertionError:
                log.warning('Ignored AssertionError in parent (threading.Thread) class.')

    def killThreads(self, tl):
        for aThread in tl:
            aThread._tstate_lock = None
            aThread._stop()


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
                global extraVerbose
                if extraVerbose: log.debug(json.dumps(GUI_dict))
                self.wfile.write(bytes(json.dumps(GUI_dict), 'UTF-8'))
                return
            elif self.path == '/getEvacEvents':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps(mlp.eventsMap), 'UTF-8'))
                return
            elif self.path == '/frontEndEventStack':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps(frontEndEventStack), 'UTF-8'))
                frontEndEventStack.clear()
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
                Thread(target=button_action_reboot, args=(self.path.split('reboot--')[1],), name="rebooterThread").start()
                log.info('Got command to reboot %r' %(self.path.split('reboot--')[1]))
                return
            elif len(self.path.split('actionScaleIn'))>1:
                Thread(target=button_action_scale, args=('in',), name="scalerThread").start()
                log.info('Got command to scale-in')
                return
            elif len(self.path.split('actionScaleOut'))>1:
                Thread(target=button_action_scale, args=('out',), name="scalerThread").start()
                log.info('Got command to scale-out')
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
    log = logging.getLogger('GUIserver')
    if argv[2:] and argv[2]=='-v':
        extraVerbose = True
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
    load_config()
    mlp = mainLogLiveParser(threadsRunning, logger=log, GUIEventStack=frontEndEventStack)
    threadsRunning.set()    
    GUIserver = HTTPServer((GUIIP, GUIPort), GUIHandler)
    GUIserverThread = ThreadInterruptable(target=GUIserver.serve_forever, name="GUIserverThread")
    serviceListPullThread = ThreadInterruptable(target = update_with_commands, args=(['nova service-list'], node_dicts, service_list_to_dict), name='serviceListPullThread')    
    dictMergerThread = ThreadInterruptable(target=dictMerger, args=(5, fetchInterval), name="dictMergerThread")
    callLoadGetterThread = ThreadInterruptable(target=update_with_call_load, name="callLoadGetterThread")
    appPutterThread = ThreadInterruptable(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha/main.log | grep -v DEBUG'], qwrs_2), name="appPutterThread")
    appGetterThread = ThreadInterruptable(target=mlp.startMappingEventsLive, args=(qwrs_2,), name="appGetterThread")
    #Thread for debugging the front end by sending dummy event messages.
    ##__dummyThread = ThreadInterruptable(target=__sendDummyEventsToGUI, name='__dummyGuiInputThread')
    allThreads += [serviceListPullThread, GUIserverThread, dictMergerThread, callLoadGetterThread, appPutterThread, appGetterThread]
    try:
        log.info('GUI running at %s:%d' %(GUIIP, GUIPort))
        for aThread in allThreads: 
            if not aThread.is_alive():
                aThread.start()
    except KeyboardInterrupt:
        log.info('Stopping GUI server and SSH-pulling.')
        threadsRunning.clear()
        for aThread in allThreads: 
            aThread._stop()
        node_dicts.join()
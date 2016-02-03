#!/usr/bin/env python3
from pexpect import pxssh, spawn, TIMEOUT
from queue import Queue
import time, re, sys, os, logging, datetime
from sshfetch import *
from threading import Thread, Event, current_thread

class ThreadInterruptable(Thread):
    def join(self, timeout=0.1):
        try:            
            super(ThreadInterruptable, self).join(timeout)
        except KeyboardInterrupt:
            try:
                logging.info("Stopping thread '%r'" %(self.name))
                self._tstate_lock = None
                self._stop()
            except AssertionError:
                logging.warning('Ignored AssertionError in parent class')

class mainLogLiveParser():
    def __init__(self, shouldRun, logger=logging):
        self.credDict = {}
        with open('config.json', 'r') as conF:
            self.credDict = json.loads(conF.read())['ssh']
        self.ip = self.credDict['ip']
        self.user = self.credDict['username']
        self.pw = self.credDict['password']
        self.shouldRun = shouldRun
        self.eventsMap = {}
        self.vmIdToNameMap = {}
        self.appDictForGui = {}
        self.updateApps = False
        self.vmIdToNameMapUpdated = False
        self.log = logger
        #logging.basicConfig(level=logLevel, format='%(asctime)s: %(message)s')
        self.vmIdToNameMapUpdaterThread = ThreadInterruptable(target=self.__updateVmIdToNameMap, name="private__updateVmIdToNameMapThread")
        self.vmIdToNameMapUpdaterThread.start()        
    
    def updateAppDictForGui(self):
        toRet = {}
        #if self.vmIdToNameMapUpdated:
        for aVmId in self.vmIdToNameMap:
            if self.vmIdToNameMap[aVmId]['host'] not in toRet:
                toRet[self.vmIdToNameMap[aVmId]['host']] = {'applications':{}}
                self.updateApps = True
        for aVmId in self.vmIdToNameMap:
            if self.vmIdToNameMap[aVmId]['name'] not in toRet[self.vmIdToNameMap[aVmId]['host']]['applications']:
                toRet[self.vmIdToNameMap[aVmId]['host']]['applications'][self.vmIdToNameMap[aVmId]['name']] = {}
                self.updateApps = True
        self.appDictForGui = toRet
        exportAppListToConfigFile(self.appDictForGui)

    def __updateVmIdToNameMap(self):
        ps = pxssh.pxssh(options={"StrictHostKeyChecking": "no"})
        if ps.login(self.ip, self.user, self.pw):
            mapList = execute_commands(ps, ['nova list --fields=name,host,metadata'])[3:-1]
            ps.logout()
            getStringFromIndex = lambda entry, i: "".join(entry.split('|')[i].split())
            for anEntry in mapList:
                self.vmIdToNameMap["".join(anEntry.split('|')[1].split())] = {'name': getStringFromIndex(anEntry, 2), \
                                                                            'host': getStringFromIndex(anEntry ,3), \
                                                                            'evacuationPolicy': json.loads(re.sub(r"u'|'", r'"', getStringFromIndex(anEntry, 4))).get('evacuation_policy') }
        self.vmIdToNameMapUpdated = True
        self.updateApps = True
        self.updateAppDictForGui()

    def updateQsWithRegexes(self, commList, qsWithRegexes):
        try:
            child = spawn('ssh '+self.user+'@'+self.ip)
            child.expect(self.user+"@"+self.ip+"'s password:")
            child.sendline(self.pw)
            self.log.info('Successfully logged in on %s', self.ip)
            for line in commList:
                child.sendline(line)
            for line in child:
                if not self.shouldRun.is_set():
                    child.sendline('^C')
                    child.sendline('exit')
                    self.log.info("Stopping thread '%s'" %(current_thread().name))
                    return
                for qwr in qsWithRegexes:
                    decodedLine = line.decode('utf-8')
                    compiledRegexMatcher = re.compile(qsWithRegexes[qwr]['regexes']['matcher'])
                    if compiledRegexMatcher.search(decodedLine) is not None:
                        self.log.info('Found a match while parsing main log, processing:\n%s' %(decodedLine))
                        toPut = {}
                        for rgf in qsWithRegexes[qwr]['regexes']['finder']:
                            #rgf pattern: [regex_to_extract_initial_data, function_to_process_found_data, string_specifying_the_type_of_data_extracted]
                            foundFragments = re.findall(rgf[0], decodedLine)
                            self.log.info('foundFragments: %r' %(foundFragments))
                            toPut[rgf[2]] = [rgf[1](aFragment) for aFragment in foundFragments][-1] if len(foundFragments)>0 else None
                        toPut['origin'] = qwr
                        qsWithRegexes[qwr]['valueQ'].put(toPut)                                
        except KeyboardInterrupt:
            self.shouldRun.clear()
            child.sendline('^C')
            child.sendline('exit')
            return
        except TIMEOUT:
            self.log.critical('SSH connection timeout, can\'t read "main.log" or "cmha.log" file')
            raise
            return 

    def startMappingEventsLive(self, qsWithRegexes):
        anEvent = {}
        try:
            while self.shouldRun.is_set():
                while not qsWithRegexes['vmUnavailable']['valueQ'].empty():
                    anEvent = qsWithRegexes['vmUnavailable']['valueQ'].get()
                    if anEvent['vm'] not in self.eventsMap and anEvent['activeSeverity']==5:
                        if self.vmIdToNameMap[anEvent['vm']]['evacuationPolicy'] is not None: 
                            self.eventsMap[anEvent['vm']] = {'host': anEvent['host'], \
                                                            'vmName' : self.vmIdToNameMap[anEvent['vm']]['name'] if anEvent['vm'] in self.vmIdToNameMap else None, \
                                                            'activeSeverity': anEvent['activeSeverity'],
                                                            'eventTime': anEvent['eventTime']}
                            #do something in self.vmIdToNameMap to alert that the vm is not available/host is in trouble
                            self.vmIdToNameMapUpdated = False
                    elif anEvent['activeSeverity']==1:
                        if anEvent['vm'] in self.vmIdToNameMap:
                            self.vmIdToNameMap[anEvent['vm']]['host'] = anEvent['host']
                            self.updateAppDictForGui()
                            self.vmIdToNameMapUpdated = True
                            self.updateApps = True
                        if anEvent['vm'] in self.eventsMap:
                            del  self.eventsMap[anEvent['vm']]
                    qsWithRegexes['vmUnavailable']['valueQ'].task_done()
                    self.log.info('-------got from Q------%r-------------', anEvent)
                    self.log.info('-------Current Events\' Map------%r-------------', self.eventsMap)
                time.sleep(2)
        except KeyboardInterrupt:
            self.shouldRun.clear()            
            for qwr in qsWithRegexes:
                qsWithRegexes[qwr]['valueQ'].join()

def fixJson(string):
    self.log.debug(string)
    return json.loads(re.sub('u\'|\'','"', '{'+string+'}'))


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


if __name__ == '__main__':
    global shouldRun
    shouldRun = Event()
    mlp = mainLogLiveParser(shouldRun)
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
    try:
        allThreads = []
        allThreads += [ThreadInterruptable(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha.log | grep -v DEBUG'], qwrs_2))]
        allThreads += [ThreadInterruptable(target=mlp.startMappingEventsLive, args=(qwrs_2,))]
        shouldRun.set()
        for aThread in allThreads: aThread.start()
    except KeyboardInterrupt:
        for aThread in allThreads: 
            if aThread.is_alive(): 
                aThread.join(1)
#!/usr/bin/env python3
from pexpect import pxssh, spawn, TIMEOUT
from queue import Queue
import time, re, sys
from sshfetch import *
from threading import Thread, Event

class mainLogLiveParser():
    def __init__(self):
        self.credDict = {}
        with open('config.json', 'r') as conF:
            self.credDict = json.loads(conF.read())['ssh']
        self.ip = self.credDict['ip']
        self.user = self.credDict['username']
        self.pw = self.credDict['password']
        self.vmIdToNameMap = {}
        self.vmIdToNameMapUpdated = False
        self.vmIdToNameMapUpdater = Thread(target=self.__updateVmIdToNameMap).start()

    def __updateVmIdToNameMap(self):
        ps = pxssh.pxssh()
        if ps.login(self.ip, self.user, self.pw):
            mapList = execute_commands(ps, ['nova list --fields=name'])[3:-1]
            ps.logout()
            for anEntry in mapList:
                self.vmIdToNameMap["".join(anEntry.split('|')[1].split())] = "".join(anEntry.split('|')[2].split())
        self.vmIdToNameMapUpdated = True        
        print(self.vmIdToNameMap)

    def updateQsWithRegexes(self, commList, qsWithRegexes):
        global shouldRun
        try:
            child = spawn('ssh '+self.user+'@'+self.ip)
            child.expect(self.user+"@"+self.ip+"'s password:")
            child.sendline(self.pw)
            print('Successfully logged in on', self.ip)
            for line in commList:
                child.sendline(line)
            for line in child:
                if not shouldRun.is_set():
                    child.sendline('^C')
                    child.sendline('exit')
                    print('\nQuitting...')
                    return
                for qwr in qsWithRegexes:
                    decodedLine = line.decode('utf-8')
                    compiledRegexMatcher = re.compile(qsWithRegexes[qwr]['regexes']['matcher'])
                    if compiledRegexMatcher.search(decodedLine) is not None:
                        #print('\n\n', 'Found a match, processing:\n', decodedLine, '\n\n')
                        toPut = {}
                        for rgf in qsWithRegexes[qwr]['regexes']['finder']:
                            #rgf pattern: [regex_to_extract_initial_data, function_to_process_found_data, string_specifying_the_type_of_data_extracted]
                            foundFragments = re.findall(rgf[0], decodedLine)
                            toPut[rgf[2]] = [rgf[1](aFragment) for aFragment in foundFragments]
                            '''
                            print('foundFragments: ', foundFragments)
                            for aFragment in foundFragments:
                                fragResults.append(rgf[1](aFragment))
                                print('fragResults:', fragResults)
                            '''
                        toPut['origin'] = qwr
                        qsWithRegexes[qwr]['valueQ'].put(toPut)                                
        except KeyboardInterrupt:
            shouldRun.clear()
            child.sendline('^C')
            child.sendline('exit')
            return

def fixJson(string):
    print(string)
    return json.loads(re.sub('u\'|\'','"', '{'+string+'}'))


if __name__ == '__main__':
    global shouldRun
    shouldRun = Event()
    mlp = mainLogLiveParser()
    qwrs_2 = {'vmUnavailable':\
                {'regexes':\
                    {'matcher':r'VM Unavailable;',\
                    'finder':[ \
                                [r'\{.+\}', lambda x: x, 'host'], \
                                [r'(?<=VM\=)(.+)(?=; major_type)', lambda x: x, 'vm'], \
                                [r'(?<=active_severity\:)(\s+\d)', lambda x: int("".join(x.split())), 'activeSeverity'] \
                            ] \
                    },\
                'valueQ': Queue()\
                }\
            }
    getterThread = Thread(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha.log | grep -v DEBUG'], qwrs_2))
    shouldRun.set()
    getterThread.start()
    try:
        while shouldRun.is_set():
            while not qwrs_2['vmUnavailable']['valueQ'].empty():
                print('-------got from Q------', qwrs_2['vmUnavailable']['valueQ'].get(), '-------------')
                qwrs_2['vmUnavailable']['valueQ'].task_done()
            time.sleep(2)
    except KeyboardInterrupt:
        shouldRun.clear()
        getterThread.join(1)
        for qwr in qwrs_2:
            qwrs_2[qwr]['valueQ'].join()
        sys.exit()
 
    '''
    qwrs_1 = {'dummy_1':\
                {'regexes':\
                    {'matcher':r'Successfully queried computes from novaclient:',\
                    'finder':[[ r'\{(.+)\}', fixJson ] ]},\
                'valueQ': Queue()},\
            'dummy_2':\
                {'regexes':\
                    {'matcher':r'\<ComputeActor\(',\
                    'finder':[[r'\((.+)\)', lambda x: x ]] }, \
                'valueQ': Queue()\
                }\
            }
    getterThread = Thread(target=mlp.updateQsWithRegexes, args=(['sudo tail -f /var/log/cmha.log'] | grep -v DEBUG, qwrs_1))
    shouldRun.set()
    getterThread.start()
    try:
        while shouldRun.is_set():
            while not qwrs_1['dummy_1']['valueQ'].empty():
                print(qwrs_1['dummy_1']['valueQ'].get(timeout=5))
                qwrs_1['dummy_1']['valueQ'].task_done()
            while not qwrs_1['dummy_2']['valueQ'].empty():
                print(qwrs_1['dummy_2']['valueQ'].get(timeout=5))
                qwrs_1['dummy_2']['valueQ'].task_done()
            time.sleep(2)
    except KeyboardInterrupt:
        shouldRun.clear()
        getterThread.join(1)
        for qwr in qwrs_1:
            qwrs_1[qwr]['valueQ'].join()
    '''
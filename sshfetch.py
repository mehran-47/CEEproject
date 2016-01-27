#!/usr/bin/env python3
import time, json, pprint, re
from sys import argv
from pexpect import pxssh, spawn
from queue import Queue

def execute_commands(sshHandle, commList, rettype='list'):
    for command in commList:
        sshHandle.sendline(command)
        sshHandle.prompt()
    return sshHandle.before.decode('UTF-8').splitlines()[1:] if rettype=='list' else sshHandle.before.decode('UTF-8')

def service_list_to_dict(outputList):
    toRet = {}
    for aNodesEntry in outputList[3:-1]:
        theEntryListed = aNodesEntry.split('|')[1:]
        hostName = "".join(theEntryListed[2].split())
        if hostName not in toRet:
            toRet[hostName] = {}
            toRet[hostName]['isEnabled'] = "".join(theEntryListed[4].split())
            toRet[hostName]['state'] = "".join(theEntryListed[5].split())
            toRet[hostName]['updatedAt'] = "".join(theEntryListed[-3].split())
    return toRet

def app_list_to_dict(outputList):
    toRet = {}
    for anAppEntry in outputList[3:-1]:
        theEntryListed = anAppEntry.split('|')[1:]
        hostName = "".join(theEntryListed[1].split())
        appName = "".join(theEntryListed[2].split())
        if hostName not in toRet:
            toRet[hostName] = {}
            toRet[hostName]['applications'] = {appName:{}}
        elif appName not in toRet[hostName]['applications']:
            toRet[hostName]['applications'][appName] = {}
    return toRet
            

def setConfigIPToActiveCIC_1():
    ps, ps1 = (pxssh.pxssh(),)*2 
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        ip, cic_ips, user, pw = configDict['ssh']['ip'], configDict['ssh']['cic_ips'] ,configDict['ssh']['username'], configDict['ssh']['password']
    if ps.login(ip, user, pw):
        main_cic_hostname = execute_commands(ps, ['sudo crm_mon -1 | grep cmha | grep Started'])[0].rsplit('Started')[-1]
        main_cic_hostname = "".join(main_cic_hostname.split())
        print('Main cic hostname:%s' %(main_cic_hostname))
        current_host_hostname = "".join(execute_commands(ps, ['hostname -s'])[-1].split())
        if main_cic_hostname!=current_host_hostname:
            print("CIC IP not set to main CIC")
        ps.logout()
    for anIP in cic_ips:
        pass


def updateWithCallLoadInfo(sshHandle):
    with open('config.json', 'r') as conF: 
        creds = json.loads(conF.read())['ssh_call_info']
    if sshHandle.login(creds['ip'], creds['username'], creds['password']):
        sshHandle.sendline(creds['command_to_send'])
        sshHandle.prompt()
    return json.loads(ps.before.decode('utf-8').splitlines()[-1])


if __name__=='__main__':
    p = pprint.PrettyPrinter()
    ps = pxssh.pxssh()
    print(getCallLoadInfo(ps))
    ps.logout()
    #setConfigIPToActiveCIC()
    '''
    ps = pxssh.pxssh()
    with open('config.json', 'r') as conF:
        configDict = json.loads(conF.read())
        ip, user, pw = configDict['ssh']['ip'] ,configDict['ssh']['username'], configDict['ssh']['password']
    if ps.login(ip, user, pw):
        print(execute_commands(ps, ['sudo tail -f /var/log/cmha.log &']))
    '''
    print(getCallLoadInfo())
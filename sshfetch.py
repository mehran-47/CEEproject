#!/usr/bin/env python3
import time, json, pprint
from sys import argv
from pexpect import pxssh

def execute_commands(sshHandle, commList, rettype='list'):
    for command in commList:
        sshHandle.sendline(command)
        sshHandle.prompt()
    return sshHandle.before.decode('UTF-8').splitlines()[1:] if rettype=='list' else sshHandle.before.decode('UTF-8')

def service_list_to_json(outputList):
    toRet = {}
    for aNodesEntry in outputList[3:-1]:
        theEntryListed = aNodesEntry.split('|')[1:]
        if theEntryListed[2] not in toRet:
            hostName = "".join(theEntryListed[2].split())
            toRet[hostName] = {}
            toRet[hostName]['isEnabled'] = "".join(theEntryListed[4].split())
            toRet[hostName]['state'] = "".join(theEntryListed[5].split())
            toRet[hostName]['updatedAt'] = "".join(theEntryListed[-3].split())
    return json.dumps(toRet)
    #return toRet

if __name__=='__main__':
    p = pprint.PrettyPrinter()
    with open('sample_output.txt', 'r') as f: p.pprint(service_list_to_json(f.read().splitlines()))
    """  
    if argv[2:]:
        ps = pxssh.pxssh()
        if not ps.login(argv[1], argv[2], argv[3]):
            print(str(ps))
        else:
            print(execute_commands(ps, ['cd /home/mk/Downloads', 'ls -la', 'echo "hello from ssh" > toF.txt', 'ls -la'], 'string'))
            print(execute_commands(ps, ['cat /home/mk/Documents/ceeprojSandbox/'+argv[0]]))
    else:
        print('Usage:\n%s <destination IP> <SSH username> <SSH password>')
    """
    
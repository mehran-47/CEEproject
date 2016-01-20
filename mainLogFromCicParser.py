#!/usr/bin/env python3
from pexpect import pxssh, spawn
import time, re, queue

class mainLogParser():
	def __init__(self, credDict):
		self.credDict = credDict
		self.ip = credDict['ip']
		self.user = credDict['user']
		self.pw = credDict['pw']

	def get_output(self, commList, regex):
		child = spawn('ssh '+self.user+'@'+self.ip)
		child.expect(self.user+"@"+self.ip+"'s password:")
		child.sendline(self.pw)
		child.sendline(commList[-1])
		for line in child:
			foundLines = re.findall(regex, line.decode('utf-8'))
			if len(foundLines)>0:
				print(foundLines[0])

if __name__ == '__main__':
	credDict = {'ip':'10.118.37.164', 'user':'ceeadm', 'pw':'#Ce3Adm1N#'}
	p = mainLogParser({'ip':'10.118.37.164', 'user':'ceeadm', 'pw':'#Ce3Adm1N#'})
	p.get_output(['sudo tail -f /var/log/cmha.log | grep --color=never "Successfully queried computes from novaclient"'])

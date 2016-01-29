#!/usr/bin/env python3
from sys import argv
import re

def checkRegexAgainst(stringList, regexToTest):
	foundList = []
	return [re.findall(regexToTest, aString)[-1] for aString in stringList]	

if __name__ == '__main__':
	toTest = r'(\d{4}\-\d{2}\-\d{2}\s\d{2}\:\d{2}\:\d{2})(?=\s)'
	linesList = [
	"2016-01-29 20:07:33 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local",\
	"2016-01-29 20:07:33 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local",\
	"2016-01-29 20:07:33 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local",\
	"2016-01-29 20:07:33 cmha: Fuel:RegionOne:192.168.0.11 ERROR can update uptime: Command '('timeout', '9', 'ssh', '-o', 'UserKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=no', '192.168.0.11', '--', 'cat /proc/uptime')' returned non-zero exit status 255",\
	"2016-01-29 20:07:34 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local",\
	"2016-01-29 20:07:34 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local",\
	"2016-01-29 20:07:34 cmha: urllib3.connectionpool INFO Starting new HTTPS connection (1): public.fuel.local"]
	print(checkRegexAgainst(linesList, toTest))
	#checkRegexAgainst(linesList, toTest)
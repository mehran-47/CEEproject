#!/usr/bin/env python3
import re, sys, json

if __name__ == '__main__':
	if sys.argv[1:] and sys.argv[1]=='--reset' or sys.argv[1]=='-r':
		print('Resetting to default view: "isDemoCase":False and "visibility":True for all')
		with open('html/appViewConfig.json', 'r') as avc: avcDict = json.loads(avc.read())
		for anApp in avcDict: avcDict[anApp]['isDemoCase'], avcDict[anApp]['visibility'] = False, True
		with open('html/appViewConfig.json', 'w') as avc: avc.write(json.dumps(avcDict, indent=4, separators=(',', ':')))
		sys.exit()
	if not sys.argv[2:]:
		print('usage: \nsetDemoCases.py <regex_1> ... <regex_n> <True or False>')
	else:
		avcDict = {}
		toSet = True if sys.argv[-1]=='True' or sys.argv[-1]=='true' else False
		with open('html/appViewConfig.json', 'r') as avc: avcDict = json.loads(avc.read())
		for aRegex in sys.argv[1:-1]:
			compiledRegex = re.compile(aRegex, re.I)
			for anApp in avcDict:
				if compiledRegex.search(anApp) is not None:
					avcDict[anApp]['isDemoCase'], avcDict[anApp]['visibility'] = toSet, toSet
					print('Setting visibility and democase ', toSet ,'for :', anApp)
		with open('html/appViewConfig.json', 'w') as avc: avc.write(json.dumps(avcDict, indent=4, separators=(',', ':')))

#!/usr/bin/env python3
from sys import argv
if __name__ == '__main__':
	fixedList = []
	with open(argv[1], 'r') as f:
		fixedList = [line.rsplit('\n')[0] for line in f.readlines() if "".join(line).split(' ')!='']
		print(fixedList)
	with open(argv[1], 'w') as f:
		f.write("\n".join(fixedList))


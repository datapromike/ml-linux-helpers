#!/usr/bin/python

# ###########################################
# Version: 0.1.0
# ###########################################
# Reviews Log File and Extracts Pertinant
#  Segmentation Fault information
# ###########################################
import sys
import argparse

## Command Line ARgument Parsing ##
parser = argparse.ArgumentParser(description='Extract Pertinent Segmentation Fault Details from ErrorLog')
parser.add_argument("-v","--verbose", help="Enable verbose output", action="store_true")
parser.add_argument("--file", help="Input file name. Default is ./ErrorLog.txt", action="store")
args=parser.parse_args()

if args.file is not None:
	logFile = args.file 
else:
	logFile = './ErrorLog.txt'

if args.verbose == True:
	verbose = True
else:
	verbose = False

## Default Values ##
lookFor = "Segmentation fault in thread"
threadId = ""
faultStart = ""
segFaultReport = ""
faultCounter = 0

# Try to open the file and throw an error
try:
	with open(logFile, "r") as a:
		print >> sys.stdout, "\n\t\t#################################"
		print >> sys.stdout, "\n\t\tProcessing File: %15s\n" % logFile
		print >> sys.stdout, "\t\t#################################\n"
except:
	print >> sys.stdout, logFile, 'does not exist. Please check that the file exists'

with open(logFile, "r") as errorLog:
    match = False

    for line in errorLog:
 		if verbose == True:
			print >> sys.stdout, "          %s" % line
		if not line.strip():
			()
		elif lookFor in line:
			lineParts = [x.strip() for x in line.split()]
			threadId = lineParts[-1]  #threadId is last word in string
			match = True
			faultCounter += 1

		if match == True and threadId in line:
			if verbose == True:
				print >> sys.stdout, line
			segFaultReport += line
			if "Thread" in line:
				faultStart = True
		elif match == True and faultStart == True:
			if "Thread" in line:
				faultStart = False
				match = False
			else:
				if verbose == True:
					print >> sys.stdout, line
				segFaultReport += line
errorLog.close()
print >> sys.stdout, "\t\tTotal Faults: %d \n" % faultCounter

print >> sys.stdout, segFaultReport

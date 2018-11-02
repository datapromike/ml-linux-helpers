#!/usr/bin/python

# ###########################################
# Version: 1.0.3
# ###########################################

import re
import os
import os.path
import tempfile
import subprocess
import multiprocessing
import platform
import stat
import pdb
import sys
import socket
import locale
locale.setlocale(locale.LC_ALL, '')

from time import gmtime, strftime
from stat import *
import argparse

## Command Line ARgument Parsing ##
parser = argparse.ArgumentParser(description='Check RHEL configuration against MarkLogic best practices')
parser.add_argument("-v","--verbose", help="Enable verbose output", action="store_true")
parser.add_argument("--check", help="Only Check Settings. Do not make changes", action="store_true")
parser.add_argument("--fix", help="Automatically apply default fix suggestions.  Use with Caution", action="store_true")
parser.add_argument("--silent", help="Output to Logging file and not console", action="store_true")
parser.add_argument("--test", help="Use test configuration files located in /tmp. Used for debugging script", action="store_true")
parser.add_argument("--device", help="Specify MarkLogic block storage device  Default is: /sys/block/sda", action="store")
parser.add_argument("--lhp", help="Specify Transparent Huge Pages Value.")
args=parser.parse_args()

#File List to Check for Settings
if args.test == False:
	thp_file="/sys/kernel/mm/transparent_hugepage/enabled"
	grub_file="/etc/grub.conf"
	meminfo_file="/proc/meminfo"
	sysctl_file="/etc/sysctl.conf"
	huge_page_file="/proc/sys/vm/nr_hugepages"
	marklogic_log_dir="/var/opt/MarkLogic/Logs/"
	uuid_file='/sys/devices/virtual/dmi/id/product_uuid'
else:
	thp_file="/sys/kernel/mm/redhat_transparent_hugepage/enabled"
	grub_file="/etc/grub.conf"
	meminfo_file="/proc/meminfo"
	sysctl_file="/tmp/sysctl.conf"
	huge_page_file="/tmp/nr_hugepages"
	marklogic_log_dir='/tmp/Logs/'
	default_block_dev='/tmp/block/sda'
	uuid_file='/sys/devices/virtual/dmi/id/product_uuid'

# Get FQDN and Date/Time for logging and reporting
#hostname = socket.gethostbyaddr(socket.gethostname())[0]
hostname = socket.gethostname()
sys_datetime = strftime("%Y%m%d-%H%M%S", gmtime())

#Set Logfile Name with Basename+Hostname+YYYYMMDD-hhmmss.out
basename = "ML-best-practice"

#Set Logfile for --fix mode.  For now generic.  Later will add hostname & date to filename
output_file=basename+"."+hostname+"."+sys_datetime+".out"

#Set output device (file or stdout) depending on --fix flag.
if args.silent == True:
	sys.stdout = open(output_file, "w")
#	sys.stderr = 

#Print out key values in Verbose mode
if args.verbose == True:
	print >> sys.stdout, "hostname = %s" % hostname
	print >> sys.stdout, "sys_datetime = %s" % sys_datetime
	print >> sys.stdout, "output_file = %s" % output_file
	print >> sys.stdout, "thp_file = %s" % thp_file
	print >> sys.stdout, "grub_file = %s" % grub_file
	print >> sys.stdout, "meminfo_file = %s" % meminfo_file
	print >> sys.stdout, "sysctl_file = %s" % sysctl_file
	print >> sys.stdout, "huge_page_file = %s" % huge_page_file
	print >> sys.stdout, "marklogic_log_dir = %s" % marklogic_log_dir

# Check for EC2/non EC2 to set default block device
try:
        fh_uuid_file = open(uuid_file, "r")
except PermissionError:
        print ("\n%15s" % (uuid_file))
else:
        fh_uuid_file = open(uuid_file, "r")

uuid_value = fh_uuid_file.readline()
fh_uuid_file.close()

# If UUID starts with EC2, then good chance it's AWS EC2 Instance
if not re.search(r'^EC2', uuid_value):
	print "\n\nINFO:  Non-EC2 RHEL detected"
	default_block_dev='/sys/block/sda'
else:
	print "\n\nINFO:  EC2 RHEL detected"
	default_block_dev='/sys/block/xvda'

#Get command line options or set default values
if args.device is not None:
	if os.path.exists(args.device+"/queue/scheduler"):
		io_sched_file=args.device+"/queue/scheduler"
	else:
		print >> sys.stderr, (args.device +" is not a valid block device")
		print >> sys.stderr, "Please check the device"
		sys.exit(1)
else :
	if os.path.exists(default_block_dev+"/queue/scheduler"):
		io_sched_file=default_block_dev+"/queue/scheduler"
	else:
                print >> sys.stderr, (default_block_dev +" is not a valid block device")
                print >> sys.stderr, "Please check the device"
                sys.exit(1)

#Print out key values in Verbose mode
if args.verbose == True:
	print "io_sched_file = %s" % (io_sched_file)

#Temp directories and files
temp_sysctl_file='/tmp/sysctl.conf.tmp'
temp_file_1='/tmp/settings1.%s.tmp' % os.getpid
temp_file_2='/tmp/settings2.%s.tmp' % os.getpid

if (args.fix == True and args.check == True):
	print >> sys.stderr, "[Check] and [Fix] are mutually exclusive ."
	print >> sys.stderr, "Please choose one option, and try again."
	sys.exit(1)

#If Autofix flag is set, enable otherwise set to 0
if args.fix == True:
	fix_flag = 1
	swappiness_fix_flag = 1
	hugepages_fix_flag = 1
	thp_fix_flag = 1
	io_sched_fix_flag = 1
	sched_choice = 1   # noop default
else:
	fix_flag = 0
	swappiness_fix_flag = 0
	hugepages_fix_flag = 0
	thp_fix_flag = 0
	io_sched_fix_flag = 0

if args.verbose == True:
	print >> sys.stdout, ("fix_flag = %s : swappiness_fix_flag = %s : hugepages_fix_flag = %s : thp_fix_flag = %s" % 
		(fix_flag, swappiness_fix_flag, hugepages_fix_flag, thp_fix_flag))
	print >> sys.stdout, "\n"



if os.getuid() == "0":
	print >> sys.stderr, ("%15s: Get UID" % os.getuid())
	print >> sys.stderr, "Script requires elevated permissions to evaluate and change server settings"
 	print >> sys.stderr, "Try running with sudo or as an administrative user/root"
 	sys.exit(1)

# Get number of CPU threads for Minimum memory protection
thread_count = multiprocessing.cpu_count()

# print 'Memory available:', sysinfo.memory_available()
#  max_memory is in Gb and min_memory are in Mb.
total_memory_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
max_memory_kb = total_memory_bytes/1024
max_memory = total_memory_bytes/(1024.**3)
min_memory = 1024 * int(thread_count)
mem_per_thread = (max_memory / thread_count )
rec_mem_by_thread = int(thread_count * 4)

#Assumption is default value is based on 64Gb RAM capped at 262,120 (4x Default value)
max_map_count = int(max_memory / 64) * 65530
if max_map_count > 262120:
	max_map_count = 262120
elif max_map_count < 65530:
	max_map_count = 65530

if args.verbose == True:
	print >> sys.stdout, ("max_map_count = %s " % max_map_count)

print >> sys.stdout, 'INFO:  CPUs available: \t\t%s Threads/vCPUs' % thread_count
print >> sys.stdout, 'INFO:  Mem Total:\t\t%.2f GB' % max_memory
# MarkLogic Reccomends 4 GB RAM per Thread or vCPU
if mem_per_thread < 4:
	print >> sys.stdout, 'WARNING:  Memory Available is below recommendation'
	print >> sys.stdout, 'WARNING:    Current Mem per Thread/vCPU:\t%.2f GB/CPU'  % mem_per_thread
	print >> sys.stdout, 'WARNING:    Reccommended per Thread/vCPU: \t%s GB/CPU' % '4'
	print >> sys.stdout, 'WARNING:    Reccommended Min Mem: \t%.2f GB' % rec_mem_by_thread
else:
	print >> sys.stdout, 'INFO:  Mem per Thread/vCPU:\t%.2f GB/CPU'  % mem_per_thread
print >> sys.stdout, '\n'

###  Check for Transparent Huge Page Setting
### 
try:
	fh_thp_file = open(thp_file, "w")
except PermissionError:
	print ("\n%15s" % (thp_file))
else:
	fh_thp_file = open(thp_file, "r+w")

thp_value = fh_thp_file.readline()

if not re.search(r"\[never\]", thp_value):
	print  "WARNING:  Transparent Huge Pages are Enabled"
	if args.check == True:
		print >> sys.stdout, 'INFO:  Checking configuration.  No changes will be made.'
	elif args.fix == True:
		thp_fix_flag = 1
		if args.verbose == True:
			print "thp_fix_flag:  %s" % thp_fix_flag
	else :			
		print "\nWOULD YOU LIKE TO FIX TRANSPARENT HUGEPAGES?:  "
		user_input = raw_input('y or [n]:  ')
		if user_input == 'y':
			print('You said yes!')
			fix_flag = 1
			thp_fix_flag = 1
		elif user_input == 'n':
			print ('You said no!  No Changes Will be Made!')
		else:
			print ('Invalid Option:  No Changes Will be Made!') 
else:
	print  "INFO:  Transparent Huge Pages are Disabled" 

fh_thp_file.close()

 
### Check the number of huge pages ##
huge_page_fh = open(huge_page_file,'r')
num_huge_pages = int(huge_page_fh.readline())
#% format((hugepage_size_kb / 1024), "n")
 
print>> sys.stdout, "INFO:  Number of Huge Pages Configured:  %s" % format((num_huge_pages),"n")
 
huge_page_fh.close()

## Open Meminfo file to get swap, huge pages and other settings

fh_meminfo_file = open(meminfo_file, "r")
meminfo_values = fh_meminfo_file.read().split('\n')


##  Huge Pages
#   Huge Pages should be no more than 3/8 the size of physical memory
# Get settings from linux configuration files
hugepage_size_setting = [line for line in meminfo_values if "Hugepagesize" in line]
hugepage_size_of_page = "".join(hugepage_size_setting).split()[1]
hugepage_size_kb = int(hugepage_size_of_page) * int(num_huge_pages)
if args.verbose == True:
#	print  ("num_huge_pages = %s " % num_huge_pages)
	print >> sys.stdout, ("hugepage_size_setting = %s " % hugepage_size_setting)
	print >> sys.stdout, ("hugepage_size_of_page = %s kb " % hugepage_size_of_page)
	print >> sys.stdout, ("hugepage_size_kb = %s kb" % hugepage_size_kb)


#  3/8 Main Memory Value - Default Upper Limit if no other recommendations found
#    0 - Default lower limit if no other recommendations found
ml_hugepage_rec_high = int((int(max_memory_kb) * 3 / 8) / int(hugepage_size_of_page))
ml_hugepage_rec_low = 0

## Check for MarkLogic log entries for Huge Pages
if os.path.exists(marklogic_log_dir) == True:
	ml_hugepage_rec = os.popen('grep "Linux Huge Pages"  /var/opt/MarkLogic/Logs/*').read().split(',')[-1]
	if len(ml_hugepage_rec.split()) == 4:
		ml_hugepage_rec_low = ml_hugepage_rec.split()[1]
		ml_hugepage_rec_high = ml_hugepage_rec.split()[3]
		print >> sys.stdout, "INFO:  MarkLogic Hugepage Sizing Recommendation (in pages)"
		print >> sys.stdout, ('HUGEPAGE LOW:  %s pages 	HUGEPAGE HIGH:  %s pages \n' % (ml_hugepage_rec_low, ml_hugepage_rec_high))
else:
	print >> sys.stdout, "INFO:  MarkLogic not Currently Installed."


## If ml_huge
#Should be 3/8 the size of main memory.
#max_hugepage_setting = ml_hugepage_rec_high
max_hugepage_size_kb = int(ml_hugepage_rec_high) * int(hugepage_size_of_page)

# Check out the remaining memory after lhp removed
mem_avail_to_os = int(max_memory_kb - hugepage_size_kb)

## Check for command line entry for huge pages, else: default to the greater of 3/8 memory or ML recommendation Low bounds
if args.lhp is not None:
	lhp_value = args.lhp
elif ml_hugepage_rec_low > ml_hugepage_rec_high:
	lhp_value = ml_hugepage_rec_low
else:
	lhp_value = ml_hugepage_rec_high


if args.verbose == True:
	print >> sys.stdout, ("ml_hugepage_rec_low = %s" % ml_hugepage_rec_low)
	print >> sys.stdout, ("ml_hugepage_rec_high = %s" % ml_hugepage_rec_high)
	#print >> sys.stdout, ("max_hugepage_setting = %s"  % ml_hugepage_rec_high)   
	print >> sys.stdout, ("max_hugepage_size_kb = %s" % max_hugepage_size_kb)  
	print >> sys.stdout, ("max_memory_kb = %s" % int(max_memory_kb))
	print >> sys.stdout, ("num_huge_pages = %s" % num_huge_pages)
	print >> sys.stdout, ("lhp_value = %s" % lhp_value)
	print >> sys.stdout, ("mem_avail_to_os = %s" % mem_avail_to_os)


if args.lhp is not None:
	if((int(lhp_value) > int(num_huge_pages) or (int(lhp_value) < int(num_huge_pages)))):
		print >> sys.stdout, ("INFO:  Specified Linux Huge Pages Value is Different From Current Setting")
		print >> sys.stdout, ("INFO:  Current Setting: %s Pages       Specified Setting: %s Pages" %
			(num_huge_pages, lhp_value))

# Verify that LHP setting will not starve OS
#   RHEL recommends 1 Gb per thread
if mem_avail_to_os < min_memory:
	print >> sys.stdout, ("WARNING:  Current Hugepages setting may starve the OS and/or prevent booting")
	print >> sys.stdout, ("WARNING:    Current OS Memory: %s     Hugepage setting: %s" %
		format(mem_available_to_os,"n"), format(hugepage_size_kb,"n"))
elif meminfo_file >= min_memory:
	print >> sys.stdout, ("INFO:  Minimum Recommended Memory for OS: %.2f GB" % float(min_memory/1024))

if (int(hugepage_size_kb) > int(max_hugepage_size_kb)) or (int(hugepage_size_kb) == 0) or (int(hugepage_size_kb) < int(ml_hugepage_rec_low)):
	print >> sys.stdout, ("WARNING:  Current Hugepages setting is outside recommendations")
#Add lhp_value check for size
	print >> sys.stdout, ("WARNING:    Current Setting: %s Pages (%sKb)" % 
		(num_huge_pages, format(hugepage_size_kb,"n")))
	print >> sys.stdout, ("WARNING:    Max Setting %s Pages (%sKb)" % 
		(ml_hugepage_rec_high, format(max_hugepage_size_kb,"n")))
	if args.check == True:
		fix_flag = 0
		hugepages_fix_flag = 0
	elif args.fix == True:
		fix_flag = 1
		hugepages_fix_flag = 1
	else:
		print ("\nWOULD YOU LIKE TO FIX HUGEPAGES?:  ")
		user_input = raw_input('y or [n]:  ')
		if user_input == 'y':
			print('You said yes!')
			fix_flag = 1
			hugepages_fix_flag = 1
		elif user_input == 'n':
			print ('You said no!  No Changes Will be Made!')
		else:
			print ('Invalid Option:  No Changes Will be Made!') 
elif hugepage_size_kb > 0:
	print >> sys.stdout, ("INFO:  Hugepages are within recommendations")
	print >> sys.stdout, ("INFO:  Check against suggested values located in MarkLogic errorlog")
	print >> sys.stdout, ("INFO:    Current Setting: %s Mb" % format((hugepage_size_kb / 1024), "n"))
	print >> sys.stdout, ("INFO:    Max Setting: %s Mb\n" % format((max_hugepage_size_kb / 1024),"n"))

##  Swap Space
#   Swap should be set to 1 x Ram - Huge Pages setting up to 32GB

swap_space_setting = [line for line in meminfo_values if "SwapTotal" in line]
swap_space_kb = "".join(swap_space_setting).split()[1]
swap_space_mb = int(swap_space_kb) / 1024

rec_swap_space_kb = int(max_memory_kb) - int(hugepage_size_kb)

#Check for over 32Gb recommendation
if rec_swap_space_kb > (int(32)*1024*1024):
	rec_swap_sapce_mb = (int(32)*1024)
else:
	rec_swap_space_mb = (int(rec_swap_space_kb) / 1024)

if swap_space_mb < rec_swap_space_mb:
	print >> sys.stdout, ("WARNING:  Swap space is set below MarkLogic guidelines")
	print >> sys.stdout, ("WARNING:    Current Setting:	    %s Mb" % format(swap_space_mb, "n"))
	print >> sys.stdout, ("WARNING: 	Recommended Min:	%s Mb\n" % format(rec_swap_space_mb, "n"))
else:
	print >> sys.stdout, ("INFO:  Swap space is within MarkLogic guidelines")
	print >> sys.stdout, ("INFO:  Current Setting:		    %s Mb" % format(swap_space_mb, "n"))
	print >> sys.stdout, ("INFO:  	Recommended Min:    	%s Mb\n" % format(rec_swap_space_mb, "n"))


fh_meminfo_file.close()


### Swappiness
#  swappiness should be set to 1

fh_sysctl_file = open(sysctl_file, "r")

sysctl_file_values = fh_sysctl_file.readlines()
swappiness_setting = [line for line in sysctl_file_values if "swappiness" in line]

if swappiness_setting == []:
	print >> sys.stdout, "WARNING:  Swappiness has not been set, default value is 60"
	print >> sys.stdout, "WARNING:  Recommended Setting is 1"
	if args.check == True:
		fix_flag = 0
		swappiness_fix_flag = 0
	elif args.fix == True:
		fix_flag = 1
		swappiness_fix_flag = 1
	else:
		print "\nWOULD YOU LIKE TO FIX SWAPPINESS?:  "
		user_input = raw_input('y or [n]:  ')
		if user_input == 'y':
			print('You said yes!')
			fix_flag = 1
			swappiness_fix_flag = 1
		elif user_input == 'n':
			print ('You said no!  No Changes Will be Made!')
		else:
			print ('Invalid Option:  No Changes Will be Made!') 
else:
	swappiness_value = "".join(swappiness_setting).split('=')[1]
	if int(swappiness_value) > 1:
		if args.check == True:
			fix_flag = 0
			swappiness_fix_flag = 0
		elif args.fix == True:
			fix_flag = 1
			swappiness_fix_flag = 1
		else:
			print  ("WARNING:  Swappiness is set to %s" % swappiness_value)
			print  "WARNING:  Recommended Setting is 1"
			print "\nWOULD YOU LIKE TO FIX SWAPPINESS?:  "
			user_input = raw_input('y or [n]:  ')
			if user_input == 'y':
				print('You said yes!')
				fix_flag = 1
				swappiness_fix_flag = 1
			elif user_input == 'n':
				print ('You said no!  No Changes Will be Made!')
			else:
				print ('Invalid Option:  No Changes Will be Made!') 
	else:
		print  ("INFO:  Swappiness is set to  %s" % swappiness_value)

fh_sysctl_file.close()


### Check the IO Scheduler setting
fh_io_sched_file = open(io_sched_file, "r")
io_sched_value = fh_io_sched_file.readline()
fh_io_sched_file.close()

if re.search(r"\[deadline\]", io_sched_value):
	print >> sys.stdout, "INFO:  IO Scheduler is using:  deadline"
	if args.fix == True:
		io_sched_fix_flag = 0
elif re.search(r"\[noop\]", io_sched_value):
	print >> sys.stdout, "INFO:  IO Scheduler is using:  noop"
	print >> sys.stdout, "INFO:    Ensure you are using SSD or Intelligent I/O Controllers (Hardware Raid)"
	print >> sys.stdout, "INFO:	   Or are operating in a VMware environment\n"
	if args.fix == True:
		io_sched_fix_flag = 0
else:
	print >> sys.stdout, "WARNING:  IO Scheduler should be set to either [deadline] or [noop]"

	if args.check == True:
		fix_flag = 0
		io_sched_fix_flag = 0
	elif args.fix == True:
		fix_flag = 1
		io_sched_fix_flag = 1
		sched_choice = 1
	else:
		print "\nWOULD YOU LIKE TO CHANGE IO SCHEDULER?:  "
		user_input = raw_input('y or [n]:  ')
		if user_input == 'y':
			print('You said yes!')
			fix_flag = 1
			io_sched_fix_flag = 1
			# Pick the Scheduler
			print('Choose 1 for [noop] or 2 for [deadline]')
			sched_choice = int(raw_input('1 or 2:  '))
			if sched_choice == 1:
				print('IO Scheduler will be changed to [noop]')
			elif sched_choice == 2:
				print('IO Scheduler will be changed to [deadline]')
			else:
				print ('Invalid Option:  No Changes Will be Made!')
				io_sched_fix_flag = 0
		elif user_input == 'n':
			print ('You said no!  No Changes Will be Made!')
			io_sched_fix_flag = 0
		else:
			print ('Invalid Option:  No Changes Will be Made!')
			io_sched_fix_flag = 0


###  Fix Section - All Logic to change settings should be in this section

if fix_flag == 1:
	if swappiness_fix_flag == 1:
		#Remove existing settings from sysctl.conf file if they exist
		os.system('cp -p /etc/sysctl.conf /tmp/sysctl.bak1')
		os.system('cat /etc/sysctl.conf | grep -v vm.swappiness | grep -v vm.dirty_background_ratio | grep -v dirty_ratio | grep -v MarkLogic> /tmp/sysctl.conf.tmp')
		os.system('cat /tmp/sysctl.conf.tmp > /etc/sysctl.conf')
		#Write Settings to systcl.conf file
		fh_sysctl_file = open(sysctl_file, 'a')
		print >> fh_sysctl_file, ("\n# MarkLogic Recommended Settings")
		print >> fh_sysctl_file, ("vm.swappiness = 1")
		print >> fh_sysctl_file, ("vm.dirty_background_ratio = 1")
		print >> fh_sysctl_file, ("vm.dirty_ratio = 40")
		# max_map_count set to default (65530) x 4 per help.marklogic.com
		print >> fh_sysctl_file, ("vm.max_map_count = %s" % max_map_count )
		fh_sysctl_file.close()
		# Remove Temp File
		os.remove("/tmp/sysctl.conf.tmp")
		
	if hugepages_fix_flag == 1:
		#Remove esisting settings from sysctl.conf if they exist
		os.system('cp -p /etc/sysctl.conf /tmp/sysctl.bak2')
		os.system('cat /etc/sysctl.conf | grep -v vm.nr_hugepages > /tmp/sysctl.conf.tmp')
		os.system('cat /tmp/sysctl.conf.tmp > /etc/sysctl.conf')
		#Write SEttings to systcl.conf file
		fh_sysctl_file = open(sysctl_file, 'a')
		print >> fh_sysctl_file, ("vm.nr_hugepages = %s" % ml_hugepage_rec_high)

		fh_sysctl_file.close()
		# Remove Temp File
		os.remove("/tmp/sysctl.conf.tmp")

	if thp_fix_flag == 1:
		#Update /etc/grub.conf using grubby command with --grub2 flag to support RHEL 7
		# easier than editing /etc/default/grub and using grub2-mkconfig
		os.system('grubby --grub2 --update-kernel=ALL --args="transparent_hugepage=never"')
		os.system('echo never > /sys/kernel/mm/transparent_hugepage/enabled')
		os.system('echo never > /sys/kernel/mm/transparent_hugepage/defrag')

	if io_sched_fix_flag == 1:
		if sched_choice == 1:
			#Update /etc/grup.conf using grubby command
			os.system('grubby --grub2 --update-kernel=ALL --args="elevator=noop"')
			os.system('echo noop > ' + io_sched_file)
		else:
			os.system('grubby --grub2 --update-kernel=ALL --args="elevator=deadline"')
			os.system('echo deadline > ' + io_sched_file)

	#If a change was made to sysctl.conf, issue 'sysctl -f' for settings to take effect.
	if (swappiness_fix_flag == 1) or (hugepages_fix_flag == 1):
		os.system('sysctl -f')

#Close output file if the fiex argument is set
if args.silent == True:
	sys.stdout.close()

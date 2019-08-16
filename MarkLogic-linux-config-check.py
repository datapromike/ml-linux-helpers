#!/usr/bin/python

# ###########################################
# MarkLogic-linux-config.py
# Version: 1.0.0
# Author: Mike Gardner
# ###########################################
#
# This script will check Red Hat/CentOS configuration
#  values against published best practices for
#  configuring MarkLogic server on Linux.
#  This script requires elevated privileges to run
#  but does not make any changes to the system.
#  
#
##############################################

import re
import os
import os.path
import multiprocessing
import platform
import stat
import sys
import socket
import locale
import glob
from time import gmtime, strftime
from stat import *
import argparse


################################################
#   Retreive Platform/Host Information         #
################################################
def get_platform_details():
  global default_block_device, distro_name, distro_version,hostname,sys_datetime
# If UUID starts with EC2, then good chance it's AWS EC2 Instance
  #os_version = platform.dist()
  if os.path.exists("/etc/redhat-release"):
    distro_name = "redhat"
  elif os.path.exists("/etc/centos-release"):
    distro_name = "centos"
  elif os.path.exists("/etc/system-release"):
    distro_name = "other"

  try:
    open(uuid_file, "r")
  except Exception:
    print ("\n%15s" % (uuid_file))
  else:
    with open(uuid_file, "r") as fh_uuid_file:
      uuid_value = fh_uuid_file.readline()


  if not re.search(r'^EC2', uuid_value):
    print "\n%s %s detected - non EC2" % (info, distro_name.upper())
    default_block_dev='/sys/block/sda'
  else:
    print "\n%s %s detected - EC2" % (info, distro_name.upper())
    default_block_dev='/sys/block/xvda'

  if distro_name is not "redhat":
    print >> sys.stdout, "%s This script was created and tested against RHEL 7" % warn
    print >> sys.stdout, "%s   use any other Linux distributions may not work \n" % warn
  #redhat /etc/redhat-release
  #centos /etc/centos-release
  #Amazon /etc/system-release
  # Get FQDN and Date/Time for logging and reporting
  #hostname = socket.gethostbyaddr(socket.gethostname())[0]
  hostname = socket.gethostname()
  sys_datetime = strftime("%Y%m%d-%H%M%S", gmtime())

################################################
#   Retreive Device Information                #
################################################
def get_device_details():
  global io_sched_file
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
################################################
#   Retreive Hardware Information              #
################################################
def get_hardware_details():
  ###  Declare the Global Variables  ###
  global rhel_min, thread_count, total_memory_bytes, max_memory_kb, max_memory, min_memory, mem_per_thread

  if args.verbose == True:
    print >> sys.stdout, "Entering function get_hardware_details"

  rhel_min = 1024  #1 Gb per thread for RHEL 7
  thread_count = multiprocessing.cpu_count()
  total_memory_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')

  max_memory_kb = total_memory_bytes/1024

  max_memory = total_memory_bytes/(1024.**3)  #Returns GB

  min_memory = rhel_min * int(thread_count) 

  mem_per_thread = (max_memory / thread_count )

  if args.verbose == True:
    print >> sys.stdout, "Exiting function get_hardware_details"


################################################
#  Compare hardware details against minimums
#  and recommendations
################################################
def compare_values():
  global rec_mem_by_thread
  # https://docs.marklogic.com/guide/installation/intro#id_11335
  # Prod - At least 4G RAM per thread/vCPU; 8 thread/vCPU
  # Dev  - Minimum 2G RAM total; Recommended at least 4G RAM total
  if prod == True:
    rec_mem_by_thread = int(thread_count * 4) #4GB Rec
  else:
    rec_mem_by_thread = int(thread_count * 1) #Falling back to RHEL recommendation
    min_mem_dev = 2  #in Gb
    rec_mem_dev = 4  #in Gb
  print >> sys.stdout, '%s CPUs available: \t\t%s Threads/vCPUs' % (info, thread_count)
  print >> sys.stdout, '%s Mem Total:\t\t%.2f GB' % (info, max_memory)
  # MarkLogic Reccomends 4 GB RAM per Thread or vCPU in Production systems
  if prod == True and mem_per_thread < 4:
    print >> sys.stdout, '%s Memory Available is below recommendation' % warn
    print >> sys.stdout, '%s Current memory per thread/vCPU:\t%.2f GB/CPU'  % (warn, mem_per_thread)
    print >> sys.stdout, '%s Recommended minimum memory per thread/vCPU: \t%s GB/CPU' % (warn,'4')
    print >> sys.stdout, '%s Recommended minimum total memory: \t%.2f GB' % (warn,rec_mem_by_thread)
  else:
    print >> sys.stdout, '%s Memory available meets or exceeds minimum recommendation' % (info)
    print >> sys.stdout, '%s Memory per thread/vCPU:\t%.2f GB/CPU'  % (info,mem_per_thread)


  # MarkLogic requires at least 2 GB, and recommends at least 4 GB total RAM in non-production systems
  if prod == False and max_memory < min_mem_dev:
    print >> sys.stdout, '%s Memory Available is below minimum requirements' % warn
    print >> sys.stdout, '%s Current memory (non-production):\t%.2f GB'  % (warn,max_memory)
    print >> sys.stdout, '%s Minimum memory required:\t%.2f GB' % (warn,min_mem_dev)
    print >> sys.stdout, '%s Recommended memory: at least \t%.2f GB' % (warn,rec_mem_dev)

  elif prod == False and max_memory >= min_mem_dev and max_memory < rec_mem_dev:
    print >> sys.stdout, '%s Memory Available is below recommendation' % warn
    print >> sys.stdout, '%s Current memory (non-production):\t%.2f GB'  % (warn,max_memory)
    print >> sys.stdout, '%s Recommended memory: at least \t%.2f GB' % (warn,rec_mem_dev)

  elif prod == False and max_memory >= rec_mem_dev:
    print >> sys.stdout, '%s Memory Available meets or exceeds recommendations' % info
    print >> sys.stdout, '%s Current memory (non-production):\t%.2f GB'  % (info,max_memory)
    print >> sys.stdout, '%s Recommended memory: at least \t%.2f GB' % (info,rec_mem_dev)


  print >> sys.stdout, '\n'

#############################################
#  Check for Transparent Huge Page Disabled #
#############################################
def trans_huge_page():
  # Try to open the file and throw an error
  try:
    open(thp_file,"r")
  except PermissionError:
    print ("\n%15s" % (thp_file))
  else:
    with open(thp_file,"r") as fh_thp_filename:
      thp_setting = fh_thp_filename.readline()
      if "[never]" not in thp_setting:
        #print >> sys.stdout, "Not Found - Enabled"
        print >> sys.stdout, '%s Transparent Huge Pages are Enabled' % warn
      else:
        #print >> sys.stdout, "Found - Disabled"
        print >> sys.stdout, '%s Transparent Huge Pages are Disabled' % info

#########################################
# linux_huge_page_config                #
#########################################
def linux_huge_page_config():
  global hugepage_size_kb
  global meminfo_values
# Get the number of huge pages configured
  if args.verbose == True:
    print "Try/Catch #1"
  try:
    open(huge_page_file,"r")
  except PermissionError:
    print ("\n%15s" % (huge_page_file))
  else:
    with open(huge_page_file,"r") as fh_hugepage_filename:
      num_huge_pages = int(fh_hugepage_filename.readline())

#  Get the value of Hugepagesize, and determine size based on number of pages configured
  if args.verbose == True:
    print "Try/Catch #2"
  try:
    open(meminfo_file, "r")
  except PermissionError:
    print ("\n%15s" % (meminfo_file))
  else:
    with open(meminfo_file,"r") as fh_meminfo_file:
      meminfo_values = fh_meminfo_file.read().split('\n')
      hugepage_size_setting = [line for line in meminfo_values if "Hugepagesize" in line]
      hugepage_size_of_page = "".join(hugepage_size_setting).split()[1]
      hugepage_size_kb = int(hugepage_size_of_page) * int(num_huge_pages)

#  Seed value of huge page recommendations in case MarkLogic doesn't have value
#    Default recommendation is 3/8 main memory.
  ml_hugepage_rec_high = int((int(max_memory_kb) * 3 / 8) / int(hugepage_size_of_page))
  ml_hugepage_rec_low = 0

#  Check for MarkLogic log files, and search for Hugepage recommendations
  if args.verbose == True:
    print "Try/Catch #3"
    #print os.listdir(marklogic_log_dir)

  try:
    os.listdir(marklogic_log_dir)
    print >> sys.stdout, "%s Checking %s" % (info,marklogic_log_dir)
  except:
    print >> sys.stdout, "%s  MarkLogic Logs Directory not found." % info
    print >> sys.stdout, "%s  Using default Linux Huge Page recommendations" % info
    if args.verbose == True:
      print >> sys.stdout, "Exception thrown on Try #3"
  else:
    files = glob.glob(marklogic_log_dir + "ErrorLog*")
    files.sort(key=os.path.getmtime,reverse=True)
    if args.verbose == True:
      print >> sys.stdout, str(files)[1:-1]
    found = False
    for logfile in glob.glob(marklogic_log_dir + "ErrorLog*"):
      with open(logfile,"r") as fh_logfile:
        for line in reversed(fh_logfile.readlines()):
#        for cnt, line in enumerate(fh_logfile):
          if "Linux Huge Pages" in line:
            if args.verbose == True:
              print logfile
              print line
              print len(line.split())
              print line.split()[-1]
              print line.split()[-3]
            
            if len(line.split()) == 12:
              ml_hugepage_rec_low = line.split()[-3]
              ml_hugepage_rec_high = line.split()[-1]
            else:
              print "MarkLogic Log Entry found but not parsed."
            found = True
          if found == True:
            break
      if found == True:
        break
  if args.lhp is not None:
    if((int(lhp_value) > int(num_huge_pages) or (int(lhp_value) < int(num_huge_pages)))):
      print >> sys.stdout, ("INFO:  Specified Linux Huge Pages Value is Different From Current Setting")
      print >> sys.stdout, ("INFO:  Current Setting: %s Pages     Specified Setting: %s Pages" %
        (num_huge_pages, lhp_value))
  else:
    print >> sys.stdout, "INFO:  Number of Huge Pages Configured:  %s" % format((num_huge_pages),"n")
  print >> sys.stdout, "INFO:  MarkLogic Hugepage Sizing Recommendation (in pages)"
  print >> sys.stdout, ('INFO:    HUGEPAGE LOW:  %s pages   HUGEPAGE HIGH:  %s pages \n' % 
        (ml_hugepage_rec_low, ml_hugepage_rec_high))
  
  # Verify that LHP setting will not starve OS
  #   RHEL 7 recommends 1 Gb per thread
  #   RHEL 8 recommends 1.5 Gb per thread
  #   https://access.redhat.com/articles/rhel-limits
  mem_avail_to_os = int(max_memory_kb - hugepage_size_kb)
  max_hugepage_size_kb = int(ml_hugepage_rec_high) * int(hugepage_size_of_page)

  if mem_avail_to_os < min_memory:
    print >> sys.stdout, ("%s Current Hugepages setting may starve the OS and/or prevent booting") % warn
    print >> sys.stdout, ("%s Current OS Memory: %s   Hugepage setting: %s" % (warn,
      format(mem_available_to_os,"n"), format(hugepage_size_kb,"n")))
  elif mem_avail_to_os >= min_memory:
    print >> sys.stdout, ("INFO:  Minimum Recommended Memory for OS: %.2f GB" % float(min_memory/1024))

  if (int(hugepage_size_kb) > int(max_hugepage_size_kb)) or (int(hugepage_size_kb) == 0) or (int(hugepage_size_kb) < int(ml_hugepage_rec_low)):
    print >> sys.stdout, ("%s Current Hugepages setting is outside recommendations") % warn
  #Add lhp_value check for size
    print >> sys.stdout, ("%s Current Setting: %s Pages (%s Kb)" % (warn,
      num_huge_pages, format(hugepage_size_kb,"n")))
    print >> sys.stdout, ("%s  Max Setting %s Pages (%s Kb)" % (warn,
      ml_hugepage_rec_high, format(max_hugepage_size_kb,"n")))
  elif hugepage_size_kb > 0:
    print >> sys.stdout, ("%s Hugepages are within recommendations") % info
    print >> sys.stdout, ("%s Check against suggested values located in MarkLogic errorlog") % info
    print >> sys.stdout, ("%s Current Setting: %s Mb" % format((hugepage_size_kb / 1024), "n")) % info
    print >> sys.stdout, ("%s Max Setting: %s Mb\n" % format((max_hugepage_size_kb / 1024),"n")) % info

  if args.verbose == True:
    print >> sys.stdout, ("hugepage_size_setting = %s " % hugepage_size_setting)
    print >> sys.stdout, ("hugepage_size_of_page = %s kb " % hugepage_size_of_page)
    print >> sys.stdout, ("hugepage_size_kb = %s kb" % hugepage_size_kb)

#########################################
# swap_config                           #
#########################################
def swap_config():
##  Swap Space
#   Swap should be set to 1 x Ram - Huge Pages setting up to 32GB

  swap_space_setting = [line for line in meminfo_values if "SwapTotal" in line]
  swap_space_kb = "".join(swap_space_setting).split()[1]
  swap_space_mb = int(swap_space_kb) / 1024

  rec_swap_space_kb = int(max_memory_kb) - int(hugepage_size_kb)

  #Check for over 32Gb recommendation
  if rec_swap_space_kb > (int(32)*1024*1024):
    rec_swap_space_mb = (int(32)*1024)
  else:
    rec_swap_space_mb = (int(rec_swap_space_kb) / 1024)

  if swap_space_mb < rec_swap_space_mb:
    print >> sys.stdout, ("%s Swap space is set below MarkLogic guidelines") % warn
    print >> sys.stdout, ("%s Current Setting:    %s Mb" % (warn,format(swap_space_mb, "n")))
    print >> sys.stdout, ("%s Recommended Min:  %s Mb\n" % (warn,format(rec_swap_space_mb, "n")))
  else:
    print >> sys.stdout, ("%s Swap space is within MarkLogic guidelines") % info
    print >> sys.stdout, ("%s Current Setting:      %s Mb" % (info,format(swap_space_mb, "n")))
    print >> sys.stdout, ("%s   Recommended Min:    %s Mb\n" % (info,format(rec_swap_space_mb, "n")))

#########################################
# swappiness_config                     #
#########################################
def swappiness_config():
## Swappiness
#  swappiness should be set to 1
  try:
    open(sysctl_file,"r")
  except PermissionError:
    print ("\n%15s" % (sysctl_file))
  else:
    with open(sysctl_file,"r") as fh_sysctl_file:
      sysctl_file_values = fh_sysctl_file.readlines()
      swappiness_setting = [line for line in sysctl_file_values if "swappiness" in line]

  if swappiness_setting == []:
    print >> sys.stdout, "%s Swappiness has not been set, default value is 60" % warn
    print >> sys.stdout, "%s Recommended Setting is 1" % warn
  else:
    swappiness_value = "".join(swappiness_setting).split('=')[1]
    if int(swappiness_value) > 1 or int(swappiness_value) < 1:
      print >> sys.stdout, "%s Swappiness is set to %s" % (warn,swappiness_value)
      print >> sys.stdout, "%s Recommended Setting is 1" % warn
    else:
      print  >> sys.stdout, "%s Swappiness is set to  %s" % (info,swappiness_value)

#########################################
# io_sched_config                     #
#########################################
def io_sched_config():
## Swappiness
#  swappiness should be set to 1
  try:
    open(io_sched_file,"r")
  except PermissionError:
    print ("\n%15s" % (sysctl_file))
  else:
    with open(io_sched_file,"r") as fh_io_sched_file:
      io_sched_value = fh_io_sched_file.readline()

  if re.search(r"\[deadline\]", io_sched_value):
    print >> sys.stdout, "%s IO Scheduler is using:  deadline" % info
    # if args.fix == True:
    #   io_sched_fix_flag = 0
  elif re.search(r"\[noop\]", io_sched_value):
    print >> sys.stdout, "%s IO Scheduler is using:  noop" % info
    print >> sys.stdout, "%s Ensure you are using SSD or Intelligent I/O Controllers (Hardware Raid)" % info
    print >> sys.stdout, "%s    Or are operating in a VMware environment\n" % info
    # if args.fix == True:
    #   io_sched_fix_flag = 0
  else:
    print >> sys.stdout, "%s IO Scheduler should be set to either [deadline] or [noop]\n" % warn

############################
#  End Functions           #
############################

############################
# Start script             #
############################
# Try to set local for number formating
try:
  locale.setlocale(locale.LC_ALL, '')
except:
  pass

## Command Line ARgument Parsing ##
parser = argparse.ArgumentParser(description='Check RHEL configuration against MarkLogic best practices')
parser.add_argument("-v","--verbose", help="Enable verbose output. Primarily for troublshooting script.", action="store_true")
parser.add_argument("--dev", help="Type of Deployment (dev or prod). Default is Prod", action="store_true")
parser.add_argument("--silent", help="Output to Logging file and not console", action="store_true")
parser.add_argument("--device", help="Specify MarkLogic block storage device. Default is: /sys/block/sda", action="store")
parser.add_argument("--lhp", help="Specify Transparent Huge Pages Value.")
args=parser.parse_args()

print >> sys.stdout, "############## START ##############"

#Settings/Configuration file list
thp_file="/sys/kernel/mm/transparent_hugepage/enabled"
grub_file="/etc/grub.conf"
meminfo_file="/proc/meminfo"
sysctl_file="/etc/sysctl.conf"
huge_page_file="/proc/sys/vm/nr_hugepages"
marklogic_log_dir="/var/opt/MarkLogic/Logs/"
uuid_file='/sys/devices/virtual/dmi/id/product_uuid'

#Define string output for info, and warning messages
outputReport = ""
info = "INFO: "
warn = "WARNING: "

#Check to see if this has been identified as a production instance
if args.dev == True:
  prod = False
else:
  prod = True

if args.verbose == True:
  print >> sys.stdout, "<<Entering get_platform_details>>"
get_platform_details()

#Set Logfile Name with Basename+Hostname+YYYYMMDD-hhmmss.out
basename = "marklogic_linux_config"

#Set Logfile for --fix mode.  For now generic.  Later will add hostname & date to filename
output_file=basename+"."+hostname+"."+sys_datetime+".out"

#Set output device (file or stdout).
if args.silent == True:
  sys.stdout = open(output_file, "w")
#  sys.stderr = 

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

if os.getuid() != 0:
  if args.verbose == True:
    print >> sys.stderr, ("%15s: Get UID" % os.getuid())
    print >> sys.stderr, "Script requires elevated permissions to evaluate and change server settings"
    print >> sys.stderr, "Try running with sudo or as an administrative user/root"
    sys.exit(1)


if args.verbose == True:
  print >> sys.stdout, "<<Entering get_device_details>>"
get_device_details()

if args.verbose == True:
  print >> sys.stdout, "<<Entering get_hardware_details>>"
get_hardware_details()

if args.verbose == True:
  print >> sys.stdout, "<<Entering compare_values>>"
compare_values()

if args.verbose == True:
  print >> sys.stdout, "<<Entering trans_huge_page>>"
trans_huge_page()
if args.verbose == True:
  print >> sys.stdout, "<<Entering linux_huge_page_config>>"
linux_huge_page_config()

if args.verbose == True:
  print >> sys.stdout, "<<Entering swap_config>>"
swap_config()

if args.verbose == True:
  print >> sys.stdout, "<<Entering swappiness_config>>"
swappiness_config()

if args.verbose == True:
  print >> sys.stdout, "<<Entering io_sched_config>>"
io_sched_config()

print >> sys.stdout, "############### END ###############"

# Close output file if used
if args.silent == True:
  sys.stdout.close()

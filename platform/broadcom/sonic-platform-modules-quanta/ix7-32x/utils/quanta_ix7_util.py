#!/usr/bin/env python
#
# Copyright (C) 2018 Quanta Computer Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Usage: %(scriptName)s [options] command object

options:
    -h | --help     : this help message
    -d | --debug    : run with debug mode
    -f | --force    : ignore error during installation or clean
command:
    install     : install drivers and generate related sysfs nodes
    clean       : uninstall drivers and remove related sysfs nodes
"""

import os
import commands
import sys, getopt
import logging
import time

DEBUG = False
args = []
FORCE = 0
i2c_prefix = '/sys/bus/i2c/devices/'


if DEBUG == True:
    print sys.argv[0]
    print 'ARGV      :', sys.argv[1:]


def main():
    global DEBUG
    global args
    global FORCE

    if len(sys.argv)<2:
        show_help()

    options, args = getopt.getopt(sys.argv[1:], 'hdf', ['help',
                                                       'debug',
                                                       'force',
                                                          ])
    if DEBUG == True:
        print options
        print args
        print len(sys.argv)

    for opt, arg in options:
        if opt in ('-h', '--help'):
            show_help()
        elif opt in ('-d', '--debug'):
            DEBUG = True
            logging.basicConfig(level=logging.INFO)
        elif opt in ('-f', '--force'):
            FORCE = 1
        else:
            logging.info('no option')
    for arg in args:
        if arg == 'install':
           install()
        elif arg == 'clean':
           uninstall()
        else:
            show_help()


    return 0

def show_help():
    print __doc__ % {'scriptName' : sys.argv[0].split("/")[-1]}
    sys.exit(0)

def show_log(txt):
    if DEBUG == True:
        print "[IX7-32X]"+txt
    return

def exec_cmd(cmd, show):
    logging.info('Run :'+cmd)
    status, output = commands.getstatusoutput(cmd)
    show_log (cmd +"with result:" + str(status))
    show_log ("      output:"+output)
    if status:
        logging.info('Failed :'+cmd)
        if show:
            print('Failed :'+cmd)
    return  status, output

instantiate =[
#Enable front-ports LED decoding
'echo 1 > /sys/class/cpld-led/CPLDLED-1/led_decode',
'echo 1 > /sys/class/cpld-led/CPLDLED-2/led_decode',
#Update System LED
'echo 42 > /sys/class/gpio/export',
'echo out > /sys/class/gpio/gpio42/direction',
'echo 0 > /sys/class/gpio/gpio42/value',
'echo 43 > /sys/class/gpio/export',
'echo out > /sys/class/gpio/gpio43/direction',
'echo 1 > /sys/class/gpio/gpio43/value',
]

drivers =[
'lpc_ich',
'i2c-i801',
'i2c-dev',
'i2c-mux-pca954x force_deselect_on_exit=1',
'gpio-pca953x',
'optoe',
'qci_cpld',
'qci_cpld_led',
'quanta_platform_ix7',
'ipmi_devintf',
'quanta_hwmon_ipmi'
]

un_drivers =[
'lpc_ich',
'i2c-i801',
'i2c-dev',
'i2c-mux-pca954x',
'gpio-pca953x',
'optoe',
'qci_cpld',
'qci_cpld_led',
'quanta_platform_ix7',
'ipmi_devintf',
'quanta_hwmon_ipmi'
]

def system_install():
    global FORCE

    #remove default drivers to avoid modprobe order conflicts
    exec_cmd("echo 'blacklist i2c-ismt' > /etc/modprobe.d/blacklist.conf", 1)
    time.sleep(1)
    exec_cmd("modprobe -r i2c-ismt ", 1)
    exec_cmd("modprobe -r i2c-i801 ", 1)
    #setup driver dependency
    exec_cmd("depmod -a ", 1)
    #install drivers
    for i in range(0,len(drivers)):
        status, output = exec_cmd("modprobe "+drivers[i], 1)
    if status:
        print output
        if FORCE == 0:
            return status

    #turn on module power
    exec_cmd("echo 21 > /sys/class/gpio/export ", 1)
    exec_cmd("echo high > /sys/class/gpio/gpio21/direction ", 1)

    #Reset fron-ports LED CPLD
    exec_cmd("echo 33 > /sys/class/gpio/export ", 1)
    status, output = exec_cmd("cat /sys/class/gpio/gpio33/value", 1)
    if output != '1':
        exec_cmd("echo out > /sys/class/gpio/gpio33/direction ", 1)
        exec_cmd("echo 0 >/sys/class/gpio/gpio33/value", 1)
        exec_cmd("echo 1 >/sys/class/gpio/gpio33/value", 1)

    #instantiate devices
    for i in range(0,len(instantiate)):
        status, output = exec_cmd(instantiate[i], 1)
    if status:
        print output
        if FORCE == 0:
            return status

    #QSFP for 1~32 port
    for port_number in range(1,33):
        bus_number = port_number + 16
        os.system("echo %d >/sys/bus/i2c/devices/%d-0050/port_name" % (port_number, bus_number))
    return


def system_ready():
    if not device_found():
        return False
    return True

def install():
    if not device_found():
        print "No device, installing...."
        status = system_install()
        if status:
            if FORCE == 0:
                return  status

        status, output = exec_cmd("pip3 install  /usr/share/sonic/device/x86_64-quanta_ix7_rglbmc-r0/sonic_platform-1.0-py3-none-any.whl",1)
        if status:
               print output
               if FORCE == 0:
                  return status
    else:
        print " ix7 driver already installed...."
    return

def uninstall():
    global FORCE
    #uninstall drivers
    for i in range(len(un_drivers)-1,-1,-1):
       status, output = exec_cmd("rmmod "+un_drivers[i], 1)
    if status:
        print output
        if FORCE == 0:
            return status

    status, output = exec_cmd("pip3 uninstall  sonic-platform -y ",1)
    if status:
	   print output
	   if FORCE == 0:
	      return status
    return

def device_found():
    ret1, log1 = exec_cmd("cat /proc/modules | grep ix7 > /tmp/chkdriver.log", 0)
    ret2, log2 = exec_cmd("cat /tmp/chkdriver.log | grep ix7", 0)

    if ret1 == 0 and len(log2) > 0:
        return True
    else:
        return False

if __name__ == "__main__":
    main()

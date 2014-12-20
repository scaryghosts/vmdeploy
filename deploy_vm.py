#!/usr/bin/python
import ConfigParser
import subprocess
import argparse
import os


def check_clone_file(filename):
    if os.access(clone_script_location, os.X_OK) is True:
    	return 'OK'
    elif os.path.exists(clone_script_location) is True:
    	return 'clone script path correct but not executable, please chmod +x'
    elif os.path.exists(clone_script_location) is False:
    	return 'clone_script option in master config file incorrect or not set'




def write_example_conf_infoblox():
    words = """\
#This is an example configuration file for deploying vms
#For each guest iterate the [Guest1] to the next number
#hostname should be the fqdn that is in Infoblox, this will fail if it is not in Infoblox
#vlan should be just the vlan id
#vcenter should be the fqdn of the vcenter server
#image should be the image identifier specified in master config file
#numcpu should be an integer for how many cpus
#mem should be an integer for how much memory in GB
#cluster should be the cluster to deploy too, this must exist in the above vcenter
#example below
[Guest1]
hostname: clone-dev.fq.dn
vlan: 3102
vcenter: vcenter.fq.dn
image: linux
numcpu: 1
mem: 4
cluster: Super Cluster
\
"""
    return words

def write_example_conf_manual():
    words = """\
#This is an example configuration file for deploying vms
#For each guest iterate the [Guest1] to the next number
#hostname should be the fqdn that is in Infoblox, this will fail if it is not in Infoblox
#vlan should be just the vlan id
#vcenter should be the fqdn of the vcenter server
#image should be the image identifier specified in master config file
#numcpu should be an integer for how many cpus
#mem should be an integer for how much memory in GB
#cluster should be the cluster to deploy too, this must exist in the above vcenter
#example below
[Guest1]
hostname: clone-dev.fq.dn
vlan: 3102
vcenter: vcenter.fq.dn
image: linux
numcpu: 1
mem: 4
cluster: Super Cluster
ip: 192.168.1.100
subnetmask: 255.255.255.0
gateway: 192.168.1.1
\
"""
    return words

def deploy_vm_infoblox(args, clone_script_location):
    conf = ConfigParser.ConfigParser()
    conf.read(args.file)
    sections = conf.sections()
    for S in sections:
    	try:
    		fqdn = conf.get(S, 'hostname')
    		vcenter = conf.get(S, 'vcenter')
    		cluster = conf.get(S, 'cluster')
    		image = conf.get(S, 'image')
    		numCPU = conf.get(S, 'numcpu')
    		memGB = conf.get(S, 'mem')
    		vlan = conf.get(S, 'vlan')
    	except IOError, e:
    		print("IOError {0}".format(e))

        deploy_return_code = subprocess.call([clone_script_location, '--vcenter', vcenter, '--fqdn', fqdn, '--cluster', cluster, '--image', image, '--numcpu', numCPU, '--memgb', memGB, '--vlan', vlan, '--config', args.master_config], shell=False)
        if deploy_return_code != 0:
        	print("%s failed to deploy" % fqdn)

def deploy_vm_manual(conf_file, clone_script_location):
    print('not implemented yet')
    exit(0)

parser = argparse.ArgumentParser()
parser.add_argument("-f", '--file', action='store', dest='file', help='specify location of deployment config file')
parser.add_argument("-g", '--generate', action='store_true', dest='genyorn', help='generate example config file')
parser.add_argument("-c", '--config', action='store', dest='master_config', default='vmdeploy.conf', help='specify location of the master config file, default is vmdeploy.conf in the same directory')
args = parser.parse_args()

master_conf = ConfigParser.ConfigParser()
master_conf.read(args.master_config)
if not master_conf.sections():
    if os.access(args.master_config, os.R_OK) is True:
        print('master config file has no sections file is possibly empty, typically vmdeploy.conf')
        exit(1)
    else:
        print('master config file not found')
        exit(1)


        
ip_config_mode = master_conf.get('config_file_options', 'ip_config_mode')
clone_script_location = master_conf.get('config_file_options', 'clone_script_location')

clone_script_status = check_clone_file(clone_script_location)
if clone_script_status != 'OK':
	print("{0}".format(clone_script_status))	
	exit(1)


if args.genyorn is True:
    if ip_config_mode == 'infoblox':
    	with open('example.conf', 'w') as thisfile:
    		thisfile.write(write_example_conf_infoblox())
    	print('example.conf created')
    	exit(0)
    elif ip_config_mode == 'manual':
    	with open('example.conf', 'w') as thisfile:
    		thisfile.write(write_example_conf_manual())
    	print('example.conf created')
    	exit(0)
    else:
    	print('ip_config_mode not specified properly in master. should be manual or infoblox')
    	exit(0)

if ip_config_mode == 'infoblox':
	deploy_vm_infoblox(args, clone_script_location)
elif ip_config_mode == 'manual':
	deploy_vm_manual(args.file, clone_script_location)
else:
	print('ip_config_mode not set properly, should be manual or infoblox')

exit()





#!/usr/bin/python

import atexit
import pyVim.connect
import pyVmomi
import re
import socket
import requests
import iptools
import json
import time
import sys
import collections
import argparse
import ConfigParser

def cidrmap(x):
        return {
                '22' : '255.255.252.0',
                '23' : '255.255.254.0',
                '24' : '255.255.255.0',
                '25' : '255.255.255.128',
                '26' : '255.255.255.192',
                '27' : '255.255.255.224',
                '28' : '255.255.255.240',
                '29' : '255.255.255.248',
                '30' : '255.255.255.252'
        }.get(x, '255.255.255.0')

#returns a vm object
def getvm(vlist, vname):
        returnme = 'nothing'
        for v in vlist:
                if v.name == vname:
                        returnme = v
                        break
        return returnme

# to monitor the clone task given to vcenter
def waittask(task):
                time.sleep(5)
                print (task.info.state)
                while task.info.state == pyVmomi.vim.TaskInfo.State.running:
                        #print('sleeping')
                        time.sleep(5)
                if task.info.state == pyVmomi.vim.TaskInfo.State.success:
                        return 0
                else:
                        return 1
# returns a nice device which is part of the vm object
def getVmNic (vm):
        returnme = 'nothing'
        for device in vm.config.hardware.device:
                        if isinstance(device, pyVmomi.vim.vm.device.VirtualVmxnet3):
                                returnme = device
        return returnme


# to attach nic to proper port profile
def createNicSpec(vm, choice_vlan, master_conf_handle):
        nic = getVmNic(vm)

        if master_conf_handle.get('vcenter', 'using_dvs').lower() == 'true':
            dvs_uuid = master_conf_handle.get('vcenter', 'dvs_uuid')

            #most of this is because of vss to dvs, including backing and newnic, connectinfo


            nicspec = pyVmomi.vim.vm.device.VirtualDeviceSpec()
            dvsport = pyVmomi.vim.DistributedVirtualSwitchPortConnection()
            #fileoperation = pyVmomi.vim.VirtualDeviceConfigSpecFileOperation('replace')
            backing = pyVmomi.vim.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            #newnic = pyVmomi.vim.vm.device.VirtualEthernetCard()
            connectinfo = pyVmomi.vim.VirtualDeviceConnectInfo()
            connectinfo.startConnected = True
            connectinfo.connected = True
            connectinfo.allowGuestControl = True
            #newnic.connectable = connectinfo
            #newnic.backing = backing
            #newnic.addressType = 'Assigned'

            nicspec.operation = pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.edit
            #nicspec.fileOperation = fileoperation
            #nicspec.backing = backing
            nic.backing = backing


            dvsport.switchUuid = dvs_uuid
            dvsport.portgroupKey = choice_vlan.key
            nic.backing.port = dvsport
            #newnic.backing.port = dvsport

            nic.connectable = connectinfo


            nicspec.device = nic
            #nicspec.device = newnic
            return nicspec
        elif using_dvs is False:
                nicspec = pyVmomi.vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.edit
                nicspec.device = nic
                nicspec.device.backing.network = choice_vlan
                nicspec.device.backing.deviceName = choice_vlan.name

                return nicspec
        else:
                return 'nothing'


def create_image_dictionary(master_conf_handle):
	d = {}
	for image in master_conf_handle.options('images'):
		d[image] = master_conf_handle.get('images', image)
	return d

def create_dns_list(master_conf_handle):
    dns = []
    for entry in master_conf_handle.options('dnsservers'):
        dns.append(master_conf_handle.get('dnsservers', entry))
    return dns

def createLinuxIdentity(fqdn, master_conf_handle):

        split_list = fqdn.split('.')
        shortname = split_list.pop(0)
        domainstring = ".".join(split_list)

        identity = pyVmomi.vim.vm.customization.LinuxPrep()
        identity.domain = domainstring
        identity.hostName = pyVmomi.vim.vm.customization.FixedName()
        identity.hostName.name = shortname
        identity.timeZone = master_conf_handle.get('guest_options', 'linux_timezone')
        identity.hwClockUTC = False

        return identity

# windows time zone needs to be an integer
def createWindowsIdentity(fqdn, master_conf_handle):
        split_list = fqdn.split('.')
        shortname = split_list.pop(0)
        domainstring = ".".join(split_list)

        identity = pyVmomi.vim.CustomizationSysprep()
        guiunattended = pyVmomi.vim.CustomizationGuiUnattended()
        guiunattended.autoLogon = True
        guiunattended.autoLogonCount = 1
        cust_pass = pyVmomi.vim.CustomizationPassword()
        cust_pass.plainText = True
        cust_pass.value = master_conf_handle.get('guest_options', 'windows_admin_password')
        guiunattended.timeZone = int(master_conf_handle.get('guest_options', 'windows_timezone'))
        guiunattended.password = cust_pass
        identity.guiUnattended = guiunattended
        ident = pyVmomi.vim.CustomizationIdentification()
        ident.domainAdmin = master_conf_handle.get('guest_options', 'domain_join_account')
        ident.joinDomain = master_conf_handle.get('guest_options', 'ad_domain')
        domain_pass =  pyVmomi.vim.CustomizationPassword()
        domain_pass.plainText = True
        domain_pass.value = master_conf_handle.get('guest_options', 'domain_join_password')
        ident.domainAdminPassword = domain_pass
        identity.identification = ident
        userdata = pyVmomi.vim.CustomizationUserData()
        userdata.computerName =  pyVmomi.vim.vm.customization.FixedName()
        userdata.computerName.name = shortname
        userdata.fullName = master_conf_handle.get('guest_options', 'windows_fullname')
        userdata.orgName = master_conf_handle.get('guest_options', 'windows_orgname')
        identity.userData = userdata

        return identity


def createWindowsSysprepOptions():
        coptions_win = pyVmomi.vim.CustomizationWinOptions()
        coptions_win.changeSID = True
        coptions_sysprepreboot = pyVmomi.vim.CustomizationSysprepRebootOption('reboot')
        coptions_win.reboot = coptions_sysprepreboot
        return coptions_win



def get_ip_configuration(args, master_conf_handle):
    ipmode = master_conf_handle.get('config_file_options', 'ip_config_mode')
    ip_settings = collections.namedtuple("ip_settings", "ip, subnetmask, gateway, shortname")
    ip_settings.shortname = fqdn.split('.')[0]
    if ipmode == 'infoblox':
        ip_settings.ip = socket.gethostbyname(args.fqdn)
        url = master_conf_handle.get('infoblox', 'infoblox_url')
        apiuser = master_conf_handle.get('infoblox', 'apiuser')
        apipassword = master_conf_handle.get('infoblox', 'apipassword')
        response = requests.get(url + 'ipv4address?ip_address=' + ip_settings.ip, verify=False, auth=(apiuser, apipassword))
        response_text = response.text
        infoblox_record = json.loads(response_text.encode('ascii'))
        host_network = infoblox_record[0]['network']
        network_root, network_cidr = host_network.encode('ascii').split('/')
        ip_settings.subnetmask = cidrmap(network_cidr)        
        part1, part2, part3, part4 = network_root.split('.')
        new_part4 = str(int(part4) + 1)
        ip_settings.gateway = part1 + '.' + part2 + '.' + part3 + '.' + new_part4
    elif ipmode == 'manual':
        ip_settings.ip = args.ip
        ip_settings.subnetmask = args.subnetmask
        ip_settings.gateway = args.gateway
    else:
    	print('ipmode set incorrectly')
    	exit(1)
    return ip_settings








parser = argparse.ArgumentParser()
parser.add_argument("-e", "--vcenter", action="store", dest="vcenter", help="define vcenter")
parser.add_argument("-f", "--fqdn", action="store", dest="fqdn", help="define fqdn")
parser.add_argument("-c", "--cluster", action="store", dest="desired_cluster", help="define cluster full name with quotes")
parser.add_argument("-o", "--image", action="store",  dest="image", help="define image name")
parser.add_argument("-n", "--numcpu", action="store",  dest="numCPU", help="define number of cpu")
parser.add_argument("-m", "--memgb", action="store",  dest="memGB", help="define memory in MB")
parser.add_argument("-l", "--vlan", action="store", dest="vlan_number", help="define VLAN number")
parser.add_argument("-i", "--ip", action="store", dest="ip", help="define ip in manual mode only")
parser.add_argument("-s", "--subnetmask", action="store", dest="subnetmask", help="define subnet mask in manual mode only")
parser.add_argument("-g", "--gateway", action="store", dest="gateway", help="define ip in manual mode only")
parser.add_argument("-z", '--config', action='store', dest='master_config', default='vmdeploy.conf', help='specify location of the master config file, default is vmdeploy.conf in the same directory')
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



#always need these items
vcenter = args.vcenter
fqdn = args.fqdn
desired_cluster = args.desired_cluster
vlan_number = int(args.vlan_number)
numCPU = int(args.numCPU)
memGB = int(args.memGB)
image = args.image
images = create_image_dictionary(master_conf)
image_template = images[image]
memMB = int(memGB) * 1024
split_fqdn = fqdn.split('.')
shortfqdn = split_fqdn.pop(0)
fqdndomainstring = ".".join(split_fqdn)





#connect to vcenter

try:
    si = pyVim.connect.SmartConnect(host=vcenter, user=master_conf.get('vcenter', 'username'), pwd=master_conf.get('vcenter', 'password'), port=443)
except IOError, e:
	print('could not connect to vcenter')
	exit(1)

atexit.register(pyVim.connect.Disconnect, si)

# get datacenter object, if there were two would need to specify
content = si.RetrieveContent()
datacenter = content.rootFolder.childEntity[0]
vmfolder = datacenter.vmFolder



#Get Clusters

hostfolder = datacenter.hostFolder
clusters = {}
for x in hostfolder.childEntity:
        if x.name:
                clusters[x.name] = x


hosts = clusters[desired_cluster].host



# Find host with lowest memory usage

lowest_mem_usage = {}

for h in hosts:
        if h.runtime.inMaintenanceMode == True:
                continue
        this_memory = h.summary.quickStats.overallMemoryUsage
        if this_memory not in lowest_mem_usage.keys():
                lowest_mem_usage[this_memory] = h

choice_hkey = min(lowest_mem_usage.keys())
choice_host = lowest_mem_usage[choice_hkey]


#Get datastores
datastores = clusters[desired_cluster].datastore

# Find datastore with most free space


highest_free_space = {}

#i want
mirror_match = re.compile("(^M-|.*N3.*)")
for d in datastores:
        if mirror_match.match(d.name):
                        continue
        this_freespace = d.summary.freeSpace
        if d.summary.multipleHostAccess == True:
                if this_freespace not in highest_free_space.keys():
                        highest_free_space[this_freespace] = d

choice_dkey = max(highest_free_space.keys())
choice_datastore = highest_free_space[choice_dkey]


#Get network list

networks = clusters[desired_cluster].network


#Create network list
network_dict = {}
for n in networks:
        network_dict[n.name] = n


vlan_string = str('VLAN' + str(vlan_number).strip() + '(-|$)')
re_vlan = re.compile(vlan_string, re.IGNORECASE)

#Choose network to attach to based on VLAN regex
choice_vlan = None
choice_vlan_key = filter(re_vlan.search, network_dict.keys())[0]
choice_vlan = network_dict[choice_vlan_key]


#get ip settings based on ipmode in master config file
ip_settings = get_ip_configuration(args, master_conf)

#create adaptermap based on ip settings
adaptermap = pyVmomi.vim.vm.customization.AdapterMapping()
adaptermap.adapter = pyVmomi.vim.vm.customization.IPSettings()
adaptermap.adapter.ip = pyVmomi.vim.vm.customization.FixedIp()
adaptermap.adapter.ip.ipAddress = ip_settings.ip
adaptermap.adapter.subnetMask = ip_settings.subnetmask
adaptermap.adapter.gateway = ip_settings.gateway

#create global ip settings
globalip = pyVmomi.vim.vm.customization.GlobalIPSettings()
globalip.dnsServerList = create_dns_list(master_conf)



match_linux = re.compile('linux', re.IGNORECASE)
match_windows = re.compile('windows', re.IGNORECASE)
if match_linux.search(image) is not None:
	globalip.dnsSuffixList = [fqdndomainstring]
	identity = createLinuxIdentity(fqdn, master_conf)
elif match_windows.search(image) is not None and match_linux.search(image) is None:
	identify = createWindowsIdentity(fqdn, master_conf)
else:
	print('error - imagename does not match windows or linux - exiting')
	exit(1)




#create location spec
location_spec = pyVmomi.vim.vm.RelocateSpec()
location_spec.datastore = choice_datastore
location_spec.pool = clusters[desired_cluster].resourcePool


#get template vm
view = content.viewManager.CreateContainerView(content.rootFolder,[pyVmomi.vim.VirtualMachine],True)
vmlist = view.view

# configure resources
templateVM = getvm(vmlist, image_template)
vmconf = pyVmomi.vim.vm.ConfigSpec()
vmconf.numCPUs = numCPU
vmconf.memoryMB = memMB

customspec = pyVmomi.vim.vm.customization.Specification()
customspec.nicSettingMap = [adaptermap]
customspec.globalIPSettings = globalip
customspec.identity = identity

if match_windows.search(image) is True:
    cust_options = createWindowsSysprepOptions()
    customspec.options = cust_options

#for the actual clone
clonespec = pyVmomi.vim.vm.CloneSpec()
clonespec.location = location_spec
clonespec.config = vmconf
clonespec.customization = customspec
clonespec.powerOn = False
clonespec.template = False

#need to remove this is cruft
clonespec2 = pyVmomi.vim.vm.CloneSpec()
clonespec2.location = location_spec

task = templateVM.CloneVM_Task(folder=vmfolder, name=fqdn, spec=clonespec)
result = waittask(task)
if result == 1:
    print('error 1 at clone task -- exiting')
    exit(1)

# the vm is cloned at this point, now change the port profile and power on
view = content.viewManager.CreateContainerView(content.rootFolder,[pyVmomi.vim.VirtualMachine],True)
vmlist = view.view

fqdn_vm = getvm(vmlist, fqdn)
devices = []
ns = createNicSpec(fqdn_vm, choice_vlan, master_conf)
devices.append(ns)
vmconf_postclone = pyVmomi.vim.vm.ConfigSpec()
vmconf_postclone.deviceChange = devices
task2 = fqdn_vm.ReconfigVM_Task(vmconf_postclone)
result2 = waittask(task2)
fqdn_vm.PowerOnVM_Task()

print("{0} cloned successfully".format(fqdn))
exit()

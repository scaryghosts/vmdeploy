vmdeploy
========

VMware guest deployment script using VMware Python Api

This script was designed to quickly deploy templates with as little work as possible. 

All variables should be set in the master config file (default=vmdeploy.conf but an alternate location can be specified.). This first version was designed to work with a few particulars that I plan on ironing out later for a more general version. Right now it expects that you are using Infoblox for DNS and and that you identify your port profiles with VLAN#### in the name.

To use, simply fill out the information in the master config file, then use deploy_vm -g to generate a sample deployment configuration file. Fill out with the deployment file with any number of guests and kick the script off and let it run. I recommend having another mechanism (shell scripts, salt/puppet/chef, etc) to finish off the build after deployment.

Usage:

Generate a sample config file:

deploy_vm -g

Edit that config file with the corrent options then run

deploy_vm -f example.conf

In infoblox mode, the config file might look like this:
--
[Guest1]
hostname: weasel-web-01.fq.dn
vlan: 100
vcenter: vcenter.fq.dn
image: linux-default
numcpu: 2
mem: 4
cluster: Development

[Guest1]
hostname: weasel-web-02.fq.dn
vlan: 100
vcenter: vcenter.fq.dn
image: linux-default
numcpu: 2
mem: 4
cluster: Development
--


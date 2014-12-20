vmdeploy
========

VMware guest deployment script using VMware Python Api

This script was designed to quickly deploy templates with as little work as possible. 

All variables should be set in the master config file (default=vmdeploy.conf but an alternate location can be specified.). This first version was designed to work with a few particulars that I plan on ironing out later for a more general version. Right now it expects that you are using Infoblox for DNS and and that you identify your port profiles with VLAN#### in the name.

To use, simply fill out the information in the master config file, then use deploy_vm -g to generate a sample deployment configuration file. Fill out with the deployment file with any number of guests and kick the script off and let it run. I recommend having another mechanism (shell scripts, salt/puppet/chef, etc) to finish off the build after deployment.

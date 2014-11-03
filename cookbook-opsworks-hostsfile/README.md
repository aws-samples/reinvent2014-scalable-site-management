# opsworks-hostsfile cookbook
Installs a script in cron for root user that will re-write the /etc/hosts file
on a regular basis with all hosts in all OpsWorks stacks in the account.  This
is intended to be used on a bastion/jump host.  

It will also require an IAM Role attached to the instance with the following permission:

    {
      "Statement": [
        {
          "Action": [
            "opsworks:DescribeInstances",
            "opsworks:DescribeLayers",
            "opsworks:DescribeStacks"
          ],
          "Resource": [
            "arn:aws:opsworks:*:*"
          ],
          "Effect": "Allow"
        }
      ]
    }

The format of the entries in /etc/hosts will be `<stackname>-<hostname>`.  This will
allow you to SSH from a bastion/jump host to a machine in another stack without needing
to look up the Internal IP or use a DNS server.

If a configure event is run on the bastion/jump host - OpsWorks will re-write the `/etc/hosts`
file and remove the custom entries added.  Within a few minutes, the script will re-run and add them
back.  Increase the cron frequency (`node['opsworks_hostsfile']['cron_frequency']`) if desired.

# Requirements
Cookbook assumes it will be run on an Amazon Linux machine.  Relies on `python-botocore`
package being available in installed yum repositories.

It has been tested on Amazon Linux 2014.03/09 running Python 2.6+.  

# Usage
Include the default recipe on the OpsWorks `setup` or `configure` lifecycle event

# Attributes

* `node['opsworks_hostsfile']['cron_frequency']`: Specify the cron frequency - default is `*/15`
* `node['opsworks_hostsfile']['script_location']`: Specify where to store the script - default is `/root/hosts.py`
* `node['opsworks_hostsfile']['user']`: Specify which user to install the script and cron for - default is `root`
* `node['opsworks_hostsfile']['group']`: Specify which group for the ownership of the script - default is `root`

# Recipes

## default
Installs python-botocore package and will configure the script to run in Cron

# Author

Author: Amazon.com, Inc

OpsWorks lifeceycle events can be used to configure Nagios with the current list of
instances within the stack.  When a machine is added or removed from the stack,
the Nagios server will receive a *configure* lifecycle event and the code below can
be used to rewrite the hosts.cfg and hostgroups.cfg files to reflect the change.


This code is a snippet of a Chef recipe that will find all instances in the OpsWorks stack and
write out the `/etc/nagios/conf.d/hostgroups.cfg` and `/etc/nagios/conf.d/hosts.cfg` templates.

The current `hosts.cfg.erb` file will configure Nagios to use the hostname as the address of the instance.  

Alternatively, the *private_ip* is available to the template, so that could be used instead
if you do not wish to rely on the `/etc/hosts` file (which is also updated by OpsWorks)

All OpsWorks instances will be assigned to a hostgroup that reflects the Layer(s) the
instance belongs to.  Instances will also be assigned to a hostgroup for the
availability zone (us-east-1a, us-west-2b, etc) that it is running in.

# Using Chef Search - recipe-search-configure.rb
This version uses Chef Search to list all *online* instances.  If you need to include
stopped instances in your Nagios server, you will need to look at the alternative method below.

Note: If you include instances that are not in an *online* state, the checks against
those machines will likely fail.

# Using OpsWorks Layers Attributes - recipe-configure.rb
This version uses the node attributes provided by OpsWorks to describe all layers
and their associated instances.  If an instance appears in more than one layer,
it will appear in this list twice (so need to merge the hostgroups).

This method also provides you with instances that are in any state.  So if you
wish to include 'Stopped' instances - simple modify the status check `if instance_info['status'] == 'online'`



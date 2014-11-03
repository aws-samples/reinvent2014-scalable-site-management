#
# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#  http://aws.amazon.com/apache2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.
#

all_hosts = {}
all_hostgroups = {}

# Gets all (online only) instances in OpsWorks stack
all_instances = search(:node, 'role:*')
all_instances.each do |instance|
  node_hostgroups = {}
  # add a hostgroup for each layer the instance is in
  instance['opsworks']['layers'].each do |layer_id, layer_info|
    node_hostgroups[layer_id] = layer_info['name']
  end
  # add a hostgroup for each availability zone
  node_hostgroups[instance['availability_zone']] = instance['availability_zone']
  all_hosts[instance['hostname']] = {
      :hostgroups => node_hostgroups,
      :private_ip => instance['private_ip']
  }
  all_hostgroups = all_hostgroups.merge(node_hostgroups)
end

template '/etc/nagios/conf.d/hostgroups.cfg' do
  source 'hostgroups.cfg.erb'
  owner 'nagios'
  group 'nagios'
  mode '0644'
  variables(
    :hostgroups => all_hostgroups
  )
  notifies :reload, 'service[nagios]'
  backup 0
end

template "/etc/nagios/conf.d/hosts.cfg" do
  source 'hosts.cfg.erb'
  owner 'nagios'
  group 'nagios'
  mode '0644'
  variables(
    :hosts => all_hosts
  )
  notifies :reload, 'service[nagios]'
  backup 0
end
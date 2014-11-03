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

node['opsworks']['layers'].each do |layer_id, layer_info|
  all_hostgroups[layer_id] = layer_info['name']
  layer_info['instances'].each do |instance_name, instance_info|
    if instance_info['status'] == 'online'
      node_hostgroups[instance_info['availability_zone']] = instance_info['availability_zone']
      node_hostgroups[layer_id] = layer_info['name']

      all_hostgroups = all_hostgroups.merge(node_hostgroups)
      if all_hosts.has_key?(instance_name)
        # host is in more than one layer - so merge them
        all_hosts[instance_name][:hostgroups] = all_hosts[instance_name][:hostgroups].merge(node_hostgroups)
      else
        all_hosts[instance_name] = {
          :hostgroups => node_hostgroups,
          :private_ip => instance_info['private_ip']
        }
      end
    end
  end
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
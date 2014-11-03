#!/usr/bin/python

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

import botocore.session


session = botocore.session.get_session()
service = session.get_service('opsworks')
endpoint = service.get_endpoint('us-east-1')


def _make_api_call(api_operation, **kwargs):
  """
  Make an API call using botocore for the given api operation.
  :param api_operation: Operation name to perform
  :param kwargs: Any additional arguments to be passed to the service call
  :return: If an OK response returned, returns the data from the call.  Will exit(1) otherwise
  """
  operation = service.get_operation(api_operation)
  response, response_data = operation.call(endpoint, **kwargs)
  if response.ok:
    return response_data

  click.echo("Error occurred calling {0} - {1} - Status {2} Message {3}".format(response.url,
                                                                                api_operation,
                                                                                response.status_code,
                                                                                response.text))
  sys.exit(1)


if __name__ == '__main__':
  hosts_delimeter = "### All Hosts ###"
  custom_hosts = [hosts_delimeter]

  stack_map = {}
  stacks = _make_api_call('DescribeStacks')['Stacks']
  for each in stacks:
    stack_id = each['StackId']
    stack_name = each['Name']
    stack_map[stack_name] = stack_id

  for stack_name,stack_id in stack_map.iteritems():
    instances = _make_api_call('DescribeInstances', stack_id=stack_id)['Instances']
    for each in instances:
      host_name = each['Hostname']
      if 'PrivateIp' in each:
        custom_hosts.append("{0} {1}-{2}".format(each['PrivateIp'], stack_name, host_name))

  opsworks_hosts = []
  with open('/etc/hosts', 'r') as host_file:
    for each in host_file:
      if hosts_delimeter in each:
        break
      opsworks_hosts.append(each.strip())

  with open('/etc/hosts', 'w') as host_file:
    for each in opsworks_hosts:
      host_file.write(each + "\n")
    for each in custom_hosts:
      host_file.write(each + "\n")



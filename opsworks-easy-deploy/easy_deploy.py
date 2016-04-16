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

import click
import os
import sys
import time
import json
import arrow
import botocore.session


class Operation(object):
    def __init__(self, context):
        self.session = botocore.session.get_session()
        self.service_endpoints = {
            'opsworks': context.obj['OPSWORKS_REGION'],
            'elb': context.obj['ELB_REGION']
        }
        self.stack_name = None
        self.layer_name = None
        self.deploy_timeout = None
        self._stack_id = None
        self._layer_id = None

        self.pre_deployment_hooks = []
        self.post_deployment_hooks = []

    def init(self, stack_name, timeout=None, layer_name=None):
        self.stack_name = stack_name
        self.layer_name = layer_name
        self.deploy_timeout = timeout

    @property
    def stack_id(self):
        if self._stack_id is None:
            stacks = self._make_api_call('opsworks', 'describe_stacks')['Stacks']
            stack_names = [stack['Name'] for stack in stacks]
            for stack in stacks:
                stack_id = stack['StackId']
                if self.stack_name.lower() == stack['Name'].lower():
                    self._stack_id = stack_id
                    break
            else:
                log("Stack {0} not found.  Stacks found: {1}.  Aborting".format(self.stack_name, stack_names))
                sys.exit(1)
        return self._stack_id

    @property
    def layer_id(self):
        if self._layer_id is None:
            layers = self._make_api_call('opsworks', 'describe_layers', StackId=self.stack_id)['Layers']
            layer_names = [each_layer['Name'] for each_layer in layers]
            for each_layer in layers:
                layer_id = each_layer['LayerId']
                if self.layer_name.lower() == each_layer['Name'].lower():
                    self._layer_id = layer_id
                    break
            else:
                log("No Layer found with name {0} in stack {1}.  Layers found: {2}.  Aborting".format(self.layer_name, self.stack_name, layer_names))
                sys.exit(1)
        return self._layer_id

    def layer_at_once(self, comment, exclude_hosts=None):
        all_instances = self._make_api_call('opsworks', 'describe_instances', LayerId=self.layer_id)

        if exclude_hosts is None:
            exclude_hosts = []

        deployment_instance_ids = []
        for each in all_instances['Instances']:
            if each['Status'] == 'online' and each['Hostname'] not in exclude_hosts:
                deployment_instance_ids.append(each['InstanceId'])
        self._deploy_to(InstanceIds=deployment_instance_ids, Name="{0} instances".format(self.layer_name), Comment=comment)

    def layer_rolling(self, comment):
        load_balancer_name = self._get_opsworks_elb_name()

        if load_balancer_name is not None:
            self.pre_deployment_hooks.append(self._remove_instance_from_elb)
            self.post_deployment_hooks.append(self._add_instance_to_elb)

        all_instances = self._make_api_call('opsworks', 'describe_instances', LayerId=self.layer_id)
        for each in all_instances['Instances']:
            if each['Status'] != 'online':
                continue

            hostname = each['Hostname']
            instance_id = each['InstanceId']
            ec2_instance_id = each['Ec2InstanceId']

            self._deploy_to(InstanceIds=[instance_id], Name=hostname, Comment=comment, LoadBalancerName=load_balancer_name, Ec2InstanceId=ec2_instance_id)

    def instances_at_once(self, host_names, comment):
        all_instances = self._make_api_call('opsworks', 'describe_instances', StackId=self.stack_id)

        deployment_instance_ids = []
        for each in all_instances['Instances']:
            if each['Status'] == 'online' and each['Hostname'] in host_names:
                deployment_instance_ids.append(each['InstanceId'])

        self._deploy_to(InstanceIds=deployment_instance_ids, Name=", ".join(host_names), Comment=comment)

    def post_elb_registration(self, hostname, load_balancer_name):
        describe_result = self._make_api_call('elb', 'describe_load_balancers', LoadBalancerNames=[load_balancer_name])
        healthy_threshold = describe_result['LoadBalancerDescriptions'][0]['HealthCheck']['HealthyThreshold']
        interval = describe_result['LoadBalancerDescriptions'][0]['HealthCheck']['Interval']

        instance_healthy_wait = ((healthy_threshold + 2) * interval)
        log("Added {0} to ELB {1}.  Sleeping for {2} seconds for it to be online".format(hostname, load_balancer_name, instance_healthy_wait))
        time.sleep(instance_healthy_wait)

    def _get_opsworks_elb_name(self):
        """
        Get an OpsWorks ELB Name of the layer id in the stack if is associated with the layer
        :return: Elastic Load Balancer name if associated with the layer, otherwise None
        """
        elbs = self._make_api_call('opsworks', 'describe_elastic_load_balancers', LayerIds=[self.layer_id])
        if len(elbs['ElasticLoadBalancers']) > 0:
            return elbs['ElasticLoadBalancers'][0]['ElasticLoadBalancerName']
        else:
            return None

    def _deploy_to(self, **kwargs):
        for pre_deploy in self.pre_deployment_hooks:
            pre_deploy(**kwargs)

        arguments = self._create_deployment_arguments(kwargs['InstanceIds'], kwargs['Comment'])
        deployment = self._make_api_call('opsworks', 'create_deployment', **arguments)

        deployment_id = deployment['DeploymentId']
        log("Deployment {0} to {1} requested - command: {2}".format(deployment_id, kwargs['Name'], self.command))

        self._poll_deployment_complete(deployment_id)

        for post_deploy in self.post_deployment_hooks:
            post_deploy(**kwargs)

    def _create_deployment_arguments(self, instance_ids, comment):
        raise NotImplemented('Method must be implemented in child class')

    def _poll_deployment_complete(self, deployment_id):
        start_time = time.time()
        while True:
            deployment_status = self._make_api_call('opsworks', 'describe_deployments', DeploymentIds=[deployment_id])

            for each in deployment_status['Deployments']:
                if each['DeploymentId'] == deployment_id:
                    if each['Status'] == 'successful':
                        log("Deployment {0} completed successfully at {1} after {2} seconds".format(deployment_id, each['CompletedAt'], self._get_deployment_duration(each).seconds))
                        return

                    if each['Status'] == 'failed':
                        log("Deployment {0} failed in {1} seconds".format(deployment_id, self._get_deployment_duration(each).seconds))
                        sys.exit(1)

                    log("Deployment {0} is currently {1}".format(deployment_id, each['Status']))
                    continue

            elapsed_time = time.time() - start_time
            if self.deploy_timeout is not None and elapsed_time > self.deploy_timeout:
                log("Deployment {0} has exceeded the timeout of {1} seconds.  Aborting".format(deployment_id, self.deploy_timeout))
                sys.exit(1)
            time.sleep(20)

    @staticmethod
    def _get_deployment_duration(deployment_status):
        """
        Given a deployment status, calculate and return the duration.
        For some reason the "Duration" parameter is not always populated
        from the OpsWorks API, so this works around that.
        :param deployment_status:
        :return:
        """
        started_at = arrow.get(deployment_status['CreatedAt'])
        completed_at = arrow.get(deployment_status['CompletedAt'])
        return completed_at - started_at

    def _add_instance_to_elb(self, **kwargs):
        self._make_api_call('elb', 'register_instances_with_load_balancer',
                            LoadBalancerName=kwargs['LoadBalancerName'],
                            Instances=[{'InstanceId': kwargs['Ec2InstanceId']}])

        self.post_elb_registration(kwargs['Name'], kwargs['LoadBalancerName'])

        if not self._is_instance_healthy(kwargs['LoadBalancerName'], kwargs['Ec2InstanceId']):
            log("Instance {0} did not come online after deploy. Aborting remaining deployment".format(kwargs['Name']))
            sys.exit(1)

    def _remove_instance_from_elb(self, **kwargs):
        deregister_response = self._make_api_call('elb', 'deregister_instances_from_load_balancer',
                                                  LoadBalancerName=kwargs['LoadBalancerName'],
                                                  Instances=[{'InstanceId': kwargs['Ec2InstanceId']}])
        log("Removed {0} from ELB {1}. There are still {2} instance(s) online".format(kwargs['Name'], kwargs['LoadBalancerName'], len(deregister_response['Instances'])))

        self._wait_for_elb(kwargs['LoadBalancerName'])

    def _wait_for_elb(self, load_balancer_name):
        elb_attributes = self._make_api_call('elb', 'describe_load_balancer_attributes',
                                             LoadBalancerName=load_balancer_name)
        if 'ConnectionDraining' in elb_attributes['LoadBalancerAttributes']:
            connection_draining = elb_attributes['LoadBalancerAttributes']['ConnectionDraining']
            if connection_draining['Enabled']:
                log("Connection Draining enabled - sleeping for {0} seconds".format(connection_draining['Timeout']))
                time.sleep(connection_draining['Timeout'])
                return

        log("Connection Draining not enabled - sleeping for 20 seconds")
        time.sleep(20)

    def _is_instance_healthy(self, load_balancer_name, instance_id):
        instance_health = self._make_api_call('elb', 'describe_instance_health',
                                              LoadBalancerName=load_balancer_name,
                                              Instances=[{'InstanceId': instance_id}])

        for each in instance_health['InstanceStates']:
            if each['InstanceId'] == instance_id:
                status_detail = ""
                if each['State'] != 'InService':
                    status_detail = " ({0} - {1})".format(each['ReasonCode'], each['Description'])
                log("Current instance state is {0}{1}".format(each['State'], status_detail))
                return each['State'] == 'InService'

        return False

    def _make_api_call(self, service_name, api_operation, **kwargs):
        """
        Make an API call using botocore for the given service and api operation.
        :param service_name: AWS Service name (all lowercase)
        :param api_operation: Operation name to perform
        :param kwargs: Any additional arguments to be passed to the service call
        :return: Returns the data from the call.
        """
        service_endpoint = self.service_endpoints[service_name]
        service = self.session.create_client(service_name, service_endpoint)
        return getattr(service, api_operation)(**kwargs)


class Update(Operation):
    """
    Used to issue an Update Dependencies operation within OpsWorks
    """
    def __init__(self, context):
        self.allow_reboot = False
        self.amazon_linux_release = None
        self.reboot_delay = 300

        super(Update, self).__init__(context)
        self.post_deployment_hooks.append(self.wait_for_reboot)

    @property
    def command(self):
        return 'update_dependencies'

    def wait_for_reboot(self, **kwargs):
        """
        Additional buffer when performing updates
        """
        if self.allow_reboot:
            log("Sleeping {0} seconds to allow {1} to reboot (if required)".format(self.reboot_delay, kwargs['Name']))
            time.sleep(self.reboot_delay)

    def _create_deployment_arguments(self, instance_ids, comment):
        custom_json = {
            'dependencies': {
                'allow_reboot': self.allow_reboot
            }
        }
        if self.amazon_linux_release is not None:
            custom_json['dependencies']['os_release_version'] = self.amazon_linux_release

        return {
            'StackId': self.stack_id,
            'InstanceIds': instance_ids,
            'Command': {'Name': self.command},
            'Comment': comment,
            'CustomJson': json.dumps(custom_json)
        }


class Deploy(Operation):
    """
    Used to issue a Deployment operation within OpsWorks
    """
    def __init__(self, context):
        self.application_name = None
        self._application_id = None

        super(Deploy, self).__init__(context)

    @property
    def command(self):
        return 'deploy'

    @property
    def application_id(self):
        if self._application_id is None:
            applications = self._make_api_call('opsworks', 'describe_apps', StackId=self.stack_id)
            application_names = [each['Shortname'] for each in applications['Apps']]
            for each in applications['Apps']:
                if each['Shortname'] == self.application_name:
                    self._application_id = each['AppId']
                    break

            if self._application_id is None:
                log("Application {0} not found in stack {1}.  Applications found: {2}.  Aborting".format(self.application_name, self.stack_name, application_names))
                sys.exit(1)

        return self._application_id

    def _create_deployment_arguments(self, instance_ids, comment):
        return {
            'StackId': self.stack_id,
            'AppId': self.application_id,
            'InstanceIds': instance_ids,
            'Command': {'Name': self.command},
            'Comment': comment
        }


def log(message):
    click.echo("[{0}] {1}".format(arrow.utcnow().format('YYYY-MM-DD HH:mm:ss ZZ'), message))


@click.group(chain=True)
@click.option('--profile', type=click.STRING, help='Profile used to lookup credentials.')
@click.option('--opsworks-region', type=click.STRING, default='us-east-1', help="OpsWorks region endpoint")
@click.option('--elb-region', type=click.STRING, default='us-east-1', help="Elastic Load Balancer region endpoint")
@click.pass_context
def cli(ctx, profile, opsworks_region, elb_region):
    if profile is not None:
        os.environ['BOTO_DEFAULT_PROFILE'] = profile
    ctx.obj['OPSWORKS_REGION'] = opsworks_region
    ctx.obj['ELB_REGION'] = elb_region


@cli.command(help='Installs regular operating system updates and package updates')
@click.option('--allow-reboot/--no-all-reboot', default=False, help='Allow OpsWorks to reboot instance if kernel was updated')
@click.option('--amazon-linux-release', type=click.STRING, help='Set the Amazon Linux version, only use it when OpsWorks has support for it')
@click.pass_context
def update(ctx, allow_reboot, amazon_linux_release):
    operation = Update(ctx)
    operation.allow_reboot = allow_reboot
    operation.amazon_linux_release = amazon_linux_release
    ctx.obj['OPERATION'] = operation


@cli.command(help='Deploys an application')
@click.option('--application', type=click.STRING, required=True, help='OpsWorks Application')
@click.pass_context
def deploy(ctx, application):
    operation = Deploy(ctx)
    operation.application_name = application
    ctx.obj['OPERATION'] = operation


@cli.command(help='Execute operation on all hosts in the layer at once')
@click.option('--stack-name', type=click.STRING, required=True, help='OpsWorks Stack name')
@click.option('--layer-name', type=click.STRING, required=True, help='Layer to deploy application to')
@click.option('--exclude-hosts', '-x', default=None, help='Host names to exclude from deployment (comma separated list)')
@click.option('--comment', help='Deployment message')
@click.option('--timeout', default=None, help='Deployment timeout')
@click.pass_context
def all(ctx, stack_name, layer_name, exclude_hosts, comment, timeout):
    operation = ctx.obj['OPERATION']
    operation.init(stack_name=stack_name, layer_name=layer_name, timeout=timeout)
    if exclude_hosts is not None:
        exclude_hosts = exclude_hosts.split(',')
    operation.layer_at_once(comment=comment, exclude_hosts=exclude_hosts)


@cli.command(help='Rolling execution of operation to all hosts in the layer')
@click.option('--stack-name', type=click.STRING, required=True, help='OpsWorks Stack name')
@click.option('--layer-name', type=click.STRING, required=True, help='Layer to deploy application to')
@click.option('--comment', help='Deployment message')
@click.option('--timeout', default=None, help='Deployment timeout')
@click.pass_context
def rolling(ctx, stack_name, layer_name, comment, timeout):
    operation = ctx.obj['OPERATION']
    operation.init(stack_name=stack_name, layer_name=layer_name, timeout=timeout)
    operation.layer_rolling(comment=comment)


@cli.command(help='Execute operation on specific hosts')
@click.option('--stack-name', type=click.STRING, required=True, help='OpsWorks Stack name')
@click.option('--hosts', '-H', type=click.STRING, required=True, help='Host names to deploy application to (comma separated list)')
@click.option('--comment', help='Deployment message')
@click.option('--timeout', default=None, help='Deployment timeout')
@click.pass_context
def instances(ctx, stack_name, hosts, comment, timeout):
    operation = ctx.obj['OPERATION']
    operation.init(stack_name=stack_name, timeout=timeout)
    hosts = hosts.split(',')
    operation.instances_at_once(comment=comment, host_names=hosts)


if __name__ == '__main__':
    cli(obj={})

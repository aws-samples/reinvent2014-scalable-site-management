Python opsworks script which simplifies doing application deployments and applying OS updates with AWS OpsWorks.

While some of this functionality could be achieved by simply using the AWS Management Console,
the real purpose of this script is to automate deployments to OpsWorks instances behind an ELB.

When you do a deployment, there will be a brief time when the HealthCheck will fail but the instance will
still be in the ELB and receiving traffic (which will receive errors).  If you know you are doing a deployment
it is better for the users if you just remove the instance prior to deployment, and add it back after deployment
is complete.

This script will loop through all machines in an OpsWorks Layer and issue deployment commands to each one
in turn.  If the layer is also associated with an Elastic Load Balancer, it will first deregister that instance,
wait for the ELB's ConnectionDraining Timeout setting (if enabled, otherwise 20 seconds) and then initiate the deployment.

Once the deployment is complete - it will register the instance back in the ELB.  The script will read the
ELB `HealthCheck` configuration and wait for the `HealthyThreshold * Interval` seconds for the instance to be online.

Once complete, it will move on to the next instance in the ELB and perform the same steps.

The result is a 0 downtime deployment.

## Examples

    easy_deploy.py deploy --application=myapp rolling --stack-name=teststack --layer-name=apiserver --comment="Rolling deployment to all apiservers" --timeout=300

    easy_deploy.py deploy --application=myapp instances --stack-name=teststack --hosts=host1,host2 --comment="Deploy to host1 and host2"

    easy_deploy.py --profile=dev deploy --application=myapp all --stack-name=teststack --layer-name=appserver --comment="Deploy to all servers"

    easy_deploy.py update --no-allow-reboot rolling --stack-name=teststack --layer-name=apiserver --comment="Rolling patch to all apiservers

    easy_deploy.py update --allow-reboot --amazon-linux-release=2014.09 instances --stack-name=teststack --hosts=host1,host2 --comment="Updating host1 and host2 to latest Amazon Linux"

    easy_deploy.py update --allow-reboot all --stack-name=teststack --layer-name=appserver --comment="Applying kernel patches to all servers"

## Configuration

This script shares the same configuration used by the [AWS CLI](https://github.com/aws/aws-cli).  You can either specify your credentials via:

* Environment variables
* Config file
* IAM Role

Please see the [AWS CLI getting-started page](https://github.com/aws/aws-cli#getting-started) for more information.


## Command Options

`easy_deploy.py` uses [Click](http://click.pocoo.org/3/) for the CLI.  Specifically it uses command chaining - with certain options being applied to earlier
commands in the chain. The result is that you need to specify the flag/option after the command it is for, not all at the end.

The list below identifies which options are for which commands.

* `--profile`: AWS profile to use.  Can be omitted if running on an instance with IAM Profiles.  Or can be set via the ENV variable `BOTO_DEFAULT_PROFILE`.  Or use the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` ENV variables.
* `--opsworks-region`: AWS region that OpsWorks is in (default: `us-east-1`) *Note: this is not the region your instances are in, but the region OpsWorks endpoints are in*
* `--elb-region`: AWS region your Elastic Load Balancer is in (default: `us-east-1`)

### deploy

* `--application`: Application shortname within OpsWorks

### update

* `--allow-reboot/--no-allow-reboot`: Flag to allow the instance to reboot itself after applying updates.  It will only reboot if a kernel update was applied (and only on RHEL based systems). (Default: `--no-allow-reboot`)
* `--amazon-linux-release`: Version of Amazon Linux to set the instance to.  Only works on Amazon Linux.  Do not use this before OpsWorks adds support for that version.

### instances

* `--hosts`, `-H`: Comma separated list of hostnames to run command on
* `--stack-name`: OpsWorks stack to run command on
* `--comment`: Comment to be set on the OpsWorks deployment
* `--timeout`: (in seconds) Timeout, use this to specify an upper limit to the deployment duration.  If the deploy command exceeds this, the script will exit with error 1.  *Note: if the timeout is exceeded, it will not cancel the already running deployment within OpsWorks.  However it will prevent it from executing a deployment on any further instances*

### all

* `--exclude-hosts`, `-x`: Comma separated list of hostnames to exclude from command
* `--layer-name`: OpsWorks layer shortname to run command on (all instances in this layer will get command)
* `--stack-name`: OpsWorks stack shortname to run command on
* `--timeout`: (in seconds) Timeout, use this to specify an upper limit to the deployment duration.  If the deploy command exceeds this, the script will exit with error 1.  *Note: if the timeout is exceeded, it will not cancel the already running deployment within OpsWorks*

### rolling

* `--exclude-hosts`, `-x`: Comma separated list of hostnames to exclude from command
* `--layer-name`: OpsWorks layer shortname to run command on (all instances in this layer will get command)
* `--stack-name`: OpsWorks stack shortname to run command on
* `--timeout`: (in seconds) Timeout, use this to specify an upper limit to the deployment duration.  If the deploy command exceeds this, the script will exit with error 1.  *Note: if the timeout is exceeded, it will not cancel the already running deployment within OpsWorks.  However it will prevent it from executing a deployment on any further instances*

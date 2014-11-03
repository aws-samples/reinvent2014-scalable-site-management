
With (Packer)[https://www.packer.io/] installed [packer.io]:

     packer build \
        -var 'aws_access_key=AKIAIOSFODNN7EXAMPLE' \
        -var 'aws_secret_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' \
        -var 'security_group_ids=<security_group_ids>' \
        -var 'subnet_id=<subnet_id>' \
        -var 'vpc_id=<vpc_id>' \
        -var 'instance_type=<instance_type>' \
        amazon-2014.09.json

In the command above, you will need to replace the following with values for your setup:

* `aws_access_key`: AWS Access Key with permissions to launch EC2 instances and create AMIs
* `aws_secret_key`: AWS Secret Access Key
* `security_group_ids`: Comma separated list of security group ids that will allow SSH access to the machine you are about to run this on.
* `subnet_id`: ID of the VPC subnet to launch this instance into
* `vpc_id`: ID of the VPC to run this instance in
* `instance_type`: Instance Type to use when building the AMI

There are various other values in the amazon-2014.09.json file that can be altered depending on your setup.

Refer to the documentation at [Amazon AMI Builder](https://www.packer.io/docs/builders/amazon.html).  Specifically [AMI Builder - EBS Backed](https://www.packer.io/docs/builders/amazon-ebs.html)

On it's own, this AMI only adds a single ephemeral drive mapped to the instance beyond
what OpsWorks will provide using the "Amazon Linux" option.  However, it can be extended
by adding your own shell scripts (or any other provisioning methods Packer supports) to
add other software or configuration into this base AMI while it is being built.

Add a shell script to the `scripts` list:

    "provisioners": [
      {
        "execute_command": "echo 'packer' | {{.Vars}} sudo -S -E bash '{{.Path}}'",
        "scripts": [
          "<local-path-to-script.sh>"
        ],
        "type": "shell"
      }
    ]

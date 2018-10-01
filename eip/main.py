import os
import sys
import time
import functools
import http.client
import json
import random
import subprocess
import struct
import socket
import fcntl
import logging

import boto3
from botocore.exceptions import ClientError

DEV_MODE = True if os.environ.get("DEV_MODE", "") else False

ENV = os.environ.get("ENV", "")
APP_SPEC = os.environ.get("APP_SPEC", "")
BOTO_REGION = os.environ.get("BOTO_REGION", "")

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")

ENI_TAG_KEY = "exhibitor-eni-pool"
ENI_TAG_VALUE = "{}-exhibitor-{}-eni-pool".format(ENV, APP_SPEC).replace("exhibitor--eni", "exhibitor-eni")


def ensure_written(content, path_to_file):
    """Ensure that the content is in the given `path_to_file`
    (append if not)."""
    with open(path_to_file, "r") as read_fd:
        already_written = content in read_fd.read()
    if not already_written:
        with open(path_to_file, "a") as append_fd:
            append_fd.write(content)


def get_internal_subnets(ec2, current_az):
    return ec2.describe_subnets(
        Filters=[
            {
                "Name": "availability-zone",
                "Values": [current_az]
            }
            # ,
            # {
            #     "Name": "tag:Name",
            #     "Values": ["internal-{}".format(current_az)]
            # }
        ]
    )["Subnets"]

@functools.lru_cache(1)
def get_metadata():
    conn = http.client.HTTPConnection("169.254.169.254", 80, timeout=10)
    conn.request("GET", "/latest/dynamic/instance-identity/document")
    r1 = conn.getresponse()
    return json.loads(r1.read().decode("utf-8"))

def get_free_enis(ec2, internal_subnet):
    """
    Get all free NetworkInterfaces in the internal subnet with the tag.
    """

    return ec2.describe_network_interfaces(
        Filters=[
            # {
            #     "Name": "tag:{}".format(ENI_TAG_KEY),
            #     "Values": [ENI_TAG_VALUE]
            # },
            {
                "Name": "subnet-id",
                "Values": [internal_subnet["SubnetId"]]
            },
            {
                "Name": "status",
                "Values": ["available"]
            }

        ]
    )['NetworkInterfaces']

def wait_for_attachment(ec2, eni_id, instance_id, attachment_id,
                        timeout=60*4, interval=10):
    """
    Wait until ENI with `eni_id` got attached to `instance_id`
    with `attachment_id`.
    If it did not happen within timeout, this method will raise `TimeoutError`.
    """
    def get_attachment():
        while True:
            try:
                response = ec2.describe_network_interface_attribute(
                    NetworkInterfaceId=eni_id,
                    Attribute="attachment"
                )
                logging.info("Got attachment of ENI: "
                             "%s to EC2-instance: %s with id: %s::\n%s",
                             eni_id, instance_id, attachment_id, response)
                return response.get("Attachment")
            except ClientError as e:
                logging.warning(e)
                time.sleep(1)

    attachment = get_attachment()
    wait_time = 0
    while (attachment is None or
           attachment["AttachmentId"] != attachment_id or
           attachment["InstanceId"] != instance_id or
           attachment["Status"] != "attached"):
        if wait_time >= timeout:
            message = "Timeout waiting for attachment %s of ENI %s" \
                      " to EC2 instance %s" %\
                      (attachment_id, eni_id, instance_id)
            logging.error(message)
            raise TimeoutError(message)
        time.sleep(interval)
        wait_time += interval
        attachment = get_attachment()
    return attachment


def allocate_and_associate_eip(ec2, instance_id):
    try:
        allocation = ec2.allocate_address(Domain='vpc')
        print(allocation)
        response = ec2.associate_address(AllocationId=allocation['AllocationId'],
                                        InstanceId=instance_id)
        print(response)
        return allocation['AllocationId']
    except ClientError as e:
        print(e)    

def release_eip(ec2, allocation_id):
    try:
        response = ec2.release_address(AllocationId=allocation_id)
        print('Address released', allocation_id)
    except ClientError as e:
        print(e)    

def main():
    instance_id = get_metadata()["instanceId"]
    current_az = get_metadata()["availabilityZone"]
    logging.info("Current Instance ID %s", instance_id)
    logging.info("Current AZ %s", current_az)

    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ec2_res = boto3.resource('ec2', region_name=BOTO_REGION)
    # allocation_id = allocate_and_associate_eip(ec2, instance_id)
    # release_eip(ec2, allocation_id)
    metadata = get_metadata()
    print(metadata)


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
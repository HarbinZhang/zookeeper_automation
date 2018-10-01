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

@functools.lru_cache(1)
def get_metadata():
    conn = http.client.HTTPConnection("169.254.169.254", 80, timeout=10)
    conn.request("GET", "/latest/dynamic/instance-identity/document")
    r1 = conn.getresponse()
    return json.loads(r1.read().decode("utf-8"))

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
        return None

def release_eip(ec2, allocation_id):
    try:
        response = ec2.release_address(AllocationId=allocation_id)
        print('Address released', allocation_id)
    except ClientError as e:
        print(e)    

def main():
    instance_id = get_metadata()["instanceId"]
    current_az = get_metadata()["availabilityZone"]
    # logging.info("Current Instance ID %s", instance_id)
    # logging.info("Current AZ %s", current_az)

    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ec2_res = boto3.resource('ec2', region_name=BOTO_REGION)
    # allocation_id = allocate_and_associate_eip(ec2, instance_id)
    # release_eip(ec2, allocation_id)
    # metadata = get_metadata()
    metadata = ec2.describe_instances(InstanceIds=[instance_id])
    print(metadata['Reservations'][0]['Instances']['PublicIpAddress'])


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
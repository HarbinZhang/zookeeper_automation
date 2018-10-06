import os
import sys
import time
import functools
# import http.client
import httplib
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

CLUSTER = 'automation'
CLUSTER_SIZE = 3

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2") # Need to change

# @functools.lru_cache(1)
def get_metadata():
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
    conn.request("GET", "/latest/dynamic/instance-identity/document")
    r1 = conn.getresponse()
    return json.loads(r1.read().decode("utf-8"))

# @functools.lru_cache(1)
def get_public_ipv4():
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
    conn.request("GET", "/latest/meta-data/public-ipv4")
    r1 = conn.getresponse()
    return r1.read().decode("utf-8")
    # public_ipv4 = ec2.describe_instances(InstanceIds=[instance_id])
    # print(public_ipv4['Reservations'][0]['Instances'][0]['PublicIpAddress'])

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
    # TODO: retry
    # TODO: prepare config file
    # TODO: tempory connection to determine new cluster or not
    
    instance_id = get_metadata()["instanceId"]
    logging.info("Current Instance ID %s", instance_id)
    # logging.info("Current AZ %s", current_az)

    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ec2_res = boto3.resource('ec2', region_name=BOTO_REGION)

    # allocation_id = allocate_and_associate_eip(ec2, instance_id)
    # release_eip(ec2, allocation_id)
    ipv4 = get_public_ipv4()
    print(ipv4)
    
    ecs = boto3.client('ecs', region_name=BOTO_REGION)
    list_response = ecs.list_container_instances(
        cluster=CLUSTER
    )

    descriptions_response = ecs.describe_container_instances(
        cluster=CLUSTER,
        containerInstances=list_response['containerInstanceArns']
    )

    # get Instance Ids
    instance_ids = []
    for it in descriptions_response['containerInstances']:
        # Deduplicate: set 0.0.0.0 for self
        if it['ec2InstanceId'] == instance_id:
            continue
        instance_ids.append(it['ec2InstanceId'])
    instances = ec2.describe_instances(InstanceIds=instance_ids)

    # get Instance Public Ips
    public_ips = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            public_ips.append(instance['PublicIpAddress'])
    print(public_ips)




if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
import os
import sys
import time
import functools
# import http.client
import json
import random
import subprocess
import struct
import socket
import fcntl
import logging
import httplib

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



# @functools.lru_cache(1)
def get_metadata():
    # conn = http.client.HTTPConnection("169.254.169.254", 80, timeout=10)
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
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


def find_attached_eni_or_attach(ec2, ec2_res, instance_id, internal_subnet):
    """
    Checks if an ENI from the pool is already attached to the instance
    and returns it.
    If none is attached than tries to attach and return attached.
    In case of errors retries up to 5 times with 20 seconds delay.
    """

    eni_to_configure = None

    MAX_RETRIES = 5
    retries = 0
    while retries < MAX_RETRIES:
        retries += 1

        current_instance = ec2_res.Instance(instance_id)
        found_attached = False

        for eni in current_instance.network_interfaces:
            if found_attached:
                break
            eni.load()
            for tag in eni.tag_set or []:
                if tag["Key"] == ENI_TAG_KEY and tag["Value"] == ENI_TAG_VALUE:
                    found_attached = True
                    eni_to_configure = eni
                    logging.info("Found attached ENI %s", eni.id)
                    break

        if not found_attached:
            logging.info("Found no attached ENI, trying to find a free one"
                         "and attach it")
            # It's possible to have an ENI and not get it attached,
            # as another machine already attached it. Simply retry in this case
            try:
                free_enis = get_free_enis(ec2, internal_subnet)

                logging.info("Free ENIs in subnet %s: %s",
                             internal_subnet["SubnetId"],
                             [eni["NetworkInterfaceId"] for eni in free_enis])

                if len(free_enis) == 0:
                    logging.warning("No free ENIs, retrying")
                else:
                    eni_to_attach = random.choice(free_enis)
                    eni_id = eni_to_attach["NetworkInterfaceId"]
                    logging.info("Trying to attach ENI %s", eni_id)
                    attachment_id = ec2.attach_network_interface(
                        NetworkInterfaceId=eni_id,
                        InstanceId=instance_id,
                        DeviceIndex=1
                    )["AttachmentId"]
                    attachment = wait_for_attachment(ec2, eni_id, instance_id,
                                                     attachment_id)
                    if attachment:
                        eni_to_configure = ec2_res.NetworkInterface(eni_id)
                        eni_to_configure.load()
                        logging.info("ENI attached: %s", attachment)
                        break

            except Exception as e:
                logging.exception(e)

            logging.info("Sleeping for 20 seconds")
            time.sleep(20)
        else:
            break

    return eni_to_configure



def main():
    print("hi")
    instance_id = get_metadata()["instanceId"]
    current_az = get_metadata()["availabilityZone"]
    logging.info("Current Instance ID %s", instance_id)
    logging.info("Current AZ %s", current_az)

    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ec2_res = boto3.resource('ec2', region_name=BOTO_REGION)
    internal_subnets = get_internal_subnets(ec2, current_az)

    if not internal_subnets:
        logging.error("No internal subnet found for availability zone %s",
                      current_az)
        sys.exit(1)

    logging.info("Found internal subnets: %s", internal_subnets)
    internal_subnet = internal_subnets[0]
    logging.info("Using internal subnet: %s", internal_subnet)

    eni_to_configure = find_attached_eni_or_attach(
        ec2, ec2_res, instance_id, internal_subnet)

    if eni_to_configure is None:
        logging.error("Could not attach any ENI, exiting")
        sys.exit(1)

    eni_ip = eni_to_configure.private_ip_address
    logging.info("ENI_IP is: %s", eni_ip)
    # if not NetworkConfiguration.configure_new_iface("eth1", expected_ip=eni_ip):
    #     logging.error("Error configuring new ENI, exiting")
    #     sys.exit(1)

    if not NetworkConfiguration.fix_same_net_routing(
            "eth0", NetworkConfiguration.get_ip_address("eth0"),
            "eth1", eni_ip,
            NetworkConfiguration.get_default_gateway(),
            internal_subnet["CidrBlock"]):
        logging.error("Error while fixing same-net-routing. exiting.")
        sys.exit(1)
    pass


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
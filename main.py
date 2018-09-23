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


@functools.lru_cache(1)
def get_metadata():
    """
    Get ec2 instance metadata for the machine running this code.
    calls:
        http://169.254.169.254/latest/dynamic/instance-identity/document
    example answer:
    {
      "devpayProductCodes" : null,
      "privateIp" : "10.0.0.1",
      "availabilityZone" : "eu-central-1b",
      "version" : "2010-08-31",
      "region" : "eu-central-1",
      "instanceId" : "i-xxxxxxxxxxxxxxx",
      "billingProducts" : null,
      "instanceType" : "t2.micro",
      "pendingTime" : "2017-03-07T11:18:20Z",
      "accountId" : "xxxxxxxxxxxx",
      "architecture" : "x86_64",
      "kernelId" : null,
      "ramdiskId" : null,
      "imageId" : "ami-xxxxxxxxx"
    }
    """
    if not DEV_MODE:
        conn = http.client.HTTPConnection("169.254.169.254", 80, timeout=10)
        conn.request("GET", "/latest/dynamic/instance-identity/document")
        r1 = conn.getresponse()
        return json.loads(r1.read().decode("utf-8"))
    else:
        return {
            "devpayProductCodes": None,
            "privateIp": "10.0.0.1",
            "availabilityZone": "eu-central-1b",
            "version": "2010-08-31",
            "region": "eu-central-1",
            "instanceId": "i-xxxxxxxxxxx",
            "billingProducts": None,
            "instanceType": "t2.micro",
            "pendingTime": "2017-03-07T11:18:20Z",
            "accountId": "xxxxxxxxx",
            "architecture": "x86_64",
            "kernelId": None,
            "ramdiskId": None,
            "imageId": "ami-xxxxxxxxxx"
        }



def main():
    print("hi")
    instance_id = get_metadata()["instanceId"]

if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
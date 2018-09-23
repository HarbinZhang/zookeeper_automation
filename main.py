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

# ENV = os.environ["ENV"]
# APP_SPEC = os.environ["APP_SPEC"]
# BOTO_REGION = os.environ["BOTO_REGION"]

# if BOTO_REGION == "":
#     BOTO_REGION = os.environ["AWS_DEFAULT_REGION"]

# ENI_TAG_KEY = "exhibitor-eni-pool"
# ENI_TAG_VALUE = "{}-exhibitor-{}-eni-pool".format(ENV, APP_SPEC).replace("exhibitor--eni", "exhibitor-eni")



@functools.lru_cache(1)
def get_metadata():
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
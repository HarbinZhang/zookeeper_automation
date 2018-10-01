import boto3
import os
from botocore.exceptions import ClientError


BOTO_REGION = os.environ.get("BOTO_REGION", "")

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")


ec2 = boto3.client('ec2', region_name=BOTO_REGION)

try:
    allocation = ec2.allocate_address(Domain='vpc')
    print(allocation)
    response = ec2.associate_address(AllocationId=allocation['AllocationId'],
                                     InstanceId='INSTANCE_ID')
    print(response)
except ClientError as e:
    print(e)
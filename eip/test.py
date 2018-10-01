import boto3
import os

BOTO_REGION = os.environ.get("BOTO_REGION", "")

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")


ec2 = boto3.client('ec2', region_name=BOTO_REGION)
filters = [
    {'Name': 'domain', 'Values': ['vpc']}
]
response = ec2.describe_addresses(Filters=filters)
print(response)
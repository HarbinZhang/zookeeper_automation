import boto3


ec2 = boto3.client('ec2', 'us-east-2')
filters = [
    {'Name': 'domain', 'Values': ['vpc']},
    {'Name': 'publicip', 'Values': ['52.15.164.175']}
]
response = ec2.describe_addresses(Filters=filters)
print(response)
import boto3


ec2 = boto3.client('ec2', 'us-east-2')
filters = [
    {'Name': 'domain', 'Values': ['vpc']},
    {'Name': 'public-ip', 'Values': ['52.15.164.175']}
]
response = ec2.describe_addresses(Filters=filters)
id = response['Addresses'][0]['AllocationId']
print (id)
print response

# res = ec2.create_tags(
#     Resources=[
#         id,
#     ],
#     Tags=[
#         {
#             'Key': 'Stack',
#             'Value': 'production',
#         },
#     ],    
# )
# print(res)
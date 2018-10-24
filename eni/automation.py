import os
import sys
import time
import functools
import httplib
import json
import random
import subprocess
import struct
import socket
import fcntl
import logging
import errno
import collections

import boto3
from botocore.exceptions import ClientError


ENV = os.environ.get("ENV", "")
APP_SPEC = os.environ.get("APP_SPEC", "")
BOTO_REGION = os.environ.get("BOTO_REGION", "")

CLUSTER = 'eni'
CLUSTER_SIZE = 3
CLUSTER_LOCATION = 'us-east-2'
RETRY_TIMES = 5
RETRY_INTERVAL = 20

ENV_TAG_KEY = "env"
ENV_TAG_VALUE = "eni"

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", CLUSTER_LOCATION) # Need to change


def main():
    instance_id = get_metadata()["instanceId"]
    logging.info("Current Instance ID %s", instance_id)

    # get all private IPs
    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ecs = boto3.client('ecs', region_name=BOTO_REGION)
    res = boto3.resource('ec2', region_name=BOTO_REGION)

    
    list_response = ecs.list_container_instances(
        cluster=CLUSTER
    )
    
    descriptions_response = ecs.describe_container_instances(
        cluster=CLUSTER,
        containerInstances=list_response['containerInstanceArns']
    )  
    # print(descriptions_response)

    # get Instances' info
    instance_ids = []
    for it in descriptions_response['containerInstances']:
        instance_ids.append(it['ec2InstanceId'])
    instances = ec2.describe_instances(InstanceIds=instance_ids)
    # print(instances)

    # get private IPs
    # private_ips = get_info_from_instances(instances, "PrivateIpAddress")
    # sorted_eni_ips = sorted(private_ips, key=lambda item: socket.inet_aton(item[0]))
    # assert len(sorted_eni_ips) == CLUSTER_SIZE

    
    local_ip = get_private_ipv4()

    eni_ips = get_eni_ips(instances)
    sorted_eni_ips = sorted(eni_ips, key=lambda item: socket.inet_aton(item[0]))
    assert len(sorted_eni_ips) == CLUSTER_SIZE


    local_eni_ip = get_my_eni_ip(instances, local_ip)


    # is_new_cluster = True
    # for ip in sorted_eni_ips:
    #     if(local_ip == ip):
    #         continue
    #     if testZookeeper(ip):
    #         is_new_cluster = False
    #         break

    # if is_new_cluster:
    #     # produce myid based on sorted private ips
    #     logging.info("This is a new cluster")

    # else:
    #     logging.info("This is an existing cluster")


    myid = sorted_eni_ips.index(local_eni_ip) + 1
    prepare_myid(myid)
      
    id_to_eni_ip_dict = {}
    for index, ip in enumerate(sorted_eni_ips):
        id_to_eni_ip_dict[index+1] = ip


    print(id_to_eni_ip_dict)

    prepare_zoocfg(myid, id_to_eni_ip_dict)

    logging.info("zookeeper automation finished")


def get_my_eni_ip(instances, local_ip):
    res = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if instance["PrivateIpAddress"] == local_ip:
                res = instance["NetworkInterfaces"][1]["PrivateIpAddress"]
    return res

def get_eni_ips(instances):
    res = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            res.append(instance["NetworkInterfaces"][1]["PrivateIpAddress"])
    return res


def testZookeeper(hostname):
    data = netcat(hostname, 2181, "ruok")
    if data is None:
        logging.info("zookeeper: %s is NOT working", hostname)
        return False
    elif data == "imok":
        logging.info("zookeeper: %s is working", hostname)
        return True
    logging.warn("Zookeeper return status wrong %s", data)
    return False


def netcat(hostname, port, content):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((hostname, port))
        s.settimeout(1)
        s.sendall(content)
        s.shutdown(socket.SHUT_WR)
        data = s.recv(1024)
        s.close()
        return data
    except:
        s.close()
        return None



def prepare_myid(myid):
    filename = "/ecs/data/zookeeper/data/myid"
    os.environ["ZOO_MY_ID"] = str(myid)
    with open(filename, "w") as f:
        f.write(str(myid))
        logging.info("myid %d prepared in %s", myid, filename)
 

def prepare_zoocfg(myid, public_ips_dict):
    filename = "/ecs/data/zookeeper/conf/zoo.cfg"
    zoo_servers = []
    with open(filename, "a") as f:
        f.write("\n")
        for id in range(1, CLUSTER_SIZE+1):
            if id == myid:
                f.write("server."+str(myid)+"=0.0.0.0:2888:3888\n")
                zoo_servers.append("server."+str(myid)+"=0.0.0.0:2888:3888")
            else:
                f.write("server."+str(id)+"="+str(public_ips_dict[id])+":2888:3888\n")
                zoo_servers.append("server."+str(id)+"="+str(public_ips_dict[id])+":2888:3888")
        logging.info("zoo.cfg prepared in %s", filename)
        os.environ["ZOO_SERVERS"] = ' '.join(zoo_servers)


def allocate_and_associate_eip(ec2, instance_id):
    try:
        allocation = ec2.allocate_address(Domain='vpc')
        print(allocation)
        response = ec2.associate_address(AllocationId=allocation['AllocationId'],
                                        InstanceId=instance_id)
        print(response)
        # logging.info(response)
        return allocation
    except ClientError as e:
        print(e)    
        return None


def release_eip(ec2, public_ip):
    try:
        response = ec2.release_address(PublicIp=public_ip)
        print('Address released', public_ip)
    except ClientError as e:
        print(e)  


def get_info_from_instances(instances, key):
    res = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            # print(instance[key][1]["Attachment"])
            # print(instance[key][1]["PrivateIpAddress"])
            res.append(instance[key][1]["PrivateIpAddress"])
    return res


def get_id_to_public_ip(instances, sorted_eni_ips):
    res = {}
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            print(instance)
            try:
                logging.info("This instance already has public Ip: %s", instance["PublicIpAddress"])
                res[sorted_eni_ips.index(instance["PrivateIpAddress"]) + 1] = instance["PublicIpAddress"]
            except Exception as e:
                logging.warn("Exception when getting public ips: %s", str(e))
                logging.warn("A instance has not public IP, need to wait")
                print(res)
                return res
    return res


# @functools.lru_cache(1)
def get_metadata():
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
    conn.request("GET", "/latest/dynamic/instance-identity/document")
    r1 = conn.getresponse()
    return json.loads(r1.read().decode("utf-8"))


# @functools.lru_cache(1)
def get_public_ipv4(ec2, instance_id, myid):
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
    conn.request("GET", "/latest/meta-data/public-ipv4")
    r1 = conn.getresponse()
    res = r1.read().decode("utf-8")

    if len(res) < 20:
        logging.info("Already has a public IP: %s", res)
    else:
        allocation = allocate_and_associate_eip(ec2, instance_id)
        logging.info("Allocate a new elastic IP: %s", allocation["PublicIp"])
        res = allocation["PublicIp"]
        logging.info("Tag it: %d", myid)
        response = ec2.create_tags(
            Resources=[
                allocation['AllocationId'],
            ],
            Tags=[
                {
                    'Key': 'myid',
                    'Value': str(myid) ,
                },
                {
                    'Key': ENV_TAG_KEY,
                    'Value': ENV_TAG_VALUE,
                },
            ],    
        )        
    return res
    # public_ipv4 = ec2.describe_instances(InstanceIds=[instance_id])
    # print(public_ipv4['Reservations'][0]['Instances'][0]['PublicIpAddress'])


def get_private_ipv4():
    conn = httplib.HTTPConnection("169.254.169.254", timeout=10)
    conn.request("GET", "/latest/meta-data/local-ipv4")
    r1 = conn.getresponse()
    return r1.read().decode("utf-8")


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
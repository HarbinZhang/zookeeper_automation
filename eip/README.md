# EIP
### eip(Elastic IP)
![Alt text](../images/eip.png?raw=true "eip")
This idea is using Elastic IP as a static IP.

### How to determine if it is a new cluster?
Using zookeeper server response.
If there is no response from any server, we think it is a new cluster.
``` python
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
```

### How to prepare myid?
Using the cluster private IPs list.
Determine myid based on the sorted private IPs list.
``` python
    private_ips = get_info_from_instances(instances, "PrivateIpAddress")
    sorted_ips = sorted(private_ips, key=lambda item: socket.inet_aton(item[0]))
    myid = sorted_ips.index(local_ip) + 1
```

### How to prepare zoo.cfg?
Two things:
1. Sync(): Waiting until all zookeepers get their elastic IP.
2. Prepare zoo.cfg.

##### Details
1. Sync():
``` python
    # sync() retry wait until all instances have public IP
    for i in range(RETRY_TIMES):
        instance_ids = []
        for it in descriptions_response['containerInstances']:
            instance_ids.append(it['ec2InstanceId'])
        instances = ec2.describe_instances(InstanceIds=instance_ids)        

        public_ips_dict = get_id_to_public_ip(instances, sorted_ips)
        if len(public_ips_dict) == CLUSTER_SIZE:
            logging.info("All instances have public IP, ready to prepare config files")
            break
        else:
            logging.info("Still Waiting some instances get their public IP, retried: %d times", i)
            time.sleep(RETRY_INTERVAL)
    if len(public_ips_dict) != CLUSTER_SIZE:
        logging.error("#instances have public IP not equal to cluster size")
        release_eip(ec2, public_ip)
        return       
```

2. Prepare zoo.cfg.
Using the dict{myid: elastic ip} to prepare the zoo.cfg
``` python
def get_id_to_public_ip(instances, sorted_ips):
    res = {}
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            print(instance)
            try:
                logging.info("This instance already has public Ip: %s", instance["PublicIpAddress"])
                res[sorted_ips.index(instance["PrivateIpAddress"]) + 1] = instance["PublicIpAddress"]
            except Exception as e:
                logging.warn("Exception when getting public ips: %s", str(e))
                logging.warn("A instance has not public IP, need to wait")
                print(res)
                return res
    return res
```

### When join an existing cluster, how to prepare myid&zoo.cfg
Steps:
1. Get all new zookeepers list, which doesn't have their elastic IP.
2. Get all working zookeepers list.
3. Get all Elastic IPs of this cluster.(By elastic IP tag)
4. Based on 1,2,3, get the available elastic IPs.
5. Based on the "How to prepare myid?" strategy, prepare new myid, elastic IP from the available elastic IPs.
6. Prepare myid&zoo.cfg.

##### Details
``` python
        new_myids_to_public_ips = {}
        new_myids = []
        for address in response['Addresses']:
            if address['PublicIp'] in valid_public_ips:
                continue
            else:
                for tag in address['Tags']:
                    if tag['Key'] == 'myid':
                        new_myids_to_public_ips[tag['Value']] = address['PublicIp']
                        new_myids.append(tag['Value'])


        new_myids.sort(key=lambda item:item[0])
        new_private_ips.sort(key=lambda item: socket.inet_aton(item[0]))
        print(new_myids_to_public_ips)
        print(new_myids)
        print(local_ip)

        myid = new_myids[new_private_ips.index(local_ip)]
        my_public_ip = new_myids_to_public_ips[myid]
        print(myid)
        print(my_public_ip)

        response = ec2.associate_address(PublicIp=my_public_ip,
                                        InstanceId=instance_id)
        print("associate response: ",response)
```
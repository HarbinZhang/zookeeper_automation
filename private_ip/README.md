# Private IP
### private_ip(dynamic config file)
![Alt text](../images/private_ip.png?raw=true "private_ip")
This idea is using the newer version of zookeeper(3.5.0+) to enable the dynamic reconfiguration feature.

### With Zuora
the current zookeeper version using in Zuora is: zookeeper-3.4.11.
The dynamic reconfiguration requires version: 3.5.0+.

https://zookeeper.apache.org/doc/r3.5.3-beta/zookeeperReconfig.html  
http://www-eu.apache.org/dist/zookeeper/

3.5.0+ only beta version.

### How to prepare myid?
Using the cluster private IPs list.
Determine myid based on the sorted private IPs list.
``` python
    private_ips = get_info_from_instances(instances, "PrivateIpAddress")
    sorted_ips = sorted(private_ips, key=lambda item: socket.inet_aton(item[0]))
    myid = sorted_ips.index(local_ip) + 1
```

### How to prepare zoo.cfg?
Using myid and private IP to prepare the zoo.cfg. (The similar idea in eip)

### How to hanlde joining an existing cluster?
Just idea, not implemented yet.
Build a kazoo server for zookeeper health check and dynamic reconfiguration.


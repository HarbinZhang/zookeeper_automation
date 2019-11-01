# zookeeper_automation
## Background
Zookeeper requires zoo.cfg and unique myid to start. A zookeeper cluster, in general, has 5 zookeepers. That means each zookeeper needs an unique myid from 1 to 5. Before we prepared zoo.cfg and myid manually. It's not convenient when we deploy zookeepers to a new environment or some instance got replaced because of maintenance. So we want some automation in place to generate the necessary zoo.cfg and myid etc.

## Requirements
Zookeeper automation includes two parts:    deployment + maintenance.
1. deployment: zookeeper automation would provide zoo.cfg and unique myid for each zookeeper.
2. maintenance: zookeeper automation would let newly started zookeeper know it's joining an existing zookeeper cluster, and provide the same zoo.cfg and myid for it as the previous one.

## Basic Idea
![Alt text](images/basicIdea.png?raw=true "basicIdea")
The basic idea is when a new zookeeper deployed to a cluster, we need to figure out: whether the cluster is a new cluster or not.
Then we can prepare appropriate config files. 
Zookeeper automation includes two parts:    deployment + maintenance.
1. deployment: Zookeepers get their "static" IP, associate it and get all other zookeepers "static" IPs. It also prepare itself myid, get all others id and write their ids, IPs into zoo.cfg. Then start zookeeper server. 
2. maintenance: When one or more zookeepers down, we can start new zookeepers automatically, and let them join the cluster without restarting other alive zookeepers. We want to use "static-like" IP to achieve this goal.
## Solutions
There are several ways(we tried) to achieve these requirements:
Basically, I choose their IP as the common key, and their ID can be determined by their IP order in the sorted IPs.
Zookeepers get their "static" IP, associate it and get all other zookeepers "static" IPs. All zookeepers sort their "static" IP and get the same ordered list. Then each zookeeper can generate their unique myid based on their IP order in the sorted list.
### eip(Elastic IP)
![Alt text](images/eip.png?raw=true "eip")
This idea is using Elastic IP as a static IP.
### eni(Elastic Network Interface)
![Alt text](images/eni.png?raw=true "eni")
This idea is using eni(the secondary private IP) as a static IP.
### private_ip(dynamic config file)
![Alt text](images/private_ip.png?raw=true "private_ip")
This idea is using the newer version of zookeeper(3.5.0+) to enable the dynamic reconfiguration feature.
### elb(Elastic Load Balance)
This idea is "One Load Balancer per zookeeper". Then zookeepers connect to each other by ELB. Theoretically feasible but wired.
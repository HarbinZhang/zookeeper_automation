# zookeeper_automation

## Requirements
Zookeeper automation includes two parts:    deployment + maintenance.
1. maintenance: when one or more zookeepers down, we can start new zookeepers, let them join the cluster without restart other normal zookeepers. We want to use "static-like" IP to achieve this goal.
2. deployment: zookeepers will get their "static" IP, associate it, get all other zookeepers "static" IPs. Write them into zoo.cfg. Then start zookeeper server.

## Basic Idea
![Alt text](images/basicIdea.png?raw=true "basicIdea")
The basic idea is when a new zookeeper deployed to a cluster, we need to figure out whether the cluster is a new cluster or not.
Then we can prepare appropriate config files.

## Solutions
There are several ways(we tried) to achieve these requirements:
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
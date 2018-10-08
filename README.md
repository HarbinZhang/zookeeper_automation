# zookeeper_automation

## Requirements
zookeeper automation includes two parts:    deployment + maintenance.
1. maintenance: when one or more zookeepers down, we can start new zookeepers, let them join the cluster without restart other normal zookeepers. We want to use "static-like" IP to achieve this goal.
2. deployment: zookeepers will get their "static" IP, associate it, get all other zookeepers "static" IPs. Write them into zoo.cfg. Then start zookeeper server.

## Basic Idea
![Alt text](images/basicIdea.png?raw=true "Title")

There are several ways(we try) to achieve these requirements:
## eip(Elastic IP)
## eni(Elastic Network Interface)
## ()
## elb(Elastic Load Balance)
# ENI
This is from https://jobs.zalando.com/tech/blog/rock-solid-kafka/  
The code is from https://gist.github.com/rcillo/1a64d757bf3ebaffcb3c71eb95607f1f  
The code is working for attaching a secondary ENI to the instance. But for Changing arp_filter, the code does not have enough permission. (See "Problem" below)

More Information:
https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html
https://forums.aws.amazon.com/thread.jspa?threadID=84340

FYI
>"Launching an EC2 instance with multiple network interfaces will automatically configure interfaces, private IP addresses and route tables on the operating system of the instance. Warm or hot attaching an additional network interface (when the instance is stopped or running) may require you to manually bring up the second interface, configure the private IP address, and modify the route table accordingly. Microsoft Windows Server 2003 and 2008 instances will automatically recognize the warm or hot attach and will automatically configure themselves. Instances that are not running a Microsoft Windows Server operating system might require the manual interaction to configure the interface on the operating system.)"

### Update
With the latest Amazon Linux(2018.03), The secondary network interface can work without restarting the instance. 

I have tested with 
``` bash
nc -l 2181      # in one instance

nc -vz host_eni_ip 2181 # in another instance.
```
They can build tcp connection successfully.

But in zookeeper cluster, They cannot build connection with each other with their eni_ip, Got socket Timeout Exception.  
```
Cannot open channel to 1 at election address /172.31.27.***:3888 java.net.SocketTimeoutException: connect timed out
```  
I think it's because the ec2 instance would choose either eth0 or eth1 to send request randomly. So Creating a proper route table can solve this problem.  
https://serverfault.com/questions/336021/two-network-interfaces-and-two-ip-addresses-on-the-same-subnet-in-linux
  
But multiple network interfaces on the same subnet is still not recommended. 
### eni(Elastic Network Interface)
![Alt text](../images/eni.png?raw=true "eni")
This idea is using eni(the secondary private IP) as a static IP.
### Problem
This code cannot get enough permission to run, which is necessary to ENI working.
``` python
    def fix_same_net_routing(iface1, iface1_ip, iface2, iface2_ip,
                             gateway, subnet_cidr):
        """
        Configure proper routing with 2 local interfaces
        within the same IP subnet.

        It's basically this:
        http://serverfault.com/questions/336021/two-network-interfaces-and-two-ip-addresses-on-the-same-subnet-in-linux

        with fixed routing to other subnets.
        """

        # arp_filter - BOOLEAN
        #    1 - Allows you to have multiple network interfaces on the same
        #    subnet, and have the ARPs for each interface be answered
        #    based on whether or not the kernel would route a packet from
        #    the ARP'd IP out that interface (therefore you must use source
        #    based routing for this to work). In other words it allows control
        #    of which cards (usually 1) will respond to an arp request.
        try:
            with open("/proc/sys/net/ipv4/conf/all/arp_filter", "w") as all_arp_filter:
                all_arp_filter.write("1")

            arp_filter_setting = """
    net.ipv4.conf.all.arp_filter = 1
    """
            ensure_written(arp_filter_setting, "/etc/sysctl.conf")

            # add additional routing tables
            rt_table_iface1 = iface1
            rt_table_iface2 = iface2
            rt_tables = """
1   {}
2   {}
""".format(rt_table_iface1, rt_table_iface2)
            ensure_written(rt_tables, "/etc/iproute2/rt_tables")
        except IOError as e:
            logging.exception("Error fixing same-net-routing for two interfaces")
            return False
        commands = [
            ["ip", "route", "add", "default", "via", gateway, "dev", iface1, "table", rt_table_iface1],
            ["ip", "route", "add", "default", "via", gateway, "dev", iface2, "table", rt_table_iface2],
            ["ip", "route", "add", subnet_cidr, "dev", iface1, "src", iface1_ip, "table", rt_table_iface1],
            ["ip", "route", "add", subnet_cidr, "dev", iface2, "src", iface2_ip, "table", rt_table_iface2],
            ["ip", "rule", "add", "from", iface1_ip, "table", rt_table_iface1],
            ["ip", "rule", "add", "from", iface2_ip, "table", rt_table_iface2]
        ]
        for command in commands:
            cmd_string = " ".join(command)
            logging.info("Executing: " + cmd_string)
            retval = subprocess.call(command, stderr=subprocess.STDOUT)
            if retval == 2:
                # route already exists, that's fine
                pass
            elif retval != 0:
                logging.error("Command %s failed with return code %s. exiting.",
                              cmd_string, retval)
                return False
        return True

```
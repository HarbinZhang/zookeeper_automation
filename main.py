import os
import sys
import time
import functools
import http.client
import json
import random
import subprocess
import struct
import socket
import fcntl
import logging

import boto3
from botocore.exceptions import ClientError

DEV_MODE = True if os.environ.get("DEV_MODE", "") else False

ENV = os.environ.get("ENV", "")
APP_SPEC = os.environ.get("APP_SPEC", "")
BOTO_REGION = os.environ.get("BOTO_REGION", "")

if BOTO_REGION == "":
    BOTO_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")

ENI_TAG_KEY = "exhibitor-eni-pool"
ENI_TAG_VALUE = "{}-exhibitor-{}-eni-pool".format(ENV, APP_SPEC).replace("exhibitor--eni", "exhibitor-eni")


class NetworkConfiguration(object):

    @staticmethod
    def get_default_gateway():
        """Read the default gateway directly from /proc."""
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue

                return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        return ""

    @staticmethod
    def get_ip_address(ifname):
        """
        Get the local IP address of the given interface.

        :param ifname name of the network interface
        :return the IP address (if any)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode("utf-8"))
        )[20:24])

    @staticmethod
    def configure_new_iface(iface, expected_ip=None):

        retval = subprocess.call(["dhclient", iface], stderr=subprocess.STDOUT)
        if retval != 0:
            # do not exit here, known bug, IP should be configured:
            # http://unix.stackexchange.com/questions/155990/docker-bridges-dhcp#155995
            logging.error("Configuring iface %s seemed to have failed", iface)
            return False
        if expected_ip is not None:
            iface_ip = NetworkConfiguration.get_ip_address(iface)
            if iface_ip != expected_ip:
                logging.error("Configuring %s did not yield the expected IP "
                              "%s but another one %s", iface, expected_ip,
                              iface_ip)
                return False
        return True

    @staticmethod
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


def ensure_written(content, path_to_file):
    """Ensure that the content is in the given `path_to_file`
    (append if not)."""
    with open(path_to_file, "r") as read_fd:
        already_written = content in read_fd.read()
    if not already_written:
        with open(path_to_file, "a") as append_fd:
            append_fd.write(content)


def get_internal_subnets(ec2, current_az):
    return ec2.describe_subnets(
        Filters=[
            {
                "Name": "availability-zone",
                "Values": [current_az]
            }
            # ,
            # {
            #     "Name": "tag:Name",
            #     "Values": ["internal-{}".format(current_az)]
            # }
        ]
    )["Subnets"]

@functools.lru_cache(1)
def get_metadata():
    conn = http.client.HTTPConnection("169.254.169.254", 80, timeout=10)
    conn.request("GET", "/latest/dynamic/instance-identity/document")
    r1 = conn.getresponse()
    return json.loads(r1.read().decode("utf-8"))

def get_free_enis(ec2, internal_subnet):
    """
    Get all free NetworkInterfaces in the internal subnet with the tag.
    """

    return ec2.describe_network_interfaces(
        Filters=[
            # {
            #     "Name": "tag:{}".format(ENI_TAG_KEY),
            #     "Values": [ENI_TAG_VALUE]
            # },
            {
                "Name": "subnet-id",
                "Values": [internal_subnet["SubnetId"]]
            },
            {
                "Name": "status",
                "Values": ["available"]
            }

        ]
    )['NetworkInterfaces']

def wait_for_attachment(ec2, eni_id, instance_id, attachment_id,
                        timeout=60*4, interval=10):
    """
    Wait until ENI with `eni_id` got attached to `instance_id`
    with `attachment_id`.
    If it did not happen within timeout, this method will raise `TimeoutError`.
    """
    def get_attachment():
        while True:
            try:
                response = ec2.describe_network_interface_attribute(
                    NetworkInterfaceId=eni_id,
                    Attribute="attachment"
                )
                logging.info("Got attachment of ENI: "
                             "%s to EC2-instance: %s with id: %s::\n%s",
                             eni_id, instance_id, attachment_id, response)
                return response.get("Attachment")
            except ClientError as e:
                logging.warning(e)
                time.sleep(1)

    attachment = get_attachment()
    wait_time = 0
    while (attachment is None or
           attachment["AttachmentId"] != attachment_id or
           attachment["InstanceId"] != instance_id or
           attachment["Status"] != "attached"):
        if wait_time >= timeout:
            message = "Timeout waiting for attachment %s of ENI %s" \
                      " to EC2 instance %s" %\
                      (attachment_id, eni_id, instance_id)
            logging.error(message)
            raise TimeoutError(message)
        time.sleep(interval)
        wait_time += interval
        attachment = get_attachment()
    return attachment


def find_attached_eni_or_attach(ec2, ec2_res, instance_id, internal_subnet):
    """
    Checks if an ENI from the pool is already attached to the instance
    and returns it.
    If none is attached than tries to attach and return attached.
    In case of errors retries up to 5 times with 20 seconds delay.
    """

    eni_to_configure = None

    MAX_RETRIES = 5
    retries = 0
    while retries < MAX_RETRIES:
        retries += 1

        current_instance = ec2_res.Instance(instance_id)
        found_attached = False

        for eni in current_instance.network_interfaces:
            if found_attached:
                break
            eni.load()
            for tag in eni.tag_set or []:
                if tag["Key"] == ENI_TAG_KEY and tag["Value"] == ENI_TAG_VALUE:
                    found_attached = True
                    eni_to_configure = eni
                    logging.info("Found attached ENI %s", eni.id)
                    break

        if not found_attached:
            logging.info("Found no attached ENI, trying to find a free one"
                         "and attach it")
            # It's possible to have an ENI and not get it attached,
            # as another machine already attached it. Simply retry in this case
            try:
                free_enis = get_free_enis(ec2, internal_subnet)

                logging.info("Free ENIs in subnet %s: %s",
                             internal_subnet["SubnetId"],
                             [eni["NetworkInterfaceId"] for eni in free_enis])

                if len(free_enis) == 0:
                    logging.warning("No free ENIs, retrying")
                else:
                    eni_to_attach = random.choice(free_enis)
                    eni_id = eni_to_attach["NetworkInterfaceId"]
                    logging.info("Trying to attach ENI %s", eni_id)
                    attachment_id = ec2.attach_network_interface(
                        NetworkInterfaceId=eni_id,
                        InstanceId=instance_id,
                        DeviceIndex=1
                    )["AttachmentId"]
                    attachment = wait_for_attachment(ec2, eni_id, instance_id,
                                                     attachment_id)
                    if attachment:
                        eni_to_configure = ec2_res.NetworkInterface(eni_id)
                        eni_to_configure.load()
                        logging.info("ENI attached: %s", attachment)
                        break

            except Exception as e:
                logging.exception(e)

            logging.info("Sleeping for 20 seconds")
            time.sleep(20)
        else:
            break

    return eni_to_configure



def main():
    print("hi")
    instance_id = get_metadata()["instanceId"]
    current_az = get_metadata()["availabilityZone"]
    logging.info("Current Instance ID %s", instance_id)
    logging.info("Current AZ %s", current_az)

    ec2 = boto3.client('ec2', region_name=BOTO_REGION)
    ec2_res = boto3.resource('ec2', region_name=BOTO_REGION)
    internal_subnets = get_internal_subnets(ec2, current_az)

    if not internal_subnets:
        logging.error("No internal subnet found for availability zone %s",
                      current_az)
        sys.exit(1)

    logging.info("Found internal subnets: %s", internal_subnets)
    internal_subnet = internal_subnets[0]
    logging.info("Using internal subnet: %s", internal_subnet)

    eni_to_configure = find_attached_eni_or_attach(
        ec2, ec2_res, instance_id, internal_subnet)

    if eni_to_configure is None:
        logging.error("Could not attach any ENI, exiting")
        sys.exit(1)

    eni_ip = eni_to_configure.private_ip_address
    if not NetworkConfiguration.configure_new_iface("eth1", expected_ip=eni_ip):
        logging.error("Error configuring new ENI, exiting")
        sys.exit(1)

    if not NetworkConfiguration.fix_same_net_routing(
            "eth0", NetworkConfiguration.get_ip_address("eth0"),
            "eth1", eni_ip,
            NetworkConfiguration.get_default_gateway(),
            internal_subnet["CidrBlock"]):
        logging.error("Error while fixing same-net-routing. exiting.")
        sys.exit(1)
    pass


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s] %(message)s",
        level=logging.INFO,
        stream=sys.stdout
    )
    main()
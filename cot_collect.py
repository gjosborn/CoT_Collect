import sys
from socket import *
import prometheus_client
from prometheus_client import start_http_server, Gauge
from takproto import *
import netifaces as ni
from pprint import pprint


class Collector:
    def __init__(self, ):
        self.lat = Gauge('lat', 'current_latitude', ['uid', 'callsign'])
        self.lon = Gauge('lon', 'current_longitude', ['uid', 'callsign'])
        self.hae = Gauge('hae', 'hae_gauge', ['uid', 'callsign'])

    def collect_info(self, parsed_msg):
        uid = str(parsed_msg.cotEvent.uid)
        callsign = str(parsed_msg.cotEvent.detail.contact.callsign)
        lat = parsed_msg.cotEvent.lat
        lon = parsed_msg.cotEvent.lon
        hae = parsed_msg.cotEvent.hae
        self.lat.labels(uid=uid, callsign=callsign).set(lat)
        self.lon.labels(uid=uid, callsign=callsign).set(lon)
        self.hae.labels(uid=uid, callsign=callsign).set(hae)


class Ingester:
    def __init__(self, port, multicast_group, interface):
        self.port = port
        self.multicast_group = multicast_group
        self.interface = interface

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind(("", multicast_port))
        self.mreq = inet_aton(self.multicast_group) + inet_aton(self.interface)
        self.sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, self.mreq)

    def ingest(self):
        return self.sock.recv(1500)


# This function will return the human-readable names for the network interfaces. This is only necessary on Windows
# machines. Unix systems return useful interfaces by default
def win_select(iface_guids):
    import winreg as wr
    iface_names = {'(unknown)': '' for i in range(len(iface_guids))}

    reg = wr.ConnectRegistry(None, wr.HKEY_LOCAL_MACHINE)
    reg_key = wr.OpenKey(reg, r'SYSTEM\CurrentControlSet\Control\Network\{4d36e972-e325-11ce-bfc1-08002be10318}')
    for i in range(len(iface_guids)):
        try:
            reg_subkey = wr.OpenKey(reg_key, iface_guids[i] + r'\Connection')
            if 2 in ni.ifaddresses(iface_guids[i]):
                iface_names[i] = [wr.QueryValueEx(reg_subkey, 'Name')[0], ni.ifaddresses(iface_guids[i])[2][0]['addr']]
            else:
                iface_names[i] = [wr.QueryValueEx(reg_subkey, 'Name')[0], '']
        except FileNotFoundError:
            pass
    return iface_names


def linux_select(iface_names):
    ret_iface_names = {}
    for i in range(len(iface_names)):
        if 2 in ni.ifaddresses(iface_names[i]):
            ret_iface_names[i] = [iface_names[i], ni.ifaddresses(iface_names[i])[2][0]['addr']]
        else:
            ret_iface_names[i] = [iface_names[i], '']

    return ret_iface_names


if __name__ == '__main__':
    # You will have to set your own interface_ip in this code. There are ways to do it automatically but none that
    # worked efficiently in the way I was testing the code. Your interface_ip should just be the default gateway of
    # whatever network interface the ATAK devices are connected through (ipconfig)

    interfaces = ni.interfaces()
    if sys.platform == 'win32':
        int_if_list = win_select(interfaces)
    else:
        int_if_list = linux_select(interfaces)
    pprint(int_if_list)
    interface_option = int(input("Choose Interface: "))

    # The multicast port and group are the default values for ATAK devices operating in mesh mode. This is not always
    # the case
    multicast_port = 6969
    multicast_group = "239.2.3.1"
    interface_ip = int_if_list[interface_option][1]
    print("You have chosen the following interface: " + interface_ip)

    # Unregister various default prometheus collectors that are unnecessary for this application
    prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
    prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
    prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)

    # Start http server to expose metrics, create collector instance, and ingester which takes care of the networking
    # upon instantiation. The parameter for this function is any unused port but must be reflected in the prometheus
    # config
    start_http_server(10000)
    collector = Collector()
    ingester = Ingester(multicast_port, multicast_group, interface_ip)

    while True:
        print("listening")
        packet = ingester.ingest()
        parsed = parse_proto(bytearray(packet))
        if parsed is not None:
            # This event type is friendly ground units, aka other ATAK devices. You will have to adjust this
            # or add other conditionals if you want to track drones, imagery, etc., some specification info for how the
            # event type is configured can be found at the following link:
            # https://github.com/deptofdefense/AndroidTacticalAssaultKit-CIV/blob/master/takcot/mitre/types.txt
            # The event type is based off os MIL-STD-2525 which is available through (but good luck interpreting it)
            if parsed.cotEvent.type == "a-f-G-U-C":
                print('heartbeat')
                collector.collect_info(parsed)

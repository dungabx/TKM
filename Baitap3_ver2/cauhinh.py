#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spine-Leaf VXLAN Topology with FRRouting
Topology Bao Loc - TP.HCM Campus Network

Topology:
- 2 Spine routers (s1, s2) 
- 5 Leaf routers (s3-s7)
- VLANs: Admin (10), Lab (20), KTX (30)
- VXLAN overlay với BGP EVPN
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, Host, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import os
import sys
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Sử dụng backend không cần GUI
import matplotlib.pyplot as plt


class FRRNode(Host):
    """
    Node chạy FRRouting daemons
    Kế thừa từ Host của Mininet để tạo router với FRR
    """
    
    def __init__(self, name, **params):
        super(FRRNode, self).__init__(name, **params)
        self.frr_dir = f'/tmp/frr_{name}'
        
    def config(self, **params):
        super(FRRNode, self).config(**params)
        # Bật IP forwarding
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')
        
        # Tạo thư mục cho FRR config
        self.cmd(f'mkdir -p {self.frr_dir}')
        
        # Khởi tạo FRR daemons (nếu cần)
        # Lưu ý: Cần cài đặt FRR trên hệ thống
        info(f'*** {self.name}: FRR node initialized\n')
    
    def start(self, controllers=None):
        """Start method để tương thích khi được sử dụng như router"""
        # FRR node không cần controllers như switch
        pass
        
    def terminate(self):
        # Cleanup FRR processes
        self.cmd('killall -9 zebra staticd bgpd ospfd 2> /dev/null')
        super(FRRNode, self).terminate()



class SpineLeafTopo(Topo):
    """
    Spine-Leaf Topology với VXLAN
    
    Cấu trúc:
    - Spine Layer: s1, s2 (FRR routers)
    - Leaf Layer: s3 (Admin), s4 (Lab), s5 (KTX), s6 (Internet), s7 (HCM) (FRR routers)
    """
    
    def build(self):
        info('*** Đang xây dựng Spine-Leaf Topology\n')
        
        # ===========================================
        # 1. TẠO SPINE ROUTERS (Core Layer)
        # ===========================================
        info('*** Tạo Spine routers\n')
        s1 = self.addHost('s1', cls=FRRNode, ip='1.1.1.1/32')  # Spine 1
        s2 = self.addHost('s2', cls=FRRNode, ip='1.1.1.2/32')  # Spine 2
        
        # ===========================================
        # 2. TẠO OVS BRIDGES (Layer 2 Switching)
        # ===========================================
        info('*** Tạo OVS bridges cho Layer 2 switching\n')
        br_s3 = self.addSwitch('br-s3')  # Bridge cho Admin VLAN
        br_s4 = self.addSwitch('br-s4')  # Bridge cho Lab VLAN
        br_s5 = self.addSwitch('br-s5')  # Bridge cho KTX VLAN
        br_s6 = self.addSwitch('br-s6')  # Bridge cho Internet
        br_s7 = self.addSwitch('br-s7')  # Bridge cho ServerQ7
        
        # ===========================================
        # 3. TẠO LEAF ROUTERS (Access/Distribution Layer)
        # ===========================================
        info('*** Tạo Leaf routers\n')
        s3 = self.addHost('s3', cls=FRRNode, ip='1.1.1.3/32')  # Leaf Admin
        s4 = self.addHost('s4', cls=FRRNode, ip='1.1.1.4/32')  # Leaf Lab
        s5 = self.addHost('s5', cls=FRRNode, ip='1.1.1.5/32')  # Leaf KTX
        s6 = self.addHost('s6', cls=FRRNode, ip='1.1.1.6/32')  # Border Internet
        s7 = self.addHost('s7', cls=FRRNode, ip='1.1.1.7/32')  # Border HCM
        
        # ===========================================
        # 4. TẠO END HOSTS
        # ===========================================
        info('*** Tạo hosts\n')
        
        # VLAN 10 - Admin (kết nối với s3)
        admin1 = self.addHost('admin1', ip='192.168.10.10/24', 
                             defaultRoute='via 192.168.10.1')
        admin2 = self.addHost('admin2', ip='192.168.10.11/24',
                             defaultRoute='via 192.168.10.1')
        
        # VLAN 20 - Lab (kết nối với s4)
        lab1 = self.addHost('lab1', ip='192.168.20.10/24',
                           defaultRoute='via 192.168.20.1')
        lab2 = self.addHost('lab2', ip='192.168.20.11/24',
                           defaultRoute='via 192.168.20.1')
        
        # VLAN 30 - KTX (kết nối với s5)
        ktx1 = self.addHost('ktx1', ip='192.168.30.10/24',
                           defaultRoute='via 192.168.30.1')
        ktx2 = self.addHost('ktx2', ip='192.168.30.11/24',
                           defaultRoute='via 192.168.30.1')
        
        # Server bên ngoài (kết nối với Border Leaf)
        internet = self.addHost('internet', ip='203.0.113.2/30',
                               defaultRoute='via 203.0.113.1')
        serverq7 = self.addHost('serverq7', ip='172.16.1.2/30',
                               defaultRoute='via 172.16.1.1')
        
        # ===========================================
        # 5. KẾT NỐI HOSTS VỚI OVS BRIDGES (Layer 2)
        # ===========================================
        info('*** Kết nối hosts với OVS bridges\n')
        
        # Admin hosts -> br-s3 (OVS bridge)
        self.addLink(admin1, br_s3)
        self.addLink(admin2, br_s3)
        
        # Lab hosts -> br-s4 (OVS bridge)
        self.addLink(lab1, br_s4)
        self.addLink(lab2, br_s4)
        
        # KTX hosts -> br-s5 (OVS bridge)
        self.addLink(ktx1, br_s5)
        self.addLink(ktx2, br_s5)
        
        # External connections -> bridges
        self.addLink(internet, br_s6)
        self.addLink(serverq7, br_s7)
        
        # ===========================================
        # 6. KẾT NỐI OVS BRIDGES VỚI LEAF ROUTERS (Layer 3)
        # ===========================================
        info('*** Kết nối OVS bridges với Leaf routers\n')
        
        # Bridges kết nối với corresponding routers
        self.addLink(br_s3, s3)  # Admin bridge -> router
        self.addLink(br_s4, s4)  # Lab bridge -> router
        self.addLink(br_s5, s5)  # KTX bridge -> router
        self.addLink(br_s6, s6)  # Internet bridge -> router
        self.addLink(br_s7, s7)  # HCM bridge -> router
        
        # ===========================================
        # 7. KẾT NỐI SPINE-LEAF (FULL MESH)
        # ===========================================
        info('*** Tạo kết nối Full-mesh Spine-Leaf\n')
        
        # Spine s1 kết nối với tất cả Leaf
        self.addLink(s1, s3, cls=TCLink, bw=1000)  # s1-s3: 10.0.13.0/31
        self.addLink(s1, s4, cls=TCLink, bw=1000)  # s1-s4: 10.0.14.0/31
        self.addLink(s1, s5, cls=TCLink, bw=1000)  # s1-s5: 10.0.15.0/31
        self.addLink(s1, s6, cls=TCLink, bw=1000)  # s1-s6: 10.0.16.0/31
        self.addLink(s1, s7, cls=TCLink, bw=1000)  # s1-s7: 10.0.17.0/31
        
        # Spine s2 kết nối với tất cả Leaf
        self.addLink(s2, s3, cls=TCLink, bw=1000)  # s2-s3: 10.0.23.0/31
        self.addLink(s2, s4, cls=TCLink, bw=1000)  # s2-s4: 10.0.24.0/31
        self.addLink(s2, s5, cls=TCLink, bw=1000)  # s2-s5: 10.0.25.0/31
        self.addLink(s2, s6, cls=TCLink, bw=1000)  # s2-s6: 10.0.26.0/31
        self.addLink(s2, s7, cls=TCLink, bw=1000)  # s2-s7: 10.0.27.0/31
        
        info('*** Topology đã được xây dựng thành công!\n')


def configure_underlay(net):
    """
    Cấu hình Underlay Network (IP cho các link Point-to-Point và Bridge-Router)
    """
    info('\n*** Cấu hình Underlay Network\n')
    
    # ===========================================
    # 1. CẤU HÌNH LOOPBACK INTERFACES (VTEP)
    # ===========================================
    info('*** Cấu hình Loopback addresses cho VTEP\n')
    net['s1'].cmd('ip addr add 1.1.1.1/32 dev lo')
    net['s2'].cmd('ip addr add 1.1.1.2/32 dev lo')
    net['s3'].cmd('ip addr add 1.1.1.3/32 dev lo')
    net['s4'].cmd('ip addr add 1.1.1.4/32 dev lo')
    net['s5'].cmd('ip addr add 1.1.1.5/32 dev lo')
    net['s6'].cmd('ip addr add 1.1.1.6/32 dev lo')
    net['s7'].cmd('ip addr add 1.1.1.7/32 dev lo')
    
    # ===========================================
    # 2. CẤU HÌNH IP CHO ROUTER INTERFACES (Bridge-Router connection)
    # ===========================================
    info('*** Cấu hình gateway IPs trên Leaf routers\n')
    
    # s3 - Admin VLAN 10 (192.168.10.0/24)
    # Interface từ s3 đến br-s3
    s3_links = net['s3'].connectionsTo(net['br-s3'])
    if s3_links:
        intf = s3_links[0][0]  # Interface trên s3
        net['s3'].cmd(f'ip addr add 192.168.10.1/24 dev {intf}')
        info(f'    s3 {intf}: 192.168.10.1/24\n')
    
    # s4 - Lab VLAN 20 (192.168.20.0/24)
    s4_links = net['s4'].connectionsTo(net['br-s4'])
    if s4_links:
        intf = s4_links[0][0]
        net['s4'].cmd(f'ip addr add 192.168.20.1/24 dev {intf}')
        info(f'    s4 {intf}: 192.168.20.1/24\n')
    
    # s5 - KTX VLAN 30 (192.168.30.0/24)
    s5_links = net['s5'].connectionsTo(net['br-s5'])
    if s5_links:
        intf = s5_links[0][0]
        net['s5'].cmd(f'ip addr add 192.168.30.1/24 dev {intf}')
        info(f'    s5 {intf}: 192.168.30.1/24\n')
    
    # s6 - Internet (203.0.113.0/30)
    s6_links = net['s6'].connectionsTo(net['br-s6'])
    if s6_links:
        intf = s6_links[0][0]
        net['s6'].cmd(f'ip addr add 203.0.113.1/30 dev {intf}')
        info(f'    s6 {intf}: 203.0.113.1/30\n')
    
    # s7 - ServerQ7 HCM (172.16.1.0/30)
    s7_links = net['s7'].connectionsTo(net['br-s7'])
    if s7_links:
        intf = s7_links[0][0]
        net['s7'].cmd(f'ip addr add 172.16.1.1/30 dev {intf}')
        info(f'    s7 {intf}: 172.16.1.1/30\n')
    
    # ===========================================
    # 3. CẤU HÌNH IP CHO SPINE-LEAF LINKS
    # ===========================================
    info('*** Cấu hình Point-to-Point IPs cho Spine-Leaf links\n')
    
    # Định nghĩa IP cho từng link (sử dụng /31 để tiết kiệm)
    spine_leaf_ips = {
        # Format: (node1, node2): (ip1, ip2)
        ('s1', 's3'): ('10.0.13.0/31', '10.0.13.1/31'),
        ('s1', 's4'): ('10.0.14.0/31', '10.0.14.1/31'),
        ('s1', 's5'): ('10.0.15.0/31', '10.0.15.1/31'),
        ('s1', 's6'): ('10.0.16.0/31', '10.0.16.1/31'),
        ('s1', 's7'): ('10.0.17.0/31', '10.0.17.1/31'),
        ('s2', 's3'): ('10.0.23.0/31', '10.0.23.1/31'),
        ('s2', 's4'): ('10.0.24.0/31', '10.0.24.1/31'),
        ('s2', 's5'): ('10.0.25.0/31', '10.0.25.1/31'),
        ('s2', 's6'): ('10.0.26.0/31', '10.0.26.1/31'),
        ('s2', 's7'): ('10.0.27.0/31', '10.0.27.1/31'),
    }
    
    for (n1, n2), (ip1, ip2) in spine_leaf_ips.items():
        links = net[n1].connectionsTo(net[n2])
        if links:
            intf1, intf2 = links[0]
            net[n1].cmd(f'ip addr add {ip1} dev {intf1}')
            net[n2].cmd(f'ip addr add {ip2} dev {intf2}')
            info(f'    {n1} {intf1}: {ip1} <-> {n2} {intf2}: {ip2}\n')
    
    # ===========================================
    # 4. THÊM STATIC ROUTES (để các Leaf nhìn thấy nhau qua Spine)
    # ===========================================
    info('*** Cấu hình static routes\n')
    
    # Các Leaf routes để đến các mạng khác qua Spine
    # s3 (Admin) routes đến Lab và KTX
    net['s3'].cmd('ip route add 192.168.20.0/24 via 10.0.13.0')  # Qua s1
    net['s3'].cmd('ip route add 192.168.30.0/24 via 10.0.13.0')  # Qua s1
    net['s3'].cmd('ip route add 203.0.113.0/30 via 10.0.13.0')   # Internet
    net['s3'].cmd('ip route add 172.16.1.0/30 via 10.0.13.0')    # ServerQ7
    
    # s4 (Lab) routes đến Admin và KTX
    net['s4'].cmd('ip route add 192.168.10.0/24 via 10.0.14.0')  # Qua s1
    net['s4'].cmd('ip route add 192.168.30.0/24 via 10.0.14.0')  # Qua s1
    net['s4'].cmd('ip route add 203.0.113.0/30 via 10.0.14.0')   # Internet
    net['s4'].cmd('ip route add 172.16.1.0/30 via 10.0.14.0')    # ServerQ7
    
    # s5 (KTX) routes đến Admin và Lab
    net['s5'].cmd('ip route add 192.168.10.0/24 via 10.0.15.0')  # Qua s1
    net['s5'].cmd('ip route add 192.168.20.0/24 via 10.0.15.0')  # Qua s1
    net['s5'].cmd('ip route add 203.0.113.0/30 via 10.0.15.0')   # Internet
    net['s5'].cmd('ip route add 172.16.1.0/30 via 10.0.15.0')    # ServerQ7
    
    # s6 (Internet Border) routes đến internal networks
    net['s6'].cmd('ip route add 192.168.10.0/24 via 10.0.16.0')  # Admin
    net['s6'].cmd('ip route add 192.168.20.0/24 via 10.0.16.0')  # Lab
    net['s6'].cmd('ip route add 192.168.30.0/24 via 10.0.16.0')  # KTX
    net['s6'].cmd('ip route add 172.16.1.0/30 via 10.0.16.0')    # ServerQ7
    
    # s7 (HCM Border) routes đến internal networks
    net['s7'].cmd('ip route add 192.168.10.0/24 via 10.0.17.0')  # Admin
    net['s7'].cmd('ip route add 192.168.20.0/24 via 10.0.17.0')  # Lab
    net['s7'].cmd('ip route add 192.168.30.0/24 via 10.0.17.0')  # KTX
    net['s7'].cmd('ip route add 203.0.113.0/30 via 10.0.17.0')   # Internet
    
    # Spine s1 routes - nhận mọi traffic và forward đến đúng Leaf
    net['s1'].cmd('ip route add 192.168.10.0/24 via 10.0.13.1')  # s3
    net['s1'].cmd('ip route add 192.168.20.0/24 via 10.0.14.1')  # s4
    net['s1'].cmd('ip route add 192.168.30.0/24 via 10.0.15.1')  # s5
    net['s1'].cmd('ip route add 203.0.113.0/30 via 10.0.16.1')   # s6
    net['s1'].cmd('ip route add 172.16.1.0/30 via 10.0.17.1')    # s7
    
    # Spine s2 routes (backup routes)
    net['s2'].cmd('ip route add 192.168.10.0/24 via 10.0.23.1')  # s3
    net['s2'].cmd('ip route add 192.168.20.0/24 via 10.0.24.1')  # s4
    net['s2'].cmd('ip route add 192.168.30.0/24 via 10.0.25.1')  # s5
    net['s2'].cmd('ip route add 203.0.113.0/30 via 10.0.26.1')   # s6
    net['s2'].cmd('ip route add 172.16.1.0/30 via 10.0.27.1')    # s7
    
    info('*** Underlay Network đã được cấu hình!\n')



def configure_overlay(net):
    """
    Cấu hình Overlay Network (VXLAN với BGP EVPN)
    """
    info('\n*** Cấu hình Overlay Network (VXLAN)\n')
    
    # Mapping VLAN -> VNI
    vlan_vni_map = {
        10: 10010,  # Admin
        20: 10020,  # Lab
        30: 10030,  # KTX
        99: 10099,  # NMS
    }
    
    info('*** VLAN-VNI Mapping:\n')
    for vlan, vni in vlan_vni_map.items():
        info(f'    VLAN {vlan} -> VNI {vni}\n')
    
    # Cấu hình VXLAN interfaces trên các Leaf switches
    # Lưu ý: Cần sử dụng ovs-vsctl để tạo VXLAN tunnels
    # ovs-vsctl add-port <bridge> <vxlan_port> -- set interface <vxlan_port> type=vxlan options:remote_ip=<VTEP_IP> options:key=<VNI>
    
    info('*** Overlay VXLAN đã được thiết lập (cần cấu hình OVS chi tiết)\n')


def populate_arp_cache(net):
    """
    Populate ARP cache để giảm packet loss do ARP learning delay
    Gửi ping để các nodes học MAC addresses của nhau
    """
    info('\n*** Populate ARP cache và MAC learning\n')
    
    # ===========================================
    # 1. TỐI ƯU HÓA OVS BRIDGES
    # ===========================================
    info('*** Tối ưu hóa OVS bridges\n')
    
    # Disable STP (Spanning Tree Protocol) để tránh delay 30s
    for br in ['br-s3', 'br-s4', 'br-s5', 'br-s6', 'br-s7']:
        if br in net:
            net[br].cmd('ovs-vsctl set bridge {} stp_enable=false'.format(br))
            # Tăng MAC aging time lên 300s thay vì default 30s
            net[br].cmd('ovs-vsctl set bridge {} other-config:mac-aging-time=300'.format(br))
            info(f'    {br}: STP disabled, MAC aging = 300s\n')
    
    # ===========================================
    # 2. THÊM STATIC ARP ENTRIES CHO GATEWAYS
    # ===========================================
    info('*** Thêm static ARP entries cho gateways\n')
    
    # Danh sách các hosts và IPs
    hosts_ips = {
        'admin1': '192.168.10.10',
        'admin2': '192.168.10.11',
        'lab1': '192.168.20.10',
        'lab2': '192.168.20.11',
        'ktx1': '192.168.30.10',
        'ktx2': '192.168.30.11',
        'internet': '203.0.113.2',
        'serverq7': '172.16.1.2',
    }
    
    # Lấy MAC addresses của router interfaces và add static ARP
    for host_name, host_ip in hosts_ips.items():
        host = net[host_name]
        
        # Add ARP entry cho gateway
        if '192.168.10' in host_ip:
            # Admin VLAN gateway
            s3_intf = net['s3'].connectionsTo(net['br-s3'])[0][0]
            gw_mac = net['s3'].cmd(f'cat /sys/class/net/{s3_intf}/address').strip()
            host.cmd(f'arp -s 192.168.10.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.10.1 -> {gw_mac}\n')
        elif '192.168.20' in host_ip:
            # Lab VLAN gateway
            s4_intf = net['s4'].connectionsTo(net['br-s4'])[0][0]
            gw_mac = net['s4'].cmd(f'cat /sys/class/net/{s4_intf}/address').strip()
            host.cmd(f'arp -s 192.168.20.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.20.1 -> {gw_mac}\n')
        elif '192.168.30' in host_ip:
            # KTX VLAN gateway
            s5_intf = net['s5'].connectionsTo(net['br-s5'])[0][0]
            gw_mac = net['s5'].cmd(f'cat /sys/class/net/{s5_intf}/address').strip()
            host.cmd(f'arp -s 192.168.30.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.30.1 -> {gw_mac}\n')
    
    # ===========================================
    # 3. PRIME ARP CACHE VỚI COMPREHENSIVE PINGS
    # ===========================================
    info('*** Priming ARP cache với comprehensive pings...\n')
    
    # Ping tất cả hosts trong cùng VLAN
    net['admin1'].cmd('ping -c 2 -W 1 192.168.10.11 > /dev/null 2>&1 &')
    net['admin2'].cmd('ping -c 2 -W 1 192.168.10.10 > /dev/null 2>&1 &')
    
    net['lab1'].cmd('ping -c 2 -W 1 192.168.20.11 > /dev/null 2>&1 &')
    net['lab2'].cmd('ping -c 2 -W 1 192.168.20.10 > /dev/null 2>&1 &')
    
    net['ktx1'].cmd('ping -c 2 -W 1 192.168.30.11 > /dev/null 2>&1 &')
    net['ktx2'].cmd('ping -c 2 -W 1 192.168.30.10 > /dev/null 2>&1 &')
    
    # Ping gateways để populate router ARP
    net['admin1'].cmd('ping -c 2 -W 1 192.168.10.1 > /dev/null 2>&1 &')
    net['lab1'].cmd('ping -c 2 -W 1 192.168.20.1 > /dev/null 2>&1 &')
    net['ktx1'].cmd('ping -c 2 -W 1 192.168.30.1 > /dev/null 2>&1 &')
    
    # Ping cross-VLAN để build routing paths
    net['admin1'].cmd('ping -c 2 -W 1 192.168.20.10 > /dev/null 2>&1 &')
    net['admin1'].cmd('ping -c 2 -W 1 192.168.30.10 > /dev/null 2>&1 &')
    
    # Đợi đủ lâu để tất cả ARP requests hoàn tất
    import time
    info('    Đợi ARP learning hoàn tất...\n')
    time.sleep(2)  # Tăng lên 2 giây
    
    info('*** ARP cache và MAC learning đã được populated!\n')


def cleanup():
    """
    Hàm cleanup để dọn dẹp môi trường Mininet
    Chạy lệnh: sudo mn -c
    """
    info('\n*** Đang cleanup Mininet...\n')
    os.system('sudo mn -c')
    info('*** Cleanup hoàn tất!\n')


def test_connectivity(net):
    """
    Test kết nối giữa các hosts trong các VLAN khác nhau
    """
    info('\n' + '='*60 + '\n')
    info('*** KIỂM TRA KẾT NỐI MẠNG\n')
    info('='*60 + '\n')
    
    # Test 1: Ping trong cùng VLAN
    info('\n[Test 1] Ping trong cùng VLAN (Admin):\n')
    result = net['admin1'].cmd('ping -c 2 192.168.10.11')
    info(f'{result}\n')
    
    # Test 2: Ping giữa các VLAN khác nhau
    info('\n[Test 2] Ping giữa VLAN Admin -> Lab:\n')
    result = net['admin1'].cmd('ping -c 2 192.168.20.10')
    info(f'{result}\n')
    
    info('\n[Test 3] Ping giữa VLAN Lab -> KTX:\n')
    result = net['lab1'].cmd('ping -c 2 192.168.30.10')
    info(f'{result}\n')
    
    info('\n[Test 4] Ping đến Internet gateway:\n')
    result = net['admin1'].cmd('ping -c 2 203.0.113.2')
    info(f'{result}\n')
    
    info('\n[Test 5] Ping đến ServerQ7:\n')
    result = net['lab1'].cmd('ping -c 2 172.16.1.2')
    info(f'{result}\n')
    
    info('='*60 + '\n')


def visualize_topology():
    """
    Vẽ và lưu sơ đồ topology sử dụng NetworkX
    """
    info('\n*** Đang tạo visualization cho topology...\n')
    
    # Tạo graph
    G = nx.Graph()
    
    # Thêm nodes
    # Spine routers
    spine_nodes = ['s1', 's2']
    # Leaf routers
    leaf_nodes = ['s3', 's4', 's5', 's6', 's7']
    # OVS Bridges
    bridge_nodes = ['br-s3', 'br-s4', 'br-s5', 'br-s6', 'br-s7']
    # Hosts
    host_nodes = ['admin1', 'admin2', 'lab1', 'lab2', 'ktx1', 'ktx2', 'internet', 'serverq7']
    
    G.add_nodes_from(spine_nodes)
    G.add_nodes_from(leaf_nodes)
    G.add_nodes_from(bridge_nodes)
    G.add_nodes_from(host_nodes)
    
    # Thêm edges (Spine-Leaf connections - Full mesh)
    for spine in spine_nodes:
        for leaf in leaf_nodes:
            G.add_edge(spine, leaf)
    
    # Thêm bridge-router connections
    G.add_edge('br-s3', 's3')
    G.add_edge('br-s4', 's4')
    G.add_edge('br-s5', 's5')
    G.add_edge('br-s6', 's6')
    G.add_edge('br-s7', 's7')
    
    # Thêm host-bridge connections
    G.add_edge('admin1', 'br-s3')
    G.add_edge('admin2', 'br-s3')
    G.add_edge('lab1', 'br-s4')
    G.add_edge('lab2', 'br-s4')
    G.add_edge('ktx1', 'br-s5')
    G.add_edge('ktx2', 'br-s5')
    G.add_edge('internet', 'br-s6')
    G.add_edge('serverq7', 'br-s7')
    
    # Tạo layout
    pos = {}
    
    # Position cho Spine layer (top)
    for i, node in enumerate(spine_nodes):
        pos[node] = (i * 3 + 4.5, 12)
    
    # Position cho Leaf layer (upper middle)
    for i, node in enumerate(leaf_nodes):
        pos[node] = (i * 2.5, 8)
    
    # Position cho Bridge layer (lower middle)
    for i, node in enumerate(bridge_nodes):
        pos[node] = (i * 2.5, 4)
    
    # Position cho Hosts (bottom)
    pos['admin1'] = (-0.5, 0)
    pos['admin2'] = (1, 0)
    pos['lab1'] = (2, 0)
    pos['lab2'] = (3, 0)
    pos['ktx1'] = (4.5, 0)
    pos['ktx2'] = (5.5, 0)
    pos['internet'] = (7, 0)
    pos['serverq7'] = (9, 0)
    
    # Vẽ graph
    plt.figure(figsize=(18, 12))
    
    # Vẽ nodes với màu sắc khác nhau
    nx.draw_networkx_nodes(G, pos, nodelist=spine_nodes, 
                          node_color='#FF6B6B', node_size=2500, 
                          label='Spine Routers', node_shape='s')
    nx.draw_networkx_nodes(G, pos, nodelist=leaf_nodes, 
                          node_color='#4ECDC4', node_size=2500, 
                          label='Leaf Routers', node_shape='s')
    nx.draw_networkx_nodes(G, pos, nodelist=bridge_nodes, 
                          node_color='#FFD93D', node_size=2000, 
                          label='OVS Bridges', node_shape='o')
    nx.draw_networkx_nodes(G, pos, nodelist=host_nodes, 
                          node_color='#95E1D3', node_size=1500, 
                          label='Hosts', node_shape='o')
    
    # Vẽ edges
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6, edge_color='#34495E')
    
    # Vẽ labels
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold')
    
    plt.title('Spine-Leaf VXLAN Topology with OVS Bridges\\nBao Loc Campus Network', 
              fontsize=18, fontweight='bold', pad=20)
    plt.legend(loc='upper right', fontsize=12, framealpha=0.9)
    plt.axis('off')
    plt.tight_layout()
    
    # Lưu file
    output_file = 'topology_visualization.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    info(f'*** Topology visualization đã được lưu: {output_file}\n')
    
    return output_file


def run():
    """
    Hàm chính để chạy Mininet với topology đã định nghĩa
    """
    # Cleanup trước khi bắt đầu
    cleanup()
    
    # Set log level
    setLogLevel('info')
    
    # Tạo topology
    topo = SpineLeafTopo()
    
    # Tạo network
    info('\n*** Đang khởi tạo Mininet network...\n')
    net = Mininet(topo=topo, link=TCLink, autoSetMacs=True, autoStaticArp=True)
    
    # Start network
    info('\n*** Đang start network...\n')
    net.start()
    
    # Cấu hình Underlay và Overlay
    configure_underlay(net)
    configure_overlay(net)
    
    # Populate ARP cache để giảm packet loss
    populate_arp_cache(net)
    
    # Hiển thị thông tin
    info('\n' + '='*60 + '\n')
    info('*** SPINE-LEAF VXLAN TOPOLOGY - Bao Loc Campus Network\n')
    info('='*60 + '\n')
    info('\nThông tin Topology:\n')
    info('  - Spine Routers: s1 (1.1.1.1), s2 (1.1.1.2)\n')
    info('  - Leaf Routers:\n')
    info('      s3 (1.1.1.3) - Admin VLAN 10\n')
    info('      s4 (1.1.1.4) - Lab VLAN 20\n')
    info('      s5 (1.1.1.5) - KTX VLAN 30\n')
    info('      s6 (1.1.1.6) - Internet Border\n')
    info('      s7 (1.1.1.7) - HCM Server Border\n')
    info('\nVLAN Mapping:\n')
    info('  - VLAN 10 (VNI 10010): Admin - 192.168.10.0/24\n')
    info('  - VLAN 20 (VNI 10020): Lab - 192.168.20.0/24\n')
    info('  - VLAN 30 (VNI 10030): KTX - 192.168.30.0/24\n')
    info('\n' + '='*60 + '\n')
    
    # Test connectivity
    #test_connectivity(net)
    
    # Mở CLI
    info('\n*** Đang mở Mininet CLI (gõ "exit" để thoát)...\n')
    CLI(net)
    
    # Stop network
    info('\n*** Đang dừng network...\n')
    net.stop()
    
    # Cleanup sau khi xong
    cleanup()


if __name__ == '__main__':
    # Kiểm tra quyền root
    if os.geteuid() != 0:
        print("Script này cần quyền root. Vui lòng chạy với sudo:")
        print("  sudo python3 cauhinh.py")
        sys.exit(1)
    
    # Kiểm tra tham số
    if len(sys.argv) > 1:
        if sys.argv[1] == 'visualize':
            # Chỉ tạo visualization
            visualize_topology()
        elif sys.argv[1] == 'clean':
            # Chỉ cleanup
            cleanup()
        else:
            print("Tham số không hợp lệ!")
            print("Sử dụng:")
            print("  sudo python3 cauhinh.py          - Chạy topology")
            print("  python3 cauhinh.py visualize     - Chỉ tạo visualization")
            print("  sudo python3 cauhinh.py clean    - Chỉ cleanup")
    else:
        # Chạy topology và tạo visualization
        visualize_topology()
        run()

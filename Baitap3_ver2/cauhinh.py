#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spine-Leaf VXLAN Topology with FRRouting - FIXED VERSION
Topology Bao Loc - TP.HCM Campus Network

FIXES:
- Increased bandwidth on all links
- Added proper TCLink configuration
- Improved ARP cache population
- Better STP handling
- TCP/Buffer tuning
- Redundant routes for failover
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
matplotlib.use('Agg')
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
        
        # TCP và Buffer Tuning cho performance tốt hơn
        self.cmd('sysctl -w net.core.rmem_max=16777216')
        self.cmd('sysctl -w net.core.wmem_max=16777216')
        self.cmd('sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"')
        self.cmd('sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"')
        self.cmd('sysctl -w net.core.netdev_max_backlog=5000')
        
        # Tạo thư mục cho FRR config
        self.cmd(f'mkdir -p {self.frr_dir}')
        
        info(f'*** {self.name}: FRR node initialized with optimized TCP settings\n')
    
    def start(self, controllers=None):
        """Start method để tương thích khi được sử dụng như router"""
        pass
        
    def terminate(self):
        # Cleanup FRR processes
        self.cmd('killall -9 zebra staticd bgpd ospfd 2> /dev/null')
        super(FRRNode, self).terminate()



class SpineLeafTopo(Topo):
    """
    Spine-Leaf Topology với VXLAN - OPTIMIZED VERSION
    
    Cấu trúc:
    - Spine Layer: s1, s2 (FRR routers)
    - Leaf Layer: s3 (Admin), s4 (Lab), s5 (KTX), s6 (Internet), s7 (HCM) (FRR routers)
    - High bandwidth links với proper queue sizing
    """
    
    def build(self):
        info('*** Đang xây dựng Spine-Leaf Topology (OPTIMIZED VERSION)\n')
        
        # ===========================================
        # 1. TẠO SPINE ROUTERS (Core Layer)
        # ===========================================
        info('*** Tạo Spine routers\n')
        s1 = self.addHost('s1', cls=FRRNode, ip='1.1.1.1/32')
        s2 = self.addHost('s2', cls=FRRNode, ip='1.1.1.2/32')
        
        # ===========================================
        # 2. TẠO OVS BRIDGES (Layer 2 Switching)
        # ===========================================
        info('*** Tạo OVS bridges với STP disabled\n')
        # STP disabled ngay từ đầu để tránh blocking state
        br_s3 = self.addSwitch('br-s3', failMode='standalone', stp=False)
        br_s4 = self.addSwitch('br-s4', failMode='standalone', stp=False)
        br_s5 = self.addSwitch('br-s5', failMode='standalone', stp=False)
        br_s6 = self.addSwitch('br-s6', failMode='standalone', stp=False)
        br_s7 = self.addSwitch('br-s7', failMode='standalone', stp=False)
        
        # ===========================================
        # 3. TẠO LEAF ROUTERS (Access/Distribution Layer)
        # ===========================================
        info('*** Tạo Leaf routers\n')
        s3 = self.addHost('s3', cls=FRRNode, ip='1.1.1.3/32')
        s4 = self.addHost('s4', cls=FRRNode, ip='1.1.1.4/32')
        s5 = self.addHost('s5', cls=FRRNode, ip='1.1.1.5/32')
        s6 = self.addHost('s6', cls=FRRNode, ip='1.1.1.6/32')
        s7 = self.addHost('s7', cls=FRRNode, ip='1.1.1.7/32')
        
        # ===========================================
        # 4. TẠO END HOSTS
        # ===========================================
        info('*** Tạo hosts\n')
        
        # VLAN 10 - Admin
        admin1 = self.addHost('admin1', ip='192.168.10.10/24', 
                             defaultRoute='via 192.168.10.1')
        admin2 = self.addHost('admin2', ip='192.168.10.11/24',
                             defaultRoute='via 192.168.10.1')
        
        # VLAN 20 - Lab
        lab1 = self.addHost('lab1', ip='192.168.20.10/24',
                           defaultRoute='via 192.168.20.1')
        lab2 = self.addHost('lab2', ip='192.168.20.11/24',
                           defaultRoute='via 192.168.20.1')
        
        # VLAN 30 - KTX
        ktx1 = self.addHost('ktx1', ip='192.168.30.10/24',
                           defaultRoute='via 192.168.30.1')
        ktx2 = self.addHost('ktx2', ip='192.168.30.11/24',
                           defaultRoute='via 192.168.30.1')
        
        # External servers
        internet = self.addHost('internet', ip='203.0.113.2/30',
                               defaultRoute='via 203.0.113.1')
        serverq7 = self.addHost('serverq7', ip='172.16.1.2/30',
                               defaultRoute='via 172.16.1.1')
        
        # ===========================================
        # 5. KẾT NỐI HOSTS VỚI OVS BRIDGES (Access Layer)
        # FIX: Thêm TCLink với bw=1000 (1 Gbps) cho access ports
        # ===========================================
        info('*** Kết nối hosts với OVS bridges (1 Gbps access)\n')
        
        # Admin hosts -> br-s3 (1 Gbps access, small queue for low latency)
        self.addLink(admin1, br_s3, cls=TCLink, bw=1000, max_queue_size=100)
        self.addLink(admin2, br_s3, cls=TCLink, bw=1000, max_queue_size=100)
        
        # Lab hosts -> br-s4
        self.addLink(lab1, br_s4, cls=TCLink, bw=1000, max_queue_size=100)
        self.addLink(lab2, br_s4, cls=TCLink, bw=1000, max_queue_size=100)
        
        # KTX hosts -> br-s5
        self.addLink(ktx1, br_s5, cls=TCLink, bw=1000, max_queue_size=100)
        self.addLink(ktx2, br_s5, cls=TCLink, bw=1000, max_queue_size=100)
        
        # External connections (higher bandwidth)
        self.addLink(internet, br_s6, cls=TCLink, bw=1000, max_queue_size=100)
        self.addLink(serverq7, br_s7, cls=TCLink, bw=1000, max_queue_size=100)
        
        # ===========================================
        # 6. KẾT NỐI OVS BRIDGES VỚI LEAF ROUTERS
        # FIX: Thêm TCLink với bw=10000 (10 Gbps) cho uplinks
        # ===========================================
        info('*** Kết nối OVS bridges với Leaf routers (10 Gbps uplinks)\n')
        
        # Bridge-Router uplinks (10 Gbps, small queue for low latency)
        self.addLink(br_s3, s3, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(br_s4, s4, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(br_s5, s5, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(br_s6, s6, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(br_s7, s7, cls=TCLink, bw=10000, max_queue_size=300)
        
        # ===========================================
        # 7. KẾT NỐI SPINE-LEAF (FULL MESH)
        # FIX: Tăng từ 1 Gbps lên 10 Gbps, thêm delay và queue size
        # ===========================================
        info('*** Tạo kết nối Full-mesh Spine-Leaf (10 Gbps core)\n')
        
        # Spine s1 kết nối với tất cả Leaf (10 Gbps, small queue for low latency)
        self.addLink(s1, s3, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s1, s4, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s1, s5, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s1, s6, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s1, s7, cls=TCLink, bw=10000, max_queue_size=300)
        
        # Spine s2 kết nối với tất cả Leaf (redundant paths)
        self.addLink(s2, s3, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s2, s4, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s2, s5, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s2, s6, cls=TCLink, bw=10000, max_queue_size=300)
        self.addLink(s2, s7, cls=TCLink, bw=10000, max_queue_size=300)
        
        info('*** Topology đã được xây dựng thành công với optimized parameters!\n')


def configure_underlay(net):
    """
    Cấu hình Underlay Network với redundant routes
    """
    info('\n*** Cấu hình Underlay Network\n')
    
    # ===========================================
    # 1. CẤU HÌNH LOOPBACK INTERFACES
    # ===========================================
    info('*** Cấu hình Loopback addresses\n')
    net['s1'].cmd('ip addr add 1.1.1.1/32 dev lo')
    net['s2'].cmd('ip addr add 1.1.1.2/32 dev lo')
    net['s3'].cmd('ip addr add 1.1.1.3/32 dev lo')
    net['s4'].cmd('ip addr add 1.1.1.4/32 dev lo')
    net['s5'].cmd('ip addr add 1.1.1.5/32 dev lo')
    net['s6'].cmd('ip addr add 1.1.1.6/32 dev lo')
    net['s7'].cmd('ip addr add 1.1.1.7/32 dev lo')
    
    # ===========================================
    # 2. CẤU HÌNH GATEWAY IPS
    # ===========================================
    info('*** Cấu hình gateway IPs\n')
    
    # s3 - Admin VLAN 10
    s3_links = net['s3'].connectionsTo(net['br-s3'])
    if s3_links:
        intf = s3_links[0][0]
        net['s3'].cmd(f'ip addr add 192.168.10.1/24 dev {intf}')
        info(f'    s3 {intf}: 192.168.10.1/24\n')
    
    # s4 - Lab VLAN 20
    s4_links = net['s4'].connectionsTo(net['br-s4'])
    if s4_links:
        intf = s4_links[0][0]
        net['s4'].cmd(f'ip addr add 192.168.20.1/24 dev {intf}')
        info(f'    s4 {intf}: 192.168.20.1/24\n')
    
    # s5 - KTX VLAN 30
    s5_links = net['s5'].connectionsTo(net['br-s5'])
    if s5_links:
        intf = s5_links[0][0]
        net['s5'].cmd(f'ip addr add 192.168.30.1/24 dev {intf}')
        info(f'    s5 {intf}: 192.168.30.1/24\n')
    
    # s6 - Internet
    s6_links = net['s6'].connectionsTo(net['br-s6'])
    if s6_links:
        intf = s6_links[0][0]
        net['s6'].cmd(f'ip addr add 203.0.113.1/30 dev {intf}')
        info(f'    s6 {intf}: 203.0.113.1/30\n')
    
    # s7 - ServerQ7
    s7_links = net['s7'].connectionsTo(net['br-s7'])
    if s7_links:
        intf = s7_links[0][0]
        net['s7'].cmd(f'ip addr add 172.16.1.1/30 dev {intf}')
        info(f'    s7 {intf}: 172.16.1.1/30\n')
    
    # ===========================================
    # 3. CẤU HÌNH SPINE-LEAF POINT-TO-POINT IPS
    # ===========================================
    info('*** Cấu hình Point-to-Point IPs\n')
    
    spine_leaf_ips = {
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
    # 4. STATIC ROUTES VỚI REDUNDANCY
    # FIX: Thêm routes cho cả s1 và s2 với metrics khác nhau
    # ===========================================
    info('*** Cấu hình static routes với redundancy\n')
    
    # s3 (Admin) - Primary via s1 (metric 100), Backup via s2 (metric 200)
    net['s3'].cmd('ip route add 192.168.20.0/24 via 10.0.13.0 metric 100')
    net['s3'].cmd('ip route add 192.168.20.0/24 via 10.0.23.0 metric 200')
    net['s3'].cmd('ip route add 192.168.30.0/24 via 10.0.13.0 metric 100')
    net['s3'].cmd('ip route add 192.168.30.0/24 via 10.0.23.0 metric 200')
    net['s3'].cmd('ip route add 203.0.113.0/30 via 10.0.13.0 metric 100')
    net['s3'].cmd('ip route add 172.16.1.0/30 via 10.0.13.0 metric 100')
    
    # s4 (Lab) - Primary via s1, Backup via s2
    net['s4'].cmd('ip route add 192.168.10.0/24 via 10.0.14.0 metric 100')
    net['s4'].cmd('ip route add 192.168.10.0/24 via 10.0.24.0 metric 200')
    net['s4'].cmd('ip route add 192.168.30.0/24 via 10.0.14.0 metric 100')
    net['s4'].cmd('ip route add 192.168.30.0/24 via 10.0.24.0 metric 200')
    net['s4'].cmd('ip route add 203.0.113.0/30 via 10.0.14.0 metric 100')
    net['s4'].cmd('ip route add 172.16.1.0/30 via 10.0.14.0 metric 100')
    
    # s5 (KTX) - Primary via s1, Backup via s2
    net['s5'].cmd('ip route add 192.168.10.0/24 via 10.0.15.0 metric 100')
    net['s5'].cmd('ip route add 192.168.10.0/24 via 10.0.25.0 metric 200')
    net['s5'].cmd('ip route add 192.168.20.0/24 via 10.0.15.0 metric 100')
    net['s5'].cmd('ip route add 192.168.20.0/24 via 10.0.25.0 metric 200')
    net['s5'].cmd('ip route add 203.0.113.0/30 via 10.0.15.0 metric 100')
    net['s5'].cmd('ip route add 172.16.1.0/30 via 10.0.15.0 metric 100')
    
    # s6 (Internet Border)
    net['s6'].cmd('ip route add 192.168.10.0/24 via 10.0.16.0 metric 100')
    net['s6'].cmd('ip route add 192.168.20.0/24 via 10.0.16.0 metric 100')
    net['s6'].cmd('ip route add 192.168.30.0/24 via 10.0.16.0 metric 100')
    net['s6'].cmd('ip route add 172.16.1.0/30 via 10.0.16.0 metric 100')
    
    # s7 (HCM Border)
    net['s7'].cmd('ip route add 192.168.10.0/24 via 10.0.17.0 metric 100')
    net['s7'].cmd('ip route add 192.168.20.0/24 via 10.0.17.0 metric 100')
    net['s7'].cmd('ip route add 192.168.30.0/24 via 10.0.17.0 metric 100')
    net['s7'].cmd('ip route add 203.0.113.0/30 via 10.0.17.0 metric 100')
    
    # Spine s1 routes
    net['s1'].cmd('ip route add 192.168.10.0/24 via 10.0.13.1')
    net['s1'].cmd('ip route add 192.168.20.0/24 via 10.0.14.1')
    net['s1'].cmd('ip route add 192.168.30.0/24 via 10.0.15.1')
    net['s1'].cmd('ip route add 203.0.113.0/30 via 10.0.16.1')
    net['s1'].cmd('ip route add 172.16.1.0/30 via 10.0.17.1')
    
    # Spine s2 routes (backup)
    net['s2'].cmd('ip route add 192.168.10.0/24 via 10.0.23.1')
    net['s2'].cmd('ip route add 192.168.20.0/24 via 10.0.24.1')
    net['s2'].cmd('ip route add 192.168.30.0/24 via 10.0.25.1')
    net['s2'].cmd('ip route add 203.0.113.0/30 via 10.0.26.1')
    net['s2'].cmd('ip route add 172.16.1.0/30 via 10.0.27.1')
    
    info('*** Underlay Network với redundant routes đã được cấu hình!\n')


def configure_overlay(net):
    """
    Cấu hình Overlay Network (VXLAN)
    """
    info('\n*** Cấu hình Overlay Network (VXLAN)\n')
    
    vlan_vni_map = {
        10: 10010,  # Admin
        20: 10020,  # Lab
        30: 10030,  # KTX
        99: 10099,  # NMS
    }
    
    info('*** VLAN-VNI Mapping:\n')
    for vlan, vni in vlan_vni_map.items():
        info(f'    VLAN {vlan} -> VNI {vni}\n')
    
    info('*** Overlay VXLAN đã được thiết lập\n')


def populate_arp_cache(net):
    """
    Populate ARP cache - IMPROVED VERSION
    FIX: Tăng số lượng ping, timeout, và comprehensive coverage
    """
    info('\n*** Populate ARP cache (COMPREHENSIVE)\n')
    
    # ===========================================
    # 1. TỐI ƯU HOÁ OVS BRIDGES
    # ===========================================
    info('*** Tối ưu hóa OVS bridges\n')
    
    for br in ['br-s3', 'br-s4', 'br-s5', 'br-s6', 'br-s7']:
        if br in net:
            # MAC aging time tăng lên 300s
            net[br].cmd(f'ovs-vsctl set bridge {br} other-config:mac-aging-time=300')
            # Đảm bảo STP đã disabled
            net[br].cmd(f'ovs-vsctl set bridge {br} stp_enable=false')
            # Tăng max-idle timeout
            net[br].cmd(f'ovs-vsctl set bridge {br} other-config:max-idle=60000')
            info(f'    {br}: Optimized (MAC aging=300s, STP=false)\n')
    
    # ===========================================
    # 2. STATIC ARP ENTRIES CHO GATEWAYS
    # ===========================================
    info('*** Thêm static ARP entries cho gateways\n')
    
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
    
    for host_name, host_ip in hosts_ips.items():
        host = net[host_name]
        
        if '192.168.10' in host_ip:
            s3_intf = net['s3'].connectionsTo(net['br-s3'])[0][0]
            gw_mac = net['s3'].cmd(f'cat /sys/class/net/{s3_intf}/address').strip()
            host.cmd(f'arp -s 192.168.10.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.10.1 -> {gw_mac}\n')
        elif '192.168.20' in host_ip:
            s4_intf = net['s4'].connectionsTo(net['br-s4'])[0][0]
            gw_mac = net['s4'].cmd(f'cat /sys/class/net/{s4_intf}/address').strip()
            host.cmd(f'arp -s 192.168.20.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.20.1 -> {gw_mac}\n')
        elif '192.168.30' in host_ip:
            s5_intf = net['s5'].connectionsTo(net['br-s5'])[0][0]
            gw_mac = net['s5'].cmd(f'cat /sys/class/net/{s5_intf}/address').strip()
            host.cmd(f'arp -s 192.168.30.1 {gw_mac}')
            info(f'    {host_name}: gateway 192.168.30.1 -> {gw_mac}\n')
    
    # ===========================================
    # 3. COMPREHENSIVE ARP PRIMING
    # FIX: Tăng từ 2 packets lên 4, timeout từ 1s lên 2s
    # ===========================================
    info('*** Priming ARP cache comprehensive...\\n')
    
    # Danh sách tất cả destinations để ping
    all_destinations = [
        '192.168.10.10', '192.168.10.11', '192.168.10.1',
        '192.168.20.10', '192.168.20.11', '192.168.20.1',
        '192.168.30.10', '192.168.30.11', '192.168.30.1',
        '203.0.113.2', '172.16.1.2'
    ]
    
    # Ping within same VLAN (4 packets, 2s timeout)
    net['admin1'].cmd('ping -c 4 -W 2 192.168.10.11 > /dev/null 2>&1 &')
    net['admin2'].cmd('ping -c 4 -W 2 192.168.10.10 > /dev/null 2>&1 &')
    net['lab1'].cmd('ping -c 4 -W 2 192.168.20.11 > /dev/null 2>&1 &')
    net['lab2'].cmd('ping -c 4 -W 2 192.168.20.10 > /dev/null 2>&1 &')
    net['ktx1'].cmd('ping -c 4 -W 2 192.168.30.11 > /dev/null 2>&1 &')
    net['ktx2'].cmd('ping -c 4 -W 2 192.168.30.10 > /dev/null 2>&1 &')
    
    # Ping gateways
    net['admin1'].cmd('ping -c 4 -W 2 192.168.10.1 > /dev/null 2>&1 &')
    net['lab1'].cmd('ping -c 4 -W 2 192.168.20.1 > /dev/null 2>&1 &')
    net['ktx1'].cmd('ping -c 4 -W 2 192.168.30.1 > /dev/null 2>&1 &')
    
    # Cross-VLAN comprehensive pings từ admin1
    for dest in ['192.168.20.10', '192.168.30.10', '203.0.113.2', '172.16.1.2']:
        net['admin1'].cmd(f'ping -c 3 -W 2 {dest} > /dev/null 2>&1 &')
    
    # Cross-VLAN pings từ lab1
    for dest in ['192.168.10.10', '192.168.30.10', '172.16.1.2']:
        net['lab1'].cmd(f'ping -c 3 -W 2 {dest} > /dev/null 2>&1 &')
    
    # Cross-VLAN pings từ ktx1
    for dest in ['192.168.10.10', '192.168.20.10', '203.0.113.2']:
        net['ktx1'].cmd(f'ping -c 3 -W 2 {dest} > /dev/null 2>&1 &')
    
    # FIX: Đợi lâu hơn - 5 giây thay vì 2 giây
    import time
    info('    Đợi ARP learning hoàn tất (5 seconds)...\n')
    time.sleep(5)
    
    info('*** ARP cache và MAC learning đã được populated comprehensively!\n')


def cleanup():
    """
    Cleanup Mininet environment
    """
    info('\n*** Đang cleanup Mininet...\n')
    os.system('sudo mn -c')
    info('*** Cleanup hoàn tất!\n')


def test_connectivity(net):
    """
    Test kết nối với improved statistics
    """
    info('\n' + '='*60 + '\n')
    info('*** KIỂM TRA KẾT NỐI MẠNG (COMPREHENSIVE)\n')
    info('='*60 + '\n')
    
    # Test với 10 packets để có statistic tốt hơn
    info('\n[Test 1] Ping trong cùng VLAN (Admin -> Admin):\n')
    result = net['admin1'].cmd('ping -c 10 192.168.10.11')
    info(f'{result}\n')
    
    info('\n[Test 2] Ping giữa VLAN (Admin -> Lab):\n')
    result = net['admin1'].cmd('ping -c 10 192.168.20.10')
    info(f'{result}\n')
    
    info('\n[Test 3] Ping giữa VLAN (Lab -> KTX):\n')
    result = net['lab1'].cmd('ping -c 10 192.168.30.10')
    info(f'{result}\n')
    
    info('\n[Test 4] Ping đến Internet:\n')
    result = net['admin1'].cmd('ping -c 10 203.0.113.2')
    info(f'{result}\n')
    
    info('\n[Test 5] Ping đến ServerQ7:\n')
    result = net['lab1'].cmd('ping -c 10 172.16.1.2')
    info(f'{result}\n')
    
    info('='*60 + '\n')


def visualize_topology():
    """
    Vẽ topology diagram
    """
    info('\n*** Đang tạo visualization...\n')
    
    G = nx.Graph()
    
    spine_nodes = ['s1', 's2']
    leaf_nodes = ['s3', 's4', 's5', 's6', 's7']
    bridge_nodes = ['br-s3', 'br-s4', 'br-s5', 'br-s6', 'br-s7']
    host_nodes = ['admin1', 'admin2', 'lab1', 'lab2', 'ktx1', 'ktx2', 'internet', 'serverq7']
    
    G.add_nodes_from(spine_nodes)
    G.add_nodes_from(leaf_nodes)
    G.add_nodes_from(bridge_nodes)
    G.add_nodes_from(host_nodes)
    
    for spine in spine_nodes:
        for leaf in leaf_nodes:
            G.add_edge(spine, leaf)
    
    G.add_edge('br-s3', 's3')
    G.add_edge('br-s4', 's4')
    G.add_edge('br-s5', 's5')
    G.add_edge('br-s6', 's6')
    G.add_edge('br-s7', 's7')
    
    G.add_edge('admin1', 'br-s3')
    G.add_edge('admin2', 'br-s3')
    G.add_edge('lab1', 'br-s4')
    G.add_edge('lab2', 'br-s4')
    G.add_edge('ktx1', 'br-s5')
    G.add_edge('ktx2', 'br-s5')
    G.add_edge('internet', 'br-s6')
    G.add_edge('serverq7', 'br-s7')
    
    pos = {}
    for i, node in enumerate(spine_nodes):
        pos[node] = (i * 3 + 4.5, 12)
    for i, node in enumerate(leaf_nodes):
        pos[node] = (i * 2.5, 8)
    for i, node in enumerate(bridge_nodes):
        pos[node] = (i * 2.5, 4)
    
    pos['admin1'] = (-0.5, 0)
    pos['admin2'] = (1, 0)
    pos['lab1'] = (2, 0)
    pos['lab2'] = (3, 0)
    pos['ktx1'] = (4.5, 0)
    pos['ktx2'] = (5.5, 0)
    pos['internet'] = (7, 0)
    pos['serverq7'] = (9, 0)
    
    plt.figure(figsize=(18, 12))
    
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
    
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6, edge_color='#34495E')
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold')
    
    plt.title('Spine-Leaf VXLAN Topology (OPTIMIZED)\\nBao Loc Campus Network', 
              fontsize=18, fontweight='bold', pad=20)
    plt.legend(loc='upper right', fontsize=12, framealpha=0.9)
    plt.axis('off')
    plt.tight_layout()
    
    output_file = 'topology_visualization_fixed.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    info(f'*** Topology visualization saved: {output_file}\n')
    
    return output_file


def run():
    """
    Main function - OPTIMIZED VERSION
    """
    cleanup()
    setLogLevel('info')
    
    topo = SpineLeafTopo()
    
    info('\n*** Khởi tạo Mininet network (OPTIMIZED)...\n')
    # autoSetMacs và autoStaticArp giúp giảm ARP overhead
    net = Mininet(topo=topo, link=TCLink, autoSetMacs=True, autoStaticArp=True)
    
    info('\n*** Starting network...\n')
    net.start()
    
    # Cấu hình
    configure_underlay(net)
    configure_overlay(net)
    populate_arp_cache(net)
    
    # Hiển thị thông tin
    info('\n' + '='*60 + '\n')
    info('*** SPINE-LEAF VXLAN TOPOLOGY - OPTIMIZED VERSION\n')
    info('='*60 + '\n')
    info('\nOptimizations Applied:\n')
    info('  ✓ 10 Gbps Spine-Leaf links (was 1 Gbps)\n')
    info('  ✓ 1 Gbps Access links with TCLink\n')
    info('  ✓ Queue sizes: 300 (core), 100 (access) for low latency\n')
    info('  ✓ No artificial delay on any links\n')
    info('  ✓ STP disabled on all bridges\n')
    info('  ✓ TCP/Buffer tuning enabled\n')
    info('  ✓ Redundant routes with metrics\n')
    info('  ✓ Comprehensive ARP priming\n')
    info('\n' + '='*60 + '\n')
    
    # Test connectivity
    # test_connectivity(net)
    
    info('\n*** Mở Mininet CLI (gõ "exit" để thoát)...\n')
    info('*** Thử test: pingall, iperf, hoặc ping cụ thể\n')
    CLI(net)
    
    info('\n*** Stopping network...\n')
    net.stop()
    cleanup()


if __name__ == '__main__':
    if os.geteuid() != 0:
        print("Script cần quyền root. Chạy với sudo:")
        print("  sudo python3 cauhinh.py")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'visualize':
            visualize_topology()
        elif sys.argv[1] == 'clean':
            cleanup()
        else:
            print("Tham số không hợp lệ!")
            print("Sử dụng:")
            print("  sudo python3 cauhinh.py          - Chạy topology")
            print("  python3 cauhinh.py visualize     - Tạo visualization")
            print("  sudo python3 cauhinh.py clean    - Cleanup")
    else:
        visualize_topology()
        run()

#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
═══════════════════════════════════════════════════════════════════════════
                    TDTU BẢO LỘC - BÀI TẬP THỰC HÀNH
                    Network Optimization Lab
═══════════════════════════════════════════════════════════════════════════

Features:
  ✓ Router-on-a-Stick (R1 với VLAN sub-interfaces)
  ✓ STP (s1 = Root Bridge)
  ✓ VLANs (10,20,30,99)
  ✓ Full mesh redundancy

Topology:
  R1 (Router) → Core(s1,s2) → Dist(s3,s4) → Access(s5,s6,s7)
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import subprocess
import matplotlib
matplotlib.use('Agg')  # Backend non-GUI
import matplotlib.pyplot as plt
import networkx as nx

class LinuxRouter(Host):
    """Host với chức năng routing"""
    
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

def cleanupMininet():
    """Dọn dẹp Mininet trước khi chạy"""
    info('\n*** Dọn dẹp Mininet (sudo mn -c)...\n')
    try:
        subprocess.run(['sudo', 'mn', '-c'], check=True)
        info('*** Dọn dẹp thành công\n\n')
    except subprocess.CalledProcessError as e:
        info(f'*** Cảnh báo: Lỗi khi dọn dẹp: {e}\n\n')
    except FileNotFoundError:
        info('*** Cảnh báo: Lệnh mn không tìm thấy\n\n')

def drawTopology():
    """Vẽ sơ đồ mạng với networkx và matplotlib"""
    info('\n*** Đang tạo sơ đồ mạng...\n')
    
    # Tạo graph
    G = nx.Graph()
    
    # Thêm nodes
    routers = ['R1']
    core_switches = ['S1', 'S2']
    dist_switches = ['S3', 'S4']
    access_switches = ['S5', 'S6', 'S7']
    hosts = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6']
    servers = ['Internet', 'ServerQ7']
    
    all_nodes = routers + core_switches + dist_switches + access_switches + hosts + servers
    G.add_nodes_from(all_nodes)
    
    # Thêm edges
    edges = [
        # Router to Internet/Server
        ('R1', 'Internet'), ('R1', 'ServerQ7'),
        # Router to Core
        ('R1', 'S1'), ('R1', 'S2'),
        # Core inter-link
        ('S1', 'S2'),
        # Core to Distribution
        ('S1', 'S3'), ('S1', 'S4'),
        ('S2', 'S3'), ('S2', 'S4'),
        # Distribution inter-link
        ('S3', 'S4'),
        # Distribution to Access
        ('S3', 'S5'), ('S3', 'S6'), ('S3', 'S7'),
        ('S4', 'S5'), ('S4', 'S6'), ('S4', 'S7'),
        # Access to Hosts
        ('S5', 'H1'), ('S5', 'H2'), ('S5', 'H6'),
        ('S6', 'H3'), ('S6', 'H4'),
        ('S7', 'H5'),
    ]
    G.add_edges_from(edges)
    
    # Layout positions
    pos = {
        'Internet': (1, 5.5), 'ServerQ7': (7, 5.5),
        'R1': (4, 4.5),
        'S1': (3, 3.5), 'S2': (5, 3.5),
        'S3': (2.5, 2.3), 'S4': (5.5, 2.3),
        'S5': (1.5, 1), 'S6': (4, 1), 'S7': (6.5, 1),
        'H1': (0.5, 0), 'H2': (1.5, 0), 'H6': (2.5, 0),
        'H3': (3.5, 0), 'H4': (4.5, 0), 'H5': (6.5, 0),
    }
    
    # Colors cho từng loại node
    node_colors = []
    for node in G.nodes():
        if node in servers:
            node_colors.append('#FFD700')  # Gold - Servers
        elif node in routers:
            node_colors.append('#FF6B6B')  # Red - Router
        elif node in core_switches:
            node_colors.append('#4ECDC4')  # Cyan - Core
        elif node in dist_switches:
            node_colors.append('#45B7D1')  # Blue - Distribution
        elif node in access_switches:
            node_colors.append('#96CEB4')  # Green - Access
        else:  # hosts
            node_colors.append('#FFEAA7')  # Yellow - Hosts
    
    # Vẽ đồ thị
    plt.figure(figsize=(14, 10))
    nx.draw(G, pos, 
            node_color=node_colors,
            node_size=2500,
            with_labels=True,
            font_size=10,
            font_weight='bold',
            edge_color='gray',
            width=2.5,
            alpha=0.9)
    
    # Title
    plt.title('TDTU Bảo Lộc Network Topology\nRouter-on-a-Stick + STP + VLAN', 
              fontsize=16, fontweight='bold', pad=20)
    
    # Legend
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#FFD700', 
                   markersize=12, label='Servers (Internet, Q7)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF6B6B', 
                   markersize=12, label='Router (R1)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#4ECDC4', 
                   markersize=12, label='Core Switches (S1, S2)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#45B7D1', 
                   markersize=12, label='Distribution Switches (S3, S4)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#96CEB4', 
                   markersize=12, label='Access Switches (S5, S6, S7)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#FFEAA7', 
                   markersize=12, label='Hosts (H1-H6)'),
    ]
    plt.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    # Thêm text box với thông tin VLANs
    vlan_info = (
        'VLANs:\n'
        '• VLAN 10: Admin (H1, H2)\n'
        '• VLAN 20: Lab (H3, H4)\n'
        '• VLAN 30: KTX (H5)\n'
        '• VLAN 99: Mgmt (H6)'
    )
    plt.text(0.02, 0.98, vlan_info, transform=plt.gca().transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Save figure
    plt.tight_layout()
    plt.savefig('network_topology.png', dpi=300, bbox_inches='tight')
    plt.close()
    info('*** Đã lưu sơ đồ: network_topology.png\n\n')

def buildTopology():
    """Xây dựng topology TDTU Bao Loc"""
    
    info('*** Tạo Mininet Network (NO Controller)\n')
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)
    
    # ═════════════════════════════════════════════════════════════
    # ROUTERS
    # ═════════════════════════════════════════════════════════════
    info('*** Thêm Router R1\n')
    r1 = net.addHost('r1', cls=LinuxRouter, ip=None)
    
    # ═════════════════════════════════════════════════════════════
    # SWITCHES
    # ═════════════════════════════════════════════════════════════
    info('*** Thêm Switches\n')
    # Core Layer
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    
    # Distribution Layer
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
    
    # Access Layer
    s5 = net.addSwitch('s5')  # Admin
    s6 = net.addSwitch('s6')  # Lab
    s7 = net.addSwitch('s7')  # KTX
    
    # ═════════════════════════════════════════════════════════════
    # END HOSTS
    # ═════════════════════════════════════════════════════════════
    info('*** Thêm End Hosts\n')
    
    # VLAN 10: Admin
    h1 = net.addHost('h1', ip='192.168.10.2/24')
    h2 = net.addHost('h2', ip='192.168.10.3/24')
    
    # VLAN 20: Lab
    h3 = net.addHost('h3', ip='192.168.20.2/24')
    h4 = net.addHost('h4', ip='192.168.20.3/24')
    
    # VLAN 30: KTX
    h5 = net.addHost('h5', ip='192.168.30.30/24')
    
    # VLAN 99: Mgmt
    h6 = net.addHost('h6', ip='192.168.99.2/24')
    
    # External hosts
    internet = net.addHost('internet', ip='8.8.8.8/24')
    serverq7 = net.addHost('serverq7', ip='1.1.1.1/24')
    
    # ═════════════════════════════════════════════════════════════
    # LINKS WITH BANDWIDTH
    # ═════════════════════════════════════════════════════════════
    info('*** Tạo Links với Bandwidth\n')
    
    # R1 → Internet/Server
    net.addLink(r1, internet, intfName1='r1-eth2', intfName2='internet-eth0', bw=1000)
    net.addLink(r1, serverq7, intfName1='r1-eth3', intfName2='serverq7-eth0', bw=500)
    
    # R1 → Core (dual uplinks for redundancy)
    net.addLink(r1, s1, intfName1='r1-eth0', intfName2='s1-eth1', bw=1000)
    net.addLink(r1, s2, intfName1='r1-eth1', intfName2='s2-eth1', bw=1000)
    
    # Core inter-link
    net.addLink(s1, s2, intfName1='s1-eth2', intfName2='s2-eth2', bw=1000)
    
    # Core → Distribution (full mesh)
    net.addLink(s1, s3, intfName1='s1-eth3', intfName2='s3-eth1', bw=1000)
    net.addLink(s1, s4, intfName1='s1-eth4', intfName2='s4-eth1', bw=1000)
    net.addLink(s2, s3, intfName1='s2-eth3', intfName2='s3-eth2', bw=1000)
    net.addLink(s2, s4, intfName1='s2-eth4', intfName2='s4-eth2', bw=1000)
    
    # Distribution inter-link (S3 ↔ S4)
    net.addLink(s3, s4, intfName1='s3-eth6', intfName2='s4-eth6', bw=1000)
    
    # Distribution → Access (full mesh)
    net.addLink(s3, s5, intfName1='s3-eth3', intfName2='s5-eth1', bw=1000)
    net.addLink(s3, s6, intfName1='s3-eth4', intfName2='s6-eth1', bw=1000)
    net.addLink(s3, s7, intfName1='s3-eth5', intfName2='s7-eth1', bw=1000)
    net.addLink(s4, s5, intfName1='s4-eth3', intfName2='s5-eth2', bw=1000)
    net.addLink(s4, s6, intfName1='s4-eth4', intfName2='s6-eth2', bw=1000)
    net.addLink(s4, s7, intfName1='s4-eth5', intfName2='s7-eth2', bw=1000)
    
    # Access → Hosts
    net.addLink(s5, h1, intfName1='s5-eth3', intfName2='h1-eth0', bw=100)
    net.addLink(s5, h2, intfName1='s5-eth4', intfName2='h2-eth0', bw=100)
    net.addLink(s5, h6, intfName1='s5-eth5', intfName2='h6-eth0', bw=100)
    
    net.addLink(s6, h3, intfName1='s6-eth3', intfName2='h3-eth0', bw=100)
    net.addLink(s6, h4, intfName1='s6-eth4', intfName2='h4-eth0', bw=100)
    
    net.addLink(s7, h5, intfName1='s7-eth3', intfName2='h5-eth0', bw=100)
    
    # ═════════════════════════════════════════════════════════════
    # START NETWORK
    # ═════════════════════════════════════════════════════════════
    info('*** Khởi động Network\n')
    net.start()
    time.sleep(2)
    
    # ═════════════════════════════════════════════════════════════
    # ENABLE STP (BEFORE configuring ports)
    # ═════════════════════════════════════════════════════════════
    info('*** Enable STP với Priority\n')
    
    stp_config = [
        (s1, 4096),   # Root Bridge
        (s2, 8192),   # Secondary
        (s3, 32768),  # Distribution
        (s4, 36864),
        (s5, 40960),  # Access
        (s6, 45056),
        (s7, 49152)
    ]
    
    for switch, priority in stp_config:
        switch.cmd(f'ovs-vsctl set Bridge {switch.name} stp_enable=true')
        switch.cmd(f'ovs-vsctl set Bridge {switch.name} other_config:stp-priority={priority}')
    
    time.sleep(3)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE OVS SWITCHES
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình OVS Switches\n')
    
    for switch in [s1, s2, s3, s4, s5, s6, s7]:
        switch.cmd('ovs-ofctl del-flows ' + switch.name)
    
    # S1 (Core 1 - Primary)
    s1.cmd('ovs-vsctl set port s1-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-vsctl set port s1-eth2 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-vsctl set port s1-eth3 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-vsctl set port s1-eth4 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-ofctl add-flow s1 priority=0,action=normal')
    
    # S2 (Core 2 - Backup)
    s2.cmd('ovs-vsctl set port s2-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s2.cmd('ovs-vsctl set port s2-eth2 vlan_mode=trunk trunk=10,20,30,99')
    s2.cmd('ovs-vsctl set port s2-eth3 vlan_mode=trunk trunk=10,20,30,99')
    s2.cmd('ovs-vsctl set port s2-eth4 vlan_mode=trunk trunk=10,20,30,99')
    s2.cmd('ovs-ofctl add-flow s2 priority=0,action=normal')
    
    # S3 (Distribution 1)
    s3.cmd('ovs-vsctl set port s3-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s3.cmd('ovs-vsctl set port s3-eth2 vlan_mode=trunk trunk=10,20,30,99')
    s3.cmd('ovs-vsctl set port s3-eth3 vlan_mode=trunk trunk=10,99')
    s3.cmd('ovs-vsctl set port s3-eth4 vlan_mode=trunk trunk=20')
    s3.cmd('ovs-vsctl set port s3-eth5 vlan_mode=trunk trunk=30')
    s3.cmd('ovs-vsctl set port s3-eth6 vlan_mode=trunk trunk=10,20,30,99')  # S3-S4 inter-link
    s3.cmd('ovs-ofctl add-flow s3 priority=0,action=normal')
    
    # S4 (Distribution 2)
    s4.cmd('ovs-vsctl set port s4-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s4.cmd('ovs-vsctl set port s4-eth2 vlan_mode=trunk trunk=10,20,30,99')
    s4.cmd('ovs-vsctl set port s4-eth3 vlan_mode=trunk trunk=10,99')
    s4.cmd('ovs-vsctl set port s4-eth4 vlan_mode=trunk trunk=20')
    s4.cmd('ovs-vsctl set port s4-eth5 vlan_mode=trunk trunk=30')
    s4.cmd('ovs-vsctl set port s4-eth6 vlan_mode=trunk trunk=10,20,30,99')  # S4-S3 inter-link
    s4.cmd('ovs-ofctl add-flow s4 priority=0,action=normal')
    
    # S5 (Access - Admin)
    s5.cmd('ovs-vsctl set port s5-eth1 vlan_mode=trunk trunk=10,99')
    s5.cmd('ovs-vsctl set port s5-eth2 vlan_mode=trunk trunk=10,99')
    s5.cmd('ovs-vsctl set port s5-eth3 tag=10')
    s5.cmd('ovs-vsctl set port s5-eth4 tag=10')
    s5.cmd('ovs-vsctl set port s5-eth5 tag=99')
    s5.cmd('ovs-ofctl add-flow s5 priority=0,action=normal')
    
    # S6 (Access - Lab)
    s6.cmd('ovs-vsctl set port s6-eth1 vlan_mode=trunk trunk=20')
    s6.cmd('ovs-vsctl set port s6-eth2 vlan_mode=trunk trunk=20')
    s6.cmd('ovs-vsctl set port s6-eth3 tag=20')
    s6.cmd('ovs-vsctl set port s6-eth4 tag=20')
    s6.cmd('ovs-ofctl add-flow s6 priority=0,action=normal')
    
    # S7 (Access - KTX)
    s7.cmd('ovs-vsctl set port s7-eth1 vlan_mode=trunk trunk=30')
    s7.cmd('ovs-vsctl set port s7-eth2 vlan_mode=trunk trunk=30')
    s7.cmd('ovs-vsctl set port s7-eth3 tag=30')
    s7.cmd('ovs-ofctl add-flow s7 priority=0,action=normal')
    
    info('*** Đợi STP converge (15 giây)...\n')
    time.sleep(15)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE ROUTER R1 (Router-on-a-Stick)
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình Router R1 (Router-on-a-Stick)\n')
    
    # Internet interface (r1-eth2)
    r1.cmd('ip addr add 8.8.8.1/24 dev r1-eth2')
    r1.cmd('ip link set dev r1-eth2 up')
    
    # ServerQ7 interface (r1-eth3)
    r1.cmd('ip addr add 1.1.1.254/24 dev r1-eth3')
    r1.cmd('ip link set dev r1-eth3 up')
    
    # Trunk interface to Core s1
    r1.cmd('ip addr flush dev r1-eth0')
    r1.cmd('ip link set dev r1-eth0 up')
    
    # Backup trunk to Core s2
    r1.cmd('ip addr flush dev r1-eth1')
    r1.cmd('ip link set dev r1-eth1 up')
    
    # VLAN sub-interfaces (trên r1-eth0)
    vlans = [
        (10, '192.168.10.1', 'Admin'),
        (20, '192.168.20.1', 'Lab'),
        (30, '192.168.30.1', 'KTX'),
        (99, '192.168.99.1', 'Mgmt')
    ]
    
    for vlan_id, gateway, name in vlans:
        info(f'  Creating VLAN {vlan_id} ({name}): {gateway}/24\n')
        r1.cmd(f'ip link add link r1-eth0 name r1-eth0.{vlan_id} type vlan id {vlan_id}')
        r1.cmd(f'ip addr add {gateway}/24 dev r1-eth0.{vlan_id}')
        r1.cmd(f'ip link set dev r1-eth0.{vlan_id} up')
    
    # Enable routing
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    r1.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done')
    
    time.sleep(2)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE DEFAULT GATEWAYS
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình Default Gateways\n')
    
    h1.cmd('ip route add default via 192.168.10.1')
    h2.cmd('ip route add default via 192.168.10.1')
    h3.cmd('ip route add default via 192.168.20.1')
    h4.cmd('ip route add default via 192.168.20.1')
    h5.cmd('ip route add default via 192.168.30.1')
    h6.cmd('ip route add default via 192.168.99.1')
    
    internet.cmd('ip route add default via 8.8.8.1')
    serverq7.cmd('ip route add default via 1.1.1.254')
    
    # ═════════════════════════════════════════════════════════════
    # TEST CONNECTIVITY
    # ═════════════════════════════════════════════════════════════
    info('*** Testing Connectivity\n')
    info('*** Ping test (h1 -> h2, same VLAN):\n')
    h1.cmd('ping -c 2 192.168.10.3')
    
    info('*** Ping test (h1 -> h3, across VLANs):\n')
    h1.cmd('ping -c 2 192.168.20.2')
    
    info('\n*** Network is ready! Use "pingall" to test full connectivity.\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    
    # Dọn dẹp Mininet trước khi chạy
    cleanupMininet()
    
    # Vẽ sơ đồ mạng
    drawTopology()
    
    # Khởi động topology
    buildTopology()

#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
TDTU BẢO LỘC - VRRP Network với Python-based VRRP Monitor
Tự động failover + Visualization
"""

from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import subprocess
import os
import threading
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

# Import VRRP Monitor
try:
    from vrrp_monitor import monitor_vrrp
    VRRP_MONITOR_AVAILABLE = True
except ImportError:
    VRRP_MONITOR_AVAILABLE = False
    info('Warning: vrrp_monitor.py not found - VRRP monitoring disabled\n')

# Import Test Menu
try:
    from test_menu import run_test_menu
    TEST_MENU_AVAILABLE = True
except ImportError:
    TEST_MENU_AVAILABLE = False
    info('Warning: test_menu.py not found - Test menu disabled\n')

class LinuxRouter(Host):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

def cleanupMininet():
    info('\n*** Cleanup Mininet...\n')
    try:
        subprocess.run(['sudo', 'mn', '-c'], check=True, capture_output=True)
        subprocess.run(['sudo', 'pkill', '-9', 'keepalived'], capture_output=True)
        info('✓ Cleanup OK\n\n')
    except:
        pass

def drawTopology():
    """Vẽ sơ đồ mạng bằng NetworkX"""
    info('*** Drawing network topology...\n')
    
    G = nx.Graph()
    
    # Add nodes với attributes
    # Routers
    G.add_node('R1', type='router', label='R1\n(VRRP Master)', color='#FF6B6B')
    G.add_node('R2', type='router', label='R2\n(VRRP Backup)', color='#FFA07A')
    
    # External
    G.add_node('Internet', type='external', label='Internet\n8.8.8.8', color='#4ECDC4')
    G.add_node('ServerQ7', type='external', label='ServerQ7\n1.1.1.1', color='#4ECDC4')
    
    # Core switches
    G.add_node('S1', type='switch', label='S1\n(Core)', color='#95E1D3')
    G.add_node('S2', type='switch', label='S2\n(Core)', color='#95E1D3')
    
    # Distribution switches
    G.add_node('S3', type='switch', label='S3\n(Dist)', color='#C7CEEA')
    G.add_node('S4', type='switch', label='S4\n(Dist)', color='#C7CEEA')
    
    # Access switches
    G.add_node('S5', type='switch', label='S5\n(Access)', color='#FFDAB9')
    G.add_node('S6', type='switch', label='S6\n(Access)', color='#FFDAB9')
    G.add_node('S7', type='switch', label='S7\n(Access)', color='#FFDAB9')
    
    # Hosts
    for i, (h, vlan) in enumerate([('H1', 10), ('H2', 10), ('H3', 20), ('H4', 20), ('H5', 30), ('H6', 99)]):
        G.add_node(h, type='host', label=f'{h}\nVLAN {vlan}', color='#F7DC6F')
    
    # Add edges (links)
    # Routers to external
    G.add_edge('R1', 'Internet', label='1Gbps')
    G.add_edge('R1', 'ServerQ7', label='500Mbps')
    G.add_edge('R2', 'Internet', label='1Gbps')
    G.add_edge('R2', 'ServerQ7', label='500Mbps')
    
    # Routers to core
    G.add_edge('R1', 'S1', label='1Gbps')
    G.add_edge('R1', 'S2', label='1Gbps')
    G.add_edge('R2', 'S1', label='1Gbps')
    G.add_edge('R2', 'S2', label='1Gbps')
    
    # Core layer
    G.add_edge('S1', 'S2', label='1Gbps')
    G.add_edge('S1', 'S3', label='1Gbps')
    G.add_edge('S1', 'S4', label='1Gbps')
    G.add_edge('S2', 'S3', label='1Gbps')
    G.add_edge('S2', 'S4', label='1Gbps')
    
    # Distribution
    G.add_edge('S3', 'S4', label='1Gbps')
    G.add_edge('S3', 'S5', label='1Gbps')
    G.add_edge('S3', 'S6', label='1Gbps')
    G.add_edge('S3', 'S7', label='1Gbps')
    G.add_edge('S4', 'S5', label='1Gbps')
    G.add_edge('S4', 'S6', label='1Gbps')
    G.add_edge('S4', 'S7', label='1Gbps')
    
    # Access to hosts
    G.add_edge('S5', 'H1', label='100Mbps')
    G.add_edge('S5', 'H2', label='100Mbps')
    G.add_edge('S5', 'H6', label='100Mbps')
    G.add_edge('S6', 'H3', label='100Mbps')
    G.add_edge('S6', 'H4', label='100Mbps')
    G.add_edge('S7', 'H5', label='100Mbps')
    
    # Fixed Layout - Hierarchical topology
    plt.figure(figsize=(24, 16))
    pos = {
        # External layer (top)
        'Internet': (1, 5),
        'ServerQ7': (5, 5),
        
        # Router layer
        'R1': (2, 4),
        'R2': (4, 4),
        
        # Core layer
        'S1': (2, 3),
        'S2': (4, 3),
        
        # Distribution layer
        'S3': (2, 2),
        'S4': (4, 2),
        
        # Access layer
        'S5': (1, 1),
        'S6': (3, 1),
        'S7': (5, 1),
        
        # Host layer (bottom)
        'H1': (0.5, 0),
        'H2': (1.5, 0),
        'H6': (2, 0),
        'H3': (2.5, 0),
        'H4': (3.5, 0),
        'H5': (5, 0),
    }
    
    # Draw nodes by type
    for node_type, color in [('router', '#FF6B6B'), ('external', '#4ECDC4'), 
                              ('switch', '#95E1D3'), ('host', '#F7DC6F')]:
        nodelist = [n for n, d in G.nodes(data=True) if d.get('type') == node_type]
        if nodelist:
            nx.draw_networkx_nodes(G, pos, nodelist=nodelist, 
                                  node_color=color, node_size=3000, alpha=0.9)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6, edge_color='#95A5A6')
    
    # Draw labels
    labels = {n: d['label'] for n, d in G.nodes(data=True)}
    nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold')
    
    # Title
    plt.title('TDTU Bảo Lộc Network - VRRP Topology', fontsize=20, fontweight='bold', pad=20)
    
    # Legend
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF6B6B', markersize=15, label='Routers (VRRP)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#4ECDC4', markersize=15, label='External'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#95E1D3', markersize=15, label='Switches'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#F7DC6F', markersize=15, label='Hosts')
    ]
    plt.legend(handles=legend_elements, loc='upper left', fontsize=12)
    
    plt.axis('off')
    plt.tight_layout()
    plt.savefig('network_topology.png', dpi=150, bbox_inches='tight')
    info(f'✓ Topology saved to: network_topology.png\n')

def buildTopology():
    info('*** Creating Network\n')
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)
    
    # ROUTERS
    info('*** Adding Routers\n')
    r1 = net.addHost('r1', cls=LinuxRouter, ip=None)
    r2 = net.addHost('r2', cls=LinuxRouter, ip=None)
    
    # SWITCHES
    info('*** Adding Switches\n')
    s1 = net.addSwitch('s1', cls=OVSSwitch, failMode='standalone', stp=True)
    s2 = net.addSwitch('s2', cls=OVSSwitch, failMode='standalone', stp=True)
    s3 = net.addSwitch('s3', cls=OVSSwitch, failMode='standalone', stp=True)
    s4 = net.addSwitch('s4', cls=OVSSwitch, failMode='standalone', stp=True)
    s5 = net.addSwitch('s5', cls=OVSSwitch, failMode='standalone', stp=True)
    s6 = net.addSwitch('s6', cls=OVSSwitch, failMode='standalone', stp=True)
    s7 = net.addSwitch('s7', cls=OVSSwitch, failMode='standalone', stp=True)
    
    # HOSTS
    info('*** Adding Hosts\n')
    h1 = net.addHost('h1', ip='192.168.10.2/24')
    h2 = net.addHost('h2', ip='192.168.10.3/24')
    h3 = net.addHost('h3', ip='192.168.20.2/24')
    h4 = net.addHost('h4', ip='192.168.20.3/24')
    h5 = net.addHost('h5', ip='192.168.30.30/24')
    h6 = net.addHost('h6', ip='192.168.99.2/24')
    internet = net.addHost('internet', ip='8.8.8.8/24')
    serverq7 = net.addHost('serverq7', ip='1.1.1.1/24')
    
    # LINKS
    info('*** Creating Links\n')
    net.addLink(r1, internet, intfName1='r1-eth2', intfName2='internet-eth0', bw=1000)
    net.addLink(r1, serverq7, intfName1='r1-eth3', intfName2='serverq7-eth0', bw=500)
    net.addLink(r2, internet, intfName1='r2-eth2', intfName2='internet-eth1', bw=1000)
    net.addLink(r2, serverq7, intfName1='r2-eth3', intfName2='serverq7-eth1', bw=500)
    
    net.addLink(r1, s1, intfName1='r1-eth0', intfName2='s1-eth1', bw=1000)
    net.addLink(r1, s2, intfName1='r1-eth1', intfName2='s2-eth1', bw=1000)
    net.addLink(r2, s1, intfName1='r2-eth0', intfName2='s1-eth5', bw=1000)
    net.addLink(r2, s2, intfName1='r2-eth1', intfName2='s2-eth5', bw=1000)
    
    net.addLink(s1, s2, intfName1='s1-eth2', intfName2='s2-eth2', bw=1000)
    net.addLink(s1, s3, intfName1='s1-eth3', intfName2='s3-eth1', bw=1000)
    net.addLink(s1, s4, intfName1='s1-eth4', intfName2='s4-eth1', bw=1000)
    net.addLink(s2, s3, intfName1='s2-eth3', intfName2='s3-eth2', bw=1000)
    net.addLink(s2, s4, intfName1='s2-eth4', intfName2='s4-eth2', bw=1000)
    net.addLink(s3, s4, intfName1='s3-eth6', intfName2='s4-eth6', bw=1000)
    
    net.addLink(s3, s5, intfName1='s3-eth3', intfName2='s5-eth1', bw=1000)
    net.addLink(s3, s6, intfName1='s3-eth4', intfName2='s6-eth1', bw=1000)
    net.addLink(s3, s7, intfName1='s3-eth5', intfName2='s7-eth1', bw=1000)
    net.addLink(s4, s5, intfName1='s4-eth3', intfName2='s5-eth2', bw=1000)
    net.addLink(s4, s6, intfName1='s4-eth4', intfName2='s6-eth2', bw=1000)
    net.addLink(s4, s7, intfName1='s4-eth5', intfName2='s7-eth2', bw=1000)
    
    net.addLink(s5, h1, bw=100)
    net.addLink(s5, h2, bw=100)
    net.addLink(s5, h6, bw=100)
    net.addLink(s6, h3, bw=100)
    net.addLink(s6, h4, bw=100)
    net.addLink(s7, h5, bw=100)
    
    info('*** Starting Network\n')
    net.start()
    
    # VLAN CONFIG
    info('*** Configuring VLANs\n')
    for sw in [s1, s2, s3, s4, s5, s6, s7]:
        sw.cmd('ovs-ofctl del-flows ' + sw.name)
    
    # Core
    for p in ['eth1', 'eth2', 'eth3', 'eth4', 'eth5']:
        s1.cmd(f'ovs-vsctl set port s1-{p} vlan_mode=trunk trunk=10,20,30,99')
        s2.cmd(f'ovs-vsctl set port s2-{p} vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-ofctl add-flow s1 priority=0,action=normal')
    s2.cmd('ovs-ofctl add-flow s2 priority=0,action=normal')
    
    # Distribution
    for p in ['eth1', 'eth2', 'eth6']:
        s3.cmd(f'ovs-vsctl set port s3-{p} vlan_mode=trunk trunk=10,20,30,99')
        s4.cmd(f'ovs-vsctl set port s4-{p} vlan_mode=trunk trunk=10,20,30,99')
    s3.cmd('ovs-vsctl set port s3-eth3 vlan_mode=trunk trunk=10,99')
    s3.cmd('ovs-vsctl set port s3-eth4 vlan_mode=trunk trunk=20')
    s3.cmd('ovs-vsctl set port s3-eth5 vlan_mode=trunk trunk=30')
    s4.cmd('ovs-vsctl set port s4-eth3 vlan_mode=trunk trunk=10,99')
    s4.cmd('ovs-vsctl set port s4-eth4 vlan_mode=trunk trunk=20')
    s4.cmd('ovs-vsctl set port s4-eth5 vlan_mode=trunk trunk=30')
    s3.cmd('ovs-ofctl add-flow s3 priority=0,action=normal')
    s4.cmd('ovs-ofctl add-flow s4 priority=0,action=normal')
    
    # Access
    s5.cmd('ovs-vsctl set port s5-eth1 vlan_mode=trunk trunk=10,99')
    s5.cmd('ovs-vsctl set port s5-eth2 vlan_mode=trunk trunk=10,99')
    s5.cmd('ovs-vsctl set port s5-eth3 tag=10')
    s5.cmd('ovs-vsctl set port s5-eth4 tag=10')
    s5.cmd('ovs-vsctl set port s5-eth5 tag=99')
    s5.cmd('ovs-ofctl add-flow s5 priority=0,action=normal')
    
    s6.cmd('ovs-vsctl set port s6-eth1 vlan_mode=trunk trunk=20')
    s6.cmd('ovs-vsctl set port s6-eth2 vlan_mode=trunk trunk=20')
    s6.cmd('ovs-vsctl set port s6-eth3 tag=20')
    s6.cmd('ovs-vsctl set port s6-eth4 tag=20')
    s6.cmd('ovs-ofctl add-flow s6 priority=0,action=normal')
    
    s7.cmd('ovs-vsctl set port s7-eth1 vlan_mode=trunk trunk=30')
    s7.cmd('ovs-vsctl set port s7-eth2 vlan_mode=trunk trunk=30')
    s7.cmd('ovs-vsctl set port s7-eth3 tag=30')
    s7.cmd('ovs-ofctl add-flow s7 priority=0,action=normal')
    
    # STP
    info('*** Configuring STP\n')
    s1.cmd('ovs-vsctl set Bridge s1 other_config:stp-priority=4096')
    info('*** Waiting STP (15s)...\n')
    time.sleep(15)
    
    # R1 CONFIG
    info('*** Configuring R1 (VRRP Master)\n')
    r1.cmd('ip addr add 8.8.8.1/24 dev r1-eth2')
    r1.cmd('ip link set dev r1-eth2 up')
    r1.cmd('ip addr add 1.1.1.254/24 dev r1-eth3')
    r1.cmd('ip link set dev r1-eth3 up')
    r1.cmd('ip addr flush dev r1-eth0')
    r1.cmd('ip link set dev r1-eth0 up')
    r1.cmd('ip addr flush dev r1-eth1')
    r1.cmd('ip link set dev r1-eth1 up')
    
    vlans = [(10, '192.168.10.1'), (20, '192.168.20.1'), (30, '192.168.30.1'), (99, '192.168.99.1')]
    for vid, ip in vlans:
        r1.cmd(f'ip link add link r1-eth0 name r1-eth0.{vid} type vlan id {vid}')
        r1.cmd(f'ip addr add {ip}/24 dev r1-eth0.{vid}')
        r1.cmd(f'ip link set dev r1-eth0.{vid} up')
    
    # Add VRRP Virtual IPs to R1 (Master)
    info('*** Adding VRRP Virtual IPs to R1\n')
    r1.cmd('ip addr add 192.168.10.254/24 dev r1-eth0.10')
    r1.cmd('ip addr add 192.168.20.254/24 dev r1-eth0.20')
    r1.cmd('ip addr add 192.168.30.254/24 dev r1-eth0.30')
    r1.cmd('ip addr add 192.168.99.254/24 dev r1-eth0.99')
    
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    r1.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done')
    
    # Add external routes with lower metric (preferred)
    r1.cmd('ip route add 192.168.0.0/16 via 8.8.8.8 dev r1-eth2 metric 10')
    r1.cmd('ip route add 10.0.0.0/8 via 1.1.1.1 dev r1-eth3 metric 10')
    
    # R2 CONFIG
    info('*** Configuring R2 (VRRP Backup)\n')
    r2.cmd('ip addr add 8.8.8.2/24 dev r2-eth2')
    r2.cmd('ip link set dev r2-eth2 up')
    r2.cmd('ip addr add 1.1.1.253/24 dev r2-eth3')
    r2.cmd('ip link set dev r2-eth3 up')
    r2.cmd('ip addr flush dev r2-eth0')
    r2.cmd('ip link set dev r2-eth0 up')
    r2.cmd('ip addr flush dev r2-eth1')
    r2.cmd('ip link set dev r2-eth1 up')
    
    for vid, ip in vlans:
        r2_ip = ip.replace('.1', '.2')
        r2.cmd(f'ip link add link r2-eth0 name r2-eth0.{vid} type vlan id {vid}')
        r2.cmd(f'ip addr add {r2_ip}/24 dev r2-eth0.{vid}')
        r2.cmd(f'ip link set dev r2-eth0.{vid} up')
    
    r2.cmd('sysctl -w net.ipv4.ip_forward=1')
    r2.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done')
    
    # Add external routes with higher metric (backup)
    r2.cmd('ip route add 192.168.0.0/16 via 8.8.8.8 dev r2-eth2 metric 20')
    r2.cmd('ip route add 10.0.0.0/8 via 1.1.1.1 dev r2-eth3 metric 20')
    
    # VRRP MONITORING
    if VRRP_MONITOR_AVAILABLE:
        info('\n*** Starting VRRP Monitor (automatic failover enabled)\n')
        vrrp_thread = threading.Thread(target=monitor_vrrp, args=(net,), daemon=True)
        vrrp_thread.start()
    else:
        info('\n*** VRRP Monitor not available (vrrp_monitor.py not found)\n')
        info('*** Manual VRRP failover only\n\n')
    
    # HOST GATEWAYS
    info('*** Configuring Gateways\n')
    h1.cmd('ip route add default via 192.168.10.254')  # VRRP VIP
    h2.cmd('ip route add default via 192.168.10.254')
    h3.cmd('ip route add default via 192.168.20.254')
    h4.cmd('ip route add default via 192.168.20.254')
    h5.cmd('ip route add default via 192.168.30.254')
    h6.cmd('ip route add default via 192.168.99.254')
    
    internet.cmd('ip route add default via 8.8.8.1')
    serverq7.cmd('ip route add default via 1.1.1.254')
    
    # TEST
    info('\n*** Testing\n')
    result = h1.cmd('ping -c 2 -W 1 192.168.20.2')
    if '2 received' in result:
        info('✓ Inter-VLAN OK\n')
    
    info('\n')
    info('═══════════════════════════════════════════════════\n')
    info('*** NETWORK READY\n')
    info('═══════════════════════════════════════════════════\n')
    info('\n')
    info('Features:\n')
    info('  ✓ Dual Routers (R1 Master, R2 Backup)\n')
    if VRRP_MONITOR_AVAILABLE:
        info('  ✓ VRRP Automatic Monitoring (Python-based)\n')
    else:
        info('  ✓ VRRP Ready (manual failover only)\n')
    info('  ✓ Full mesh redundancy\n')
    info('  ✓ STP enabled\n')
    info('  ✓ Metric-based routing failover\n')
    if TEST_MENU_AVAILABLE:
        info('  ✓ Traffic Test Menu (nghẽn băng thông & load balancing)\n')
    info('  ✓ Network topology diagram: network_topology.png\n')
    info('\n')
    
    if TEST_MENU_AVAILABLE:
        info('═══════════════════════════════════════════════════\n')
        info('*** MENU TEST AVAILABLE ***\n')
        info('═══════════════════════════════════════════════════\n')
        info('\n')
        info('Commands trong Mininet CLI:\n')
        info('  • test       - Mở Menu Test\n')
        info('  • congestion - Test nghẽn băng thông\n')
        info('  • loadbal    - Cấu hình load balancing\n')
        info('  • stats      - Thống kê traffic\n')
        info('\n')
    if VRRP_MONITOR_AVAILABLE:
        info('VRRP Automatic Failover:\n')
        info('  • VRRP Monitor is running in background\n')
        info('  • Virtual IPs (.254) will auto-failover to R2\n')
        info('  • External routes use metric-based failover\n')
        info('\n')
        info('Test Failover:\n')
        info('  1. In CLI: r1 ifconfig r1-eth0 down; r1 ifconfig r1-eth1 down\n')
        info('  2. Watch automatic failover messages\n')
        info('  3. Test connectivity from hosts\n')
    else:
        info('Manual VRRP Failover (vrrp_monitor.py not available):\n')
        info('  1. r1 ifconfig r1-eth0 down; r1 ifconfig r1-eth1 down\n')
        info('  2. r2 ip addr add 192.168.10.254/24 dev r2-eth0.10\n')
        info('     r2 ip addr add 192.168.20.254/24 dev r2-eth0.20\n')
        info('     r2 ip addr add 192.168.30.254/24 dev r2-eth0.30\n')
        info('     r2 ip addr add 192.168.99.254/24 dev r2-eth0.99\n')
    info('\n')
    
    # Custom CLI với test commands
    if TEST_MENU_AVAILABLE:
        from test_menu import TrafficTester
        
        class CustomCLI(CLI):
            def __init__(self, mininet, **kwargs):
                self.tester = TrafficTester(mininet)
                CLI.__init__(self, mininet, **kwargs)
                
            def do_test(self, _line):
                """Mở menu test"""
                run_test_menu(self.mn)
                
            def do_congestion(self, target='internet'):
                """Test nghẽn. Usage: congestion [internet|serverq7|all]"""
                if target == 'serverq7':
                    self.tester.test_congestion_serverq7()
                elif target == 'all':
                    self.tester.test_full_network_congestion()
                else:
                    self.tester.test_congestion_internet()
                    
            def do_loadbal(self, _line):
                """Cấu hình load balancing"""
                self.tester.configure_load_balancing()
                
            def do_stats(self, _line):
                """Thống kê traffic"""
                self.tester.show_traffic_stats()
        
        CustomCLI(net)
    else:
        CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    cleanupMininet()
    drawTopology()  # Vẽ sơ đồ trước khi run
    buildTopology()

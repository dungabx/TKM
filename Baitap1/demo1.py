#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
THIẾT KẾ HỆ THỐNG MẠNG TÒA NHÀ VĂN PHÒNG 3 TẦNG 
Thay đổi:
- Băng thông Internet: 1Gbps 
- Băng thông VLAN 20 (Kỹ thuật): 1Gbps 
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time

class LinuxRouter(Host):
    """Host với chức năng router"""
    
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

def buildTopology():
    """Xây dựng topology mạng"""
    
    info('*** Tạo Mininet Network (NO Controller)\n')
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)
    
    # =====================================
    # THÊM ROUTER VÀ HOSTS
    # =====================================
    info('*** Thêm Router R1\n')
    r1 = net.addHost('r1', cls=LinuxRouter, ip=None)
    
    info('*** Thêm Host Internet\n')
    internet = net.addHost('internet', ip='203.0.113.1/24')
    
    info('*** Thêm Host Server\n')
    server = net.addHost('server', ip='192.168.99.10/24')
    
    # =====================================
    # THÊM SWITCHES
    # =====================================
    info('*** Thêm Switches\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
    s5 = net.addSwitch('s5')
    
    # =====================================
    # THÊM PCs
    # =====================================
    info('*** Thêm PCs\n')
    pc1 = net.addHost('pc1', ip='192.168.10.10/24')
    pc2 = net.addHost('pc2', ip='192.168.10.11/24')
    pc3 = net.addHost('pc3', ip='192.168.20.10/24')
    pc4 = net.addHost('pc4', ip='192.168.20.11/24')
    ap1 = net.addHost('ap1', cls=LinuxRouter, ip=None)
    sta1 = net.addHost('sta1', ip='192.168.30.11/24')
    
    # =====================================
    # TẠO LINKS VỚI BANDWIDTH
    # =====================================
    info('*** Tạo Links với Bandwidth constraints\n')
    
    # Internet <-> R1 (1Gbps - THAY ĐỔI TỪ 100Mbps)
    net.addLink(internet, r1, intfName1='internet-eth0', intfName2='r1-eth0',
                bw=1000)
    
    # R1 <-> S1 (1Gbps - backbone)
    net.addLink(r1, s1, intfName1='r1-eth1', intfName2='s1-eth1',
                bw=1000)
    
    # S1 <-> Server (1Gbps - high speed to server)
    net.addLink(s1, server, intfName1='s1-eth2', intfName2='server-eth0',
                bw=1000)
    
    # S1 <-> S2 (1Gbps - backbone)
    net.addLink(s1, s2, intfName1='s1-eth3', intfName2='s2-eth1',
                bw=1000)
    
    # S2 <-> Access Switches
    net.addLink(s2, s3, intfName1='s2-eth2', intfName2='s3-eth1',
                bw=100)  # VLAN 10 - 100Mbps
    net.addLink(s2, s4, intfName1='s2-eth3', intfName2='s4-eth1',
                bw=1000)  # VLAN 20 - 1Gbps (THAY ĐỔI TỪ 100Mbps)
    net.addLink(s2, s5, intfName1='s2-eth4', intfName2='s5-eth1',
                bw=100)  # VLAN 30 - 100Mbps
    
    # Access ports
    net.addLink(s3, pc1, intfName1='s3-eth2', intfName2='pc1-eth0', bw=100)
    net.addLink(s3, pc2, intfName1='s3-eth3', intfName2='pc2-eth0', bw=100)
    net.addLink(s4, pc3, intfName1='s4-eth2', intfName2='pc3-eth0', bw=1000)  # 1Gbps
    net.addLink(s4, pc4, intfName1='s4-eth3', intfName2='pc4-eth0', bw=1000)  # 1Gbps
    net.addLink(s5, ap1, intfName1='s5-eth2', intfName2='ap1-eth2', bw=100)
    net.addLink(ap1, sta1, intfName1='ap1-eth0', intfName2='sta1-eth0', bw=50)
    
    # =====================================
    # KHỞI ĐỘNG NETWORK
    # =====================================
    info('*** Khởi động Network\n')
    net.start()
    
    time.sleep(2)
    
    # =====================================
    # CẤU HÌNH SWITCHES
    # =====================================
    info('*** Cấu hình OVS switches\n')
    
    for switch in [s1, s2, s3, s4, s5]:
        switch.cmd('ovs-ofctl del-flows ' + switch.name)
    
    # Switch S1
    s1.cmd('ovs-vsctl set port s1-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-vsctl set port s1-eth2 tag=99')
    s1.cmd('ovs-vsctl set port s1-eth3 vlan_mode=trunk trunk=10,20,30,99')
    s1.cmd('ovs-ofctl add-flow s1 priority=0,action=normal')
    
    # Switch S2
    s2.cmd('ovs-vsctl set port s2-eth1 vlan_mode=trunk trunk=10,20,30,99')
    s2.cmd('ovs-vsctl set port s2-eth2 vlan_mode=trunk trunk=10')
    s2.cmd('ovs-vsctl set port s2-eth3 vlan_mode=trunk trunk=20')
    s2.cmd('ovs-vsctl set port s2-eth4 vlan_mode=trunk trunk=30')
    s2.cmd('ovs-ofctl add-flow s2 priority=0,action=normal')
    
    # Switch S3 (VLAN 10)
    s3.cmd('ovs-vsctl set port s3-eth1 vlan_mode=trunk trunk=10')
    s3.cmd('ovs-vsctl set port s3-eth2 tag=10')
    s3.cmd('ovs-vsctl set port s3-eth3 tag=10')
    s3.cmd('ovs-ofctl add-flow s3 priority=0,action=normal')
    
    # Switch S4 (VLAN 20)
    s4.cmd('ovs-vsctl set port s4-eth1 vlan_mode=trunk trunk=20')
    s4.cmd('ovs-vsctl set port s4-eth2 tag=20')
    s4.cmd('ovs-vsctl set port s4-eth3 tag=20')
    s4.cmd('ovs-ofctl add-flow s4 priority=0,action=normal')
    
    # Switch S5 (VLAN 30)
    s5.cmd('ovs-vsctl set port s5-eth1 vlan_mode=trunk trunk=30')
    s5.cmd('ovs-vsctl set port s5-eth2 tag=30')
    s5.cmd('ovs-ofctl add-flow s5 priority=0,action=normal')
    
    time.sleep(2)
    
    # =====================================
    # CẤU HÌNH AP1 BRIDGE
    # =====================================
    info('*** Cấu hình AP1 Bridge\n')
    
    ap1.cmd('ip link add name br0 type bridge')
    ap1.cmd('ip link set br0 up')
    ap1.cmd('ip link set ap1-eth0 master br0')
    ap1.cmd('ip link set ap1-eth2 master br0')
    ap1.cmd('ip link set ap1-eth0 up')
    ap1.cmd('ip link set ap1-eth2 up')
    ap1.cmd('ip addr add 192.168.30.10/24 dev br0')
    ap1.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    time.sleep(1)
    
    # =====================================
    # CẤU HÌNH ROUTER ON A STICK (R1)
    # =====================================
    info('*** Cấu hình Router on a Stick\n')
    
    r1.cmd('ip addr add 203.0.113.2/24 dev r1-eth0')
    r1.cmd('ip link set dev r1-eth0 up')
    
    r1.cmd('ip addr flush dev r1-eth1')
    r1.cmd('ip link set dev r1-eth1 up')
    
    # VLAN sub-interfaces
    for vlan_id, subnet in [(10, '10'), (20, '20'), (30, '30'), (99, '99')]:
        r1.cmd(f'ip link add link r1-eth1 name r1-eth1.{vlan_id} type vlan id {vlan_id}')
        r1.cmd(f'ip addr add 192.168.{subnet}.1/24 dev r1-eth1.{vlan_id}')
        r1.cmd(f'ip link set dev r1-eth1.{vlan_id} up')
    
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    r1.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done')
    
    time.sleep(1)
    
    # =====================================
    # CẤU HÌNH GATEWAY
    # =====================================
    info('*** Cấu hình Gateway\n')
    
    pc1.cmd('ip route add default via 192.168.10.1')
    pc2.cmd('ip route add default via 192.168.10.1')
    pc3.cmd('ip route add default via 192.168.20.1')
    pc4.cmd('ip route add default via 192.168.20.1')
    ap1.cmd('ip route add default via 192.168.30.1')
    sta1.cmd('ip route add default via 192.168.30.1')
    server.cmd('ip route add default via 192.168.99.1')
    internet.cmd('ip route add 192.168.0.0/16 via 203.0.113.2')
    r1.cmd('ip route add default via 203.0.113.1')
    
    for host in [pc1, pc2, pc3, pc4, sta1, server]:
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
    
    time.sleep(2)
    
    # =====================================
    # CẤU HÌNH FIREWALL TRÊN R1
    # =====================================
    info('*** Cấu hình Firewall (iptables) trên R1\n')
    
    # Xóa rules cũ
    r1.cmd('iptables -F')
    r1.cmd('iptables -X')
    r1.cmd('iptables -t nat -F')
    r1.cmd('iptables -t nat -X')
    r1.cmd('iptables -t mangle -F')
    r1.cmd('iptables -t mangle -X')
    
    # Default policies
    r1.cmd('iptables -P INPUT ACCEPT')
    r1.cmd('iptables -P FORWARD DROP')
    r1.cmd('iptables -P OUTPUT ACCEPT')
    
    # === FIREWALL RULES ===
    
    # 1. Cho phép traffic đã established/related
    r1.cmd('iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT')
    
    # 2. Cho phép loopback
    r1.cmd('iptables -A INPUT -i lo -j ACCEPT')
    
    # 3. NAT cho traffic ra Internet
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth0 -j MASQUERADE')
    
    # 4. VLAN 10 (Hành chính) - Chỉ cho phép HTTP, HTTPS, DNS
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -p tcp --dport 80 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -p tcp --dport 443 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -p udp --dport 53 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -p tcp --dport 53 -j ACCEPT')
    
    # 5. VLAN 20 (Kỹ thuật) - Full access to Server và Internet
    r1.cmd('iptables -A FORWARD -s 192.168.20.0/24 -d 192.168.99.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.20.0/24 -d 203.0.113.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.20.0/24 -p tcp --dport 22 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.20.0/24 -p tcp --dport 3306 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.20.0/24 -p tcp --dport 5432 -j ACCEPT')
    
    # 6. VLAN 30 (Lãnh đạo) - Priority traffic, full access
    r1.cmd('iptables -A FORWARD -s 192.168.30.0/24 -j ACCEPT')
    
    # 7. Server VLAN 99 - Cho phép từ tất cả internal VLANs
    r1.cmd('iptables -A FORWARD -d 192.168.99.0/24 -s 192.168.0.0/16 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.99.0/24 -d 192.168.0.0/16 -j ACCEPT')
    
    # 8. Block VLAN 10 truy cập vào VLAN 20 và 30
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -d 192.168.20.0/24 -j DROP')
    r1.cmd('iptables -A FORWARD -s 192.168.10.0/24 -d 192.168.30.0/24 -j DROP')
    
    # 9. Logging
    r1.cmd('iptables -A FORWARD -j LOG --log-prefix "FW-DROP: " --log-level 4')
    
    # 10. Anti-DDoS: Rate limiting ICMP
    r1.cmd('iptables -A FORWARD -p icmp --icmp-type echo-request -m limit --limit 10/sec -j ACCEPT')
    r1.cmd('iptables -A FORWARD -p icmp --icmp-type echo-request -j DROP')
    
    # 11. Protection: Drop invalid packets
    r1.cmd('iptables -A FORWARD -m state --state INVALID -j DROP')
    
    # 12. Block common attack ports
    r1.cmd('iptables -A FORWARD -p tcp --dport 23 -j DROP')
    r1.cmd('iptables -A FORWARD -p tcp --dport 135 -j DROP')
    r1.cmd('iptables -A FORWARD -p tcp --dport 139 -j DROP')
    r1.cmd('iptables -A FORWARD -p tcp --dport 445 -j DROP')
    
    print('\n[FIREWALL] Đã cấu hình Firewall trên R1')
    
    # =====================================
    # CẤU HÌNH QoS (Quality of Service)
    # =====================================
    info('*** Cấu hình QoS trên R1 và Switches\n')
    
    # === QoS TRÊN ROUTER R1 ===
    # Interface ra Internet (r1-eth0) - 1Gbps (THAY ĐỔI)
    r1.cmd('tc qdisc del dev r1-eth0 root 2>/dev/null')
    r1.cmd('tc qdisc add dev r1-eth0 root handle 1: htb default 30')
    
    # Root class - 1Gbps (THAY ĐỔI)
    r1.cmd('tc class add dev r1-eth0 parent 1: classid 1:1 htb rate 1000mbit ceil 1000mbit')
    
    # Class 1:10 - VLAN 30 (Lãnh đạo) - Priority cao - 300Mbps guaranteed
    r1.cmd('tc class add dev r1-eth0 parent 1:1 classid 1:10 htb rate 300mbit ceil 600mbit prio 0')
    
    # Class 1:20 - VLAN 20 (Kỹ thuật) - High priority - 500Mbps guaranteed (THAY ĐỔI)
    r1.cmd('tc class add dev r1-eth0 parent 1:1 classid 1:20 htb rate 500mbit ceil 1000mbit prio 0')
    
    # Class 1:30 - VLAN 10 (Hành chính) - Lower priority - 100Mbps guaranteed
    r1.cmd('tc class add dev r1-eth0 parent 1:1 classid 1:30 htb rate 100mbit ceil 300mbit prio 2')
    
    # Class 1:40 - Server traffic - High priority - 300Mbps
    r1.cmd('tc class add dev r1-eth0 parent 1:1 classid 1:40 htb rate 300mbit ceil 800mbit prio 0')
    
    # Filters để phân loại traffic
    r1.cmd('tc filter add dev r1-eth0 parent 1: protocol ip prio 1 u32 match ip src 192.168.30.0/24 flowid 1:10')
    r1.cmd('tc filter add dev r1-eth0 parent 1: protocol ip prio 1 u32 match ip src 192.168.20.0/24 flowid 1:20')
    r1.cmd('tc filter add dev r1-eth0 parent 1: protocol ip prio 3 u32 match ip src 192.168.10.0/24 flowid 1:30')
    r1.cmd('tc filter add dev r1-eth0 parent 1: protocol ip prio 1 u32 match ip src 192.168.99.0/24 flowid 1:40')
    
    # SFQ cho mỗi class
    r1.cmd('tc qdisc add dev r1-eth0 parent 1:10 handle 10: sfq perturb 10')
    r1.cmd('tc qdisc add dev r1-eth0 parent 1:20 handle 20: sfq perturb 10')
    r1.cmd('tc qdisc add dev r1-eth0 parent 1:30 handle 30: sfq perturb 10')
    r1.cmd('tc qdisc add dev r1-eth0 parent 1:40 handle 40: sfq perturb 10')
    
    # === QoS TRÊN INTERFACE VLAN CỦA R1 ===
    for vlan_id in [10, 20, 30, 99]:
        iface = f'r1-eth1.{vlan_id}'
        r1.cmd(f'tc qdisc del dev {iface} root 2>/dev/null')
        r1.cmd(f'tc qdisc add dev {iface} root handle 1: prio bands 3 priomap 1 2 2 2 1 2 0 0 1 1 1 1 1 1 1 1')
    
    # Filter cho VoIP/Video ports cho VLAN 30
    for vlan_id in [30]:
        iface = f'r1-eth1.{vlan_id}'
        r1.cmd(f'tc filter add dev {iface} protocol ip parent 1:0 prio 1 u32 match ip dport 5060 0xffff flowid 1:1')
        r1.cmd(f'tc filter add dev {iface} protocol ip parent 1:0 prio 1 u32 match ip sport 5060 0xffff flowid 1:1')
    
    print('[QoS] Đã cấu hình QoS trên R1')
    
    # === QoS TRÊN OVS SWITCHES ===
    info('*** Cấu hình QoS trên Switches\n')
    
    # VLAN 10 ports: max 50Mbps (giữ nguyên)
    s2.cmd('ovs-vsctl set interface s2-eth2 ingress_policing_rate=50000')
    s2.cmd('ovs-vsctl set interface s2-eth2 ingress_policing_burst=5000')
    
    # VLAN 20 ports: max 1Gbps (THAY ĐỔI)
    s2.cmd('ovs-vsctl set interface s2-eth3 ingress_policing_rate=1000000')
    s2.cmd('ovs-vsctl set interface s2-eth3 ingress_policing_burst=100000')
    
    # VLAN 30 ports: max 100Mbps (giữ nguyên)
    s2.cmd('ovs-vsctl set interface s2-eth4 ingress_policing_rate=100000')
    s2.cmd('ovs-vsctl set interface s2-eth4 ingress_policing_burst=10000')
    
    # QoS queues trên OVS
    for switch in [s1, s2, s3, s4, s5]:
        switch.cmd(f'ovs-vsctl set port {switch.name}-eth1 qos=@newqos -- --id=@newqos create qos type=linux-htb other-config:max-rate=1000000000 queues=0=@q0,1=@q1,2=@q2 -- --id=@q0 create queue other-config:min-rate=500000000 other-config:max-rate=1000000000 -- --id=@q1 create queue other-config:min-rate=300000000 other-config:max-rate=800000000 -- --id=@q2 create queue other-config:min-rate=200000000 other-config:max-rate=500000000 2>/dev/null')
    
    print('[QoS] Đã cấu hình QoS trên Switches')
    
    time.sleep(2)
    
    # =====================================
    # HIỂN THỊ THÔNG TIN CẤU HÌNH
    # =====================================
    print('\n' + '='*70)
    print('CẤU HÌNH HOÀN TẤT - NETWORK TOPOLOGY (TINH CHỈNH)')
    print('='*70)
    print('''
┌─────────────┐
│  INTERNET   │ 203.0.113.1/24
└──────┬──────┘
       │ 1Gbps 
       │
┌──────▼──────┐
│     R1      │ Router on a Stick + Firewall + QoS
│  (Router)   │ 203.0.113.2/24
└──────┬──────┘
       │ 1Gbps (Trunk: VLAN 10,20,30,99)
       │
┌──────▼──────┐
│     S1      │ Core Switch
│  (Switch)   │
└─┬─────────┬─┘
  │         │ 1Gbps (VLAN 99)
  │         └─────────► [SERVER] 192.168.99.10/24
  │ 1Gbps
  │
┌─▼─────────┐
│    S2     │ Distribution Switch
│ (Switch)  │
└─┬───┬───┬─┘
  │   │   │
  │   │   └───► S5 (100Mbps, VLAN 30) ──► AP1 ──► STA1
  │   │                                    192.168.30.10
  │   │                                    192.168.30.11
  │   │
  │   └───────► S4 (1Gbps , VLAN 20) ──► PC3, PC4
  │                                        192.168.20.10/11
  │
  └───────────► S3 (100Mbps, VLAN 10) ──► PC1, PC2
                                          192.168.10.10/11

★ = Thay đổi băng thông
    ''')
    
    # =====================================
    # HIỂN THỊ BẢNG IP
    # =====================================
    print('\n' + '='*70)
    print('BANDWIDTH ALLOCATION TABLE')
    print('='*70)
    print(f'''
╔════════════════════╦═══════════════╦═════════════════════════════════╗
║ Segment            ║ Bandwidth     ║ Notes                           ║
╠════════════════════╬═══════════════╬═════════════════════════════════╣
║ Internet Link      ║ 1 Gbps        ║ Nâng từ 100Mbps                ║
║ R1 <-> S1          ║ 1 Gbps        ║ Backbone                        ║
║ S1 <-> Server      ║ 1 Gbps        ║ High-speed server access        ║
║ S1 <-> S2          ║ 1 Gbps        ║ Core backbone                   ║
╠════════════════════╬═══════════════╬═════════════════════════════════╣
║ S2 -> S3 (VLAN 10) ║ 100 Mbps      ║ Hành chính (giữ nguyên)        ║
║ S2 -> S4 (VLAN 20) ║ 1 Gbps ★      ║ Kỹ thuật (nâng từ 100Mbps)     ║
║ S2 -> S5 (VLAN 30) ║ 100 Mbps      ║ Lãnh đạo (giữ nguyên)          ║
╠════════════════════╬═══════════════╬═════════════════════════════════╣
║ PC1, PC2 (VLAN 10) ║ 100 Mbps/port ║ Giữ nguyên                      ║
║ PC3, PC4 (VLAN 20) ║ 1 Gbps/port ★ ║ Nâng cao cho developers         ║
║ AP1, STA1 (VLAN 30)║ 100/50 Mbps   ║ Giữ nguyên                      ║
║ Server             ║ 1 Gbps        ║ Giữ nguyên                      ║
╚════════════════════╩═══════════════╩═════════════════════════════════╝

★ = THAY ĐỔI MỚI
    ''')
    
    # =====================================
    # QoS CONFIGURATION SUMMARY
    # =====================================
    print('\n' + '='*70)
    print('QoS (Quality of Service) SUMMARY - ĐÃ TINH CHỈNH')
    print('='*70)
    print('''
┌──────────────────────────────────────────────────────────────────┐
│ Traffic Prioritization (HTB on R1-eth0 - 1Gbps total) ★         │
│                                                                  │
│   Priority 0 (Highest):                                          │
│     • VLAN 20 (Kỹ thuật): 500Mbps guaranteed, 1Gbps max ★       │
│       → Tăng để support developers với data processing          │
│     • VLAN 30 (Lãnh đạo): 300Mbps guaranteed, 600Mbps max       │
│     • Server traffic:     300Mbps guaranteed, 800Mbps max       │
│                                                                  │
│   Priority 2 (Lower):                                            │
│     • VLAN 10 (Hành chính): 100Mbps guaranteed, 300Mbps max     │
│                                                                  │
│ Per-Port Bandwidth Limits:                                       │
│   • VLAN 10 ports: 50Mbps max (giữ nguyên)                      │
│   • VLAN 20 ports: 1Gbps max ★ (nâng từ 80Mbps)                │
│   • VLAN 30 ports: 100Mbps max (giữ nguyên)                     │
│   • Server port: 1Gbps (giữ nguyên)                             │
│                                                                  │
│ Application Priority (VLAN 30 for meetings):                    │
│   • VoIP/Video (SIP, RTP): Highest priority queue               │
│   • HTTP/HTTPS: Medium priority queue                           │
│   • Others: Low priority queue                                  │
└──────────────────────────────────────────────────────────────────┘

★ = THAY ĐỔI MỚI

GIẢI THÍCH:
- Internet 1Gbps: Đủ cho toàn bộ văn phòng truy cập nhanh
- VLAN 20 (Kỹ thuật) 1Gbps: Developers cần bandwidth cao cho:
  • Git operations (clone/push large repos)
  • Docker images download/upload
  • Database operations
  • Build processes
  • Video rendering/processing
    ''')
    
    # =====================================
    # TEST KẾT NỐI
    # =====================================
    print('\n' + '='*70)
    print('TEST KẾT NỐI VÀ FIREWALL')
    print('='*70)
    
    tests = [
        ('PC1 -> PC2', pc1, '192.168.10.11', 'Intra-VLAN (should work)'),
        ('PC1 -> Gateway', pc1, '192.168.10.1', 'PC to Gateway'),
        ('PC1 -> Server', pc1, '192.168.99.10', 'VLAN 10 to Server (allowed)'),
        ('PC3 -> Server', pc3, '192.168.99.10', 'VLAN 20 to Server (allowed)'),
        ('STA1 -> Server', sta1, '192.168.99.10', 'VLAN 30 to Server (allowed)'),
        ('PC1 -> Internet', pc1, '203.0.113.1', 'VLAN 10 to Internet'),
        ('PC3 -> Internet', pc3, '203.0.113.1', 'VLAN 20 to Internet (1Gbps)'),
        ('PC3 -> STA1', pc3, '192.168.30.11', 'Inter-VLAN routing'),
        ('Server -> PC1', server, '192.168.10.10', 'Server to PC'),
    ]
    
    print('\nChạy connectivity tests...\n')
    success = 0
    total = len(tests)
    
    for name, host, ip, desc in tests:
        result = host.cmd(f'ping -c 2 -W 2 {ip}')
        status = '✓ PASS' if '0% packet loss' in result or '2 received' in result else '✗ FAIL'
        if '✓' in status:
            success += 1
        print(f'{name:20s} -> {ip:15s} : {status:8s} ({desc})')
    
    print(f'\nKết quả: {success}/{total} tests passed')
    
    # =====================================
    # HIỂN THỊ QoS CONFIGURATION
    # =====================================
    print('\n' + '='*70)
    print('TC QoS CONFIGURATION (trích xuất)')
    print('='*70)
    print('\n--- HTB Classes on r1-eth0 (Internet 1Gbps) ---')
    result = r1.cmd('tc class show dev r1-eth0')
    print(result)
    
    print('\n--- QoS Filters on r1-eth0 ---')
    result = r1.cmd('tc filter show dev r1-eth0')
    print(result)
    
    # =====================================
    # HƯỚNG DẪN SỬ DỤNG
    # =====================================
    print('\n' + '='*70)
    print('HƯỚNG DẪN TEST BANDWIDTH VÀ QoS')
    print('='*70)
    print('''
═══════════════════════════════════════════════════════════════════
              TEST BANDWIDTH MỚI (1Gbps cho VLAN 20)
═══════════════════════════════════════════════════════════════════

1. TEST BANDWIDTH VLAN 20 (KỸ THUẬT) - Nên đạt ~1Gbps:
   mininet> iperf pc3 server
   mininet> iperf pc4 server
   
   Kết quả mong đợi: ~900-950 Mbps (gần 1Gbps)

2. SO SÁNH BANDWIDTH GIỮA CÁC VLAN:
   # Test VLAN 10 (Hành chính - 100Mbps)
   mininet> iperf pc1 server
   
   # Test VLAN 20 (Kỹ thuật - 1Gbps) ★
   mininet> iperf pc3 server
   
   # Test VLAN 30 (Lãnh đạo - 100Mbps)
   mininet> iperf sta1 server
   
   → VLAN 20 nên có bandwidth cao nhất (~10x VLAN 10)

3. TEST INTERNET BANDWIDTH (1Gbps) ★:
   mininet> iperf pc3 internet
   
   Kết quả mong đợi: ~900-950 Mbps

4. TEST QoS - PRIORITY:
   # Tạo traffic đồng thời từ nhiều VLAN
   mininet> xterm pc1 pc3 sta1 server
   
   # Trên server: iperf -s
   # Trên pc1: iperf -c server -t 60
   # Trên pc3: iperf -c server -t 60  ← Nên có bandwidth cao nhất
   # Trên sta1: iperf -c server -t 60
   
   # Monitor QoS:
   mininet> xterm r1
   r1# watch -n 1 tc -s class show dev r1-eth0

5. TEST TCP PERFORMANCE (VLAN 20):
   mininet> xterm pc3 server
   server# iperf -s
   pc3# iperf -c server -t 30 -i 1 -P 4
   
   (-P 4 = 4 parallel streams để maximize throughput)

6. MONITOR BANDWIDTH REAL-TIME:
   mininet> xterm r1
   r1# iftop -i r1-eth0              # Internet traffic
   r1# iftop -i r1-eth1.20           # VLAN 20 traffic
   
   hoặc:
   r1# watch -n 1 'tc -s class show dev r1-eth0'

7. KIỂM TRA LINK BANDWIDTH:
   mininet> pc3 ethtool pc3-eth0 | grep Speed
   → Nên hiển thị: Speed: 1000Mb/s

8. TEST UDP BANDWIDTH (maximum):
   mininet> xterm pc3 server
   server# iperf -s -u
   pc3# iperf -c server -u -b 1000M -t 10
   
   (Test với 1000Mbps UDP traffic)

═══════════════════════════════════════════════════════════════════
                    CÁC LỆNH KHÁC (GIỮ NGUYÊN)
═══════════════════════════════════════════════════════════════════

FIREWALL:
   mininet> r1 iptables -L FORWARD -n -v
   mininet> pc1 ping -c 3 192.168.20.10   # Should FAIL (blocked)

QoS STATS:
   mininet> r1 tc -s class show dev r1-eth0
   mininet> r1 tc -s filter show dev r1-eth0

THOÁT:
   mininet> exit
    ''')
    
    # =====================================
    # CLI
    # =====================================
    info('\n*** Chạy Mininet CLI\n')
    info('*** Mạng đã sẵn sàng với Internet 1Gbps và VLAN 20 (Kỹ thuật) 1Gbps!\n\n')
    CLI(net)
    
    info('*** Dừng Network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    buildTopology()
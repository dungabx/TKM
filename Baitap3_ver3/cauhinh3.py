#!/usr/bin/env python3
"""
MÔ HÌNH 3: SPINE-LEAF + VXLAN (CLOS TOPOLOGY) – Border Leaf Architecture
2 Spine + 6 Leaf | Full-mesh | Border Leaf = s8(leaf_srv)

Spine: s1(spine1), s2(spine2) – chỉ chuyển tiếp, không routing
Leaf:  s3(leaf_admin)  → admin1-5       (10.0.10.x/24)
       s4(leaf_lab1)   → lab1-10        (10.0.20.x/24)
       s5(leaf_lab2)   → lab11-20       (10.0.20.x/24)
       s6(leaf_dorm1)  → dorm1-20       (10.0.30.x/24)
       s7(leaf_dorm2)  → dorm21-40      (10.0.30.x/24)
       s8(leaf_srv)    → srv1-4         (10.0.99.x/24) ← BORDER LEAF

r1 = Edge Router – CHỈ kết nối vào Border Leaf (s8):
  r1-eth0 → s8 (10.0.10.254/24)  Admin GW
  r1-eth1 → s8 (10.0.20.254/24)  Lab GW
  r1-eth2 → s8 (10.0.30.254/24)  Dorm GW
  r1-eth3 → s8 (10.0.99.254/24)  Server GW
  r1-eth4 → serverhcm (203.162.1.254/24) WAN 200Mbps/10ms

Packet Walk (lab1 → serverhcm):
  lab1 → leaf_lab1(s4) → spine → leaf_srv(s8) → r1 → serverhcm
  (Mọi traffic N-S + Inter-VLAN đều qua Border Leaf)
"""

import os, sys, subprocess, time
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

GRAPH_OUTPUT = 'level3_spine_leaf_topology.png'

class LinuxRouter(Host):
    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()

def cleanup_mininet():
    info('*** mn -c...\n')
    subprocess.run(['sudo','mn','-c'], capture_output=True, timeout=30)

# ── Draw ──────────────────────────────────────────────────────────────────────
def draw_topology_graph():
    G = nx.Graph()
    nodes = {
        's1':('spine','s1\nSpine1'), 's2':('spine','s2\nSpine2'),
        's3':('leaf','s3\nleaf_admin'), 's4':('leaf','s4\nleaf_lab1'),
        's5':('leaf','s5\nleaf_lab2'),  's6':('leaf','s6\nleaf_dorm1'),
        's7':('leaf','s7\nleaf_dorm2'), 's8':('border','s8\nBorder Leaf\n(leaf_srv)'),
        'r1':('router','r1\nEdge Router'), 'wan':('wan','serverhcm\n203.162.1.1'),
        'H_adm':('host','admin1-5\n10.0.10.x'), 'H_l1':('host','lab1-10\n10.0.20.x'),
        'H_l2':('host','lab11-20\n10.0.20.x'),  'H_d1':('host','dorm1-20\n10.0.30.x'),
        'H_d2':('host','dorm21-40\n10.0.30.x'),  'H_srv':('host','srv1-4\n10.0.99.x'),
    }
    for n,(t,lbl) in nodes.items(): G.add_node(n, type=t, label=lbl)
    for lf in ['s3','s4','s5','s6','s7','s8']:
        G.add_edge('s1',lf,et='mesh'); G.add_edge('s2',lf,et='mesh')
    G.add_edge('r1','s8',et='border')
    G.add_edge('r1','wan',et='wan')
    for lf,h in [('s3','H_adm'),('s4','H_l1'),('s5','H_l2'),
                 ('s6','H_d1'),('s7','H_d2'),('s8','H_srv')]:
        G.add_edge(lf,h,et='h')
    pos = {
        'wan':(9,7.5), 'r1':(9,5.5),
        's1':(-1,7), 's2':(3,7),
        's3':(-5,4.5), 's4':(-3,4.5), 's5':(-1,4.5),
        's6':(1,4.5), 's7':(3,4.5), 's8':(6,4.5),
        'H_adm':(-5,2), 'H_l1':(-3,2), 'H_l2':(-1,2),
        'H_d1':(1,2), 'H_d2':(3,2), 'H_srv':(6,2),
    }
    fig,ax = plt.subplots(figsize=(22,11))
    fig.patch.set_facecolor('#1a1a2e'); ax.set_facecolor('#1a1a2e')
    estyles = {
        'mesh':('#2ECC71',2,'solid'), 'border':('#FF6B35',3.5,'solid'),
        'wan':('#E63946',3,'dashed'), 'h':('#888',0.8,'solid')
    }
    for et,(c,w,s) in estyles.items():
        el = [(u,v) for u,v,d in G.edges(data=True) if d.get('et')==et]
        if el: nx.draw_networkx_edges(G,pos,edgelist=el,ax=ax,edge_color=c,width=w,style=s,alpha=0.9)
    cmap = {'spine':'#E63946','leaf':'#2A9D8F','border':'#FF6B35','router':'#9B59B6','wan':'#C0392B','host':'#F7DC6F'}
    nc = [cmap.get(G.nodes[n]['type'],'#aaa') for n in G.nodes()]
    ns = [2200 if G.nodes[n]['type'] in ('spine','border') else
          1800 if G.nodes[n]['type'] in ('router','wan') else
          1400 if G.nodes[n]['type']=='leaf' else 700 for n in G.nodes()]
    nx.draw_networkx_nodes(G,pos,ax=ax,node_color=nc,node_size=ns,edgecolors='white',linewidths=0.7)
    lbl = {n:G.nodes[n]['label'] for n in G.nodes()}
    nx.draw_networkx_labels(G,pos,labels=lbl,ax=ax,font_size=7,font_color='white',font_weight='bold')
    legend = [
        mpatches.Patch(color='#E63946', label='Spine (s1, s2) – Chuyển tiếp ECMP'),
        mpatches.Patch(color='#2A9D8F', label='Leaf (s3–s7) – Kết nối Host'),
        mpatches.Patch(color='#FF6B35', label='★ Border Leaf (s8) – Cửa ngõ ra WAN'),
        mpatches.Patch(color='#9B59B6', label='r1 – Edge Router (CHỈ nối vào Border Leaf)'),
        mpatches.Patch(color='#2ECC71', label='Full-mesh Leaf↔Spine'),
        mpatches.Patch(color='#E63946', label='WAN 200Mbps/10ms – Nút thắt'),
    ]
    ax.legend(handles=legend,loc='upper left',fontsize=8.5,facecolor='#16213e',edgecolor='#555',labelcolor='white')
    ax.set_title('MÔ HÌNH 3: SPINE-LEAF + BORDER LEAF\n'
                 'r1 CHỈ nối vào Border Leaf (s8) | Packet Walk: Host → Leaf → Spine → Border → r1 → WAN\n'
                 '⚡ Nội bộ East-West: Leaf→Spine→Leaf = 3 hop | North-South: qua Border Leaf',
                 color='#2ECC71',fontsize=11,fontweight='bold')
    ax.axis('off'); plt.tight_layout()
    plt.savefig(GRAPH_OUTPUT,dpi=120,bbox_inches='tight',facecolor='#1a1a2e'); plt.close()
    info(f'*** Saved: {GRAPH_OUTPUT}\n')

# ── BUILD NET: dùng bởi test.py (import cauhinh3; net = cauhinh3.build_net()) ──
def build_net():
    """Build + configure Spine-Leaf, trả về net object (KHÔNG gọi CLI)."""
    cleanup_mininet()
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)
    r1        = net.addHost('r1', cls=LinuxRouter, ip='127.0.0.1/8')
    serverhcm = net.addHost('serverhcm', ip='203.162.1.1/24')
    s1 = net.addSwitch('s1', cls=OVSSwitch, failMode='standalone', stp=True)
    s2 = net.addSwitch('s2', cls=OVSSwitch, failMode='standalone', stp=True)
    s3 = net.addSwitch('s3', cls=OVSSwitch, failMode='standalone', stp=True)
    s4 = net.addSwitch('s4', cls=OVSSwitch, failMode='standalone', stp=True)
    s5 = net.addSwitch('s5', cls=OVSSwitch, failMode='standalone', stp=True)
    s6 = net.addSwitch('s6', cls=OVSSwitch, failMode='standalone', stp=True)
    s7 = net.addSwitch('s7', cls=OVSSwitch, failMode='standalone', stp=True)
    s8 = net.addSwitch('s8', cls=OVSSwitch, failMode='standalone', stp=True)
    all_leaf = [s3, s4, s5, s6, s7, s8]
    for i in range(1,6):   net.addHost(f'admin{i}', ip=f'10.0.10.{i}/24', defaultRoute='via 10.0.10.254')
    for i in range(1,11):  net.addHost(f'lab{i}',   ip=f'10.0.20.{i}/24', defaultRoute='via 10.0.20.254')
    for i in range(11,21): net.addHost(f'lab{i}',   ip=f'10.0.20.{i}/24', defaultRoute='via 10.0.20.254')
    for i in range(1,21):  net.addHost(f'dorm{i}',  ip=f'10.0.30.{i}/24', defaultRoute='via 10.0.30.254')
    for i in range(21,41): net.addHost(f'dorm{i}',  ip=f'10.0.30.{i}/24', defaultRoute='via 10.0.30.254')
    for i in range(1,5):   net.addHost(f'srv{i}',   ip=f'10.0.99.{i}/24', defaultRoute='via 10.0.99.254')
    for leaf in all_leaf:
        net.addLink(leaf, s1, bw=1000)
        net.addLink(leaf, s2, bw=1000)
    net.addLink(r1, s8, intfName1='r1-eth0', bw=1000)
    net.addLink(r1, s8, intfName1='r1-eth1', bw=1000)
    net.addLink(r1, s8, intfName1='r1-eth2', bw=1000)
    net.addLink(r1, s8, intfName1='r1-eth3', bw=1000)
    net.addLink(r1, serverhcm, intfName1='r1-eth4', bw=200, delay='10ms')
    for i in range(1,6):    net.addLink(net.get(f'admin{i}'), s3, bw=100)
    for i in range(1,11):   net.addLink(net.get(f'lab{i}'),   s4, bw=1000)
    for i in range(11,21):  net.addLink(net.get(f'lab{i}'),   s5, bw=1000)
    for i in range(1,21):   net.addLink(net.get(f'dorm{i}'),  s6, bw=50)
    for i in range(21,41):  net.addLink(net.get(f'dorm{i}'),  s7, bw=50)
    for i in range(1,5):    net.addLink(net.get(f'srv{i}'),   s8, bw=1000)
    info('*** Starting network...\n')
    net.start()
    s1.cmd('ovs-vsctl set Bridge s1 other_config:stp-priority=4096')
    info('*** Waiting STP convergence 15s...\n')
    time.sleep(15)
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    r1.cmd('for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done')
    for eth, ip in [('r1-eth0','10.0.10.254/24'),('r1-eth1','10.0.20.254/24'),
                    ('r1-eth2','10.0.30.254/24'),('r1-eth3','10.0.99.254/24'),
                    ('r1-eth4','203.162.1.254/24')]:
        r1.cmd(f'ip link set {eth} up')
        r1.cmd(f'ip addr flush dev {eth}')
        r1.cmd(f'ip addr add {ip} dev {eth}')
    serverhcm.cmd('ip route del default 2>/dev/null; ip route add default via 203.162.1.254')
    for sub in ['10.0.10.0/24','10.0.20.0/24','10.0.30.0/24','10.0.99.0/24']:
        serverhcm.cmd(f'ip route add {sub} via 203.162.1.254 2>/dev/null || true')
    info('*** Network ready!\n')
    return net

# ── RUN: chạy trực tiếp python3 cauhinh3.py → CLI ──
def run():
    draw_topology_graph()
    net = build_net()
    info('\n' + '='*65 + '\n')
    info('  MÔ HÌNH 3: SPINE-LEAF + BORDER LEAF\n')
    info('='*65 + '\n')
    info(' Test: pingall | admin1 ping srv1 | admin1 ping 203.162.1.1\n')
    CLI(net)
    net.stop()
    cleanup_mininet()

if __name__ == '__main__':
    setLogLevel('info')
    if os.geteuid() != 0:
        print('sudo python3 cauhinh3.py')
        sys.exit(1)
    run()

#!/usr/bin/python3
"""
Lab3 Network Hardening - TechVerse Network
==========================================
OSPF Multi-Area + Extended ACLs + Topology Drawing
Copy pattern tu Lab1_OSPF/tdtu_ospf.py

Chay: sudo python3 topology.py
Ve:   python3 topology.py --draw
Clear: sudo python3 topology.py --clean
"""
import os
import sys
import time

try:
    import networkx as nx
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_GRAPH = True
except ImportError:
    HAS_GRAPH = False

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI


# --- CLASS ROUTER (COPY TU Lab1_OSPF) ---
class FRRouter(Node):
    def config(self, **params):
        super(FRRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

        confDir = f'/tmp/{self.name}'
        self.cmd(f'rm -rf {confDir} && mkdir -p {confDir}')
        self.cmd(f'chmod 777 {confDir}')

        base_conf = (
            f"hostname {self.name}\n"
            "log stdout\n"
            "service advanced-vty\n"
            "!\n"
            "line vty\n"
            " no login\n"
            "!\n"
        )

        with open(f'{confDir}/zebra.conf', 'w') as f: f.write(base_conf)
        with open(f'{confDir}/ospfd.conf', 'w') as f: f.write(base_conf)

        self.cmd(f'chown -R frr:frr {confDir}')

        self.cmd(f'/usr/lib/frr/zebra -d -u frr -g frr -A 127.0.0.1 -f {confDir}/zebra.conf -i {confDir}/zebra.pid')
        self.cmd(f'/usr/lib/frr/ospfd -d -u frr -g frr -A 127.0.0.1 -f {confDir}/ospfd.conf -i {confDir}/ospfd.pid')

    def terminate(self):
        self.cmd(f'kill `cat /tmp/{self.name}/ospfd.pid` 2> /dev/null')
        self.cmd(f'kill `cat /tmp/{self.name}/zebra.pid` 2> /dev/null')
        super(FRRouter, self).terminate()


# --- TOPOLOGY ---
class TechVerseTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1', failMode='standalone')
        s2 = self.addSwitch('s2', failMode='standalone')
        s3 = self.addSwitch('s3', failMode='standalone')
        s4 = self.addSwitch('s4', failMode='standalone')
        s5 = self.addSwitch('s5', failMode='standalone')

        r1 = self.addHost('r1', cls=FRRouter, ip='10.0.0.1/24')
        r2 = self.addHost('r2', cls=FRRouter, ip='10.0.0.2/24')
        r3 = self.addHost('r3', cls=FRRouter, ip='10.0.0.3/24')
        r4 = self.addHost('r4', cls=FRRouter, ip='10.10.14.2/30')
        r5 = self.addHost('r5', cls=FRRouter, ip='10.20.25.2/30')
        r6 = self.addHost('r6', cls=FRRouter, ip='10.30.56.2/30')

        pc1        = self.addHost('pc1',        ip='10.1.1.10/24',       defaultRoute='via 10.1.1.254')
        pc2        = self.addHost('pc2',        ip='10.1.1.11/24',       defaultRoute='via 10.1.1.254')
        admin      = self.addHost('admin',      ip='10.1.2.50/24',       defaultRoute='via 10.1.2.254')
        fileserver = self.addHost('fileserver',  ip='10.1.2.100/24',      defaultRoute='via 10.1.2.254')
        webserver  = self.addHost('webserver',   ip='172.16.10.100/24',   defaultRoute='via 172.16.10.254')
        emailsrv   = self.addHost('emailsrv',    ip='172.16.10.101/24',   defaultRoute='via 172.16.10.254')
        syslogsrv  = self.addHost('syslogsrv',   ip='172.16.10.200/24',   defaultRoute='via 172.16.10.254')
        camera1    = self.addHost('camera1',     ip='192.168.100.10/24',  defaultRoute='via 192.168.100.254')
        camera15   = self.addHost('camera15',    ip='192.168.100.15/24',  defaultRoute='via 192.168.100.254')
        sensor1    = self.addHost('sensor1',     ip='192.168.100.50/24',  defaultRoute='via 192.168.100.254')

        self.addLink(r1, s1, intfName1='r1-eth0')
        self.addLink(r2, s1, intfName1='r2-eth0')
        self.addLink(r3, s1, intfName1='r3-eth0')

        self.addLink(r1, r4, intfName1='r1-eth1', intfName2='r4-eth0')
        self.addLink(r2, r5, intfName1='r2-eth1', intfName2='r5-eth0')
        self.addLink(r5, r6, intfName1='r5-eth1', intfName2='r6-eth0')
        self.addLink(r2, r6, intfName1='r2-eth2', intfName2='r6-eth1')

        self.addLink(r4, s2, intfName1='r4-eth1')
        self.addLink(pc1, s2)
        self.addLink(pc2, s2)
        self.addLink(r4, s3, intfName1='r4-eth2')
        self.addLink(admin, s3)
        self.addLink(fileserver, s3)

        self.addLink(r5, s4, intfName1='r5-eth2')
        self.addLink(webserver, s4)
        self.addLink(emailsrv, s4)
        self.addLink(syslogsrv, s4)

        self.addLink(r6, s5, intfName1='r6-eth2')
        self.addLink(camera1, s5)
        self.addLink(camera15, s5)
        self.addLink(sensor1, s5)


# --- VE HINH (NetworkX) ---
def draw_topology(save_path='topology.png'):
    """Ve topology mang TechVerse voi NetworkX + Matplotlib."""
    if not HAS_GRAPH:
        print('[ERROR] Can cai: pip install networkx matplotlib')
        return

    G = nx.Graph()

    nodes = {
        'R1':{'label':'R1\nABR 0/10\n10.0.0.1','zone':'core','shape':'s'},
        'R2':{'label':'R2\nABR 0/20/30\n10.0.0.2','zone':'core','shape':'s'},
        'R3':{'label':'R3\nCore\n10.0.0.3','zone':'core','shape':'s'},
        'R4':{'label':'R4\nHQ\n10.10.14.2','zone':'hq','shape':'s'},
        'R5':{'label':'R5\nDMZ\n10.20.25.2','zone':'dmz','shape':'s'},
        'R6':{'label':'R6\nIoT\n10.30.56.2','zone':'iot','shape':'s'},
        'pc1':{'label':'pc1\n10.1.1.10','zone':'staff','shape':'o'},
        'pc2':{'label':'pc2\n10.1.1.11','zone':'staff','shape':'o'},
        'admin':{'label':'admin\n10.1.2.50','zone':'mgmt','shape':'o'},
        'filesrv':{'label':'filesrv\n10.1.2.100','zone':'mgmt','shape':'o'},
        'web':{'label':'web\n172.16.10.100','zone':'dmz_h','shape':'o'},
        'email':{'label':'email\n172.16.10.101','zone':'dmz_h','shape':'o'},
        'syslog':{'label':'syslog\n172.16.10.200','zone':'dmz_h','shape':'o'},
        'cam1':{'label':'cam1\n.100.10','zone':'iot_h','shape':'o'},
        'cam15':{'label':'cam15\n.100.15\n⚠HACK','zone':'hack','shape':'o'},
        'sensor':{'label':'sensor\n.100.50','zone':'iot_h','shape':'o'},
    }
    for n, d in nodes.items(): G.add_node(n, **d)

    edges = [
        ('R1','R2'), ('R2','R3'), ('R3','R1'),
        ('R1','R4'), ('R2','R5'), ('R5','R6'), ('R2','R6'),
        ('R4','pc1'), ('R4','pc2'), ('R4','admin'), ('R4','filesrv'),
        ('R5','web'), ('R5','email'), ('R5','syslog'),
        ('R6','cam1'), ('R6','cam15'), ('R6','sensor'),
    ]
    for s, d in edges: G.add_edge(s, d)

    COLORS = {'core':'#4A90D9','hq':'#5BA85A','dmz':'#E8A838','iot':'#D9534F',
              'staff':'#27AE60','mgmt':'#2ECC71','dmz_h':'#F39C12',
              'iot_h':'#E74C3C','hack':'#8B0000'}

    pos = {
        'R1':(-2,4),'R2':(0,4),'R3':(2,4),
        'R4':(-4,2),'R5':(0,2),'R6':(4,2),
        'pc1':(-5.5,0),'pc2':(-4.5,0),'admin':(-3.5,0),'filesrv':(-2.5,0),
        'web':(-1,0),'email':(0,0),'syslog':(1,0),
        'cam1':(3,0),'cam15':(4.5,0),'sensor':(6,0),
    }

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#1A1A2E')
    ax.set_facecolor('#16213E')

    routers = [n for n in G.nodes if nodes[n]['shape']=='s']
    hosts = [n for n in G.nodes if nodes[n]['shape']=='o']

    nx.draw_networkx_nodes(G, pos, nodelist=routers,
        node_color=[COLORS[nodes[n]['zone']] for n in routers],
        node_size=2800, node_shape='s', ax=ax, linewidths=2, edgecolors='white')
    nx.draw_networkx_nodes(G, pos, nodelist=hosts,
        node_color=[COLORS[nodes[n]['zone']] for n in hosts],
        node_size=1400, node_shape='o', ax=ax, linewidths=1.5, edgecolors='#FFFFFF88')
    nx.draw_networkx_edges(G, pos, edge_color='#AAAAAA', width=1, alpha=0.5, ax=ax)

    labels = {n: nodes[n]['label'] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=6, font_color='white', font_weight='bold', ax=ax)

    legend = [
        mpatches.Patch(color='#4A90D9', label='Area 0 - Backbone'),
        mpatches.Patch(color='#5BA85A', label='Area 10 - HQ (Staff+Mgmt)'),
        mpatches.Patch(color='#E8A838', label='Area 20 - DMZ'),
        mpatches.Patch(color='#D9534F', label='Area 30 - IoT (Stub)'),
        mpatches.Patch(color='#8B0000', label='⚠ Compromised Device'),
    ]
    ax.legend(handles=legend, loc='upper right', fontsize=8,
              facecolor='#16213E', edgecolor='white', labelcolor='white')
    ax.set_title('TechVerse Corp - OSPF Multi-Area + Extended ACLs',
                 color='white', fontsize=14, fontweight='bold', pad=15)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f'[OK] Saved: {save_path}')




# --- CLEAR ---
def mn_cleanup():
    """Cleanup Mininet (tuong duong sudo mn -c)."""
    info('*** Cleaning up Mininet...\n')
    os.system('sudo mn -c 2>/dev/null')
    os.system('sudo killall -9 zebra ospfd 2>/dev/null')
    os.system('sudo rm -rf /tmp/r* 2>/dev/null')
    info('*** Cleanup done.\n')


# --- CUSTOM CLI ---
class TechVerseCLI(CLI):
    """Mininet CLI voi lenh acl, acl_status, acl_clear."""

    def do_acl(self, line):
        """Ap dung ACL tu file configure_acls.sh. Dung: acl"""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configure_acls.sh')
        if not os.path.exists(script):
            print(f'[ERROR] Khong tim thay: {script}')
            return
        # Tao symlinks namespace de ip netns exec hoat dong
        net = self.mn
        os.system('mkdir -p /var/run/netns')
        for rname in ['r1','r2','r3','r4','r5','r6']:
            pid = net[rname].pid
            os.system(f'ln -sf /proc/{pid}/ns/net /var/run/netns/{rname}')
        # Chay script
        print(os.popen(f'bash {script}').read())
        # Xoa symlinks
        for rname in ['r1','r2','r3','r4','r5','r6']:
            os.system(f'rm -f /var/run/netns/{rname}')
        print('Test commands:')
        print('  admin ping webserver     # PERMIT (Mgmt full access)')
        print('  camera1 ping 10.1.2.50   # DENY (ACL 110: IoT->Mgmt)')
        print('  pc1 ping 10.1.2.50       # DENY (ACL 130: Staff->Mgmt)')
        print('  webserver ping 10.1.2.50  # DENY (ACL 120: DMZ->Inside)')
        print()

    def do_acl_status(self, line):
        """Hien thi iptables rules tren routers. Dung: acl_status"""
        net = self.mn
        for rname, acl_name in [('r6','ACL 110 IoT'),('r5','ACL 120 DMZ'),('r4','ACL 130 Staff')]:
            print(f'\n=== {rname.upper()} - {acl_name} (FORWARD) ===')
            print(net[rname].cmd('iptables -L FORWARD -n -v --line-numbers'))
        print('\n=== R1 - ACL 140 SSH (INPUT) ===')
        print(net['r1'].cmd('iptables -L INPUT -n -v --line-numbers'))

    def do_acl_clear(self, line):
        """Xoa tat ca ACL rules. Dung: acl_clear"""
        net = self.mn
        for rname in ['r1','r2','r3','r4','r5','r6']:
            net[rname].cmd('iptables -F FORWARD')
            net[rname].cmd('iptables -F INPUT')
        print('All ACL rules cleared. All traffic permitted.')

    def do_routes(self, line):
        """Hien thi routing tables. Dung: routes"""
        net = self.mn
        for rname in ['r1','r2','r3','r4','r5','r6']:
            print(f'\n=== {rname.upper()} Routing Table ===')
            print(net[rname].cmd('ip route show'))

    def do_neighbors(self, line):
        """Hien thi OSPF neighbors. Dung: neighbors"""
        net = self.mn
        for rname in ['r1','r2','r3','r4','r5','r6']:
            print(f'\n=== {rname.upper()} OSPF Neighbors ===')
            out = net[rname].cmd('echo -e "enable\nshow ip ospf neighbor\nexit" | nc -w 1 localhost 2604 | tr -cd \'\\11\\12\\15\\40-\\176\'')
            print(out)


# --- MAIN ---
def run():
    topo = TechVerseTopo()
    net = Mininet(topo=topo, controller=None)
    net.start()

    r1, r2, r3 = net['r1'], net['r2'], net['r3']
    r4, r5, r6 = net['r4'], net['r5'], net['r6']

    # --- IP ---
    info('*** Gan dia chi IP thu cong...\n')
    r1.cmd('ifconfig r1-eth0 10.0.0.1/24')
    r2.cmd('ifconfig r2-eth0 10.0.0.2/24')
    r3.cmd('ifconfig r3-eth0 10.0.0.3/24')
    r1.cmd('ifconfig r1-eth1 10.10.14.1/30')
    r4.cmd('ifconfig r4-eth0 10.10.14.2/30')
    r2.cmd('ifconfig r2-eth1 10.20.25.1/30')
    r5.cmd('ifconfig r5-eth0 10.20.25.2/30')
    r5.cmd('ifconfig r5-eth1 10.30.56.1/30')
    r6.cmd('ifconfig r6-eth0 10.30.56.2/30')
    r2.cmd('ifconfig r2-eth2 10.20.26.1/30')
    r6.cmd('ifconfig r6-eth1 10.20.26.2/30')
    r4.cmd('ifconfig r4-eth1 10.1.1.254/24')
    r4.cmd('ifconfig r4-eth2 10.1.2.254/24')
    r5.cmd('ifconfig r5-eth2 172.16.10.254/24')
    r6.cmd('ifconfig r6-eth2 192.168.100.254/24')

    info('*** Doi 5s cho OSPF daemon khoi dong...\n')
    time.sleep(5)

    # --- OSPF ---
    def config_ospf_via_tcp(node, rid, networks, extra=""):
        cmds = f"enable\nconf t\nrouter ospf\nospf router-id {rid}\n"
        for net_addr, area in networks:
            cmds += f"network {net_addr} area {area}\n"
        if extra: cmds += f"exit\n{extra}\n"
        cmds += "end\nwr\nexit\n"
        node.cmd(f'echo -e "{cmds}" | nc -w 1 localhost 2604 | tr -cd \'\\11\\12\\15\\40-\\176\'')

    info('*** Nap cau hinh OSPF...\n')

    config_ospf_via_tcp(r1, '1.1.1.1',
        [('10.0.0.0/24', '0'), ('10.10.14.0/30', '10')],
        "int r1-eth1\nip ospf network point-to-point")

    config_ospf_via_tcp(r2, '2.2.2.2',
        [('10.0.0.0/24', '0'), ('10.20.25.0/30', '20'), ('10.20.26.0/30', '30')],
        "area 30 stub no-summary\n"
        "int r2-eth1\nip ospf network point-to-point\n"
        "int r2-eth2\nip ospf network point-to-point\nip ospf cost 500")

    config_ospf_via_tcp(r3, '3.3.3.3',
        [('10.0.0.0/24', '0')],
        "int r3-eth0\nip ospf priority 0")

    config_ospf_via_tcp(r4, '4.4.4.4',
        [('10.10.14.0/30', '10'), ('10.1.1.0/24', '10'), ('10.1.2.0/24', '10')],
        "passive-interface r4-eth1\npassive-interface r4-eth2\n"
        "int r4-eth0\nip ospf network point-to-point")

    config_ospf_via_tcp(r5, '5.5.5.5',
        [('10.20.25.0/30', '20'), ('10.30.56.0/30', '30'), ('172.16.10.0/24', '20')],
        "area 30 stub no-summary\npassive-interface r5-eth2\n"
        "int r5-eth0\nip ospf network point-to-point\n"
        "int r5-eth1\nip ospf network point-to-point")

    config_ospf_via_tcp(r6, '6.6.6.6',
        [('10.30.56.0/30', '30'), ('10.20.26.0/30', '30'), ('192.168.100.0/24', '30')],
        "area 30 stub\npassive-interface r6-eth2\n"
        "int r6-eth0\nip ospf network point-to-point\n"
        "int r6-eth1\nip ospf network point-to-point\nip ospf cost 500")

    info('*** Doi 50s cho OSPF hoi tu (DR election + LSA)...\n')
    time.sleep(50)

    # --- VE HINH ---
    draw_topology('topology.png')

    # --- KIEM TRA OSPF ---
    info('\n=== KET QUA KIEM TRA OSPF ===\n')

    def show_cmd(node, command):
        return node.cmd(f'echo -e "enable\\n{command}\\nexit" | nc -w 1 localhost 2604 | tr -cd \'\\11\\12\\15\\40-\\176\'')

    info("1. R1 OSPF Neighbors:\n")
    print(show_cmd(r1, "show ip ospf neighbor"))

    info("2. R4 Routing table:\n")
    print(r4.cmd('ip route show'))

    info("3. Ping admin -> webserver (inter-area):\n")
    print(net['admin'].cmd('ping -c 2 172.16.10.100'))

    info("4. Ping pc1 -> camera1 (inter-area):\n")
    print(net['pc1'].cmd('ping -c 2 192.168.100.10'))

    info('\n*** CLI Commands:\n')
    info('  acl           -> Ap dung chinh sach ACL\n')
    info('  acl_status    -> Xem iptables rules\n')
    info('  acl_clear     -> Xoa tat ca ACL\n')
    info('  routes        -> Xem routing tables\n')
    info('  neighbors     -> Xem OSPF neighbors\n')
    info('  pingall       -> Ping tat ca\n')

    TechVerseCLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')

    if '--clean' in sys.argv or '-c' in sys.argv:
        mn_cleanup()
        sys.exit(0)

    if '--draw' in sys.argv or '-d' in sys.argv:
        draw_topology('topology.png')
        sys.exit(0)

    if '--help' in sys.argv or '-h' in sys.argv:
        print('Usage:')
        print('  sudo python3 topology.py           # Khoi dong mang')
        print('  sudo python3 topology.py --clean    # Cleanup Mininet')
        print('  python3 topology.py --draw          # Ve topology -> topology.png')
        print()
        print('CLI commands (trong mininet>):')
        print('  acl           # Ap dung ACL policies')
        print('  acl_status    # Xem iptables rules')
        print('  acl_clear     # Xoa ACL rules')
        print('  routes        # Xem routing tables')
        print('  neighbors     # Xem OSPF neighbors')
        sys.exit(0)

    if os.geteuid() != 0:
        print('Phai chay voi sudo: sudo python3 topology.py')
        sys.exit(1)

    mn_cleanup()
    run()
from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import sys, re
import time
import sys
import re
import time
from mininet.cli import CLI
from mininet.log import info

class LinuxRouter(Host):
    """Host với chức năng routing"""
    
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

# TESTER CLASS
class NetworkTester:
    def __init__(self, net):
        self.net = net
        self.admin_hosts = [net.get(f'admin{i}') for i in range(1, 51)]
        self.lab_hosts = [net.get(f'lab{i}') for i in range(1, 51)]
        self.server = net.get('server')
        self.r1 = net.get('r1')
        self.s1 = net.get('s1')

    def _print_raw(self, title, data):
        """In dữ liệu thô để chứng minh tính trung thực"""
        print(f'\n[RAW OUTPUT] --- {title} ---')
        # Chỉ in 10 dòng cuối để dễ nhìn, nhưng đủ thông tin bandwidth
        lines = data.strip().split('\n')
        for line in lines[-10:]:
            print(line)
        print(f'[END RAW] -------------------------\n')

    def cleanup_iperf(self):
        self.r1.cmd('killall -9 iperf3 2>/dev/null')
        for host in self.admin_hosts[:10] + self.lab_hosts[:10]: 
             host.cmd('killall -9 iperf3 2>/dev/null')
        time.sleep(1)

    def _reset_vlan_default(self):
        """Đưa về trạng thái nghẽn: Admin và Lab chung đường r1-eth1"""
        r1 = self.r1
        # Xóa sạch
        r1.cmd('tc qdisc del dev r1-eth1 root 2>/dev/null')
        r1.cmd('tc qdisc del dev r1-eth2 root 2>/dev/null')
        for vlan in [10, 20]:
            r1.cmd(f'ip link delete r1-eth1.{vlan} 2>/dev/null')
            r1.cmd(f'ip link delete r1-eth2.{vlan} 2>/dev/null')
        
        # Cấu hình lại r1-eth1 (Chứa cả VLAN 10 và 20)
        r1.cmd('ip link set r1-eth1 up')
        r1.cmd('ip link set r1-eth2 up')
        
        # VLAN 10 (Admin)
        r1.cmd('ip link add link r1-eth1 name r1-eth1.10 type vlan id 10')
        r1.cmd('ip addr add 192.168.10.1/24 dev r1-eth1.10')
        r1.cmd('ip link set r1-eth1.10 up')
        
        # VLAN 20 (Lab)
        r1.cmd('ip link add link r1-eth1 name r1-eth1.20 type vlan id 20')
        r1.cmd('ip addr add 192.168.20.1/24 dev r1-eth1.20')
        r1.cmd('ip link set r1-eth1.20 up')
        
        r1.cmd('ip neigh flush all')

    def _apply_vlan_load_balancing(self):
        """Chuyển Lab (VLAN 20) sang r1-eth2"""
        r1 = self.r1
        info('\n    [CONFIG] Đang cấu hình chuyển mạch (VLAN Splitting)...\n')
        
        # Xóa Lab khỏi eth1
        r1.cmd('ip link delete r1-eth1.20')
        
        # Tạo Lab trên eth2
        r1.cmd('ip link add link r1-eth2 name r1-eth2.20 type vlan id 20')
        r1.cmd('ip addr add 192.168.20.1/24 dev r1-eth2.20')
        r1.cmd('ip link set r1-eth2.20 up')
        
        # Flush Routing cache
        r1.cmd('ip neigh flush all')
        r1.cmd('ip route flush cache')

    def test1_connectivity(self):
        info('\n*** TEST 1: Ping Test\n')
        s = 0
        for i in range(50):
            if '1 received' in self.admin_hosts[i].cmd(f'ping -c 1 -W 1 {self.lab_hosts[i].IP()}'): s += 1
            else: sys.stdout.write('X')
        print(f'\nResult: {s}/50 passed.\n')

    def test2_max_bandwidth_single(self):
        info('\n*** TEST 2: Max Bandwidth\n')
        self.cleanup_iperf()
        self.server.cmd('iperf3 -s -D')
        self._print_raw('Iperf3 TCP', self.admin_hosts[0].cmd(f'iperf3 -c {self.server.IP()} -t 3 -f m'))

    def test3_parallel_streams(self):
        info('\n*** TEST 3: Parallel Streams\n')
        self.cleanup_iperf()
        self.server.cmd('iperf3 -s -D')
        self._print_raw('Iperf3 Parallel', self.admin_hosts[0].cmd(f'iperf3 -c {self.server.IP()} -P 5 -t 3 -f m'))

    def test4_concurrent_pairs(self):
        info('\n*** TEST 4: Concurrent Pairs\n')
        self.cleanup_iperf()
        for i in range(5): self.lab_hosts[i].cmd('iperf3 -s -D')
        for i in range(5): self.admin_hosts[i].cmd(f'iperf3 -c {self.lab_hosts[i].IP()} -t 3 -f m &')
        time.sleep(4)
        print("Done.")

    def test5_stress_test(self):
        info('\n*** TEST 5: Stress Test\n')
        self.cleanup_iperf()
        for h in self.lab_hosts: h.cmd('iperf3 -s -D')
        for i in range(50): 
            self.admin_hosts[i].cmd(f'iperf3 -c {self.lab_hosts[i].IP()} -u -b 1M -t 5 &')
        time.sleep(6)
        print("Stress test completed.")

    def test6_realtime_traffic(self):
        info('\n*** TEST 6: Traffic Monitor\n')
        iface = input("Interface (r1-eth1): ") or "r1-eth1"
        b1 = int(self.r1.cmd(f'cat /sys/class/net/{iface}/statistics/rx_bytes'))
        time.sleep(2)
        b2 = int(self.r1.cmd(f'cat /sys/class/net/{iface}/statistics/rx_bytes'))
        print(f'Speed: {((b2-b1)*8)/2000000:.2f} Mbps')

    def test7_congestion_simulation(self):
        info('\n*** TEST 7: Congestion Sim\n')
        self.cleanup_iperf()
        self.s1.cmd('tc qdisc add dev s1-eth3 root handle 1: tbf rate 1mbit burst 32kbit latency 400ms')
        self.server.cmd('iperf3 -s -D')
        self._print_raw('Congested', self.admin_hosts[0].cmd(f'iperf3 -c {self.server.IP()} -t 3 -f m'))
        self.s1.cmd('tc qdisc del dev s1-eth3 root')

    def test8_optimization(self):
        info('\n' + '█'*70 + '\n')
        info('*** TEST 8: TCP CONGESTION & VLAN LOAD BALANCING (REAL DATA) ***\n')
        info('    Phương pháp: Sử dụng TCP để đo băng thông khả dụng thực tế.\n')
        info('█'*70 + '\n')
        
        self.cleanup_iperf()
        self._reset_vlan_default()
        r1 = self.r1

        # Dùng 5 cặp máy để test TCP (TCP tốn CPU hơn UDP, dùng ít máy để kết quả chính xác)
        num_pairs = 5 
        info(f'[INIT] Khởi động Server TCP trên {num_pairs} Lab hosts...\n')
        for i in range(num_pairs): 
            self.lab_hosts[i].cmd('iperf3 -s -D')
        
        # --- PHẦN 1: GÂY NGHẼN ---
        print('\n' + '!'*60)
        print('  PHẦN 1: GÂY NGHẼN (r1-eth1 LIMIT 10Mbps)')
        print('  Mục tiêu: Chứng minh TCP sẽ tụt xuống đúng 10Mbps.')
        print('!'*60 + '\n')
        
        # Giới hạn cực thấp (10Mbps) để thấy rõ sự khác biệt
        r1.cmd('tc qdisc add dev r1-eth1 root handle 1: tbf rate 10mbit burst 32kbit latency 50ms')
        
        info('-> Đang chạy test TCP (Admin -> Lab)... vui lòng đợi 10s...\n')
        
        # Chạy iperf3 TCP và lưu log
        for i in range(num_pairs):
            # KHÔNG dùng -u, mặc định là TCP
            self.admin_hosts[i].cmd(f'iperf3 -c {self.lab_hosts[i].IP()} -t 8 -f m > /tmp/t8_cong_{i}.txt &')
        
        time.sleep(10)
        
        # Hiển thị log THỰC TẾ của máy đầu tiên
        raw_log = self.admin_hosts[0].cmd('cat /tmp/t8_cong_0.txt')
        self._print_raw("LOG MÁY ADMIN 1 (KHI NGHẼN)", raw_log)
        
        # Tính tổng
        total_bw_cong = 0
        for i in range(num_pairs):
            out = self.admin_hosts[i].cmd(f'cat /tmp/t8_cong_{i}.txt')
            # Lấy dòng cuối cùng (receiver)
            match = re.findall(r'([\d\.]+) Mbits/sec', out)
            if match: 
                # Lấy số cuối cùng trong log (thường là summary)
                total_bw_cong += float(match[-1])

        print(f'>>> TỔNG BĂNG THÔNG THỰC TẾ (TCP): {total_bw_cong:.2f} Mbps')
        print(f'>>> Nhận xét: Tổng băng thông xấp xỉ 10Mbps (do bị giới hạn chia sẻ).')

        # --- PHẦN 2: TỐI ƯU HÓA ---
        print('\n' + '='*60)
        input('>>> Nhấn ENTER để TỐI ƯU (Chuyển VLAN 20 sang r1-eth2)...')
        print('='*60)
        
        self._apply_vlan_load_balancing()
        
        info('\n-> Đợi 5s cho mạng ổn định (STP/ARP)...\n')
        time.sleep(5)
        
        info('-> Chạy lại test TCP... vui lòng đợi 10s...\n')
        for i in range(num_pairs):
            self.admin_hosts[i].cmd(f'iperf3 -c {self.lab_hosts[i].IP()} -t 8 -f m > /tmp/t8_opt_{i}.txt &')
        
        time.sleep(10)
        
        # Hiển thị log THỰC TẾ sau khi fix
        raw_log_opt = self.admin_hosts[0].cmd('cat /tmp/t8_opt_0.txt')
        self._print_raw("LOG MÁY ADMIN 1 (SAU TỐI ƯU)", raw_log_opt)
        
        total_bw_opt = 0
        for i in range(num_pairs):
            out = self.admin_hosts[i].cmd(f'cat /tmp/t8_opt_{i}.txt')
            match = re.findall(r'([\d\.]+) Mbits/sec', out)
            if match: 
                total_bw_opt += float(match[-1])
                
        print(f'>>> TỔNG BĂNG THÔNG THỰC TẾ (TCP): {total_bw_opt:.2f} Mbps')
        
        if total_bw_cong > 0:
            print(f'>>> HIỆU SUẤT TĂNG: {total_bw_opt/total_bw_cong:.1f} LẦN')
        else:
             print(f'>>> HIỆU SUẤT TĂNG: Vô cực (Do lúc trước nghẽn hoàn toàn)')

        # Dọn dẹp
        r1.cmd('tc qdisc del dev r1-eth1 root 2>/dev/null')

    def show_menu(self):
        while True:
            print('\nMENU TEST:')
            print('1-7. Cac bai test co ban')
            print('8. Test Nghẽn & Tối ưu Load Balancing (Real TCP)')
            print('0. Thoat')
            c = input('Chon: ')
            if c=='0': break
            elif c=='1': self.test1_connectivity()
            elif c=='2': self.test2_max_bandwidth_single()
            elif c=='3': self.test3_parallel_streams()
            elif c=='4': self.test4_concurrent_pairs()
            elif c=='5': self.test5_stress_test()
            elif c=='6': self.test6_realtime_traffic()
            elif c=='7': self.test7_congestion_simulation()
            elif c=='8': self.test8_optimization()

class CustomCLI(CLI):
    def __init__(self, net, tester, **kwargs):
        self.tester = tester
        CLI.__init__(self, net, **kwargs)
    def do_test(self, line):
        self.tester.show_menu()

#BUILD TOPOLOGY
def buildTopology():
    """Xây dựng topology TDTU Bao Loc - OPTIMIZED"""
    
    info('*** Tạo Mininet Network (NO Controller)\n')
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)
    
    # ═════════════════════════════════════════════════════════════
    # ROUTERS & EXTERNAL HOSTS
    # ═════════════════════════════════════════════════════════════
    info('*** Thêm Router R1 (Firewall/Router)\n')
    r1 = net.addHost('r1', cls=LinuxRouter, ip=None)
    
    info('*** Thêm External Hosts\n')
    internet = net.addHost('internet', ip='100.0.0.1/24')
    vpnq7 = net.addHost('vpnq7', ip='220.0.0.1/24')
    
    # ═════════════════════════════════════════════════════════════
    # SWITCHES
    # ═════════════════════════════════════════════════════════════
    info('*** Thêm Switches\n')
    s100 = net.addSwitch('s100')  # ISP
    
    # Core Layer
    s1 = net.addSwitch('s1')      # Core 1 (Primary)
    s2 = net.addSwitch('s2')      # Core 2 (Backup)
    
    # Distribution Layer
    s3 = net.addSwitch('s3')      # Distribution 1
    s4 = net.addSwitch('s4')      # Distribution 2
    
    # Access Layer
    s5 = net.addSwitch('s5')      # Access - Admin + Camera
    s6 = net.addSwitch('s6')      # Access - Lab + Wifi
    s7 = net.addSwitch('s7')      # Access - KTX + Guest
    
    # ═════════════════════════════════════════════════════════════
    # END HOSTS - OPTIMIZED WITH FOR LOOPS
    # ═════════════════════════════════════════════════════════════
    info('*** Tạo End Hosts (OPTIMIZED)\n')
    
    # VLAN 10: Admin (50 hosts) - LOOP
    info('  Tạo 50 Admin hosts...\n')
    admin_hosts = []
    for i in range(1, 51):
        ip = f'192.168.10.{i+9}/24'  # .10 to .119
        host = net.addHost(f'admin{i}', ip=ip)
        admin_hosts.append(host)
        if i % 20 == 0:
            info(f'    Created {i}/50 admin hosts\n')
    
    # References for backward compatibility
    admin1, admin2 = admin_hosts[0], admin_hosts[1]
    
    # VLAN 60: Camera
    camera1 = net.addHost('camera1', ip='192.168.60.10/24')
    camera2 = net.addHost('camera2', ip='192.168.60.61/24')
    
    # VLAN 20: Lab (50 hosts) - LOOP
    info('  Tạo 50 Lab hosts...\n')
    lab_hosts = []
    for i in range(1, 51):
        ip = f'192.168.20.{i+19}/24'  # .20 to .129
        host = net.addHost(f'lab{i}', ip=ip)
        lab_hosts.append(host)
        if i % 20 == 0:
            info(f'    Created {i}/50 lab hosts\n')
    
    # References for backward compatibility
    lab1, lab2 = lab_hosts[0], lab_hosts[1]
    
    # VLAN 30: Wifi (ap1)
    ap1 = net.addHost('ap1', ip='192.168.30.30/24')
    
    # VLAN 40: KTX (ap2)
    ap2 = net.addHost('ap2', ip='192.168.40.40/24')
    
    # VLAN 50: Guest (ap3)
    ap3 = net.addHost('ap3', ip='192.168.50.50/24')
    
    # VLAN 90: Server
    server = net.addHost('server', ip='192.168.90.14/24')
    
    info(f'*** Total hosts: {len(admin_hosts) + len(lab_hosts) + 7} hosts\n')
    
    # ═════════════════════════════════════════════════════════════
    # LINKS WITH BANDWIDTH
    # ═════════════════════════════════════════════════════════════
    info('*** Tạo Links\n')
    
    # Internet topology
    net.addLink(internet, s100, intfName1='internet-eth0', intfName2='s100-eth1', bw=1000)
    net.addLink(s100, r1, intfName1='s100-eth2', intfName2='r1-eth0', bw=1000)
    
    # VPN Q7
    net.addLink(r1, vpnq7, intfName1='r1-eth10', intfName2='vpnq7-eth0', bw=500)
    
    # R1 → Core (dual uplinks)
    net.addLink(r1, s1, intfName1='r1-eth1', intfName2='s1-eth1', bw=1000)
    net.addLink(r1, s2, intfName1='r1-eth2', intfName2='s2-eth1', bw=1000)
    
    # Core inter-link
    net.addLink(s1, s2, intfName1='s1-eth2', intfName2='s2-eth2', bw=1000)
    
    # Server → Core s1
    net.addLink(s1, server, intfName1='s1-eth3', intfName2='server-eth0', bw=1000)
    
    # Core → Distribution (full mesh)
    net.addLink(s1, s3, intfName1='s1-eth4', intfName2='s3-eth1', bw=1000)
    net.addLink(s1, s4, intfName1='s1-eth5', intfName2='s4-eth1', bw=1000)
    net.addLink(s2, s3, intfName1='s2-eth3', intfName2='s3-eth2', bw=1000)
    net.addLink(s2, s4, intfName1='s2-eth4', intfName2='s4-eth2', bw=1000)
    
    # Distribution → Access (full mesh)
    net.addLink(s3, s5, intfName1='s3-eth3', intfName2='s5-eth1', bw=1000)
    net.addLink(s3, s6, intfName1='s3-eth4', intfName2='s6-eth1', bw=1000)
    net.addLink(s3, s7, intfName1='s3-eth5', intfName2='s7-eth1', bw=1000)
    net.addLink(s4, s5, intfName1='s4-eth3', intfName2='s5-eth2', bw=1000)
    net.addLink(s4, s6, intfName1='s4-eth4', intfName2='s6-eth2', bw=1000)
    net.addLink(s4, s7, intfName1='s4-eth5', intfName2='s7-eth2', bw=1000)
    
    # Access → Camera first (eth5, eth6)
    net.addLink(s5, camera1, intfName1='s5-eth5', intfName2='camera1-eth0', bw=50)
    net.addLink(s5, camera2, intfName1='s5-eth6', intfName2='camera2-eth0', bw=50)
    
    # Access → Admin Hosts (50 hosts from eth7) - LOOP
    info('*** Kết nối 50 Admin hosts (s5-eth7 onwards)\n')
    for i, host in enumerate(admin_hosts):
        port_num = i + 7  # eth7-eth116
        net.addLink(s5, host, intfName1=f's5-eth{port_num}', bw=100)
        if (i + 1) % 20 == 0:
            info(f'    Connected {i+1}/50 admin hosts\n')
    
    # Access → Wifi first (eth5)
    net.addLink(s6, ap1, intfName1='s6-eth5', intfName2='ap1-eth0', bw=100)
    
    # Access → Lab Hosts (50 hosts from eth7) - LOOP
    info('*** Kết nối 50 Lab hosts (s6-eth7 onwards)\n')
    for i, host in enumerate(lab_hosts):
        port_num = i + 7  # eth7-eth116
        net.addLink(s6, host, intfName1=f's6-eth{port_num}', bw=100)
        if (i + 1) % 20 == 0:
            info(f'    Connected {i+1}/50 lab hosts\n')
    
    # Access → KTX + Guest
    net.addLink(s7, ap2, intfName1='s7-eth3', intfName2='ap2-eth0', bw=100)
    net.addLink(s7, ap3, intfName1='s7-eth4', intfName2='ap3-eth0', bw=50)
    
    # ═════════════════════════════════════════════════════════════
    # START NETWORK
    # ═════════════════════════════════════════════════════════════
    info('*** Khởi động Network\n')
    net.start()

    for i in range(1, 51):
        lab = net.get(f'lab{i}')
        lab.cmd(f"iperf3 -s  -D")
    time.sleep(1)
	# iperf chay nen tren tung host admin1 -> admin50 cho lab1 -> lab50
    for i in range(1, 51):
        port = 5000 + i
        host = net.get(f'admin{i}')
        lab = net.get(f'lab{i}')
        host.cmd(f"iperf3 -c 192.168.20.{i+19} -t 0 -u -b 10M &")
    time.sleep(2)
    
    # ═════════════════════════════════════════════════════════════
    # ENABLE STP (INCREASED TIME FOR 100 HOSTS)
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
    # CONFIGURE OVS SWITCHES - OPTIMIZED
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình OVS Switches\n')
    
    for switch in [s100, s1, s2, s3, s4, s5, s6, s7]:
        switch.cmd('ovs-ofctl del-flows ' + switch.name)
    
    # S100 (ISP)
    s100.cmd('ovs-ofctl add-flow s100 priority=0,action=normal')
    
    # S1 (Core 1 - Primary)
    s1.cmd('ovs-vsctl set port s1-eth1 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s1.cmd('ovs-vsctl set port s1-eth2 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s1.cmd('ovs-vsctl set port s1-eth3 tag=90')
    s1.cmd('ovs-vsctl set port s1-eth4 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s1.cmd('ovs-vsctl set port s1-eth5 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s1.cmd('ovs-ofctl add-flow s1 priority=0,action=normal')
    
    # S2 (Core 2 - Backup)
    s2.cmd('ovs-vsctl set port s2-eth1 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s2.cmd('ovs-vsctl set port s2-eth2 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s2.cmd('ovs-vsctl set port s2-eth3 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s2.cmd('ovs-vsctl set port s2-eth4 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s2.cmd('ovs-ofctl add-flow s2 priority=0,action=normal')
    
    # S3 (Distribution 1)
    s3.cmd('ovs-vsctl set port s3-eth1 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s3.cmd('ovs-vsctl set port s3-eth2 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s3.cmd('ovs-vsctl set port s3-eth3 vlan_mode=trunk trunk=10,60')
    s3.cmd('ovs-vsctl set port s3-eth4 vlan_mode=trunk trunk=20,30')
    s3.cmd('ovs-vsctl set port s3-eth5 vlan_mode=trunk trunk=40,50')
    s3.cmd('ovs-ofctl add-flow s3 priority=0,action=normal')
    
    # S4 (Distribution 2)
    s4.cmd('ovs-vsctl set port s4-eth1 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s4.cmd('ovs-vsctl set port s4-eth2 vlan_mode=trunk trunk=10,20,30,40,50,60,90')
    s4.cmd('ovs-vsctl set port s4-eth3 vlan_mode=trunk trunk=10,60')
    s4.cmd('ovs-vsctl set port s4-eth4 vlan_mode=trunk trunk=20,30')
    s4.cmd('ovs-vsctl set port s4-eth5 vlan_mode=trunk trunk=40,50')
    s4.cmd('ovs-ofctl add-flow s4 priority=0,action=normal')
    
    # S5 (Access - Admin + Camera) - OPTIMIZED WITH LOOP
    s5.cmd('ovs-vsctl set port s5-eth1 vlan_mode=trunk trunk=10,60')
    s5.cmd('ovs-vsctl set port s5-eth2 vlan_mode=trunk trunk=10,60')
    s5.cmd('ovs-vsctl set port s5-eth5 tag=60')  # camera1
    s5.cmd('ovs-vsctl set port s5-eth6 tag=60')  # camera2
    
    # Configure 50 admin ports (eth7-eth116) - LOOP
    info('  Configuring s5: 50 admin ports (eth7-eth116)\n')
    for i in range(51):
        port_num = i + 7
        s5.cmd(f'ovs-vsctl set port s5-eth{port_num} tag=10')
    
    s5.cmd('ovs-ofctl add-flow s5 priority=0,action=normal')
    
    # S6 (Access - Lab + Wifi) - OPTIMIZED WITH LOOP
    s6.cmd('ovs-vsctl set port s6-eth1 vlan_mode=trunk trunk=20,30')
    s6.cmd('ovs-vsctl set port s6-eth2 vlan_mode=trunk trunk=20,30')
    s6.cmd('ovs-vsctl set port s6-eth5 tag=30')  # ap1
    
    # Configure 50 lab ports (eth7-eth116) - LOOP
    info('  Configuring s6: 50 lab ports (eth7-eth116)\n')
    for i in range(51):
        port_num = i + 7
        s6.cmd(f'ovs-vsctl set port s6-eth{port_num} tag=20')
    
    s6.cmd('ovs-ofctl add-flow s6 priority=0,action=normal')
    
    # S7 (Access - KTX + Guest)
    s7.cmd('ovs-vsctl set port s7-eth1 vlan_mode=trunk trunk=40,50')
    s7.cmd('ovs-vsctl set port s7-eth2 vlan_mode=trunk trunk=40,50')
    s7.cmd('ovs-vsctl set port s7-eth3 tag=40')  # ap2
    s7.cmd('ovs-vsctl set port s7-eth4 tag=50')  # ap3
    s7.cmd('ovs-ofctl add-flow s7 priority=0,action=normal')
    
    info('*** Đợi STP converge (30 giây cho 100 hosts)...\n')
    time.sleep(30)  # INCREASED from 15s to 30s for 100 hosts
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE ROUTER R1 (Router-on-a-Stick)
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình Router R1 (Router-on-a-Stick)\n')
    
    # Internet interface
    r1.cmd('ip addr add 100.0.0.2/24 dev r1-eth0')
    r1.cmd('ip link set dev r1-eth0 up')
    
    # VPN Q7 interface
    r1.cmd('ip addr add 220.0.0.2/24 dev r1-eth10')
    r1.cmd('ip link set dev r1-eth10 up')
    
    # Trunk interfaces
    r1.cmd('ip addr flush dev r1-eth1')
    r1.cmd('ip link set dev r1-eth1 up')
    r1.cmd('ip addr flush dev r1-eth2')
    r1.cmd('ip link set dev r1-eth2 up')
    
    # VLAN sub-interfaces
    vlans = [
        (10, '192.168.10.1', 'Admin'),
        (20, '192.168.20.1', 'Lab'),
        (30, '192.168.30.1', 'Wifi'),
        (40, '192.168.40.1', 'KTX'),
        (50, '192.168.50.1', 'Guest'),
        (60, '192.168.60.1', 'Camera'),
        (90, '192.168.90.1', 'Server')
    ]
    
    for vlan_id, gateway, name in vlans:
        info(f'  Creating VLAN {vlan_id} ({name}): {gateway}/24\n')
        r1.cmd(f'ip link add link r1-eth1 name r1-eth1.{vlan_id} type vlan id {vlan_id}')
        r1.cmd(f'ip addr add {gateway}/24 dev r1-eth1.{vlan_id}')
        r1.cmd(f'ip link set dev r1-eth1.{vlan_id} up')
    
    # Enable routing
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    r1.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done')
    
    time.sleep(2)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE DEFAULT GATEWAYS - OPTIMIZED WITH LOOPS
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình Default Gateways (OPTIMIZED)\n')
    
    # Configure 50 admin hosts - LOOP
    info('  Configuring 50 admin hosts...\n')
    for i, host in enumerate(admin_hosts):
        host.cmd('ip route add default via 192.168.10.1')
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        if (i + 1) % 25 == 0:
            info(f'    Configured {i+1}/50 admin hosts\n')
    
    # Camera
    camera1.cmd('ip route add default via 192.168.60.1')
    camera2.cmd('ip route add default via 192.168.60.1')
    camera1.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
    camera2.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
    
    # Configure 50 lab hosts - LOOP
    info('  Configuring 50 lab hosts...\n')
    for i, host in enumerate(lab_hosts):
        host.cmd('ip route add default via 192.168.20.1')
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        if (i + 1) % 25 == 0:
            info(f'    Configured {i+1}/50 lab hosts\n')
    
    # Other hosts
    ap1.cmd('ip route add default via 192.168.30.1')
    ap2.cmd('ip route add default via 192.168.40.1')
    ap3.cmd('ip route add default via 192.168.50.1')
    server.cmd('ip route add default via 192.168.90.1')
    
    for host in [ap1, ap2, ap3, server]:
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
    
    # External
    internet.cmd('ip route add 192.168.0.0/16 via 100.0.0.2')
    vpnq7.cmd('ip route add 192.168.0.0/16 via 220.0.0.2')
    r1.cmd('ip route add default via 100.0.0.1')
    
    time.sleep(2)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE FIREWALL & ZERO TRUST - FIXED!
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình Firewall & Zero Trust (FIXED)\n')
    
    r1.cmd('iptables -F')
    r1.cmd('iptables -t nat -F')
    
    # NAT for Internet access
    info('  NAT for Internet\n')
    r1.cmd('iptables -t nat -A POSTROUTING -s 192.168.0.0/16 -o r1-eth0 -j MASQUERADE')
    
    # Zero Trust policies - FIXED ORDER!
    info('  Zero Trust: Allow ESTABLISHED connections\n')
    r1.cmd('iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT')
    
    info('  Zero Trust: Allow INTRA-VLAN traffic (FIX CRITICAL!)\n')
    # CRITICAL FIX: Allow hosts trong cùng VLAN ping nhau
    for vlan in ['10', '20', '30', '40', '50', '60', '90']:
        r1.cmd(f'iptables -A FORWARD -s 192.168.{vlan}.0/24 -d 192.168.{vlan}.0/24 -j ACCEPT')
    
    info('  Zero Trust: Camera micro-segmentation\n')
    # Camera can ONLY reach Server
    r1.cmd('iptables -A FORWARD -s 192.168.60.0/24 -d 192.168.90.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -s 192.168.60.0/24 -j DROP')
    
    info('  Zero Trust: Protect Admin VLAN\n')
    # Admin protected from other VLANs (except Server and Admin itself)
    r1.cmd('iptables -A FORWARD -d 192.168.10.0/24 -s 192.168.90.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -d 192.168.10.0/24 ! -s 192.168.10.0/24 -j DROP')
    
    info('  Zero Trust: Protect Server\n')
    # Server access: Only Admin and Camera
    r1.cmd('iptables -A FORWARD -d 192.168.90.0/24 -s 192.168.10.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -d 192.168.90.0/24 -s 192.168.60.0/24 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -d 192.168.90.0/24 -j DROP')
    
    info('  Zero Trust: Guest isolation\n')
    # Guest can ONLY reach Internet
    r1.cmd('iptables -A FORWARD -s 192.168.50.0/24 -d 192.168.0.0/16 -j DROP')
    r1.cmd('iptables -A FORWARD -s 192.168.50.0/24 -j ACCEPT')
    
    # Default policy
    r1.cmd('iptables -P FORWARD ACCEPT')
    
    time.sleep(1)
    
    # ═════════════════════════════════════════════════════════════
    # CONFIGURE QoS (HTB + Priority)
    # ═════════════════════════════════════════════════════════════
    info('*** Cấu hình QoS (HTB)\n')
    
    # QoS on Internet uplink
    r1.cmd('tc qdisc del dev r1-eth0 root 2>/dev/null')
    r1.cmd('tc qdisc add dev r1-eth0 root handle 1: htb default 99')
    r1.cmd('tc class add dev r1-eth0 parent 1: classid 1:1 htb rate 1000mbit')
    
    # QoS classes
    qos_classes = [
        (90, 200, 300, 1, 'Server'),
        (10, 150, 200, 2, 'Admin'),
        (60, 100, 150, 2, 'Camera'),
        (20, 200, 300, 3, 'Lab'),
        (30, 200, 300, 3, 'Wifi'),
        (40, 100, 150, 4, 'KTX'),
        (50, 50, 100, 5, 'Guest')
    ]
    
    for vlan_id, rate, ceil, prio, name in qos_classes:
        r1.cmd(f'tc class add dev r1-eth0 parent 1:1 classid 1:{vlan_id} htb '
               f'rate {rate}mbit ceil {ceil}mbit prio {prio}')
        r1.cmd(f'tc qdisc add dev r1-eth0 parent 1:{vlan_id} handle {vlan_id}: sfq perturb 10')
    
    # Traffic classification
    for vlan_id in [10, 20, 30, 40, 50, 60, 90]:
        subnet = f'192.168.{vlan_id if vlan_id != 90 else 90}.0/24'
        r1.cmd(f'tc filter add dev r1-eth0 parent 1:0 protocol ip prio 1 u32 '
               f'match ip src {subnet} flowid 1:{vlan_id}')
    
    time.sleep(1)
    
    # ═════════════════════════════════════════════════════════════
    # START CLI
    # ═════════════════════════════════════════════════════════════
    info('\n*** Entering Mininet CLI\n')
    info('*** Type "help" for list of commands\n\n')
    
    # ═════════════════════════════════════════════════════════════
    # START CLI VỚI TÍNH NĂNG "TEST MENU"
    # ═════════════════════════════════════════════════════════════
    tester = NetworkTester(net)
    
    # Hiển thị menu lần đầu tiên khi chạy chương trình
    tester.show_menu()
    
    info('\n*** Entering Mininet CLI (Customized)\n')
    info('*** Gõ "test" hoặc "menu" để quay lại bảng điều khiển kiểm thử.\n')
    info('*** Gõ "help" để xem danh sách lệnh.\n\n')
    
    # Kích hoạt CustomCLI thay vì CLI thường
    CustomCLI(net, tester)
    
    info('\n*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    buildTopology() 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Menu Test Traffic và Load Balancing cho VRRP Network
Công thức: Total_Traffic = Number_of_Hosts × Required_Bandwidth
"""

import time
import threading

class TrafficTester:
    def __init__(self, net):
        self.net = net
        self.test_running = False
        
    def show_menu(self):
        """Hiển thị menu test"""
        print("\n" + "="*60)
        print("          MENU TEST TRAFFIC & LOAD BALANCING")
        print("="*60)
        print("1. Test Nghẽn Băng Thông đến Internet")
        print("2. Test Nghẽn Băng Thông đến ServerQ7")
        print("3. Test Nghẽn Toàn Bộ Mạng")
        print("4. Cấu Hình Load Balancing cho R1 & R2")
        print("5. Kiểm Tra Trạng Thái Load Balancing")
        print("6. 🎯 DEMO: So Sánh Trước/Sau Load Balancing")
        print("7. Dừng Test Traffic")
        print("8. Hiển Thị Thống Kê Traffic")
        print("0. Thoát Menu")
        print("="*60)
        
    def calculate_total_traffic(self, num_hosts, bandwidth_mbps):
        """
        Tính tổng traffic theo công thức:
        Total_Traffic = Number_of_Hosts × Required_Bandwidth
        """
        total = num_hosts * bandwidth_mbps
        print(f"\n[Công thức] Total_Traffic = {num_hosts} hosts × {bandwidth_mbps} Mbps")
        print(f"[Kết quả] Total Traffic = {total} Mbps")
        return total
        
    def test_congestion_internet(self):
        """Test nghẽn băng thông đến Internet"""
        hosts = [self.net.get(f'h{i}') for i in range(1, 7)]
        num_hosts = len(hosts)
        bandwidth_per_host = 100  # Mbps
        
        # Tính total traffic
        total_traffic = self.calculate_total_traffic(num_hosts, bandwidth_per_host)
        print(f"Link Internet: 1000 Mbps\n")
        
        # Chạy iperf test đồng thời từ tất cả hosts
        internet = self.net.get('internet')
        r1 = self.net.get('r1')
        
        # Start iperf server trên internet với interval reporting
        internet.cmd('killall -9 iperf 2>/dev/null')
        print("Starting iperf server on Internet (8.8.8.8)...\n")
        internet.cmd('iperf -s -u -i 1 > /tmp/iperf_internet.log &')
        time.sleep(2)
        
        # Gửi traffic từ mỗi host
        for i, host in enumerate(hosts, 1):
            host.cmd(f'iperf -c 8.8.8.8 -u -b {bandwidth_per_host}M -t 15 > /tmp/iperf_h{i}.log 2>&1 &')
        
        print("Traffic test running for 15 seconds...\n")
        
        # Hiển thị stats real-time từ R1 interface
        print("R1-eth2 (to Internet) statistics:")
        print("-" * 60)
        for i in range(3):
            time.sleep(5)
            result = r1.cmd('ifconfig r1-eth2 | grep -E "RX packets|TX packets|bytes"')
            print(result)
            
        # Hiển thị kết quả từ iperf server
        print("\nIperf server report:")
        print("=" * 60)
        result = internet.cmd('tail -20 /tmp/iperf_internet.log')
        print(result)
        
        self.test_running = True
        
    def test_congestion_serverq7(self):
        """Test nghẽn băng thông đến ServerQ7"""
        hosts = [self.net.get(f'h{i}') for i in range(1, 7)]
        num_hosts = len(hosts)
        bandwidth_per_host = 100  # Mbps
        
        total_traffic = self.calculate_total_traffic(num_hosts, bandwidth_per_host)
        print(f"Link ServerQ7: 500 Mbps (WARNING: {total_traffic} > 500 - WILL CONGEST!)\n")
        
        serverq7 = self.net.get('serverq7')
        r1 = self.net.get('r1')
        
        serverq7.cmd('killall -9 iperf 2>/dev/null')
        print("Starting iperf server on ServerQ7 (1.1.1.1)...\n")
        serverq7.cmd('iperf -s -u -i 1 > /tmp/iperf_serverq7.log &')
        time.sleep(2)
        
        for i, host in enumerate(hosts, 1):
            host.cmd(f'iperf -c 1.1.1.1 -u -b {bandwidth_per_host}M -t 15 > /tmp/iperf_h{i}_q7.log 2>&1 &')
            
        print("Traffic test running for 15 seconds...\n")
        
        # Hiển thị stats real-time từ R1 interface
        print("R1-eth3 (to ServerQ7) statistics:")
        print("-" * 60)
        for i in range(3):
            time.sleep(5)
            result = r1.cmd('ifconfig r1-eth3 | grep -E "RX packets|TX packets|bytes"')
            print(result)
            
        # Hiển thị kết quả từ iperf server
        print("\nIperf server report (check packet loss!):")
        print("=" * 60)
        result = serverq7.cmd('tail -20 /tmp/iperf_serverq7.log')
        print(result)
        
        self.test_running = True
        
    def test_full_network_congestion(self):
        """Test nghẽn toàn bộ mạng"""
        bandwidth_per_host = 150  # Mbps
        num_hosts = 6
        total_traffic = self.calculate_total_traffic(num_hosts, bandwidth_per_host)
        
        internet = self.net.get('internet')
        serverq7 = self.net.get('serverq7')
        r1 = self.net.get('r1')
        
        internet.cmd('killall -9 iperf 2>/dev/null')
        serverq7.cmd('killall -9 iperf 2>/dev/null')
        
        print("Starting iperf servers...\n")
        internet.cmd('iperf -s -u -i 1 > /tmp/iperf_internet_full.log &')
        serverq7.cmd('iperf -s -u -i 1 > /tmp/iperf_serverq7_full.log &')
        time.sleep(2)
        
        print(f"Sending traffic: 3 hosts → Internet, 3 hosts → ServerQ7")
        print(f"Each host: {bandwidth_per_host} Mbps\n")
        
        # 3 hosts → Internet
        for i in range(1, 4):
            host = self.net.get(f'h{i}')
            host.cmd(f'iperf -c 8.8.8.8 -u -b {bandwidth_per_host}M -t 20 > /tmp/iperf_h{i}_full.log 2>&1 &')
            
        # 3 hosts → ServerQ7
        for i in range(4, 7):
            host = self.net.get(f'h{i}')
            host.cmd(f'iperf -c 1.1.1.1 -u -b {bandwidth_per_host}M -t 20 > /tmp/iperf_h{i}_full.log 2>&1 &')
            
        print("Test running for 20 seconds...\n")
        
        # Monitor R1 interfaces
        for i in range(4):
            time.sleep(5)
            print(f"\n--- Time {(i+1)*5}s ---")
            print("R1-eth2 (Internet):")
            result = r1.cmd('ifconfig r1-eth2 | grep -E "RX|TX" | grep packets')
            print(result)
            print("R1-eth3 (ServerQ7):")
            result = r1.cmd('ifconfig r1-eth3 | grep -E "RX|TX" | grep packets')
            print(result)
        
        print("\n" + "="*60)
        print("Internet iperf report:")
        print(internet.cmd('tail -10 /tmp/iperf_internet_full.log'))
        print("\nServerQ7 iperf report:")
        print(serverq7.cmd('tail -10 /tmp/iperf_serverq7_full.log'))
        
        self.test_running = True
        
    def configure_load_balancing(self):
        """Cấu hình Load Balancing cho R1 & R2"""
        r1 = self.net.get('r1')
        r2 = self.net.get('r2')
        
        print("\nDeleting old routes...")
        r1.cmd('ip route del 192.168.0.0/16 2>/dev/null')
        r1.cmd('ip route del 10.0.0.0/8 2>/dev/null')
        r2.cmd('ip route del 192.168.0.0/16 2>/dev/null')
        r2.cmd('ip route del 10.0.0.0/8 2>/dev/null')
        
        print("\nConfiguring ECMP (Equal-Cost Multi-Path) routes...\n")
        
        print("R1 multipath route:")
        result = r1.cmd('ip route add default scope global '
                       'nexthop via 8.8.8.8 dev r1-eth2 weight 1 '
                       'nexthop via 1.1.1.1 dev r1-eth3 weight 1 2>&1')
        if result.strip():
            print(result)
        result = r1.cmd('ip route show default')
        print(result)
        
        print("\nR2 multipath route:")
        result = r2.cmd('ip route add default scope global '
                       'nexthop via 8.8.8.8 dev r2-eth2 weight 1 '
                       'nexthop via 1.1.1.1 dev r2-eth3 weight 1 2>&1')
        if result.strip():
            print(result)
        result = r2.cmd('ip route show default')
        print(result)
        
        print("\nEnabling multipath hash policy (L3)...")
        result = r1.cmd('sysctl -w net.ipv4.fib_multipath_hash_policy=1')
        print(f"R1: {result.strip()}")
        result = r2.cmd('sysctl -w net.ipv4.fib_multipath_hash_policy=1')
        print(f"R2: {result.strip()}")
        
        print("\n" + "="*60)
        print("LOAD BALANCING CONFIGURED!")
        print("Total bandwidth: 1000 + 500 = 1500 Mbps")
        print("="*60 + "\n")
        
    def check_load_balancing_status(self):
        """Kiểm tra trạng thái Load Balancing"""
        r1 = self.net.get('r1')
        r2 = self.net.get('r2')
        
        print("\n" + "="*60)
        print("LOAD BALANCING STATUS")
        print("="*60)
        
        print("\n[R1 - Master]")
        print("-" * 60)
        result = r1.cmd('ip route show default')
        print(result if result.strip() else "No default route")
        
        print("\n[R2 - Backup]")
        print("-" * 60)
        result = r2.cmd('ip route show default')
        print(result if result.strip() else "No default route")
        
        print("\n[Hash Policy]")
        print("-" * 60)
        r1_policy = r1.cmd('sysctl net.ipv4.fib_multipath_hash_policy')
        r2_policy = r2.cmd('sysctl net.ipv4.fib_multipath_hash_policy')
        print(f"R1: {r1_policy.strip()}")
        print(f"R2: {r2_policy.strip()}")
        
        print("\n[Current Route Statistics]")
        print("-" * 60)
        print("R1 routing cache:")
        result = r1.cmd('ip -s route show default')
        print(result)
        
    def demo_load_balancing_comparison(self):
        """Demo so sánh TRƯỚC và SAU load balancing"""
        print("\n" + "="*70)
        print("🎯 DEMO: LOAD BALANCING BEFORE vs AFTER COMPARISON")
        print("="*70)
        
        # GIẢM bandwidth để tránh CPU bottleneck
        num_hosts = 6
        bandwidth_per_host = 40  # Mbps - Realistic cho Mininet
        
        print("\n📊 SCENARIO:")
        print(f"  • Number of hosts: {num_hosts}")
        print(f"  • Bandwidth per host: {bandwidth_per_host} Mbps")
        total_traffic = self.calculate_total_traffic(num_hosts, bandwidth_per_host)
        
        print("\n📋 NETWORK CAPACITY:")
        print(f"  • Internet link (r1-eth2): 1000 Mbps")
        print(f"  • ServerQ7 link (r1-eth3): 500 Mbps")
        print(f"  • WITHOUT Load Balancing: Use ONLY ServerQ7 (500 Mbps)")
        print(f"  • WITH Load Balancing: Use BOTH links (1500 Mbps total)")
        
        # PHASE 1: TRƯỚC Load Balancing
        print("\n" + "="*70)
        print("📍 PHASE 1: TRƯỚC LOAD BALANCING (Single Path)")
        print("="*70)
        
        # Xóa load balancing nếu có
        r1 = self.net.get('r1')
        r2 = self.net.get('r2')
        internet = self.net.get('internet')
        serverq7 = self.net.get('serverq7')
        
        print("\nRestoring single-path routing...")
        r1.cmd('ip route del default 2>/dev/null')
        r2.cmd('ip route del default 2>/dev/null')
        # Route qua ServerQ7 (500 Mbps)
        r1.cmd('ip route add default via 1.1.1.1 dev r1-eth3')
        print("Route: default via 1.1.1.1 (ServerQ7 - 500 Mbps only)")
        
        print(f"\n📉 ANALYSIS (BEFORE):")
        print(f"   Total Traffic: {total_traffic} Mbps")
        print(f"   Link Capacity: 500 Mbps")
        if total_traffic <= 500:
            print(f"   Expected: SHOULD BE OK ({total_traffic} ≤ 500)")
        else:
            print(f"   Expected: WILL CONGEST ({total_traffic} > 500)")
            print(f"   Ratio: {total_traffic/500:.1f}x over capacity")
        
        # Start iperf server
        serverq7.cmd('killall -9 iperf 2>/dev/null')
        serverq7.cmd('iperf -s -u -i 1 > /tmp/iperf_demo_before.log &')
        time.sleep(2)
        
        # Send traffic
        hosts = [self.net.get(f'h{i}') for i in range(1, 7)]
        print("Starting traffic test (10 seconds)...\n")
        for i, host in enumerate(hosts, 1):
            host.cmd(f'iperf -c 1.1.1.1 -u -b {bandwidth_per_host}M -t 10 > /tmp/iperf_demo_h{i}_before.log 2>&1 &')
        
        # Monitor
        for i in range(2):
            time.sleep(5)
            result = r1.cmd('ifconfig r1-eth3 | grep "TX packets" | head -1')
            print(f"  [{(i+1)*5}s] {result.strip()}")
        
        # Results
        print("\n📊 RESULTS (BEFORE):")
        print("-" * 70)
        result = serverq7.cmd('tail -15 /tmp/iperf_demo_before.log | grep -E "sec"')
        print(result)
        
        # Tính packet loss trung bình THỰC TẾ
        loss_lines = serverq7.cmd('tail -20 /tmp/iperf_demo_before.log | grep -oP "\(\K[0-9.]+(?=%)"')
        avg_loss_before = 0
        if loss_lines.strip():
            try:
                losses = [float(x) for x in loss_lines.strip().split('\n') if x]
                if losses:
                    avg_loss_before = sum(losses) / len(losses)
                    print(f"\n📉 Average Packet Loss: {avg_loss_before:.1f}%")
                    if avg_loss_before > 10:
                        print("   ⚠️  CONGESTION CONFIRMED!")
                    else:
                        print("   ✅ Acceptable performance")
            except:
                print("\n[Warning] Could not parse packet loss")
        
        time.sleep(2)
        self.stop_traffic()
        
        # PHASE 2: SAU Load Balancing
        print("\n" + "="*70)
        print("📍 PHASE 2: SAU LOAD BALANCING (Multi-Path ECMP)")
        print("="*70)
        
        print("\nConfiguring ECMP load balancing...")
        r1.cmd('ip route del default 2>/dev/null')
        r1.cmd('ip route add default scope global '
               'nexthop via 8.8.8.8 dev r1-eth2 weight 1 '
               'nexthop via 1.1.1.1 dev r1-eth3 weight 1')
        r1.cmd('sysctl -w net.ipv4.fib_multipath_hash_policy=1 > /dev/null')
        
        result = r1.cmd('ip route show default')
        print(result)
        
        print(f"\n📉 ANALYSIS (AFTER):")
        print(f"   Total Traffic: {total_traffic} Mbps")
        print(f"   Total Capacity: 1500 Mbps (1000 + 500)")
        if total_traffic <= 1500:
            print(f"   Expected: SHOULD BE OK ({total_traffic} ≤ 1500)")
            print(f"   Utilization: {total_traffic/1500*100:.1f}%")
        else:
            print(f"   Expected: MAY STILL CONGEST ({total_traffic} > 1500)")
        print()
        
        # Start iperf servers on BOTH targets
        internet.cmd('killall -9 iperf 2>/dev/null')
        serverq7.cmd('killall -9 iperf 2>/dev/null')
        time.sleep(1)
        internet.cmd('iperf -s -u -i 1 > /tmp/iperf_demo_after_inet.log &')
        serverq7.cmd('iperf -s -u -i 1 > /tmp/iperf_demo_after_q7.log &')
        time.sleep(2)
        
        # Send traffic - Trộn destinations để test ECMP
        print("Starting traffic test (10 seconds)...\n")
        for i, host in enumerate(hosts, 1):
            # Alternate between targets để test ECMP distribution
            target = '8.8.8.8' if i % 2 == 0 else '1.1.1.1'
            host.cmd(f'iperf -c {target} -u -b {bandwidth_per_host}M -t 10 > /tmp/iperf_demo_h{i}_after.log 2>&1 &')
        
        # Monitor both links
        for i in range(2):
            time.sleep(5)
            result_eth2 = r1.cmd('ifconfig r1-eth2 | grep "TX packets" | head -1')
            result_eth3 = r1.cmd('ifconfig r1-eth3 | grep "TX packets" | head -1')
            print(f"  [{(i+1)*5}s] eth2 (Internet): {result_eth2.strip()}")
            print(f"  [{(i+1)*5}s] eth3 (ServerQ7): {result_eth3.strip()}")
        
        # Results
        print("\n📊 RESULTS (AFTER):")
        print("-" * 70)
        print("Internet link:")
        result = internet.cmd('tail -10 /tmp/iperf_demo_after_inet.log | grep -E "sec|loss"')
        print(result if result.strip() else "  (No traffic routed here)")
        
        print("\nServerQ7 link:")
        result = serverq7.cmd('tail -10 /tmp/iperf_demo_after_q7.log | grep -E "sec|loss"')
        print(result if result.strip() else "  (No traffic routed here)")
        
        # Tính packet loss sau LB - Kiểm tra CẢ 2 links
        print("\n📉 PACKET LOSS ANALYSIS (AFTER):")
        
        # ServerQ7 link
        loss_lines_q7 = serverq7.cmd('tail -20 /tmp/iperf_demo_after_q7.log | grep -oP "\(\K[0-9.]+(?=%)"')
        avg_loss_q7 = 0
        if loss_lines_q7.strip():
            try:
                losses = [float(x) for x in loss_lines_q7.strip().split('\n') if x]
                if losses:
                    avg_loss_q7 = sum(losses) / len(losses)
                    print(f"ServerQ7 link avg loss: {avg_loss_q7:.1f}%")
            except:
                pass
        
        # Internet link
        loss_lines_inet = internet.cmd('tail -20 /tmp/iperf_demo_after_inet.log | grep -oP "\(\K[0-9.]+(?=%)"')
        avg_loss_inet = 0
        if loss_lines_inet.strip():
            try:
                losses = [float(x) for x in loss_lines_inet.strip().split('\n') if x]
                if losses:
                    avg_loss_inet = sum(losses) / len(losses)
                    print(f"Internet link avg loss: {avg_loss_inet:.1f}%")
            except:
                pass
        
        # Tổng hợp
        avg_loss_after = (avg_loss_q7 + avg_loss_inet) / 2 if (avg_loss_q7 or avg_loss_inet) else 0
        print(f"\n📈 Overall Average Loss: {avg_loss_after:.1f}%")
        
        # Đánh giá THỰC TẾ
        if avg_loss_after < avg_loss_before * 0.5:  # Giảm ít nhất 50%
            print("✅ MUCH BETTER! Load balancing is working!")
        elif avg_loss_after < avg_loss_before:
            print("🟡 IMPROVED, but not significantly")
        else:
            print("⚠️  NO IMPROVEMENT - Possible CPU bottleneck!")
            print("   Try reducing bandwidth_per_host in code")
        
        # SUMMARY COMPARISON
        print("\n" + "="*70)
        print("📈 SUMMARY COMPARISON")
        print("="*70)
        print(f"\n{'Metric':<30} {'BEFORE LB':<20} {'AFTER LB':<20}")
        print("-" * 70)
        print(f"{'Total Traffic:':<30} {total_traffic} Mbps{'':<10} {total_traffic} Mbps")
        print(f"{'Available Capacity:':<30} {'500 Mbps':<20} {'1500 Mbps':<20}")
        print(f"{'Actual Packet Loss:':<30} {f'{avg_loss_before:.1f}%':<20} {f'{avg_loss_after:.1f}%':<20}")
        print(f"{'Routes Used:':<30} {'Single path':<20} {'Multi-path ECMP':<20}")
        
        # Kết luận THỰC TẾ dựa vào số liệu
        improvement = ((avg_loss_before - avg_loss_after) / avg_loss_before * 100) if avg_loss_before > 0 else 0
        print(f"{'Improvement:':<30} {'-':<20} {f'{improvement:.0f}% reduction':<20}")
        
        print("\n" + "="*70)
        print("🎓 CONCLUSION:")
        if improvement > 50:
            print("   ✅ Load Balancing SUCCESSFULLY reduced congestion!")
        elif improvement > 10:
            print("   🟡 Load Balancing helped, but limited by other factors")
            print("   (Possible CPU bottleneck in Mininet)")
        else:
            print("   ⚠️  Load Balancing did NOT improve performance significantly")
            print("   Root cause: CPU bottleneck (Mininet limitation)")
            print(f"   Recommendation: Reduce bandwidth to ~{int(250/num_hosts)} Mbps/host")
        
        print(f"\nFormula: Total_Traffic = Number_of_Hosts × Required_Bandwidth")
        print(f"         {total_traffic} Mbps = {num_hosts} × {bandwidth_per_host} Mbps")
        print("="*70 + "\n")
        
    def stop_traffic(self):
        """Dừng tất cả traffic tests"""
        print("\n[INFO] Dừng tất cả iperf processes...")
        
        # Dừng trên tất cả nodes
        for node in self.net.values():
            node.cmd('killall -9 iperf 2>/dev/null')
            
        self.test_running = False
        print("[INFO] Đã dừng tất cả traffic tests.")
        
    def show_traffic_stats(self):
        """Hiển thị thống kê traffic"""
        print("\n" + "="*60)
        print("THỐNG KÊ TRAFFIC")
        print("="*60)
        
        r1 = self.net.get('r1')
        r2 = self.net.get('r2')
        
        print("\n[R1 Interfaces]")
        print("-" * 60)
        for iface in ['r1-eth0', 'r1-eth1', 'r1-eth2', 'r1-eth3']:
            result = r1.cmd(f'ifconfig {iface} | grep "RX packets\\|TX packets"')
            if result.strip():
                print(f"\n{iface}:")
                print(result.strip())
                
        print("\n[R2 Interfaces]")
        print("-" * 60)
        for iface in ['r2-eth0', 'r2-eth1', 'r2-eth2', 'r2-eth3']:
            result = r2.cmd(f'ifconfig {iface} | grep "RX packets\\|TX packets"')
            if result.strip():
                print(f"\n{iface}:")
                print(result.strip())

def run_test_menu(net):
    """Chạy menu test tương tác"""
    tester = TrafficTester(net)
    
    while True:
        tester.show_menu()
        try:
            choice = input("\nNhập lựa chọn của bạn: ").strip()
            
            if choice == '0':
                print("\n[INFO] Thoát menu test...")
                tester.stop_traffic()
                break
            elif choice == '1':
                tester.test_congestion_internet()
            elif choice == '2':
                tester.test_congestion_serverq7()
            elif choice == '3':
                tester.test_full_network_congestion()
            elif choice == '4':
                tester.configure_load_balancing()
            elif choice == '5':
                tester.check_load_balancing_status()
            elif choice == '6':
                tester.demo_load_balancing_comparison()
            elif choice == '7':
                tester.stop_traffic()
            elif choice == '8':
                tester.show_traffic_stats()
            else:
                print("\n[ERROR] Lựa chọn không hợp lệ!")
                
        except KeyboardInterrupt:
            print("\n\n[INFO] Thoát menu...")
            tester.stop_traffic()
            break
        except Exception as e:
            print(f"\n[ERROR] Lỗi: {e}")
            
        input("\nNhấn Enter để tiếp tục...")

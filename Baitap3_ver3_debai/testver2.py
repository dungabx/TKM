#!/usr/bin/env python3
"""
TESTVER2.PY – 8 BÀI TEST SO SÁNH KIẾN TRÚC MẠNG
===================================================
Mỗi test so sánh các mô hình cụ thể để chứng minh TẠI SAO kiến trúc
mạng tiến hóa. Import build_net() từ cauhinh1-4.py.

Cách dùng:
  sudo python3 testver2.py                # Tự động: chạy 8 test lần lượt
  sudo python3 testver2.py test1          # Thủ công: chỉ chạy Test 1
  sudo python3 testver2.py test3 test6    # Chạy Test 3 và Test 6

8 Bài Test:
  test1 – MAC Flooding           (Model 1 vs 2)
  test2 – STP vs ECMP Bandwidth  (Model 2 vs 3)
  test3 – Core/Spine Failure     (Model 2 vs 3)
  test4 – STP Reconvergence      (Model 2 vs 4)
  test5 – Anycast vs Central GW  (Model 2 vs 3)
  test6 – Dynamic QoS            (Model 1,2,3 vs 4)
  test7 – Control Plane Failure  (Model 3 vs 4)
  test8 – Multi-hop Latency      (Model 2 vs 3)

Quy tắc: Kết quả PING/IPERF = RAW output – NGHIÊM CẤM dùng print() định dạng
"""

import os, sys, re, time, argparse, subprocess, importlib
from mininet.log import setLogLevel, info
from mininet.link import TCLink

# ── Màu terminal ────────────────────────────────────────────────
R='\033[91m'; G='\033[92m'; Y='\033[93m'; C='\033[96m'
B='\033[1m';  E='\033[0m';  SEP='━'*72

def banner(msg):  print(f'\n{B}{C}{SEP}\n  {msg}\n{SEP}{E}', flush=True)
def section(msg): print(f'\n{B}{Y}── {msg} ──{E}', flush=True)
def note(msg):    print(f'{G}  • {msg}{E}', flush=True)
def warn(msg):    print(f'{Y}  ⚠ {msg}{E}', flush=True)
def fail(msg):    print(f'{R}  ✗ {msg}{E}', flush=True)
def raw_out(t):
    if t:
        sys.stdout.write(t)
        if not t.endswith('\n'): sys.stdout.write('\n')
        sys.stdout.flush()

def parse_ping(raw):
    # Chỉ lấy phần ping statistics (bỏ garbage từ macof/iperf lẫn vào)
    stats_section = raw
    marker = re.search(r'---.*ping statistics\s*---', raw)
    if marker:
        stats_section = raw[marker.start():]
    lm  = re.search(r'(\d+(?:\.\d+)?)%\s+packet\s+loss', stats_section)
    rtm = re.search(r'rtt .* = [\d.]+/([\d.]+)/([\d.]+)/([\d.]+)', stats_section)
    loss = round(float(lm.group(1))) if lm  else 100
    if loss > 100: loss = 100
    avg  = float(rtm.group(1)) if rtm else 9999.0
    mdev = float(rtm.group(3)) if rtm else 9999.0
    return loss, avg, mdev

def parse_iperf_bw(raw):
    """Trích tổng bandwidth từ iperf output (Mbits/sec hoặc Gbits/sec)."""
    matches = re.findall(r'([\d.]+)\s+(Mbits|Gbits)/sec', raw)
    if not matches: return 0.0
    last = matches[-1]
    bw = float(last[0])
    if last[1] == 'Gbits': bw *= 1000
    return bw

def cleanup():
    subprocess.run(['sudo','mn','-c'], capture_output=True, timeout=30)

def import_cauhinh(n):
    cwd = os.path.dirname(os.path.abspath(__file__))
    if cwd not in sys.path: sys.path.insert(0, cwd)
    return importlib.import_module(f'cauhinh{n}')

def warmup(net, wan_ip='203.162.1.1'):
    admin = net.get('admin1')
    admin.cmd(f'ping -c 2 -W 2 {wan_ip} 2>/dev/null')
    time.sleep(1)

def build_and_warmup(n):
    note(f'Import cauhinh{n}.py → build_net()...')
    mod = import_cauhinh(n)
    net = mod.build_net()
    warmup(net)
    return net

def stop_net(net, n):
    note(f'Dừng mạng mô hình {n}...')
    net.stop()
    cleanup()

LABELS = {
    '1': 'Mô hình 1 – Flat',
    '2': 'Mô hình 2 – 3-Layer',
    '3': 'Mô hình 3 – Spine-Leaf',
    '4': 'Mô hình 4 – SDN+QoS',
}

def print_compare(test_name, results):
    """In bảng so sánh sau mỗi test. results = list of dict."""
    print(f'\n{B}{C}  KẾT QUẢ: {test_name}{E}')
    print(f'  {"─"*70}')
    for r in results:
        line = f'  {r["label"]:<30}'
        for k,v in r.items():
            if k == 'label': continue
            line += f'  {k}: {v}'
        print(line)
    print(f'  {"─"*70}')

# ════════════════════════════════════════════════════════════════
# TEST 1: MAC FLOODING (Model 1 vs 2)
# Mục đích: Mạng phẳng sụp đổ, mạng VLAN cách ly
# ════════════════════════════════════════════════════════════════
def test1():
    banner('TEST 1: Tấn công Tràn bảng MAC (Model 1 vs 2)')
    print('  macof từ dorm bơm MAC giả + iperf flood → admin1 ping srv1')
    print(f'  {Y}Model 1: MAC table tràn → Hub mode → admin bị flood → trễ/mất gói{E}')
    print(f'  {G}Model 2: VLAN cách ly → dorm flood không ảnh hưởng admin{E}')
    results = []

    for n in ['1','2']:
        section(f'{LABELS[n]}')
        net = None
        try:
            net = build_and_warmup(n)
            admin = net.get('admin1')
            dorm1 = net.get('dorm1')
            srv_ip = '10.0.4.1' if n == '1' else '10.0.99.1'

            if n == '1':
                # ── Model 1: Giới hạn MAC table cực nhỏ → macof tràn ngay ──
                note('Giới hạn MAC table = 2 entry (mô phỏng switch thật)...')
                for sw in ['s1','s2']:
                    net.get(sw).cmd(f'ovs-vsctl set Bridge {sw} other-config:mac-table-size=2')
                time.sleep(1)

            # Warm-up ping srv1 (Model 2 cần đợi STP)
            note(f'Warm-up: admin1 → {srv_ip}...')
            for _ in range(3):
                admin.cmd(f'ping -c 2 -W 2 {srv_ip} 2>/dev/null')
                time.sleep(1)

            # Ping TRƯỚC khi flood (baseline)
            note('Ping TRƯỚC khi flood (baseline):')
            print('─'*60, flush=True)
            raw_before = admin.cmd(f'ping -c 5 -i 0.2 {srv_ip} 2>/dev/null')
            raw_out(raw_before)
            print('─'*60, flush=True)
            loss_b, avg_b, _ = parse_ping(raw_before)

            # macof flood – 20 dorm, timeout 20s
            note('dorm1-20 chạy macof flood MAC giả (timeout 20s)...')
            for i in range(1, 21):
                d = net.get(f'dorm{i}')
                intf = d.defaultIntf().name
                d.cmd(f'timeout 20 macof -i {intf} &>/dev/null &')
            time.sleep(3)  # Đợi MAC table tràn hoàn toàn

            # Heavy traffic từ dorm 21-40 → tạo congestion nghiêm trọng
            note('dorm21-40 iperf UDP flood 100Mbps/host = 2Gbps tổng...')
            srv = net.get('srv1')
            srv.cmd('iperf -s -u -D -p 5010 2>/dev/null')
            for i in range(21, 41):
                d = net.get(f'dorm{i}')
                d.cmd(f'iperf -c {srv_ip} -u -b 100M -p 5010 -t 20 &')
            time.sleep(5)  # Đợi traffic bão hòa

            # RAW PING TRONG khi flood
            print(f'\n{B}[RAW PING – admin1 → {srv_ip} | MAC flood + 2Gbps traffic]{E}', flush=True)
            print('─'*60, flush=True)
            raw = admin.cmd(f'ping -c 15 -i 0.5 {srv_ip} 2>/dev/null')
            raw_out(raw)
            print('─'*60, flush=True)

            loss, avg, mdev = parse_ping(raw)
            note(f'→ Trước: Loss={loss_b}% Avg={avg_b:.1f}ms')
            note(f'→ Trong flood: Loss={loss}% | Avg={avg:.1f}ms | Mdev={mdev:.1f}ms')
            results.append({'label': LABELS[n],
                           'Trước': f'{loss_b}%/{avg_b:.1f}ms',
                           'Trong flood': f'{loss}%/{avg:.1f}ms'})

            # Cleanup
            for i in range(1, 21):
                net.get(f'dorm{i}').cmd('pkill macof 2>/dev/null')
            for i in range(21, 41):
                net.get(f'dorm{i}').cmd('kill %iperf 2>/dev/null')
            srv.cmd('pkill iperf 2>/dev/null')

        except Exception as e:
            fail(f'Lỗi: {e}')
            import traceback; traceback.print_exc()
            results.append({'label': LABELS[n], 'Trước': 'ERROR', 'Trong flood': 'ERROR'})
        finally:
            if net: stop_net(net, n)

    print_compare('Test 1 – MAC Flooding', results)

# ════════════════════════════════════════════════════════════════
# TEST 2: STP vs ECMP BANDWIDTH (Model 2 vs 3)
# Mục đích: STP khóa cổng = lãng phí, Spine-Leaf gộp BW
# ════════════════════════════════════════════════════════════════
def parse_iperf_sum(raw):
    """Chỉ lấy dòng SUM cuối cùng của iperf client (tổng kết toàn bộ thời gian)."""
    lines = raw.strip().splitlines()
    # Case-insensitive: xử lý cả Bits/sec lẫn bits/sec (tùy phiên bản iperf)
    sum_lines = [l for l in lines if 'SUM' in l and re.search(r'bits/sec', l, re.I)]
    if not sum_lines:
        sum_lines = [l for l in lines if re.search(r'bits/sec', l, re.I)]
    if not sum_lines:
        return 0.0
    last = sum_lines[-1]
    m = re.search(r'([\d.]+)\s+([MmGg])bits/sec', last, re.I)
    if not m: return 0.0
    bw = float(m.group(1))
    if m.group(2).upper() == 'G': bw *= 1000
    return bw

def test2():
    banner('TEST 2: Nút thắt Cổ chai Băng thông (Model 2 vs 3)')
    print('  STP block 1 link = lãng phí + bottleneck khi tải cao')
    print(f'  {Y}Model 2: 1 Core chịu toàn bộ tải → nghẽn → latency tăng{E}')
    print(f'  {G}Model 3: 2 Spine phân tải → ít nghẽn → latency ổn định{E}')
    results = []

    for n in ['2','3']:
        section(f'{LABELS[n]}')
        net = None
        srv_proc = None
        try:
            net = build_and_warmup(n)
            srv1  = net.get('srv1')
            lab1  = net.get('lab1')
            srv_ip = srv1.IP()

            # ── Warm-up routing (quan trọng: cả lab1 lẫn lab11) ──
            note('Warm-up routing...')
            for h in ['lab1', 'lab11']:
                for _ in range(3):
                    net.get(h).cmd(f'ping -c 2 -W 3 {srv_ip} 2>/dev/null')
            chk = lab1.cmd(f'ping -c 3 -W 3 {srv_ip} 2>&1')
            if '0 received' in chk:
                warn('lab1 → srv1: KHÔNG THÔNG! Skip.')
                results.append({'label': LABELS[n], 'STP blocked': '-',
                               'Iperf tổng': 'N/A',
                               'Latency thường': '-', 'Latency flood': '-',
                               'Tăng độ trễ': '-'})
                continue

            # ── PHASE 1: Đếm STP blocking ports ──
            note('PHASE 1: STP blocking ports...')
            blocked_total = 0
            sw_list = ['s2','s3','s4','s5','s7','s8','s9','s10'] if n == '2' \
                      else ['s1','s2','s3','s4','s5','s6','s7','s8']
            print('─'*60, flush=True)
            for sw_name in sw_list:
                try:
                    sw = net.get(sw_name)
                    out = sw.cmd(f'ovs-appctl stp/show {sw_name} 2>/dev/null')
                    b = out.count('blocking') + out.count('discarding')
                    blocked_total += b
                    if b > 0:
                        sys.stdout.write(f'  {sw_name}: {b} port(s) BLOCKING\n')
                        sys.stdout.flush()
                except Exception:
                    pass
            if blocked_total == 0:
                sys.stdout.write(f'  {G}→ 0 port BLOCKING (ECMP: tất cả link active){E}\n')
            else:
                sys.stdout.write(
                    f'  {Y}→ {blocked_total} port bị STP khóa = lãng phí 1 tuyến 1Gbps{E}\n')
            sys.stdout.flush()
            print('─'*60, flush=True)

            # ── PHASE 2: Ping baseline (không flood) ──
            note('PHASE 2: Ping baseline lab1 → srv1 (không có traffic)...')
            print(f'\n{B}[PING BASELINE – lab1 → {srv_ip} (không flood)]{E}', flush=True)
            print('─'*60, flush=True)
            raw_b = lab1.cmd(f'ping -c 10 -i 0.2 {srv_ip} 2>/dev/null')
            raw_out(raw_b)
            print('─'*60, flush=True)
            loss_b, avg_b, _ = parse_ping(raw_b)
            note(f'→ Baseline: loss={loss_b:.0f}%  avg={avg_b:.2f}ms')

            # ── PHASE 3: Flood 20 labs + ping đo latency ──
            note('PHASE 3: Bắt đầu flood 20 Lab iperf → srv1...')
            srv1.cmd('pkill iperf 2>/dev/null')
            time.sleep(0.5)
            srv_proc = srv1.popen(['iperf', '-s', '-p', '5001'])
            time.sleep(1)

            total_bw = 0.0
            for i in range(1, 21):
                net.get(f'lab{i}').cmd(
                    f'iperf -c {srv_ip} -p 5001 -t 20 > /tmp/iperf_t2_lab{i}.txt 2>&1 &')
            note('  Đợi 5s cho traffic bão hòa...')
            time.sleep(5)

            # Ping TRONG KHI flood (đây là chỉ số quan trọng nhất)
            note('Ping TRONG KHI flood (lab1 → srv1):')
            print(f'\n{B}[PING DURING FLOOD – lab1 → {srv_ip} | 20 Lab TCP]{E}', flush=True)
            print('─'*60, flush=True)
            raw_f = lab1.cmd(f'ping -c 15 -i 0.2 {srv_ip} 2>/dev/null')
            raw_out(raw_f)
            print('─'*60, flush=True)
            loss_f, avg_f, _ = parse_ping(raw_f)

            # Đợi iperf xong (20s total - 5s đã chạy - ~3s ping = cần thêm ~12-15s)
            note('  Đợi iperf hoàn thành...')
            time.sleep(17)


            # Thu thập throughput
            print(f'\n{B}[RAW IPERF – 20 Lab → {srv_ip} | {LABELS[n]}]{E}', flush=True)
            print('─'*60, flush=True)
            for i in range(1, 21):
                raw = net.get(f'lab{i}').cmd(f'cat /tmp/iperf_t2_lab{i}.txt 2>/dev/null')
                bw_lines = [l for l in raw.strip().splitlines()
                            if re.search(r'bits/sec', l, re.I)]
                if bw_lines:
                    sys.stdout.write(f'  lab{i:>2}: {bw_lines[-1].strip()}\n')
                else:
                    last = raw.strip().splitlines()
                    sys.stdout.write(f'  lab{i:>2}: {(last[-1] if last else "(no out)")[:70]}\n')
                sys.stdout.flush()
                total_bw += parse_iperf_sum(raw)
            print('─'*60, flush=True)

            latency_inc = avg_f - avg_b
            note(f'→ Iperf tổng = {total_bw:.0f} Mbps')
            note(f'→ Baseline: {avg_b:.1f}ms | Flood: {avg_f:.1f}ms | Tăng: +{latency_inc:.1f}ms | Loss: {loss_f:.0f}%')
            results.append({'label': LABELS[n],
                           'STP blocked': str(blocked_total),
                           'Iperf tổng': f'{total_bw:.0f} Mbps',
                           'Latency thường': f'{avg_b:.1f}ms',
                           'Latency flood': f'{avg_f:.1f}ms',
                           'Tăng độ trễ': f'+{latency_inc:.1f}ms'})

            for i in range(1, 21): net.get(f'lab{i}').cmd('kill %iperf 2>/dev/null')

        except Exception as e:
            fail(f'Lỗi: {e}')
            import traceback; traceback.print_exc()
            results.append({'label': LABELS[n], 'STP blocked': 'ERR',
                           'Iperf tổng': '-', 'Latency thường': '-',
                           'Latency flood': '-', 'Tăng độ trễ': '-'})
        finally:
            if srv_proc:
                try: srv_proc.terminate()
                except: pass
            if net: stop_net(net, n)

    print_compare('Test 2 – STP vs ECMP (Throughput + Latency)', results)







# ════════════════════════════════════════════════════════════════
# TEST 3: BỎ QUA (đã loại khỏi bộ test)
# ════════════════════════════════════════════════════════════════
def test3():
    banner('TEST 3: Sự cố Đứt Node Lõi (Model 2 vs 3)')
    warn('Test 3 đã bị loại — bỏ qua.')



# ════════════════════════════════════════════════════════════════
# TEST 4: STP RECONVERGENCE (Model 2 vs 4)
# Mục đích: STP 15-30s chết vs SDN fast failover
# ════════════════════════════════════════════════════════════════
def test4():
    banner('TEST 4: Thời gian Hội tụ STP (Model 2 vs 4)')
    print('  Cắt uplink Lab đang Forwarding → lab1 ping WAN liên tục')
    print(f'  {Y}Model 2: STP reconvergence 15-30s timeout{E}')
    print(f'  {G}Model 4: SDN fast failover < 1s{E}')
    results = []

    for n in ['2','4']:
        section(f'{LABELS[n]}')
        try:
            net = build_and_warmup(n)
            if n == '4':
                from cauhinh4 import DynamicQoSMonitor
                qos = DynamicQoSMonitor(net); qos.start()

            lab1 = net.get('lab1')
            wan_ip = '203.162.1.1'
            lab1.cmd(f'ping -c 2 -W 2 {wan_ip} 2>/dev/null')

            # Tìm uplink của lab switch
            if n == '2':
                # lab1 trên s7, uplink s7→s2 (forwarding)
                sw_name, peer = 's7', 's2'
            else:
                # lab1 trên s4, uplink s4→s1 (spine)
                sw_name, peer = 's4', 's1'

            note(f'lab1 ping WAN liên tục (30 gói, 0.5s/gói)...')
            note(f'Cắt uplink {sw_name}↔{peer} sau 5 gói...')

            # Ping nền
            lab1.cmd(f'ping -c 30 -i 0.5 {wan_ip} > /tmp/ping_test4.txt 2>&1 &')
            time.sleep(3)  # 5 gói đầu OK

            # CẮT UPLINK
            note(f'>>> CẮT LINK {sw_name} ↔ {peer} <<<')
            net.configLinkStatus(sw_name, peer, 'down')
            time.sleep(12)  # Đợi reconvergence

            # Đợi ping xong
            time.sleep(5)
            lab1.cmd('kill %ping 2>/dev/null')
            time.sleep(1)

            print(f'\n{B}[RAW PING – lab1 → {wan_ip} | Cắt uplink giữa chừng]{E}', flush=True)
            print('─'*60, flush=True)
            raw = lab1.cmd('cat /tmp/ping_test4.txt 2>/dev/null')
            raw_out(raw)
            print('─'*60, flush=True)

            loss, avg, _ = parse_ping(raw)
            # Đếm số timeout
            timeouts = raw.count('no answer') + raw.count('unreachable') + raw.count('Request timeout')
            note(f'→ Loss={loss}% | Avg={avg:.1f}ms | Timeouts phát hiện: {timeouts}')
            results.append({'label': LABELS[n], 'Loss': f'{loss}%', 'Avg': f'{avg:.1f}ms'})

            if n == '4': qos.stop()
        except Exception as e:
            fail(f'Lỗi: {e}')
            results.append({'label': LABELS[n], 'Loss': 'ERR', 'Avg': 'ERR'})
        finally:
            stop_net(net, n)

    print_compare('Test 4 – STP Reconvergence', results)

# ════════════════════════════════════════════════════════════════
# TEST 5: ANYCAST vs CENTRALIZED GATEWAY (Model 2 vs 3)
# Mục đích: Gateway tại Leaf (local) vs Gateway tại Router (remote)
# ════════════════════════════════════════════════════════════════
def test5():
    banner('TEST 5: Anycast Gateway vs Centralized (Model 2 vs 3)')
    print('  lab1 + admin1 ping Default Gateway → so latency')
    print(f'  {Y}Model 2: GW trên r1 → nhiều hop → latency cao{E}')
    print(f'  {G}Model 3: GW trên Leaf (Anycast) → 1 hop → latency thấp{E}')
    results = []

    for n in ['2','3']:
        section(f'{LABELS[n]}')
        try:
            net = build_and_warmup(n)
            admin = net.get('admin1')
            lab1  = net.get('lab1')
            gw_admin = '10.0.10.254'
            gw_lab   = '10.0.20.254'

            # Model 3: Cấu hình Anycast GW trên Leaf switches
            if n == '3':
                note('Cấu hình Anycast GW trên Leaf switches...')
                s3 = net.get('s3')  # leaf_admin
                s4 = net.get('s4')  # leaf_lab1
                # Thêm internal port + IP gateway trên Leaf
                s3.cmd('ovs-vsctl add-port s3 s3-gw -- set interface s3-gw type=internal 2>/dev/null')
                s3.cmd(f'ip addr add {gw_admin}/24 dev s3-gw; ip link set s3-gw up')
                s4.cmd('ovs-vsctl add-port s4 s4-gw -- set interface s4-gw type=internal 2>/dev/null')
                s4.cmd(f'ip addr add {gw_lab}/24 dev s4-gw; ip link set s4-gw up')
                # Xóa GW trên r1 để tránh conflict ARP
                r1 = net.get('r1')
                r1.cmd(f'ip addr del {gw_admin}/24 dev r1-eth0 2>/dev/null')
                r1.cmd(f'ip addr del {gw_lab}/24 dev r1-eth1 2>/dev/null')
                time.sleep(1)

            # RAW PING admin1 → GW
            print(f'\n{B}[RAW PING – admin1 → {gw_admin} (Gateway)]{E}', flush=True)
            print('─'*60, flush=True)
            raw_a = admin.cmd(f'ping -c 10 -i 0.2 {gw_admin} 2>&1')
            raw_out(raw_a)
            print('─'*60, flush=True)
            _, avg_a, mdev_a = parse_ping(raw_a)

            # RAW PING lab1 → GW
            print(f'\n{B}[RAW PING – lab1 → {gw_lab} (Gateway)]{E}', flush=True)
            print('─'*60, flush=True)
            raw_l = lab1.cmd(f'ping -c 10 -i 0.2 {gw_lab} 2>&1')
            raw_out(raw_l)
            print('─'*60, flush=True)
            _, avg_l, mdev_l = parse_ping(raw_l)

            note(f'→ Admin GW Avg={avg_a:.3f}ms | Lab GW Avg={avg_l:.3f}ms')
            results.append({'label': LABELS[n],
                           'Admin→GW': f'{avg_a:.3f}ms',
                           'Lab→GW': f'{avg_l:.3f}ms'})
        except Exception as e:
            fail(f'Lỗi: {e}')
            results.append({'label': LABELS[n], 'Admin→GW': 'ERR', 'Lab→GW': 'ERR'})
        finally:
            stop_net(net, n)

    print_compare('Test 5 – Anycast vs Central GW', results)

# ════════════════════════════════════════════════════════════════
# TEST 6: DYNAMIC QoS (Model 1,2,3 vs 4)
# Mục đích: SDN rate-limit Dorm → ưu tiên Admin
# ════════════════════════════════════════════════════════════════
def test6():
    banner('TEST 6: Giám sát & Điều hướng Tự động (Model 1,2,3 vs 4)')
    print('  40 Dorm UDP 5Mbps → WAN + admin1 ping')
    print(f'  {Y}Model 1,2,3: Bất lực – ping trễ/rớt nặng{E}')
    print(f'  {G}Model 4: Controller rate-limit Dorm → admin mượt lại{E}')
    results = []

    for n in ['1','2','3','4']:
        section(f'{LABELS[n]}')
        try:
            net = build_and_warmup(n)
            qos = None
            if n == '4':
                from cauhinh4 import DynamicQoSMonitor
                qos = DynamicQoSMonitor(net); qos.start()
                note('Dynamic QoS Monitor ON')

            wan = net.get('serverhcm')
            admin = net.get('admin1')
            wan_ip = '203.162.1.1'

            wan.cmd('pkill iperf 2>/dev/null; iperf -s -u -D -p 5002')
            time.sleep(0.5)

            note('40 Dorm iperf UDP 5Mbps/host → WAN...')
            for i in range(1, 41):
                net.get(f'dorm{i}').cmd(f'iperf -c {wan_ip} -u -b 5M -p 5002 -t 25 &')
            time.sleep(3)

            print(f'\n{B}[RAW PING – admin1 → {wan_ip} | 40 Dorm UDP flood]{E}', flush=True)
            if n == '4':
                print(f'{Y}  Controller sẽ can thiệp → latency giảm{E}', flush=True)
            print('─'*60, flush=True)
            raw = admin.cmd(f'ping -c 20 -i 0.3 {wan_ip} 2>&1')
            raw_out(raw)
            print('─'*60, flush=True)

            loss, avg, _ = parse_ping(raw)
            note(f'→ Loss={loss}% | Avg={avg:.1f}ms')
            results.append({'label': LABELS[n], 'Loss': f'{loss}%', 'Avg': f'{avg:.1f}ms'})

            for i in range(1, 41): net.get(f'dorm{i}').cmd('kill %iperf 2>/dev/null')
            wan.cmd('pkill iperf 2>/dev/null')
            if qos: qos.stop()
        except Exception as e:
            fail(f'Lỗi: {e}')
            results.append({'label': LABELS[n], 'Loss': 'ERR', 'Avg': 'ERR'})
        finally:
            stop_net(net, n)

    print_compare('Test 6 – Dynamic QoS', results)

# ════════════════════════════════════════════════════════════════
# TEST 7: CONTROL PLANE FAILURE (Model 3 vs 4)
# Mục đích: Kill Ryu → luồng cũ sống, luồng mới chết
# ════════════════════════════════════════════════════════════════
def test7():
    banner('TEST 7: Mất "Bộ não" Điều khiển (Model 3 vs 4)')
    print('  Kill Ryu Controller → test luồng cũ + luồng mới')
    print(f'  {G}Model 3: Standalone OVS → mạng vẫn sống{E}')
    print(f'  {R}Model 4: failMode=secure → luồng mới 100% fail{E}')
    results = []

    # ── Model 3: Standalone (không cần controller) ──
    section(f'{LABELS["3"]}')
    try:
        net = build_and_warmup('3')
        admin = net.get('admin1')
        srv4  = net.get('srv4')
        srv_ip = '10.0.99.1'
        srv4_ip = '10.0.99.4'

        note('Ping luồng cũ (admin1 → srv1):')
        print('─'*60, flush=True)
        raw1 = admin.cmd(f'ping -c 5 -i 0.3 {srv_ip} 2>&1')
        raw_out(raw1)
        print('─'*60, flush=True)
        loss1, avg1, _ = parse_ping(raw1)

        note('Ping luồng mới (srv4 → admin1):')
        print('─'*60, flush=True)
        raw2 = srv4.cmd(f'ping -c 5 -i 0.3 10.0.10.1 2>&1')
        raw_out(raw2)
        print('─'*60, flush=True)
        loss2, avg2, _ = parse_ping(raw2)

        note(f'→ Luồng cũ: {loss1}% | Luồng mới: {loss2}% (Standalone = hoạt động)')
        results.append({'label': LABELS['3'], 'Luồng cũ': f'{loss1}%', 'Luồng mới': f'{loss2}%'})
    except Exception as e:
        fail(f'Lỗi: {e}')
        results.append({'label': LABELS['3'], 'Luồng cũ': 'ERR', 'Luồng mới': 'ERR'})
    finally:
        stop_net(net, '3')

    # ── Model 4: SDN (failMode=secure) ──
    section(f'{LABELS["4"]}')
    try:
        net = build_and_warmup('4')

        # Chuyển tất cả switch sang failMode=secure
        note('Set failMode=secure trên tất cả switch...')
        for sw_name in ['s1','s2','s3','s4','s5','s6','s7','s8']:
            net.get(sw_name).cmd(f'ovs-vsctl set-fail-mode {sw_name} secure')
        time.sleep(2)

        admin = net.get('admin1')
        srv4  = net.get('srv4')

        # Tạo luồng cũ (đã có flow table)
        note('Tạo luồng cũ: admin1 → srv1 (flow table được đẩy)...')
        admin.cmd(f'ping -c 3 -W 2 10.0.99.1 2>/dev/null')
        time.sleep(1)

        # KILL RYU CONTROLLER
        note('>>> KILL RYU CONTROLLER <<<')
        subprocess.run(['sudo', 'pkill', '-f', 'ryu-manager'], capture_output=True)
        time.sleep(3)

        # Ping luồng CŨ (flow table còn)
        note('Ping luồng CŨ (admin1 → srv1) sau khi kill Controller:')
        print('─'*60, flush=True)
        raw_old = admin.cmd(f'ping -c 5 -i 0.3 10.0.99.1 2>&1')
        raw_out(raw_old)
        print('─'*60, flush=True)
        loss_old, _, _ = parse_ping(raw_old)

        # Ping luồng MỚI (srv4 chưa có flow)
        note('Ping luồng MỚI (srv4 → admin1) sau khi kill Controller:')
        print(f'\n{B}[RAW PING – srv4 → admin1 | Controller ĐÃ CHẾT]{E}', flush=True)
        print('─'*60, flush=True)
        raw_new = srv4.cmd(f'ping -c 5 -W 2 10.0.10.1 2>&1')
        raw_out(raw_new)
        print('─'*60, flush=True)
        loss_new, _, _ = parse_ping(raw_new)

        note(f'→ Luồng cũ: {loss_old}% | Luồng mới: {loss_new}% (secure → DROP)')
        results.append({'label': LABELS['4'],
                       'Luồng cũ': f'{loss_old}%',
                       'Luồng mới': f'{loss_new}% (EXPECTED 100%)'})
    except Exception as e:
        fail(f'Lỗi: {e}')
        results.append({'label': LABELS['4'], 'Luồng cũ': 'ERR', 'Luồng mới': 'ERR'})
    finally:
        stop_net(net, '4')

    print_compare('Test 7 – Control Plane Failure', results)

# ════════════════════════════════════════════════════════════════
# TEST 8: MULTI-HOP LATENCY (Model 2 vs 3)
# Mục đích: Spine-Leaf = latency đồng đều (mdev thấp)
# ════════════════════════════════════════════════════════════════
def test8():
    banner('TEST 8: Độ trễ theo số chặng (Model 2 vs 3)')
    print('  Ping nhiều cặp host → so sánh mdev (variance)')
    print(f'  {Y}Model 2: Hop count khác nhau → mdev lớn{E}')
    print(f'  {G}Model 3: Luôn 3 hop (Leaf→Spine→Leaf) → mdev nhỏ{E}')
    results = []

    pairs = [
        ('admin1', 'lab1',  'Admin→Lab'),
        ('admin1', 'srv1',  'Admin→Srv'),
        ('lab1',   'dorm1', 'Lab→Dorm'),
    ]

    for n in ['2','3']:
        section(f'{LABELS[n]}')
        try:
            net = build_and_warmup(n)
            pair_results = {}

            for src_name, dst_name, label in pairs:
                src = net.get(src_name)
                dst = net.get(dst_name)
                dst_ip = dst.IP()

                note(f'{label}: {src_name} → {dst_name} ({dst_ip})')
                print('─'*60, flush=True)
                raw = src.cmd(f'ping -c 10 -i 0.2 {dst_ip} 2>&1')
                raw_out(raw)
                print('─'*60, flush=True)

                _, avg, mdev = parse_ping(raw)
                pair_results[label] = f'{avg:.3f}ms (mdev={mdev:.3f})'

            all_mdevs = []
            for src_name, dst_name, label in pairs:
                src = net.get(src_name)
                dst = net.get(dst_name)
                r = src.cmd(f'ping -c 10 -i 0.2 {dst.IP()} 2>&1')
                _, a, m = parse_ping(r)
                all_mdevs.append(m)

            avg_mdev = sum(all_mdevs) / len(all_mdevs) if all_mdevs else 9999
            pair_results['Avg mdev'] = f'{avg_mdev:.3f}ms'
            results.append({'label': LABELS[n], **pair_results})
        except Exception as e:
            fail(f'Lỗi: {e}')
            results.append({'label': LABELS[n], 'Error': str(e)})
        finally:
            stop_net(net, n)

    print_compare('Test 8 – Multi-hop Latency', results)

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
TEST_MAP = {
    'test1': (test1, 'MAC Flooding (Model 1 vs 2)'),
    'test2': (test2, 'STP vs ECMP Bandwidth (Model 2 vs 3)'),
    'test3': (test3, 'Core/Spine Failure (Model 2 vs 3)'),
    'test4': (test4, 'STP Reconvergence (Model 2 vs 4)'),
    'test5': (test5, 'Anycast vs Central GW (Model 2 vs 3)'),
    'test6': (test6, 'Dynamic QoS (Model 1,2,3 vs 4)'),
    'test7': (test7, 'Control Plane Failure (Model 3 vs 4)'),
    'test8': (test8, 'Multi-hop Latency (Model 2 vs 3)'),
}

def main():
    if os.geteuid() != 0:
        print('Cần sudo: sudo python3 testver2.py [test1..test8]')
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description='TESTVER2 – 8 bài test so sánh kiến trúc mạng',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'tests', nargs='*', default=[],
        help='test1..test8 (để trống = chạy tất cả)')
    args = parser.parse_args()

    setLogLevel('critical')

    banner('TESTVER2 – 8 BÀI TEST SO SÁNH KIẾN TRÚC MẠNG')
    for k,(fn,desc) in TEST_MAP.items():
        print(f'  {k}: {desc}')
    print(f'\n  {Y}⚠ Test 4,6,7 dùng Model 4 → cần Ryu Controller chạy trước:{E}')
    print('     ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653')

    # Chọn test
    if args.tests:
        selected = []
        for t in args.tests:
            t = t.lower()
            if t in TEST_MAP:
                selected.append(t)
            else:
                fail(f'Test không tồn tại: {t}')
                sys.exit(1)
    else:
        selected = list(TEST_MAP.keys())

    note(f'Sẽ chạy: {", ".join(selected)}')
    print()

    for t in selected:
        fn, desc = TEST_MAP[t]
        try:
            fn()
        except Exception as e:
            fail(f'Test {t} thất bại: {e}')
            import traceback; traceback.print_exc()
        if t != selected[-1]:
            print('\n  → Chờ 3 giây trước test tiếp theo...\n')
            time.sleep(3)

    banner('HOÀN THÀNH – Xem kết quả RAW và bảng so sánh phía trên')

if __name__ == '__main__':
    main()

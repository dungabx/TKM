#!/usr/bin/env python3
"""
FILE TEST.PY – FRAMEWORK KIỂM THỬ 4 MÔ HÌNH MẠNG
====================================================
File này IMPORT trực tiếp từ cauhinh1.py → cauhinh4.py,
gọi build_net() của từng file để dựng mạng, rồi chạy 3 bài test.

Cách dùng:
  sudo python3 test.py                  # Test cả 4 mô hình lần lượt
  sudo python3 test.py --cauhinh 1      # Test riêng mô hình 1
  sudo python3 test.py --cauhinh 4      # Test riêng mô hình 4 (cần Ryu)

3 BÀI TEST:
  Test 1 – Elephant Flow:  20 Lab iperf TCP → serverhcm + admin1 ping
  Test 2 – Broadcast Storm: dorm1 broadcast flood + admin1 ping
  Test 3 – Dynamic QoS:    40 Dorm iperf UDP → WAN + admin1 ping
"""

import os, sys, re, time, argparse, subprocess, importlib
from mininet.log import setLogLevel, info

# ── Màu terminal ────────────────────────────────────────────────
R='\033[91m'; G='\033[92m'; Y='\033[93m'; C='\033[96m'
B='\033[1m';  E='\033[0m';  SEP='━'*72

def banner(msg):  print(f'\n{B}{C}{SEP}\n  {msg}\n{SEP}{E}', flush=True)
def section(msg): print(f'\n{B}{Y}── {msg} ──{E}', flush=True)
def note(msg):    print(f'{G}  • {msg}{E}', flush=True)
def warn(msg):    print(f'{Y}  ⚠ {msg}{E}', flush=True)
def fail(msg):    print(f'{R}  ✗ {msg}{E}', flush=True)

def raw_out(text):
    """In kết quả thô từ lệnh shell – không định dạng lại."""
    if text:
        sys.stdout.write(text)
        if not text.endswith('\n'):
            sys.stdout.write('\n')
        sys.stdout.flush()

def parse_ping(raw):
    """Trích loss% và avg-ms từ ping output thô."""
    lm  = re.search(r'(\d+)%\s+packet\s+loss', raw)
    rtm = re.search(r'rtt .* = [\d.]+/([\d.]+)/', raw)
    loss = int(lm.group(1))    if lm  else 100
    avg  = float(rtm.group(1)) if rtm else 9999.0
    return loss, avg

def cleanup():
    subprocess.run(['sudo','mn','-c'], capture_output=True, timeout=30)

# ── Lưu thống kê ───────────────────────────────────────────────
ALL_STATS = []

LABELS = {
    '1': 'Mô hình 1 – Mạng Phẳng (Flat)',
    '2': 'Mô hình 2 – 3 Lớp + Dual Core',
    '3': 'Mô hình 3 – Spine-Leaf',
    '4': 'Mô hình 4 – SDN + Dynamic QoS',
}

# ════════════════════════════════════════════════════════════════
# IMPORT CAUHINH: import cauhinhN.py → gọi build_net()
# ════════════════════════════════════════════════════════════════
def import_cauhinh(n):
    """Import cauhinhN module, trả về module."""
    module_name = f'cauhinh{n}'
    # Đảm bảo thư mục hiện tại trong sys.path
    cwd = os.path.dirname(os.path.abspath(__file__))
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    mod = importlib.import_module(module_name)
    return mod

# ════════════════════════════════════════════════════════════════
# WARM-UP: điền ARP cache trước khi test
# ════════════════════════════════════════════════════════════════
def warmup(net, n):
    wan_ip = '203.162.1.1'
    gw     = '10.0.0.254' if n == '1' else '10.0.10.254'
    admin  = net.get('admin1')
    note('Warm-up: điền ARP cache (ping 3 gói)...')
    admin.cmd(f'ping -c 3 -W 2 {gw} 2>/dev/null')
    admin.cmd(f'ping -c 3 -W 2 {wan_ip} 2>/dev/null')
    # Kiểm tra kết nối cơ bản
    check = admin.cmd(f'ping -c 1 -W 3 {wan_ip} 2>&1')
    if '1 received' in check:
        note(f'Warm-up OK: admin1 → {wan_ip} reachable')
    else:
        warn(f'Warm-up: admin1 → {wan_ip} chưa thông! (có thể do STP chưa hội tụ)')
        note('Đợi thêm 10s...')
        time.sleep(10)
        admin.cmd(f'ping -c 2 -W 2 {wan_ip} 2>/dev/null')

# ════════════════════════════════════════════════════════════════
# TEST 1: ELEPHANT FLOW – 20 Lab TCP → serverhcm + Admin ping
# ════════════════════════════════════════════════════════════════
def test1_wan_flood(net, n):
    section('TEST 1: Elephant Flow – 20 Lab TCP → serverhcm + admin1 ping')
    wan_ip = '203.162.1.1'
    wan    = net.get('serverhcm')
    admin  = net.get('admin1')

    wan.cmd('pkill iperf 2>/dev/null; iperf -s -D -p 5001 2>/dev/null')
    time.sleep(0.5)

    note('Kích hoạt 20 lab hosts iperf TCP → serverhcm (15s)...')
    for i in range(1, 21):
        net.get(f'lab{i}').cmd(f'iperf -c {wan_ip} -p 5001 -t 15 &')
    time.sleep(2)

    print(f'\n{B}[RAW PING – admin1 → {wan_ip} | Đang 20 Lab TCP flood WAN]{E}', flush=True)
    print('─' * 60, flush=True)
    raw = admin.cmd(f'ping -c 10 -i 0.3 {wan_ip} 2>&1')
    raw_out(raw)
    print('─' * 60, flush=True)

    loss, avg = parse_ping(raw)
    note(f'→ Thống kê: Packet Loss = {loss}% | Avg Latency = {avg:.1f} ms')

    for i in range(1, 21): net.get(f'lab{i}').cmd('kill %iperf 2>/dev/null')
    wan.cmd('pkill iperf 2>/dev/null')
    time.sleep(1)
    return loss, avg

# ════════════════════════════════════════════════════════════════
# TEST 2: BROADCAST STORM – dorm1 broadcast flood + Admin ping
# ════════════════════════════════════════════════════════════════
def test2_broadcast_storm(net, n):
    section('TEST 2: Broadcast Storm – dorm1 broadcast flood + admin1 ping')
    # Model 1: /16 → broadcast = 10.0.255.255 (ảnh hưởng toàn bộ 69 host)
    # Model 2-4: /24 → broadcast = 10.0.30.255 (chỉ trong VLAN Dorm)
    bcast = '10.0.255.255' if n == '1' else '10.0.30.255'
    gw    = '10.0.0.254'   if n == '1' else '10.0.10.254'
    dorm1 = net.get('dorm1')
    admin = net.get('admin1')

    # Bật broadcast reply trên nhiều host → khuếch đại storm (Model 1 = toàn mạng)
    if n == '1':
        note('Model 1 (Flat /16): broadcast sẽ flood toàn bộ 69 host!')
        for h in net.hosts:
            h.cmd('sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=0')
    else:
        note(f'Model {n}: broadcast chỉ trong VLAN Dorm → Admin cô lập')
        dorm1.cmd('sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=0')

    note(f'dorm1 ping flood broadcast {bcast} (500 gói)...')
    dorm1.cmd(f'ping -b -c 500 -f {bcast} >/dev/null 2>&1 &')
    # Thêm nhiều nguồn broadcast cho Model 1 để mô phỏng storm thực
    if n == '1':
        for i in [2,3,4,5]:
            net.get(f'dorm{i}').cmd(f'ping -b -c 500 -f {bcast} >/dev/null 2>&1 &')
    time.sleep(1)

    print(f'\n{B}[RAW PING – admin1 → {gw} | Đang broadcast storm]{E}', flush=True)
    print('─' * 60, flush=True)
    raw = admin.cmd(f'ping -c 10 -i 0.3 {gw} 2>&1')
    raw_out(raw)
    print('─' * 60, flush=True)

    loss, avg = parse_ping(raw)
    note(f'→ Thống kê: Packet Loss = {loss}% | Avg Latency = {avg:.1f} ms')

    dorm1.cmd('kill %ping 2>/dev/null')
    if n == '1':
        for i in [2,3,4,5]:
            net.get(f'dorm{i}').cmd('kill %ping 2>/dev/null')
    time.sleep(0.5)
    return loss, avg

# ════════════════════════════════════════════════════════════════
# TEST 3: DYNAMIC QoS – 40 Dorm UDP → WAN + Admin ping
# ════════════════════════════════════════════════════════════════
def test3_dynamic_qos(net, n):
    section('TEST 3: Dynamic QoS – 40 Dorm UDP → WAN + admin1 ping')
    wan_ip = '203.162.1.1'
    wan    = net.get('serverhcm')
    admin  = net.get('admin1')

    if n == '4':
        note('Mô hình 4 SDN: Controller giám sát WAN → tự rate-limit Dorm')
    else:
        note(f'Mô hình {n}: Không QoS động – Admin cạnh tranh BW với 40 Dorm')

    wan.cmd('pkill iperf 2>/dev/null; iperf -s -u -D -p 5002 2>/dev/null')
    time.sleep(0.5)

    note('Kích hoạt 40 Dorm iperf UDP 5Mbps/host = 200Mbps → WAN...')
    for i in range(1, 41):
        net.get(f'dorm{i}').cmd(f'iperf -c {wan_ip} -u -b 5M -p 5002 -t 25 &')
    time.sleep(3)

    print(f'\n{B}[RAW PING – admin1 → {wan_ip} | Đang 40 Dorm UDP flood]{E}', flush=True)
    if n == '4':
        print(f'{Y}  Chú ý: latency giảm khi SDN Controller rate-limit Dorm{E}', flush=True)
    print('─' * 60, flush=True)
    raw = admin.cmd(f'ping -c 20 -i 0.3 {wan_ip} 2>&1')
    raw_out(raw)
    print('─' * 60, flush=True)

    loss, avg = parse_ping(raw)
    note(f'→ Thống kê: Packet Loss = {loss}% | Avg Latency = {avg:.1f} ms')

    for i in range(1, 41): net.get(f'dorm{i}').cmd('kill %iperf 2>/dev/null')
    wan.cmd('pkill iperf 2>/dev/null')
    time.sleep(1)
    return loss, avg

# ════════════════════════════════════════════════════════════════
# BẢNG TỔNG KẾT
# ════════════════════════════════════════════════════════════════
def print_model_summary(label, s):
    print(f'\n{B}{C}  KẾT QUẢ: {label}{E}')
    print(f'  {"─"*68}')
    print(f'  {"Bài test":<35} {"Packet Loss":<15} {"Avg Latency (ms)"}')
    print(f'  {"─"*68}')
    for name, loss, avg in [
        ('Test 1 – Elephant Flow (WAN)',    s["t1_loss"], s["t1_avg"]),
        ('Test 2 – Broadcast Storm',        s["t2_loss"], s["t2_avg"]),
        ('Test 3 – Dynamic QoS (UDP WAN)',  s["t3_loss"], s["t3_avg"]),
    ]:
        lc = G if loss == 0 else (Y if loss < 30 else R)
        ac = G if avg < 50 else (Y if avg < 300 else R)
        print(f'  {name:<35} {lc}{loss:>5}%{E}          {ac}{avg:>8.1f}{E}')
    print(f'  {"─"*68}')

def print_final_table():
    if len(ALL_STATS) < 2:
        return
    banner('BẢNG SO SÁNH TỔNG HỢP')
    W = 28
    print(f'  {"Mô hình":<{W}} {"T1 Loss":<9} {"T1 Lat":<10} {"T2 Loss":<9} {"T2 Lat":<10} {"T3 Loss":<9} {"T3 Lat":<10} Nhận xét')
    print(f'  {"─"*115}')
    comments = {
        '1': 'Không phân tách – broadcast sập toàn mạng',
        '2': 'STP khóa port – cô lập VLAN',
        '3': 'ECMP tốt – không QoS động',
        '4': 'SDN rate-limit Dorm tự động',
    }
    for s in ALL_STATS:
        n = s['n']; lbl = s['label'][:W-1]
        def fc(v, g, y): return G if v<=g else (Y if v<=y else R)
        l1c=fc(s['t1_loss'],0,30); a1c=fc(s['t1_avg'],50,300)
        l2c=fc(s['t2_loss'],0,30); a2c=fc(s['t2_avg'],50,300)
        l3c=fc(s['t3_loss'],0,30); a3c=fc(s['t3_avg'],50,300)
        print(f'  {lbl:<{W}} '
              f'{l1c}{s["t1_loss"]:>4}%{E}    {a1c}{s["t1_avg"]:>7.1f}{E}   '
              f'{l2c}{s["t2_loss"]:>4}%{E}    {a2c}{s["t2_avg"]:>7.1f}{E}   '
              f'{l3c}{s["t3_loss"]:>4}%{E}    {a3c}{s["t3_avg"]:>7.1f}{E}   {comments.get(n,"")}')
    print(f'  {"─"*115}')

# ════════════════════════════════════════════════════════════════
# CHẠY TEST CHO 1 MÔ HÌNH
# ════════════════════════════════════════════════════════════════
def run_model(n):
    banner(f'{LABELS[n]}')

    # ── Import cauhinhN.py và gọi build_net() ──
    note(f'Import cauhinh{n}.py → gọi build_net()...')
    try:
        mod = import_cauhinh(n)
        net = mod.build_net()
    except Exception as e:
        fail(f'Lỗi build mạng từ cauhinh{n}.py: {e}')
        import traceback; traceback.print_exc()
        cleanup()
        return

    stats = {'n': n, 'label': LABELS[n],
             't1_loss':100,'t1_avg':9999,
             't2_loss':100,'t2_avg':9999,
             't3_loss':100,'t3_avg':9999}

    # Mô hình 4: khởi động Dynamic QoS monitor
    qos = None
    if n == '4':
        try:
            from cauhinh4 import DynamicQoSMonitor
            qos = DynamicQoSMonitor(net)
            qos.start()
            note('Dynamic QoS Monitor đã khởi động.')
        except Exception as e:
            warn(f'Không thể khởi động QoS monitor: {e}')

    try:
        warmup(net, n)
        l1, a1 = test1_wan_flood(net, n)
        l2, a2 = test2_broadcast_storm(net, n)
        l3, a3 = test3_dynamic_qos(net, n)
        stats.update(t1_loss=l1, t1_avg=a1,
                     t2_loss=l2, t2_avg=a2,
                     t3_loss=l3, t3_avg=a3)
        print_model_summary(LABELS[n], stats)
    except Exception as e:
        fail(f'Lỗi trong test: {e}')
        import traceback; traceback.print_exc()
    finally:
        if qos:
            qos.stop()
        print(f'\n{B}→ Dừng mạng mô hình {n}...{E}', flush=True)
        net.stop()
        cleanup()
        note(f'Mô hình {n} đã dừng.\n')

    ALL_STATS.append(stats)

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
def main():
    if os.geteuid() != 0:
        print('Cần sudo: sudo python3 test.py [--cauhinh 1|2|3|4]')
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description='Framework kiểm thử 4 mô hình mạng Mininet',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        '--cauhinh', default='all',
        choices=['1','2','3','4','all'],
        help='1=Flat | 2=3-Layer | 3=Spine-Leaf | 4=SDN | all=cả 4')
    args = parser.parse_args()

    setLogLevel('warning')

    banner('FRAMEWORK KIỂM THỬ 4 MÔ HÌNH MẠNG – test.py')
    print('  Mỗi mô hình: import cauhinhN.py → build_net() → chạy 3 test')
    print('  Test 1: Elephant Flow   – 20 Lab TCP → WAN + admin1 ping')
    print('  Test 2: Broadcast Storm – dorm1 broadcast + admin1 ping')
    print('  Test 3: Dynamic QoS     – 40 Dorm UDP WAN + admin1 ping')
    print(f'  {Y}Kết quả: RAW ping thô + bảng Packet Loss & Latency{E}')

    if args.cauhinh in ('4','all'):
        print(f'\n  {Y}⚠ Mô hình 4 cần Ryu Controller chạy trước:{E}')
        print('     ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653')

    selected = ['1','2','3','4'] if args.cauhinh == 'all' else [args.cauhinh]

    for n in selected:
        run_model(n)
        if args.cauhinh == 'all' and n != '4':
            print('\n  → Chờ 3 giây trước mô hình tiếp theo...\n')
            time.sleep(3)

    print_final_table()
    banner('HOÀN THÀNH – Xem RAW ping và bảng thống kê phía trên')

if __name__ == '__main__':
    main()

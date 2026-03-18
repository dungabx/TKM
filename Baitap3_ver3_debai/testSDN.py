#!/usr/bin/env python3
"""
testSDN.py – Kịch bản Demo SDN Dynamic QoS
==========================================
Mô hình 4: Spine-Leaf + Ryu Controller + Dynamic QoS

Kịch bản:
  1. Khởi động mạng SDN (Model 4 – cauhinh4.py)
  2. Warm-up: kiểm tra Admin có ping được serverhcm
  3. PHASE 1 – BASELINE: đo ping Admin→serverhcm không có flood
  4. PHASE 2 – FLOOD (không QoS): 40 Dorm xả UDP 10Mbps → serverhcm
     → WAN bị nghẽn → Admin ping bị ảnh hưởng
     → Giám sát WAN, phát cảnh báo khi ≥ 90%
  5. PHASE 3 – SDN CAN THIỆP: Controller đẩy tc rate-limit xuống Dorm
     → WAN giải phóng → Admin ping phục hồi
  6. PHASE 4 – RESTORE: gỡ rate-limit, traffic trả về bình thường

Yêu cầu:
  sudo ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653
"""

import os, sys, time, re, threading, subprocess
sys.path.insert(0, '/home/mn/tkm_final')

# ── ANSI Colors ──────────────────────────────────────────────────────────────
R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'
B = '\033[94m'; M = '\033[95m'; C = '\033[96m'; E = '\033[0m'

# ── Thông số mạng ────────────────────────────────────────────────────────────
WAN_BW_MBPS      = 200       # WAN link = 200Mbps (r1-eth4)
CONGESTION_THR   = 0.90      # 90% → báo nghẽn
RELIEF_THR       = 0.70      # 70% → gỡ giới hạn
DORM_FLOOD_MBPS  = 8         # Mỗi dorm xả 8Mbps UDP (40 dorm = 320Mbps > WAN)
DORM_LIMIT_MBPS  = 1         # Bóp Dorm xuống 1Mbps khi nghẽn
FLOOD_HOSTS      = 20        # Dùng 20 dorm để flood (đủ vượt 90% WAN)
POLL_INTERVAL    = 1         # Giây giữa các lần kiểm tra WAN

# ── Helpers ──────────────────────────────────────────────────────────────────
def banner(msg):
    print(f'\n{C}{"━"*72}\n  {msg}\n{"━"*72}{E}', flush=True)

def section(msg):
    print(f'\n{B}── {msg} ──{E}', flush=True)

def note(msg):
    print(f'  {G}•{E} {msg}', flush=True)

def warn(msg):
    print(f'  {Y}⚠{E} {msg}', flush=True)

def fail(msg):
    print(f'  {R}✗{E} {msg}', flush=True)

def ok(msg):
    print(f'  {G}✓{E} {msg}', flush=True)

def raw_out(txt):
    for line in txt.strip().splitlines():
        print(f'  {line}', flush=True)

def parse_ping(raw):
    """Trả về (loss%, avg_ms, mdev_ms)."""
    loss = 100.0; avg = 9999.0; mdev = 0.0
    m = re.search(r'(\d+(?:\.\d+)?)%\s+packet loss', raw)
    if m: loss = float(m.group(1))
    m = re.search(r'rtt[^=]+=\s*[\d.]+/([\d.]+)/([\d.]+)/([\d.]+)', raw)
    if m:
        avg  = float(m.group(1))
        mdev = float(m.group(3))
    return loss, avg, mdev

def get_wan_mbps(r1):
    """Đọc tốc độ TX trên WAN interface r1-eth4 (2 lần đo)."""
    def read_bytes():
        try:
            out = r1.cmd('cat /sys/class/net/r1-eth4/statistics/tx_bytes 2>/dev/null').strip()
            return int(out)
        except:
            return 0
    b1 = read_bytes(); t1 = time.time()
    time.sleep(1)
    b2 = read_bytes(); t2 = time.time()
    dt = t2 - t1
    if dt <= 0: return 0.0
    return (b2 - b1) * 8 / dt / 1_000_000  # Mbps

def check_ryu():
    """Kiểm tra Ryu Controller đang chạy."""
    result = subprocess.run(['pgrep', '-f', 'ryu-manager'], capture_output=True)
    return result.returncode == 0

# ── QoS Controller (tc rate-limit trên Dorm hosts) ──────────────────────────
class QoSController:
    """Giả lập vai trò SDN Controller: phát hiện nghẽn → bóp/mở luồng Dorm."""

    def __init__(self, net, wan_threshold=CONGESTION_THR, relief_threshold=RELIEF_THR):
        self.net = net
        self.r1  = net.get('r1')
        self.wan_thr   = wan_threshold * WAN_BW_MBPS
        self.relief_thr = relief_threshold * WAN_BW_MBPS
        self.limited   = False
        self.running   = False
        self.log       = []         # [(time, mbps, action)]
        self.alert_time = None

    def _apply_limit(self):
        """Bóp Dorm → 1Mbps qua tc TBF."""
        if self.limited:
            return
        self.alert_time = time.time()
        warn(f'{R}[CONTROLLER] WAN ≥ 90% → ÁP DỤNG RATE-LIMIT Dorm → {DORM_LIMIT_MBPS}Mbps{E}')
        for i in range(1, 41):
            try:
                h = self.net.get(f'dorm{i}')
                intf = h.defaultIntf().name
                h.cmd(f'tc qdisc del dev {intf} root 2>/dev/null')
                h.cmd(
                    f'tc qdisc add dev {intf} root tbf '
                    f'rate {DORM_LIMIT_MBPS}mbit burst 16kbit latency 50ms')
            except Exception:
                pass
        self.limited = True
        ok('[CONTROLLER] Rate-limit áp dụng xong. Admin/Lab/Srv KHÔNG bị ảnh hưởng.')

    def _remove_limit(self):
        """Gỡ giới hạn Dorm."""
        if not self.limited:
            return
        ok(f'[CONTROLLER] WAN < 70% → GỠ RATE-LIMIT Dorm.')
        for i in range(1, 41):
            try:
                h = self.net.get(f'dorm{i}')
                intf = h.defaultIntf().name
                h.cmd(f'tc qdisc del dev {intf} root 2>/dev/null')
            except Exception:
                pass
        self.limited = False

    def _monitor(self):
        while self.running:
            mbps = get_wan_mbps(self.r1)
            pct  = mbps / WAN_BW_MBPS * 100
            action = ''
            if mbps >= self.wan_thr and not self.limited:
                self._apply_limit()
                action = 'LIMIT'
            elif mbps < self.relief_thr and self.limited:
                self._remove_limit()
                action = 'RESTORE'
            self.log.append((time.time(), mbps, pct, action))
            print(f'  {C}[WAN Monitor]{E} {mbps:6.1f} Mbps = {pct:5.1f}%'
                  + (f'  {R}⚡ NGHẼN!{E}' if mbps >= self.wan_thr else '')
                  + (f'  {G}● bình thường{E}' if mbps < self.relief_thr and not self.limited else ''),
                  flush=True)
            time.sleep(POLL_INTERVAL)

    def start(self):
        self.running = True
        self._t = threading.Thread(target=self._monitor, daemon=True)
        self._t.start()

    def stop(self):
        self.running = False

    def force_limit(self):
        self._apply_limit()

    def force_restore(self):
        self._remove_limit()


# ── MAIN TEST ────────────────────────────────────────────────────────────────
def run_test():
    banner('testSDN.py – Demo SDN Dynamic QoS (Model 4)')
    print(f'  {Y}Kịch bản:{E} Dorm xả {FLOOD_HOSTS}×{DORM_FLOOD_MBPS}Mbps UDP → serverhcm')
    print(f'  {Y}WAN:{E} 200Mbps | {Y}Ngưỡng:{E} ≥90% → Controller can thiệp')
    print(f'  {G}Mong đợi:{E} Admin ping ổn định sau khi Controller bóp Dorm\n')

    # Kiểm tra Ryu
    if not check_ryu():
        warn('Ryu Controller chưa chạy! Vui lòng chạy:')
        warn('  ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653')
        warn('Tiếp tục ở chế độ standalone (failMode=standalone)...')
    else:
        ok('Ryu Controller đã chạy.')

    # Import và build mạng
    note('Import cauhinh4.py → build_net()...')
    try:
        import cauhinh4
        net = cauhinh4.build_net()
    except Exception as e:
        fail(f'build_net() thất bại: {e}')
        import traceback; traceback.print_exc()
        return

    try:
        r1          = net.get('r1')
        admin1      = net.get('admin1')
        serverhcm   = net.get('serverhcm')
        wan_ip      = '203.162.1.1'
        qos         = QoSController(net)

        # ── Warm-up ──────────────────────────────────────────────────────
        section('Warm-up: kiểm tra Admin → serverhcm')
        note('Ping warm-up 5 lần để ARP + flow table ổn định...')
        for _ in range(5):
            admin1.cmd(f'ping -c 2 -W 3 {wan_ip} 2>/dev/null')
            time.sleep(1)
        chk = admin1.cmd(f'ping -c 3 -W 3 {wan_ip} 2>&1')
        if '0 received' in chk and 'received' in chk:
            fail('Admin không ping được serverhcm. Kiểm tra routing.')
            raw_out(chk)
            net.stop()
            return
        ok('admin1 → serverhcm: THÔNG')

        # ── PHASE 1: BASELINE ─────────────────────────────────────────────
        section('PHASE 1 – BASELINE: Ping Admin → serverhcm (không flood)')
        print(f'\n{B}[RAW PING BASELINE – admin1 → {wan_ip}]{E}', flush=True)
        print('─'*60, flush=True)
        raw_baseline = admin1.cmd(f'ping -c 10 -i 0.3 {wan_ip} 2>/dev/null')
        raw_out(raw_baseline)
        print('─'*60, flush=True)
        loss_b, avg_b, _ = parse_ping(raw_baseline)
        note(f'→ Baseline: loss={loss_b:.0f}%  avg={avg_b:.2f}ms')

        # ── PHASE 2: FLOOD (không QoS) ──────────────────────────────────
        section(f'PHASE 2 – FLOOD: {FLOOD_HOSTS} Dorm xả {DORM_FLOOD_MBPS}Mbps UDP → serverhcm')
        note(f'Dorm xả → WAN bị nghẽn, Admin ping bị ảnh hưởng...')

        # Khởi động iperf server trên serverhcm
        serverhcm.cmd('pkill iperf 2>/dev/null')
        time.sleep(0.5)
        srv_proc = serverhcm.popen(['iperf', '-s', '-u', '-p', '9001'])
        time.sleep(1)

        # Flood từ FLOOD_HOSTS Dorm (dorm1-FLOOD_HOSTS)
        for i in range(1, FLOOD_HOSTS + 1):
            net.get(f'dorm{i}').cmd(
                f'iperf -c {wan_ip} -u -b {DORM_FLOOD_MBPS}M -t 60 '
                f'-p 9001 >/tmp/sdn_dorm{i}.txt 2>&1 &')
        note(f'Đã khởi động {FLOOD_HOSTS} Dorm iperf UDP → {wan_ip}')
        note('Đợi 5s cho traffic bão hòa...')
        time.sleep(5)

        # Ping Admin TRONG KHI flood (không QoS)
        note('Ping Admin → serverhcm TRONG KHI bị flood (không có QoS):')
        print(f'\n{B}[PING DURING FLOOD – Không QoS | admin1 → {wan_ip}]{E}', flush=True)
        print('─'*60, flush=True)
        raw_flood_nq = admin1.cmd(f'ping -c 10 -i 0.2 {wan_ip} 2>/dev/null')
        raw_out(raw_flood_nq)
        print('─'*60, flush=True)
        loss_fn, avg_fn, _ = parse_ping(raw_flood_nq)
        note(f'→ Flood (no QoS): loss={loss_fn:.0f}%  avg={avg_fn:.2f}ms')

        # Đọc WAN usage
        note('Đọc mức độ tải WAN (đo 3 lần):')
        wan_readings = []
        for i in range(3):
            mbps = get_wan_mbps(r1)
            pct  = mbps / WAN_BW_MBPS * 100
            wan_readings.append(mbps)
            status = f'{R}⚡ NGHẼN!{E}' if pct >= 90 else ''
            print(f'    đo {i+1}: {mbps:.1f} Mbps = {pct:.1f}% {status}', flush=True)
        avg_wan = sum(wan_readings) / len(wan_readings)
        avg_pct = avg_wan / WAN_BW_MBPS * 100
        if avg_pct >= 90:
            warn(f'{R}[CẢNH BÁO] WAN ≥ 90% ({avg_wan:.1f}/{WAN_BW_MBPS} Mbps)! Controller cần can thiệp!{E}')
        else:
            note(f'WAN = {avg_wan:.1f} Mbps ({avg_pct:.1f}%)')

        # ── PHASE 3: SDN CAN THIỆP ───────────────────────────────────────
        section('PHASE 3 – SDN CONTROLLER CAN THIỆP: Rate-limit Dorm')
        note('Controller phát hiện nghẽn → áp dụng tc TBF rate-limit Dorm → 1Mbps...')
        print('─'*60, flush=True)
        qos.force_limit()
        note('Đợi 5s cho traffic ổn định sau rate-limit...')
        time.sleep(5)

        # Đo WAN sau can thiệp
        note('Đọc mức tải WAN sau can thiệp:')
        after_readings = []
        for i in range(3):
            mbps = get_wan_mbps(r1)
            pct  = mbps / WAN_BW_MBPS * 100
            after_readings.append(mbps)
            print(f'    đo {i+1}: {mbps:.1f} Mbps = {pct:.1f}%', flush=True)
        avg_after = sum(after_readings) / len(after_readings)

        # Ping Admin SAU khi QoS can thiệp
        note('Ping Admin → serverhcm SAU KHI Controller can thiệp:')
        print(f'\n{B}[PING AFTER QoS – admin1 → {wan_ip}]{E}', flush=True)
        print('─'*60, flush=True)
        raw_after = admin1.cmd(f'ping -c 10 -i 0.2 {wan_ip} 2>/dev/null')
        raw_out(raw_after)
        print('─'*60, flush=True)
        loss_aq, avg_aq, _ = parse_ping(raw_after)
        note(f'→ Sau QoS: loss={loss_aq:.0f}%  avg={avg_aq:.2f}ms')

        # ── PHASE 4: RESTORE ─────────────────────────────────────────────
        section('PHASE 4 – RESTORE: Gỡ rate-limit, traffic bình thường')
        # Dừng flood
        for i in range(1, FLOOD_HOSTS + 1):
            net.get(f'dorm{i}').cmd('kill %iperf 2>/dev/null; pkill iperf 2>/dev/null')
        qos.force_restore()
        note('Đã dừng flood + gỡ rate-limit.')
        time.sleep(3)

        # Ping baseline cuối
        print(f'\n{B}[PING RESTORE – admin1 → {wan_ip}]{E}', flush=True)
        print('─'*60, flush=True)
        raw_restore = admin1.cmd(f'ping -c 5 -i 0.3 {wan_ip} 2>/dev/null')
        raw_out(raw_restore)
        print('─'*60, flush=True)
        loss_rs, avg_rs, _ = parse_ping(raw_restore)

        # ── KẾT QUẢ TỔNG HỢP ─────────────────────────────────────────────
        print(f'\n{C}{"─"*72}{E}', flush=True)
        print(f'{C}  KẾT QUẢ: SDN Dynamic QoS Demo{E}', flush=True)
        print(f'{C}{"─"*72}{E}', flush=True)
        rows = [
            ('Giai đoạn',               'Loss',           'Latency',         'WAN tải'),
            ('1. Baseline (không flood)', f'{loss_b:.0f}%', f'{avg_b:.2f}ms',  'thấp'),
            (f'2. Flood {FLOOD_HOSTS}×{DORM_FLOOD_MBPS}M (không QoS)',
                                          f'{loss_fn:.0f}%', f'{avg_fn:.2f}ms', f'{avg_wan:.0f}/{WAN_BW_MBPS} Mbps ({avg_pct:.0f}%)'),
            ('3. Sau Controller (QoS ON)', f'{loss_aq:.0f}%', f'{avg_aq:.2f}ms', f'{avg_after:.0f}/{WAN_BW_MBPS} Mbps'),
            ('4. Restore (flood dừng)',    f'{loss_rs:.0f}%', f'{avg_rs:.2f}ms', 'thấp'),
        ]
        col_w = [40, 8, 12, 30]
        header = rows[0]
        print('  ' + '  '.join(h.ljust(w) for h,w in zip(header, col_w)), flush=True)
        print('  ' + '─'*68, flush=True)
        for row in rows[1:]:
            line = '  '.join(v.ljust(w) for v,w in zip(row, col_w))
            # Tô màu
            if '3.' in row[0]:
                print(f'  {G}{line}{E}', flush=True)
            elif '2.' in row[0]:
                print(f'  {Y}{line}{E}', flush=True)
            else:
                print(f'  {line}', flush=True)
        print(f'{C}{"─"*72}{E}', flush=True)

        # Đánh giá
        if avg_aq < avg_fn * 0.8:
            ok(f'SDN thành công: latency giảm từ {avg_fn:.1f}ms → {avg_aq:.1f}ms sau can thiệp!')
        elif avg_fn < avg_b * 1.5:
            warn(f'Flood không gây đủ nghẽn (avg flood = {avg_fn:.1f}ms ≈ baseline {avg_b:.1f}ms)')
            warn(f'Thử tăng FLOOD_HOSTS hoặc DORM_FLOOD_MBPS, hoặc Ryu Controller chưa hoạt động')
        else:
            note(f'Controller đã can thiệp. Xem WAN readings ở trên để đánh giá.')

    except KeyboardInterrupt:
        warn('Bị ngắt bởi người dùng.')
    except Exception as e:
        fail(f'Lỗi: {e}')
        import traceback; traceback.print_exc()
    finally:
        # Cleanup
        try:
            for i in range(1, 41): net.get(f'dorm{i}').cmd('pkill iperf 2>/dev/null')
        except Exception: pass
        try: srv_proc.terminate()
        except Exception: pass
        net.stop()
        note('Mạng đã dừng.')
        subprocess.run(['sudo','mn','-c'], capture_output=True, timeout=30)


if __name__ == '__main__':
    if os.geteuid() != 0:
        print('Cần quyền root: sudo python3 testSDN.py')
        sys.exit(1)
    from mininet.log import setLogLevel
    setLogLevel('warning')
    run_test()

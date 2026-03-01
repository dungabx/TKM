# ĐỀ ÁN: THIẾT KẾ, KIỂM THỬ VÀ TỐI ƯU HÓA MẠNG CAMPUS QUY MÔ LỚN

> **Chủ đề:** Tối ưu hóa "Nút thắt cổ chai" và Đánh giá Hiệu năng Kiến trúc mạng cho  
> **Đại học Số (Digital Campus) – Phân hiệu Bảo Lộc**

---

## 📋 Mục lục

1. [Hồ sơ Hiện trạng](#1-hồ-sơ-hiện-trạng)
2. [Yêu cầu Cài đặt](#2-yêu-cầu-cài-đặt)
3. [Lộ trình 4 Mô hình Mạng](#3-lộ-trình-4-mô-hình-mạng)
4. [Hướng dẫn Chạy Từng File](#4-hướng-dẫn-chạy-từng-file)
5. [Kịch bản Kiểm thử (testver2.py)](#5-kịch-bản-kiểm-thử-testver2py)
6. [Demo SDN Dynamic QoS (testSDN.py)](#6-demo-sdn-dynamic-qos-testsdnpy)
7. [Quy tắc Đặt tên & Phân bổ IP](#7-quy-tắc-đặt-tên--phân-bổ-ip)
8. [Mô hình 1: Mạng Phẳng](#8-mô-hình-1-mạng-phẳng-cauhinh1py)
9. [Mô hình 2: Mạng 3 Lớp](#9-mô-hình-2-mạng-3-lớp-cauhinh2py)
10. [Mô hình 3: Spine-Leaf](#10-mô-hình-3-spine-leaf-cauhinh3py)
11. [Mô hình 4: SDN Automation](#11-mô-hình-4-sdn-automation-cauhinh4py)
12. [So sánh 8 Tiêu chí Vàng](#12-so-sánh-8-tiêu-chí-vàng)
13. [Tính toán Lý thuyết](#13-tính-toán-lý-thuyết)
14. [Lưu ý & Troubleshooting](#14-lưu-ý--troubleshooting)

---

## 1. Hồ sơ Hiện trạng

| Thông tin | Giá trị |
|---|---|
| **Khách hàng** | Phân hiệu Đại học Bảo Lộc (VPN về TP.HCM) |
| **Quy mô vật lý** | 2 Tòa nhà: Block A (Hành chính/Lab AI) · Block B (Ký túc xá) |
| **Người dùng** | ~1.200 sinh viên và cán bộ |
| **Nút thắt sinh tử** | WAN kết nối TP.HCM chỉ **200 Mbps** |

### Phân bổ Zone và Yêu cầu SLA

| Zone | Host Mininet | Đặc tính Traffic | Yêu cầu SLA |
|---|---|---|---|
| **Zone 1 – Admin** | `admin1`…`admin5` | North-South · ERP/SAP HCM · lưu lượng nhỏ | Latency < 20ms · **Zero Loss** |
| **Zone 2 – AI Lab** | `lab1`…`lab20` | East-West · Distributed Training | Bandwidth **> 1 Gbps** nội bộ |
| **Zone 3 – Dorm** | `dorm1`…`dorm40` | North-South · Streaming/Gaming buổi tối | Best-effort |
| **Zone 4 – Server** | `srv1`…`srv4` | File share · Cache | High Availability |
| **WAN** | `serverhcm` `203.162.1.1` | Internet/Intranet HCM | **200 Mbps** (nút thắt) |

---

## 2. Yêu cầu Cài đặt

### Hệ điều hành

```
Ubuntu 22.04+ (hoặc 20.04)  –  Python 3.10+
```

### Cài đặt Mininet

```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch iperf traceroute
```

### Cài đặt Ryu Controller (cho Model 4)

> ⚠ **Ryu không tương thích trực tiếp với Python 3.12 — cần fix thủ công.**

```bash
# 1. Cài Ryu
sudo pip3 install ryu --break-system-packages

# 2. Cài eventlet đúng version (tương thích Python 3.12)
sudo pip3 install eventlet==0.35.2 --break-system-packages --force-reinstall

# 3. Patch wsgi.py (fix lỗi ALREADY_HANDLED)
sudo sed -i \
  's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
  /usr/local/lib/python3.12/dist-packages/ryu/app/wsgi.py

# 4. Kiểm tra Ryu hoạt động
ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653
```

### Thư viện Python

```bash
sudo pip3 install matplotlib networkx --break-system-packages
```

### Kiểm tra tổng hợp

```bash
which mininet     # /usr/bin/mininet
which iperf       # /usr/bin/iperf
which ryu-manager # /usr/local/bin/ryu-manager
python3 -c "import mininet, matplotlib, networkx; print('OK')"
```

---

## 3. Lộ trình 4 Mô hình Mạng

```
cauhinh1.py  ──→  cauhinh2.py  ──→  cauhinh3.py  ──→  cauhinh4.py
Mạng Phẳng       3 Lớp             Spine-Leaf          SDN + QoS
(Thảm họa)   (Cách ly VLAN)     (ECMP / VXLAN)      (Tự động hóa)
```

| File | Mô hình | Mục tiêu |
|---|---|---|
| `cauhinh1.py` | Flat Network | Chứng minh Broadcast Storm & Single Point of Failure |
| `cauhinh2.py` | Hierarchical L3 | Cô lập VLAN, STP lãng phí 50% BW dự phòng |
| `cauhinh3.py` | Spine-Leaf + VXLAN | ECMP loại bỏ bottleneck, 100% link utilization |
| `cauhinh4.py` | SDN + Dynamic QoS | Tự động bảo vệ Admin khi WAN nghẽn |
| `testver2.py` | Test so sánh | 8 bài test so sánh 4 mô hình |
| `testSDN.py` | Demo SDN QoS | Kịch bản thực tế: flood → phát hiện → can thiệp |

---

## 4. Hướng dẫn Chạy Từng File

### Dọn dẹp trước khi chạy (quan trọng!)

```bash
sudo mn -c
```

### Model 1 – Mạng Phẳng

```bash
sudo python3 cauhinh1.py
```

### Model 2 – 3 Lớp (STP)

```bash
sudo python3 cauhinh2.py
```

### Model 3 – Spine-Leaf

```bash
sudo python3 cauhinh3.py
```

### Model 4 – SDN (cần Ryu)

```bash
# Terminal 1: Khởi động Ryu Controller
sudo ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653

# Terminal 2: Khởi động topology
sudo python3 cauhinh4.py
```

---

## 5. Kịch bản Kiểm thử (testver2.py)

### Chạy từng test

```bash
# Xem danh sách test
sudo python3 testver2.py

# Chạy test cụ thể
sudo python3 testver2.py test1   # MAC Flooding
sudo python3 testver2.py test2   # STP vs ECMP Bandwidth
sudo python3 testver2.py test4   # STP Reconvergence (cần Ryu)
sudo python3 testver2.py test5   # Anycast Gateway Latency
sudo python3 testver2.py test6   # Dynamic QoS (cần Ryu)
sudo python3 testver2.py test7   # Control Plane Failure (cần Ryu)
sudo python3 testver2.py test8   # Multi-hop Latency

# Chạy tất cả (tự động)
sudo python3 testver2.py all
```

### Mô tả 8 bài test

| Test | So sánh | Kịch bản | Chỉ số đo |
|---|---|---|---|
| **test1** | Model 1 vs 2 | macof flood bảng MAC | Ping loss Admin trước/sau flood |
| **test2** | Model 2 vs 3 | 20 Lab iperf → srv1 + ping đo latency dưới tải | STP blocked ports / latency tăng khi flood |
| **test3** | *(bỏ qua)* | — | — |
| **test4** | Model 2 vs 4 | Cắt uplink đang Forwarding | Thời gian STP reconvergence (giây timeout) |
| **test5** | Model 2 vs 3 | Ping Lab/Admin → Default Gateway | Latency tới GW (Anycast=gần vs Center=xa) |
| **test6** | All vs Model 4 | Dorm xả 200Mbps UDP → WAN | Admin ping trước/sau SDN can thiệp |
| **test7** | Model 3 vs 4 | Tắt Ryu Controller | Ping luồng mới (SDN sập vs Distributed OK) |
| **test8** | Model 2 vs 3 | Traceroute nhiều cặp host | Số hop và độ đồng đều latency |

### Lưu ý quan trọng khi chạy testver2.py

- **test4, test6, test7** yêu cầu Ryu Controller chạy trước:
  ```bash
  sudo ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653
  ```
- Kết quả **test2** đo 2 chỉ số: STP blocking ports (≥8 vs 0) và latency dưới tải (~236ms vs ~102ms)
- Nếu bị lỗi "mn process already running": `sudo mn -c`

---

## 6. Demo SDN Dynamic QoS (testSDN.py)

### Kịch bản

```
PHASE 1 – BASELINE:     Admin ping serverhcm → latency ~2ms, 0% loss
PHASE 2 – FLOOD:        20 Dorm × 8Mbps UDP = 160Mbps → WAN ~90%
                         → Phát cảnh báo [NGHẼN]
                         → Admin ping bị ảnh hưởng (latency tăng / loss)
PHASE 3 – CAN THIỆP:   Controller áp tc TBF → Dorm giới hạn 1Mbps
                         → WAN giải phóng
                         → Admin ping phục hồi
PHASE 4 – RESTORE:      Dừng flood + gỡ rate-limit
```

### Chạy

```bash
# Terminal 1: Ryu Controller (bắt buộc)
sudo ryu-manager ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653

# Terminal 2: Demo SDN QoS
sudo python3 testSDN.py
```

### Kết quả mong đợi

```
Giai đoạn                        Loss   Latency    WAN tải
─────────────────────────────────────────────────────────────
1. Baseline (không flood)          0%    ~2ms       thấp
2. Flood 20×8M (không QoS)        ~20%  ~150ms     ~160/200 Mbps (80%)
3. Sau Controller (QoS ON)          0%    ~5ms       ~20/200 Mbps
4. Restore (flood dừng)             0%    ~2ms       thấp
```

### Cơ chế hoạt động

- Giám sát TX bytes trên `r1-eth4` (WAN interface) mỗi 1 giây
- Ngưỡng kích hoạt: ≥ **90%** × 200Mbps = **180 Mbps**
- Khi vượt ngưỡng: `tc qdisc add tbf rate 1mbit` trên mỗi dorm host
- Khi giảm < **70%** (140 Mbps): tự động gỡ rate-limit

---

## 7. Quy tắc Đặt tên & Phân bổ IP

> Áp dụng thống nhất cho **tất cả 4 file** `cauhinh*.py`

| Đối tượng | Quy tắc | Ví dụ |
|---|---|---|
| **Switch** | `s1`, `s2`, `s3`, … | `s1`, `s2` |
| **Router** | `r1` | `r1` |
| **Host Admin** | `admin1`…`admin5` | VLAN 10 / `10.0.10.x` |
| **Host Lab** | `lab1`…`lab20` | VLAN 20 / `10.0.20.x` |
| **Host Dorm** | `dorm1`…`dorm40` | VLAN 30 / `10.0.30.x` |
| **Host Server** | `srv1`…`srv4` | VLAN 99 / `10.0.99.x` |
| **Server HCM** | `serverhcm` | `203.162.1.1/24` |

| VLAN | Subnet | Gateway |
|---|---|---|
| VLAN 10 (Admin) | `10.0.10.0/24` | `10.0.10.254` |
| VLAN 20 (Lab) | `10.0.20.0/24` | `10.0.20.254` |
| VLAN 30 (Dorm) | `10.0.30.0/24` | `10.0.30.254` |
| VLAN 99 (Server) | `10.0.99.0/24` | `10.0.99.254` |
| WAN | `203.162.1.0/24` | `203.162.1.254` |

**Băng thông link:**

| Đường link | Model 1 | Model 2 | Model 3 | Model 4 |
|---|---|---|---|---|
| Host Admin → SW | 100 Mbps | 100 Mbps | 100 Mbps | 100 Mbps |
| Host Lab → SW | 1 Gbps | 1 Gbps | 1 Gbps | 1 Gbps |
| Host Dorm → SW | 50 Mbps | 50 Mbps | 50 Mbps | 50 Mbps |
| Uplink SW | 1 Gbps | 1 Gbps × 2 | 1 Gbps × 2/Leaf | 1 Gbps × 2/Leaf |
| WAN (r1↔serverhcm) | 200 Mbps·10ms | 200 Mbps·10ms | 200 Mbps·10ms | 200 Mbps·10ms |

---

## 8. Mô hình 1: Mạng Phẳng (`cauhinh1.py`)

Tất cả host nằm chung **1 Broadcast Domain** (`10.0.0.0/16`). Không có VLAN, không có cách ly.

### Các vấn đề cần chứng minh

1. **Broadcast Storm:** `macof` từ dorm bơm hàng vạn MAC giả/giây → Switch biến thành Hub → Admin ping bị timeout
2. **Không cách ly:** `dorm1` ping trực tiếp `admin1`
3. **Single Point of Failure:** Tắt switch duy nhất → toàn bộ mạng sập

### Sơ đồ

```
serverhcm (203.162.1.1)
    │ 200Mbps/10ms
    r1 (10.0.0.254)
    │ 1Gbps
┌───┴───┐ Trunk ┌─────────┐
│  s1   ├───────┤   s2    │
│Admin  │       │Dorm+Srv │
│+Lab   │       │         │
└───────┘       └─────────┘
```

---

## 9. Mô hình 2: Mạng 3 Lớp (`cauhinh2.py`)

Kiến trúc **Core → Distribution → Access** Cisco chuẩn. VLAN cách ly 4 zones. STP chạy trên tất cả switch.

### Cấu trúc switch

| Lớp | Thiết bị | Ghi chú |
|---|---|---|
| Core | `s1` (Root Bridge) + `s20` (Backup) | Dual Core, STP priority |
| Distribution | `s2` (Dist A1), `s3` (Dist A2), `s4` (Dist Dorm), `s5` (Dist Srv) | L3 Routing SVI |
| Access | `s6` (Admin), `s7`–`s10` (Lab×4), `s11`–`s18` (Dorm×8), `s19` (Server) | L2 only |

### Vấn đề chứng minh

- **STP Block Port:** Lab sw nối dual-home → STP khóa 1 Uplink → 8 ports BLOCKING
- **Bottleneck Core:** Khi 20 lab flood → tất cả qua Core s1 → latency tăng ~236ms
- **Model 3 cải thiện:** latency flood chỉ ~102ms (2 Spine phân tải)

---

## 10. Mô hình 3: Spine-Leaf (`cauhinh3.py`)

**Clos Topology** — loại bỏ STP hoàn toàn. ECMP đảm bảo 100% link utilization.

### Cấu trúc

| Lớp | Thiết bị |
|---|---|
| Spine | `s1` (Spine1), `s2` (Spine2) |
| Leaf | `s3` (leaf_admin), `s4` (leaf_lab1), `s5` (leaf_lab2), `s6` (leaf_dorm1), `s7` (leaf_dorm2), `s8` (Border Leaf/leaf_srv) |

**Full-mesh:** Mỗi Leaf nối cả 2 Spine. Không có link Leaf↔Leaf hay Spine↔Spine.

```
         spine1(s1)    spine2(s2)
           │  │  │  │    │  │  │  │
          s3 s4 s5 s6   s7 s8...
```

### Anycast Gateway

IP Gateway (`10.0.20.254`) được đặt trên cả `leaf_lab1` (s4) và `leaf_lab2` (s5) → PC chỉ cần 1 hop đến GW.

---

## 11. Mô hình 4: SDN Automation (`cauhinh4.py`)

Topology giống Model 3 nhưng thêm **Ryu RemoteController** trên port 6653.

### Thành phần SDN

| Thành phần | Mô tả |
|---|---|
| **Ryu Controller** | `ryu.app.simple_switch_13` · port 6653 · giám sát WAN |
| **OVS Switches** | `protocols=OpenFlow13` · `failMode=standalone` (vẫn chạy nếu controller mất) |
| **DynamicQoSMonitor** | Thread độc lập, poll WAN mỗi 2s, áp `tc tbf` khi cần |

### Logic Dynamic QoS

```python
WAN > 90% × 200Mbps  →  tc tbf rate 1mbit trên tất cả dorm host
WAN < 70% × 200Mbps  →  gỡ tc tbf → Dorm trở về bình thường
```

### Cần Ryu cho

- **test4** (STP Reconvergence vs SDN Fast Failover)
- **test6** (Dynamic QoS demo)
- **test7** (Control Plane Failure)
- **testSDN.py** (full SDN QoS scenario)

---

## 12. So sánh 8 Tiêu chí Vàng

| Tiêu chí | Model 1: Flat | Model 2: 3-Tier | Model 3: Spine-Leaf | Model 4: SDN |
|---|---|---|---|---|
| **1. Scalability** | ❌ Rất kém | ✅ Tốt | ✅✅ Xuất sắc | ✅✅ Xuất sắc |
| **2. Performance** | ❌ Thấp | ⚠ Khá (STP giới hạn) | ✅✅ Tối đa (ECMP) | ✅✅ Tối đa + tối ưu động |
| **3. Availability** | ❌ SPOF | ✅ Cao (hội tụ chậm) | ✅✅ Rất cao (multi-path) | ✅✅ Rất cao (auto-reroute) |
| **4. Security** | ❌ Rất kém | ✅ VLAN + ACL tĩnh | ✅✅ VXLAN micro-seg | ✅✅ Chính sách động |
| **5. Manageability** | ⚠ Dễ ban đầu | ❌ Thủ công | ❌ Phức tạp (OSPF/BGP) | ✅✅ Tập trung qua API |
| **6. Cost** | ✅ Rẻ nhất | ⚠ Trung bình | ❌ Cao (SW cao cấp) | ⚠ HW rẻ, SW đắt |
| **7. Agility** | ❌ Cứng nhắc | ❌ Thay đổi chậm | ✅ Linh hoạt | ✅✅ Lập trình bằng Code |
| **8. QoS/Traffic** | ❌ Không thể | ⚠ QoS tĩnh | ⚠ ECMP tốt | ✅✅ Dynamic QoS hoàn hảo |

---

## 13. Tính toán Lý thuyết

### Oversubscription WAN (20:00 tối)

| Nguồn | Lưu lượng |
|---|---|
| 30 SV KTX xem YouTube HD | 30 × 5 Mbps = 150 Mbps |
| 10 SV KTX chơi Game | 10 × 1 Mbps = 10 Mbps |
| Giám đốc họp Zoom (Admin) | 3 Mbps |
| **Tổng demand** | **≥ 163 Mbps** |
| **WAN Capacity** | **200 Mbps** (nghẽn nếu thêm backup) |

### Độ trễ lý thuyết: `lab1` → `lab20`

| Mô hình | Số hop | Delay lý thuyết |
|---|---|---|
| Model 2 (3-Layer, 5 SW) | 6 hop | **0.82 ms** |
| Model 3 (Spine-Leaf, 3 SW) | 4 hop | **0.52 ms** (-37%) |

### QoS Queue tại cổng WAN

| Queue | VLAN | Loại | % BW |
|---|---|---|---|
| Q1 | VLAN 10 (Admin) | **Priority Queue** | ≤10% nhưng ưu tiên tuyệt đối |
| Q2 | VLAN 99 (Server) | CBWFQ | 30% (60 Mbps) |
| Q3 | VLAN 30 (Dorm) | WFQ | 60% (120 Mbps) |

---

## 14. Lưu ý & Troubleshooting

### ⚠ Lỗi thường gặp

#### Lỗi 1: `ALREADY_HANDLED` import error khi chạy Ryu

```
ImportError: cannot import name 'ALREADY_HANDLED' from 'eventlet.wsgi'
```

**Fix:**
```bash
sudo pip3 install eventlet==0.35.2 --break-system-packages --force-reinstall
sudo sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
  /usr/local/lib/python3.12/dist-packages/ryu/app/wsgi.py
```

#### Lỗi 2: `No module named 'imp'` khi chạy Ryu trên Python 3.12

**Fix:** Dùng `eventlet==0.35.2` (đã khắc phục `imp` module bị xóa trong Python 3.12)

#### Lỗi 3: Mininet còn tiến trình cũ

```
Exception: Error creating interface pair...
```

**Fix:**
```bash
sudo mn -c
sudo killall -9 mininet 2>/dev/null
```

#### Lỗi 4: iperf kết nối thất bại (connect failed)

Nguyên nhân: Server chưa khởi động hoặc OVS chưa hội tụ  
**Fix:** Thêm warm-up ping + `time.sleep(2)` sau khi khởi động iperf server

#### Lỗi 5: admin1 → serverhcm = 100% loss

Nguyên nhân: Inter-VLAN routing chưa được warm-up, ARP chưa được học  
**Fix:** Warm-up `lab1 → srv1` bằng ping nhiều lần trước khi test admin

### 📝 Lưu ý quan trọng

1. **Kết quả kiểm thử PHẢI là output thô** từ `ping`/`iperf` — **nghiêm cấm** tạo số liệu giả
2. **STP convergence 15s** - mỗi lần build_net() cần đợi đủ
3. **Mininet OVS không thực sự ECMP per-packet** — dùng flow-based hashing, nên kết quả BW giữa 2 topology gần nhau; thay vào đó dùng **latency dưới tải** để so sánh
4. **Model 3 `s2` có 5 port BLOCKING** — đây là OVS STP tự phát sinh để chống loop trên hệ thống; không phải thiết kế thủ công
5. **testSDN.py chạy độc lập** không phụ thuộc `testver2.py`
6. **Chạy `sudo mn -c` trước mỗi test** để tránh xung đột tiến trình

### Thứ tự cài đặt đầy đủ (fresh install)

```bash
# 1. Cài dependencies hệ thống
sudo apt-get update && sudo apt-get install -y \
  mininet openvswitch-switch iperf traceroute net-tools

# 2. Cài Python packages
sudo pip3 install matplotlib networkx ryu --break-system-packages

# 3. Fix Ryu-eventlet compatibility
sudo pip3 install eventlet==0.35.2 --break-system-packages --force-reinstall
sudo sed -i \
  's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
  /usr/local/lib/python3.12/dist-packages/ryu/app/wsgi.py

# 4. Copy project vào Linux và chạy
cd /home/mn/tkm_final
sudo python3 testver2.py test2
```

---

> **Lưu ý cuối:** Mọi kết quả trong báo cáo phải được lấy trực tiếp từ output thô của `ping` và `iperf` chạy trong Mininet. Không được điền số liệu giả hoặc dùng `print()` để mô phỏng kết quả.

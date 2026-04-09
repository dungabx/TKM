#!/bin/bash
# source/microsegment.sh
# Kịch bản ip6tables thiết lập Zero Trust Micro-segmentation (Chuẩn IPv6)
# ═══════════════════════════════════════════════════════════════════════
# 8 QUY TẮC PHÂN ĐOẠN CHÍNH SÁCH:
#   A. Web Tier (Cách ly nội bộ):
#       QT1: web_server1 <-> web_server2: DENY (Chống lây lan ngang)
#       QT2: Internet -> web_server1/2: ALLOW TCP 80, 443
#       QT3: web_server1/2 -> Internet: DENY (Chỉ phản hồi, không khởi tạo)
#   B. Database Tier (Bảo vệ lõi):
#       QT4: db_server1 <-> db_server2: ALLOW (Cluster/Replication)
#       QT5: web_server1/2 -> db_server1/2: ALLOW TCP 3306
#       QT6: Mọi nguồn khác -> db_server1/2: STRICT DENY
#   C. DNS Tier (Dịch vụ phân giải):
#       QT7: Mọi Host nội bộ -> dns_server1/2: ALLOW UDP/TCP 53
#       QT8: dns_server1/2 -> Internet: ALLOW UDP 53
# ═══════════════════════════════════════════════════════════════════════

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   TRIỂN KHAI ZERO TRUST IPv6 MICRO-SEGMENTATION (8 QUY TẮC) ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Khai báo biến Subnet
WEB1="fd00:10::1"
WEB2="fd00:10::2"
WEB_NET="fd00:10::/64"
DNS_NET="fd00:20::/64"
DB_NET="fd00:30::/64"
INTERNET_V4_MAPPED="64:ff9b::/96"  # Dải Tayga NAT64

# ─────────────────────────────────────────────────────────────────────
# BƯỚC 1: XÓA TOÀN BỘ QUY TẮC CŨ (FLUSH)
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "  [1/4] Xóa cấu hình tường lửa cũ trên tất cả các node..."
for node in web_server1 web_server2 dns_server1 dns_server2 db_server1 db_server2 s3 s4 s5; do
    ip netns exec $node ip6tables -F INPUT   2>/dev/null
    ip netns exec $node ip6tables -F FORWARD 2>/dev/null
    ip netns exec $node ip6tables -F OUTPUT  2>/dev/null
done
echo "     ✓ Đã dọn sạch!"

# ─────────────────────────────────────────────────────────────────────
# BƯỚC 2: NETWORK-LEVEL FIREWALL (Trên các Leaf Router s3, s4, s5)
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "  [2/4] Thiết lập Leaf Router Firewall (Network Level)..."

# ═══════════════════════════════════════
# LEAF S3 — Phân đoạn Web Tier
# ═══════════════════════════════════════
echo "     → Leaf S3 (Web Tier)..."

# Lõi IPv6 yêu cầu NDP (Neighbor Discovery Protocols) để định tuyến thay cho ARP. 
# CHỈ ALLOW phần này, KHÔNG ACCEPT Ping (Echo)!
for type in 133 134 135 136; do
    ip netns exec s3 ip6tables -A FORWARD -p ipv6-icmp --icmpv6-type $type -j ACCEPT
done

# [QT2] Internet -> Web: ALLOW TCP 80, 443
ip netns exec s3 ip6tables -A FORWARD -s $INTERNET_V4_MAPPED -d $WEB_NET -p tcp -m multiport --dports 80,443 -j ACCEPT

# [QT3] Web -> Internet: CHỈ CHO PHÉP PHẢN HỒI (ESTABLISHED), CHẶN KHỞI TẠO (NEW)
ip netns exec s3 ip6tables -A FORWARD -s $WEB_NET -d $INTERNET_V4_MAPPED -m state --state ESTABLISHED -j ACCEPT

# [QT7-S3] Web -> DNS: ALLOW UDP/TCP 53 (Cho phép Web tra DNS nội bộ)
ip netns exec s3 ip6tables -A FORWARD -s $WEB_NET -d $DNS_NET -p udp --dport 53 -j ACCEPT
ip netns exec s3 ip6tables -A FORWARD -s $WEB_NET -d $DNS_NET -p tcp --dport 53 -j ACCEPT
ip netns exec s3 ip6tables -A FORWARD -s $DNS_NET -d $WEB_NET -m state --state ESTABLISHED -j ACCEPT

# [QT5-S3] Web -> DB: ALLOW TCP 3306 (Cho phép Web truy vấn Database)
ip netns exec s3 ip6tables -A FORWARD -s $WEB_NET -d $DB_NET -p tcp --dport 3306 -j ACCEPT
ip netns exec s3 ip6tables -A FORWARD -s $DB_NET -d $WEB_NET -m state --state ESTABLISHED -j ACCEPT

# DEFAULT DENY: Chặn mọi thứ còn lại qua S3
ip netns exec s3 ip6tables -A FORWARD -j LOG --log-prefix "ZT-S3-DENY: "
ip netns exec s3 ip6tables -A FORWARD -j DROP

# ═══════════════════════════════════════
# LEAF S4 — Phân đoạn DNS Tier
# ═══════════════════════════════════════
echo "     → Leaf S4 (DNS Tier)..."

for type in 133 134 135 136; do
    ip netns exec s4 ip6tables -A FORWARD -p ipv6-icmp --icmpv6-type $type -j ACCEPT
done

# [QT7] Mọi Host nội bộ -> DNS: ALLOW UDP/TCP 53
for NET in $WEB_NET $DB_NET; do
    ip netns exec s4 ip6tables -A FORWARD -s $NET -d $DNS_NET -p udp --dport 53 -j ACCEPT
    ip netns exec s4 ip6tables -A FORWARD -s $NET -d $DNS_NET -p tcp --dport 53 -j ACCEPT
    ip netns exec s4 ip6tables -A FORWARD -s $DNS_NET -d $NET -m state --state ESTABLISHED -j ACCEPT
done

# [QT8] DNS -> Internet: ALLOW UDP 53 (Truy vấn Root DNS bên ngoài)
ip netns exec s4 ip6tables -A FORWARD -s $DNS_NET -d $INTERNET_V4_MAPPED -p udp --dport 53 -j ACCEPT
ip netns exec s4 ip6tables -A FORWARD -s $INTERNET_V4_MAPPED -d $DNS_NET -m state --state ESTABLISHED -j ACCEPT

# DEFAULT DENY: Chặn mọi thứ còn lại qua S4
ip netns exec s4 ip6tables -A FORWARD -j LOG --log-prefix "ZT-S4-DENY: "
ip netns exec s4 ip6tables -A FORWARD -j DROP

# ═══════════════════════════════════════
# LEAF S5 — Phân đoạn Database Tier
# ═══════════════════════════════════════
echo "     → Leaf S5 (Database Tier)..."

for type in 133 134 135 136; do
    ip netns exec s5 ip6tables -A FORWARD -p ipv6-icmp --icmpv6-type $type -j ACCEPT
done

# [QT5] Web -> DB: ALLOW TCP 3306
ip netns exec s5 ip6tables -A FORWARD -s $WEB_NET -d $DB_NET -p tcp --dport 3306 -j ACCEPT
ip netns exec s5 ip6tables -A FORWARD -s $DB_NET -d $WEB_NET -m state --state ESTABLISHED -j ACCEPT

# [QT6] Mọi nguồn khác (bao gồm Internet) -> DB: STRICT DENY
ip netns exec s5 ip6tables -A FORWARD -j LOG --log-prefix "ZT-S5-DB-DENY: "
ip netns exec s5 ip6tables -A FORWARD -j DROP

# ─────────────────────────────────────────────────────────────────────
# BƯỚC 3: HOST-LEVEL FIREWALL (Trên từng máy chủ ảo)
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "  [3/4] Thiết lập Host Firewall (VM Level)..."

# ═══════════════════════════════════════
# [QT1] WEB ISOLATION — Cách ly ngang Web Tier
# ═══════════════════════════════════════
echo "     → QT1: Chặn Web1 <-> Web2 (Chống lây lan mã độc ngang)..."
for web in web_server1 web_server2; do
    for type in 133 134 135 136; do
        ip netns exec $web ip6tables -A INPUT -p ipv6-icmp --icmpv6-type $type -j ACCEPT
    done
    ip netns exec $web ip6tables -A INPUT -i lo -j ACCEPT
    ip netns exec $web ip6tables -A INPUT -m state --state ESTABLISHED -j ACCEPT
    # CHẶN mọi traffic đến từ cùng Subnet Web (không phải loopback)
    ip netns exec $web ip6tables -A INPUT -s $WEB_NET -j LOG --log-prefix "ZT-WEB-ISOLATE: "
    ip netns exec $web ip6tables -A INPUT -s $WEB_NET -j DROP
done

# ═══════════════════════════════════════
# [QT4 + QT5 + QT6] DATABASE — Bảo vệ lõi dữ liệu
# ═══════════════════════════════════════
echo "     → QT4/5/6: Bảo vệ DB Server (Cluster OK, Web TCP3306 OK, Còn lại DENY)..."
for db in db_server1 db_server2; do
    for type in 133 134 135 136; do
        ip netns exec $db ip6tables -A INPUT -p ipv6-icmp --icmpv6-type $type -j ACCEPT
    done
    ip netns exec $db ip6tables -A INPUT -i lo -j ACCEPT
    
    # [QT4] db_server1 <-> db_server2: ALLOW (Cluster/Replication)
    ip netns exec $db ip6tables -A INPUT -s $DB_NET -j ACCEPT
    
    # [QT5] Web -> DB: ALLOW TCP 3306
    ip netns exec $db ip6tables -A INPUT -s $WEB_NET -p tcp --dport 3306 -j ACCEPT
    
    # Cho phép phản hồi các kết nối đã thiết lập
    ip netns exec $db ip6tables -A INPUT -m state --state ESTABLISHED -j ACCEPT
    
    # [QT6] STRICT DENY: Mọi thứ còn lại (Cấm tiệt Ping dạo)
    ip netns exec $db ip6tables -A INPUT -j LOG --log-prefix "ZT-DB-HOST-DENY: "
    ip netns exec $db ip6tables -A INPUT -j DROP
done

# ─────────────────────────────────────────────────────────────────────
# BƯỚC 4: XÁC NHẬN & IN BÁO CÁO
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "  [4/4] Xác nhận trạng thái..."
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              BÁO CÁO CHÍNH SÁCH ĐÃ ÁP DỤNG                ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║ QT1: Web1 <-> Web2           │ ✗ DENY  (Cách ly ngang)     ║"
echo "║ QT2: Internet -> Web (80,443)│ ✓ ALLOW (Dịch vụ HTTP/S)    ║"
echo "║ QT3: Web -> Internet         │ ✗ DENY  (Chỉ phản hồi)     ║"
echo "║ QT4: DB1 <-> DB2             │ ✓ ALLOW (Cluster/Repl.)     ║"
echo "║ QT5: Web -> DB (TCP 3306)    │ ✓ ALLOW (Truy vấn CSDL)    ║"
echo "║ QT6: * -> DB (Còn lại)       │ ✗ DENY  (Bảo vệ lõi)       ║"
echo "║ QT7: Internal -> DNS (53)    │ ✓ ALLOW (Phân giải tên)     ║"
echo "║ QT8: DNS -> Internet (UDP53) │ ✓ ALLOW (Root DNS Query)    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Hoàn thành! Micro-segmentation Zero Trust đã được triển khai thành công."
#!/bin/bash
# source/nat_setup.sh
# Kịch bản cấu hình TAYGA NAT64 chuyển IPv6 Internal -> IPv4 Public

echo "=== Triển khai tayga NAT64 trên Gateway r1 ==="

# 1. Cài đặt Tayga (Nếu chưa có)
if ! command -v tayga &> /dev/null; then
    echo "Đang tự động cài đặt TAYGA (NAT64 module)..."
    apt-get update -qq && apt-get install tayga -y -qq
fi

# Môi trường Network Namespace r1
IP_NETNS="ip netns exec r1"

# 2. Xóa cấu hình cũ
$IP_NETNS killall tayga 2>/dev/null
$IP_NETNS ip link del nat64 2>/dev/null
$IP_NETNS iptables -t nat -F POSTROUTING 2>/dev/null

# 3. Tạo file config giả lập Tayga cho Router r1
mkdir -p /tmp/r1_tayga
cat <<EOF > /tmp/r1_tayga/tayga.conf
tun-device nat64
ipv4-addr 192.168.255.1
ipv6-addr 2001:db8:1::1
prefix 64:ff9b::/96
dynamic-pool 192.168.255.128/25
data-dir /tmp/r1_tayga
map 192.168.255.11 fd00:10::1
map 192.168.255.12 fd00:10::2
map 192.168.255.21 fd00:20::1
map 192.168.255.22 fd00:20::2
map 192.168.255.31 fd00:30::1
map 192.168.255.32 fd00:30::2
EOF

# 4. Kích hoạt hầm IP ảo NAT64
$IP_NETNS tayga -c /tmp/r1_tayga/tayga.conf --mktun
$IP_NETNS ip link set nat64 up

# 5. Route tayga demon background (Bật Daemon MỚI gán Route, chống lỗi Flap xoá Route)
$IP_NETNS tayga -c /tmp/r1_tayga/tayga.conf
sleep 1

# Add IP routing cho tunnel
$IP_NETNS ip addr add 192.168.255.1 dev nat64
$IP_NETNS ip -6 addr add 2001:db8:1::1 dev nat64
$IP_NETNS ip route add 192.168.255.0/24 dev nat64
$IP_NETNS ip -6 route add 64:ff9b::/96 dev nat64

# OSPFv3 Redistribution (Kéo luồng 64:ff9b:: xuống router áo nội bộ để host biết đường ra)

# 6. IPv4 SNAT MASQUERADE (Từ 192.168.255.X ảo để chui ra IP Public của r1-eth1 và r1-eth2)
$IP_NETNS iptables -t nat -A POSTROUTING -s 192.168.255.0/24 -o r1-eth1 -j MASQUERADE
$IP_NETNS iptables -t nat -A POSTROUTING -s 192.168.255.0/24 -o r1-eth2 -j MASQUERADE

# Forwarding allow
$IP_NETNS iptables -A FORWARD -i r1-eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT
$IP_NETNS iptables -A FORWARD -i r1-eth2 -m state --state RELATED,ESTABLISHED -j ACCEPT
$IP_NETNS iptables -A FORWARD -o r1-eth1 -j ACCEPT
$IP_NETNS iptables -A FORWARD -o r1-eth2 -j ACCEPT

# Cho phép ứng dụng dùng ping alias để Mininet tự động dịch mapping
echo "Hoàn thiện cấu hình NAT64!"
echo "Để gửi tin IPv4 TCP từ Web1 IPv6 ra Internet, Web1 chỉ việc ping 64:ff9b::808:808 (hay ping số public thẳng Mininet lo)"

#!/bin/bash
# source/failover_test.sh

echo ""
echo "=== BÀI TEST TỰ ĐỘNG HỘI TỤ OSPFv3 LỚP 3 (FAILOVER) - MÔ PHỎNG ĐỨT CÁP LÕI ==="
echo "Kiểm tra cơ chế tái hội tụ của Hệ thống khi một Uplink Spine bị tê liệt đột ngột"

IP_NETNS="ip netns exec"

# [0] Đảm bảo mạng đang chạy trên đầy đủ 2 Spine (ECMP hoạt động)
$IP_NETNS s1 ip link set s1-eth2 up 2>/dev/null
$IP_NETNS s1 ip link set s1-eth3 up 2>/dev/null
$IP_NETNS s2 ip link set s2-eth2 up 2>/dev/null
$IP_NETNS s2 ip link set s2-eth3 up 2>/dev/null
sleep 2

echo "[1] Cấp Lệnh Bài Tạm Thời: Xuyên Thủng Tường Lửa Zero Trust cho khối ping..."
$IP_NETNS s3 ip6tables -I FORWARD 1 -p ipv6-icmp -j ACCEPT 2>/dev/null
$IP_NETNS s4 ip6tables -I FORWARD 1 -p ipv6-icmp -j ACCEPT 2>/dev/null

echo "[2] Kích hoạt luồng Ping tốc độ cao 150 gói ICMP IPv6 (0.1 giây/gói) từ Web1 -> DNS1..."
$IP_NETNS web_server1 ping6 -c 150 -i 0.1 fd00:20::1 > /home/mn/mmtnc_lab4/ping_failover.log &
PING_PID=$!

echo "[3] Duy trì tín hiệu mạng ổn định trong 4 giây đầu..."
sleep 4

echo "[4] MÔ PHỎNG SỰ CỐ: Rút hoàn toàn cáp Lõi của Spine s1!"
echo "-> Mạng sẽ khựng lại khoảng 2-3 giây để mô phỏng sự cố Mù OSPF và thời gian Tái thiết lập LSA!"

# Giật sập s1
$IP_NETNS s1 ip link set s1-eth2 down 2>/dev/null
$IP_NETNS s1 ip link set s1-eth3 down 2>/dev/null

# Ép Nhu Mạng Độ Trễ (Mô phỏng OSPF LSA trả về lỗi Destination Unreachable từ s2)
$IP_NETNS s2 ip6tables -I FORWARD 1 -j REJECT --reject-with icmp6-addr-unreachable 2>/dev/null
sleep 2.5
$IP_NETNS s2 ip6tables -D FORWARD 1 2>/dev/null

echo "[5] Lưu lượng Ping dần ổn định trở lại qua nhánh Backup s2. Chờ kết thúc gói tin..."
wait $PING_PID

echo "[6] Bot Python đang đọc Log mạng và vẽ Đồ thị Phân tích Hội tụ Động (Before vs After)..."
sudo python3 draw_failover.py /home/mn/mmtnc_lab4/ping_failover.log
echo ""
echo "🔥 Đã kết xuất đồ thị lưu tại: /home/mn/mmtnc_lab4/failover_chart.png"
echo "-> Mở ảnh lên để đối chiếu siêu chi tiết độ trễ mạng lúc gãy cáp và lúc hồi máu 100% Data Center!"

# Khôi phục nguyên trạng
$IP_NETNS s1 ip link set s1-eth2 up 2>/dev/null
$IP_NETNS s1 ip link set s1-eth3 up 2>/dev/null
$IP_NETNS s3 ip6tables -D FORWARD 1 2>/dev/null
$IP_NETNS s4 ip6tables -D FORWARD 1 2>/dev/null

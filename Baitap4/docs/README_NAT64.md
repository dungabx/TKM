# 📘 Hướng Dẫn Chi Tiết Cấu Hình Dịch Thuật NAT64 (Tayga) Trong Kiến Trúc IPv6

Tài liệu này giải phẫu cơ chế hoạt động của bộ điều phối biên dịch **NAT64** nằm trên bộ định tuyến ranh giới (Border Router `R1`). Trong mạng IPv6-Only, NAT64 là cánh cửa duy nhất để các Server nói chuyện được với cõi mặt trời của Internet IPv4 cũ kỹ. Toàn bộ logic này xuất phát từ file `source/nat_setup.sh`.

---

## 📦 Yêu Cầu Hệ Thống
Để bộ máy biên dịch có thể hoạt động trên hạt nhân Linux/Mininet:
1. **Tayga**: `sudo apt install tayga` (Đây là phần mềm Daemon cực nhẹ chuyên chuyển đổi Header IPv6 ↔ IPv4 theo mô hình Stateless NAT64/Stateful NAT64).
2. **Iptables**: (Sử dụng hệ tường lửa truyền thống IPv4 để chốt chặn và mạo danh IP Public).
3. **Môi trường Namespace**: Mọi mã lệnh tác động tới NAT64 phải được bao bọc bởi tiền tố `ip netns exec r1` để nó áp dụng đúng vào Não của Border Router R1, không đụng tới máy chủ vật lý thật ngoài đời.

---

## 🧩 Khối Mã Nguồn Hoàn Chỉnh Cấu Hình NAT64
Dưới đây là **toàn cảnh khối code thực thi NAT64** được gom gọn từ script Shell. Chúng ta sẽ cùng nhìn tổng thể hệ lưu chuyển của nó.

```bash
    # [PHẦN 1] Dọn Rác & Chuẩn bị Cấu Hình File Tayga.conf
    IP_NETNS="ip netns exec r1"
    $IP_NETNS killall tayga 2>/dev/null
    $IP_NETNS ip link del nat64 2>/dev/null
    $IP_NETNS iptables -t nat -F POSTROUTING 2>/dev/null
    
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
    ... (Map IPv4 nội bộ ảo <-> IPv6 Server thật)
    EOF

    # [PHẦN 2] Kích Hoạt "Giao Diện Mạng Ảo" (TUN Device)
    $IP_NETNS tayga -c /tmp/r1_tayga/tayga.conf --mktun
    $IP_NETNS ip link set nat64 up

    # Bật Daemon chạy nền cho Tayga rình rập và nhặt gói tin
    $IP_NETNS tayga -c /tmp/r1_tayga/tayga.conf
    sleep 1

    # [PHẦN 3] Nạp Bộ Định Tuyến Ép Chảy Gói Tin Vào Hầm NAT64
    $IP_NETNS ip addr add 192.168.255.1 dev nat64
    $IP_NETNS ip -6 addr add 2001:db8:1::1 dev nat64
    $IP_NETNS ip route add 192.168.255.0/24 dev nat64
    $IP_NETNS ip -6 route add 64:ff9b::/96 dev nat64

    # [PHẦN 4] Chuyển Hóa Gói Tin Ảo Thành IP PUBLIC Bằng Kỹ Thuật SNAT-MASQUERADE
    $IP_NETNS iptables -t nat -A POSTROUTING -s 192.168.255.0/24 -o r1-eth1 -j MASQUERADE
    $IP_NETNS iptables -t nat -A POSTROUTING -s 192.168.255.0/24 -o r1-eth2 -j MASQUERADE
```

---

## 🔍 Giải Phẫu Chi Tiết Mã Nguồn

Quá trình dịch gói mạng từ hệ IP dài 128-bit (IPv6) sang IP ngắn 32-bit (IPv4) không đơn giản là gọt bớt chữ số. Cần cả một hệ sinh thái biến đổi phức tạp trải qua **Lớp Ảo Hóa IP ↔ Masked IP ↔ Public IP** như trên đoạn mã mô tả.

### 1. File Quy Ước Tayga (Cái Não Của Dịch Thuật)
Lệnh `cat <<EOF > tayga.conf` sẽ tạo ra bảng tham chiếu luật trong thư mục tạm:
- **`prefix 64:ff9b::/96`**: Tiền tố siêu kinh điển (Well-Known Prefix) cho chuẩn NAT64 Toàn cầu (RFC 6052). Khi Server IPv6 gõ lệnh ping tới Internet IPv4 (ví dụ tới Google `8.8.8.8`), Hệ điều hành chặn gói lại và ghép nó với tiền tố ảo hóa thành: `64:ff9b::8.8.8.8` (hay viết chuẩn hex là `64:ff9b::808:808`). 
- **`dynamic-pool 192.168.255.128/25`**: Một ao chứa "IP Mồi" IPv4 của nội bộ. Tayga sau khi bóc lớp vỏ IPv6 của gói tin ra xong, nó thấy máy chủ gửi tên là Web Server (Gốc IPv6), nó sẽ lấy tạm một cái IP Mồi trong dải `192.168` này đắp vào làm IP Chữ Ký Nguồn (Source IPv4) mới cho gói tin.
- **`map [ip ảo] [ip gốc]`**: Tính năng Tĩnh Mạch (Static NAT64) cho phép Internet IPv4 ngoài đời ping thẳng xuyên vào trong IPv6. Gói tin đi từ ngoài vào sẽ nhắm tới tên miển ảo `192.168.1.11`, và Tayga sẽ lột sạch, chuyển mặt nạ IP Đích biến ngược về `fd00:10::1` (Máy Web server thật).

### 2. Kích Pháo Lên Không Trung (MKTUN)
Sự đặc biệt của Tayga là nó không chạy trên phần cứng mà chạy ở User-Space. Do đó nó cần 1 cái ống TUN ảo (`--mktun`). Máy chủ gõ `ip link set nat64 up` sẽ dựng lên cái vách nối mỏng dính làm trung gian giữa hệ IPv4 của eth ngoài, và hệ IPv6 của vNIC trong lõi.

### 3. Điều Hướng Bắt Gói (IP Route dev nat64)
Sự tồn tại của Interface `nat64` trên R1 không có ý nghĩa nếu R1 không ném tin vào đó. 
- Dòng `ip -6 route add 64:ff9b::/96 dev nat64` chính là cái Rây Lọc! Bất cứ gói IPv6 nào lọt tới biên giới R1 mà có cái đầu gắn chữ `64:ff9b::`, Linux tự động đơm gói này ném tuột vào mồm miệng đang há của đường hầm `nat64`. 
> Lúc này, phần mềm Tayga đứng đợi sẵn ở đáy Hầm, thực thi xé giấy, biên dịch mã, đắp mác `192.168.x.x` và ném trả gói IPv4 lại vào không gian OS để đi tiếp. 

*(💡 Lưu ý: Hãy kết hợp OSPFv3 `default-information originate` ở README OSPF để Server biết quăng gói `64:ff9b::` này về R1 ngay từ đầu nhé!)*

### 4. Đột Xác Thành Khổng Lồ (IPTABLES MASQUERADE)
Khi gói tin đi ra khỏi mồm đường hầm Tayga `nat64`, nó mang cái thẻ tên IPv4 `192.168.255.11` để sống trong thế giới IPv4.
Nhưng `192.168` là IP Private (dành cho LAN trong nhà riêng), ra ngoài Internet 8.8.8.8 nó tát cho sưng mặt vì Cấm Đi!
Để gói này ra được Internet thật, chúng ta dùng Cửa Khẩu Lửa:
```bash
iptables -t nat -A POSTROUTING -s 192.168.255.0/24 -o r1-eth1 -j MASQUERADE
```
- Ngay khi gói `192.168.x.x` chạm chân lên đường viền chót `r1-eth1` (Port vật lý cắm ra Internet), ngọn lửa `MASQUERADE` sẽ thiêu rụi cái nhãn cũ, mạo danh hoàn toàn IP Source của nó thành chính IP thật của cánh cổng `r1-eth1` (tức `203.162.1.254`). Nhờ chiêu thay hình đổi dạng (Network Address Translation thứ cấp - PAT) này, Gói tin của Server IPv6 mới hoàn hảo bước đi hiên ngang giữa đường phố IPv4 quốc tế!

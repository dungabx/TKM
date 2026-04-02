# 📘 Hướng Dẫn Chi Tiết Cấu Hình OSPFv3 Trong Kiến Trúc Spine-Leaf IPv6

Tài liệu này tập trung giải phẫu chuyên sâu vào logic phân phối và nạp cấu hình định tuyến động OSPFv3 (thuần IPv6) được trích xuất từ tệp `topology.py`.

---

## 📦 Yêu Cầu Hệ Thống & Thư Viện Cần Thiết
Để chạy kịch bản tự động hóa OSPFv3 bằng Python trên Mininet, hệ thống Ubuntu của bạn yêu cầu:
1. **Mininet**: `sudo apt install mininet` (Dựng Topo ảo hóa).
2. **FRRouting (FRR)**: `sudo apt install frr frr-pythontools` (Động cơ Routing thay thế Quagga cũ, cung cấp 2 tiến trình cốt lõi là `zebra` và `ospf6d`).
3. **Netcat**: `sudo apt install netcat-openbsd` (Quyền năng TCP nội soi thẳng cấu hình vào đầu FRRouting).
4. **Hạt nhân Linux Kernel 4.12+**: Mở tính năng `forwarding` và L4 Hash ECMP chia tải.

---

## 🧩 Khối Mã Nguồn Hoàn Chỉnh Cấu Hình OSPFv3
Dưới đây là **toàn cảnh khối code thực thi OSPFv3** được gom gọn lại thành một mảng duy nhất từ trong ruột `topology.py`. Chúng ta sẽ cùng nhìn tổng thể trước khi mổ xẻ nó.

```python
    info('*** Cấu hình OSPFv3 (ospf6d) cho định tuyến mạng IPv6...\n')
    
    # [PHẦN 1] Định nghĩa hàm nạp cấu hình tự động (Bơm qua TCP)
    def config_ospf6_via_tcp(node, rid, infts, r_extra=""):
        # 1.1: Đánh thức giao thức OSPFv3 và thiết lập chữ ký (Router ID)
        cmds = f"enable\nconf t\nrouter ospf6\nospf6 router-id {rid}\nexit\n"
        
        # 1.2: Quét tất cả các cổng vật lý (interfaces), cắm thẳng vào Vùng xương sống 0
        for i in infts:
            cmds += f"interface {i}\nipv6 ospf6 area 0\nexit\n" 
            
        # 1.3: Cấy ghép cấu hình đặc nhiệm (Bơm tuyến phụ hoặc Lệnh ngoại lai)
        if r_extra:
            cmds += f"router ospf6\n{r_extra}\nexit\n"
            
        # 1.4: Lưu cấu hình mảng vty
        cmds += "end\nwr\nexit\n"
        
        # 1.5: Thổi toàn bộ khối lệnh trên qua khe cửa TCP Port 2606 dùng Netcat
        node.cmd(f'echo -e "{cmds}" | nc -w 1 127.0.0.1 2606 | tr -cd \'\\11\\12\\15\\40-\\176\'')

    # [PHẦN 2] Phân bổ cấu hình xuống Tầng Core và Spine (Đường trục Tốc độ cao)
    config_ospf6_via_tcp(s7, '7.7.7.7', ['s7-eth0', 's7-eth1', 's7-eth2', 'lo'])
    config_ospf6_via_tcp(s1, '1.1.1.1', ['s1-eth0', 's1-eth1', 's1-eth2', 's1-eth3', 'lo'])
    config_ospf6_via_tcp(s2, '2.2.2.2', ['s2-eth0', 's2-eth1', 's2-eth2', 's2-eth3', 'lo'])
    
    # [PHẦN 3] Phân bổ cấu hình xuống Tầng Leaf (Bộ mặt đón Server máy trạm)
    # Ghi chú: Chân 'br0' chính là cụm Bridge L2 Ảo đã nhét sẵn IP Gateway đi ra ngoài.
    config_ospf6_via_tcp(s3, '3.3.3.3', ['s3-eth0', 's3-eth1', 'br0', 'lo'])
    config_ospf6_via_tcp(s4, '4.4.4.4', ['s4-eth0', 's4-eth1', 'br0', 'lo'])
    config_ospf6_via_tcp(s5, '5.5.5.5', ['s5-eth0', 's5-eth1', 'br0', 'lo'])
    
    # [PHẦN 4] Trạm Biên NAT64 (R1) - Quán quân nhồi tuyến mặc định (Default Route)
    config_ospf6_via_tcp(r1, '100.100.100.100', ['r1-eth0', 'lo'], "redistribute static\nredistribute kernel\ndefault-information originate always")
```

---

## 🔍 Giải Phẫu Chi Tiết Mã Nguồn

Thay vì sử dụng phần mềm hỗ trợ hoặc gõ thủ công từng dòng lệnh (VTY Terminal) như truyền thống, đoạn Python trên vận hành theo kiểu **Controller nội soi (Distributed Configuration)** thông qua 4 phân đoạn cấu trúc.

### 1. Hàm Bơm Config Xuyên Mạng Cốt Lõi (`config_ospf6_via_tcp`)
Đây là khối tim của đoạn kịch bản. Nó gom một tập tin văn bản giả lập và sử dụng chương trình Terminal ẩn để cài vào não `OSPF6D`.

- **Câu lệnh `router ospf6` & `ospf6 router-id {rid}`**:
  Tuy mạng của chúng ta đang chạy 100% bằng **IPv6** siêu dài, nhưng tiêu chuẩn kỹ thuật quốc tế của OSPFv3 bắt buộc nhãn dán danh tính (Router-ID) **vẫn phải duy trì ở chuẩn nén IPv4 (32-bit)**. Thế nên trong các khối lệnh dưới, S1 được dán mác `1.1.1.1`, S3 được dán mác `3.3.3.3` nhằm đáp ứng điều kiện tiên quyết của tiến trình.
- **Vòng lặp `interface {i}` -> `ipv6 ospf6 area 0`**:
  OSPFv3 không kích hoạt trên Subnet IP! Thay vào đó, nó kích hoạt **thẳng rẽ trên cổng dây vật lý (Interface)**. Khi ta nạp dây lệnh vào, Router sẽ lấy mã Link-Local của mỗi interface (mã FE80::) để đan nối và trao đổi LSA với nhau. Mọi đường P2P và Bridge `br0` đều được thả vào lòng Backbone `Area 0`.
- **Cú chót `nc -w 1 127.0.0.1 2606`**:
  Nghệ thuật Hacking nội bộ! Cổng `2606` chính là cửa hầu ngầm ẩn của OSPF6D Daemon do FRR tạo ra. Bằng cách nối Netcat `nc` đẩy dòng text, ta không cần ai ngồi gõ lệnh pass mà Router OSPF vẫn nhận và sinh cấu hình đầy đủ y hệt cắm console Cisco thật.

### 2. Tầng Backbone Core & Spine ([PHẦN 2])
Gọi lệnh đổ cấu hình cho thiết bị mạnh nhất (`S7`, `S1`, `S2`).
Chúng được lồng toàn bộ các cổng cáp chéo `sX-ethX` dọc vào hệ thống, cộng hưởng với ngõ `lo` (Loopback giả tưởng). Ngõ `lo` mang IP `fc00:1111::X` sẽ được OSPF quảng bá bay lơ lửng khắp hội đồng mạng để chuẩn bị làm IP VTEP cho trò ảo thuật Tunnel VXLAN đằng sau.

### 3. Tầng Đón Khách Leaf ([PHẦN 3])
Leaf (`S3`, `S4`, `S5`) chịu trách nhiệm nối máy Server. 
Ở đây, thay vì nạp `eth2` hay `eth3`, ta nạp cái ngõ ảo `br0`. Vì sao? Vì máy chủ Web cắm vào dây `eth2` không tự biết nói chuyện trực tiếp OSPF. Mọi cấu hình phải tập trung tại cổng Gateway `br0`, khi OSPF vươn ra khỏi `br0`, nó sẽ thu gom toàn bộ dải mạng `/64` của Leaf để báo cho mọi người biết "Cụm Web/DNS hiện đã lên sóng rẽ vào nhà tôi".

### 4. Vị Vua Đặc Trị Route Biên, R1 ([PHẦN 4])
Đoạn Code uy quyền nhất lồng biến `r_extra` rơi vào trạm `R1` (Kẻ đứng gác cổng dịch thuật NAT64 với Internet):
```python
redistribute static
redistribute kernel
default-information originate always
```
- **`redistribute static/kernel`**: Bốc tất cả các lộ tuyến cấu hình tĩnh nằm dưới váng Kernel (được bộ phận Tayga NAT64 đính lên hệ thống) quăng ngược vào cái miệng lu loa của OSPF để OSPF mách lẻo lại cho Spine hay.
- **`default-information originate always`**: Tuyên bố hùng hồn của vị Vua gác cửa với hội nghị OSPF: *"Nếu có gói tin IPv6 nào mà chúng mày không biết đích đến (Ví dụ: Các Server mồ côi gõ lệnh ping `google.com` hoặc `64:ff9b::808:808`), hãy quăng tất cả vào xe rác tuyến `::/0` trỏ về cho tao!"*. Nhờ sự nhồi nhét cực gắt này, Data Center mới thông suốt mạch máu ra được Internet IPv4.

---

> [!TIP]
> **Phép Bổ Trợ Kernel Song Hành (Bắt buộc):**
> Nhớ rằng OSPFv3 ở dạng Code gốc ở trên sẽ chết kẹt nếu bạn vô tình quyên ném lệnh cấu hình Kernel Linux lúc `FRRouter` khởi động. Hãy bảo đảm biến chuyển tiếp (`net.ipv6.conf.all.forwarding=1`), ép sung bỏ qua DAD Delay (`net.ipv6.conf.all.accept_dad=0`) và Băm cổng L4 ECMP (`net.ipv6.fib_multipath_hash_policy=1`) đã được kích hoạt đủ nhé!

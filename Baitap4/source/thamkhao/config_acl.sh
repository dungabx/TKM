#!/bin/bash
# ============================================================
# Lab3 Network Hardening - Extended ACLs (iptables)
# ============================================================
# File nay duoc goi tu trong Mininet CLI:
#   mininet> sh sudo bash configure_acls.sh
#
# Hoac goi tu topology.py khi go lenh: acl
# ============================================================

echo "=== Deploying Extended ACLs ==="

# ----------------------------------------------------------
# ACL 110: IoT Isolation (R6, interface r6-eth2, direction IN)
# Muc tieu: Chan moi traffic tu IoT -> Management, Staff, DMZ
# Chi cho phep: IoT -> Syslog (UDP 514) va ICMP echo
# ----------------------------------------------------------
echo "  ACL 110: IoT Isolation on R6..."

# Xoa rules cu
ip netns exec r6 iptables -F FORWARD 2>/dev/null

# Cho phep return traffic (stateful)
ip netns exec r6 iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# 1. PERMIT: IoT -> Syslog Server (172.16.10.200:514/UDP)
#    Ly do: IoT can gui logs de monitoring
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 172.16.10.200 -p udp --dport 514 -j ACCEPT

# 2. DENY zones TRUOC ICMP (vi ICMP match 0.0.0.0/0, first-match-wins!)

# 3. DENY: IoT -> Management Zone (10.1.2.0/24) - LOG
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.1.2.0/24 -j LOG --log-prefix "ACL110-DENY-MGMT "
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.1.2.0/24 -j DROP

# 4. DENY: IoT -> Staff Zone (10.1.1.0/24) - LOG
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.1.1.0/24 -j LOG --log-prefix "ACL110-DENY-STAFF "
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.1.1.0/24 -j DROP

# 5. DENY: IoT -> DMZ (tru Syslog da permit) - LOG
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 172.16.10.0/24 -j LOG --log-prefix "ACL110-DENY-DMZ "
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 172.16.10.0/24 -j DROP

# 6. DENY: IoT -> any inside (10.0.0.0/8) - LOG
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.0.0.0/8 -j LOG --log-prefix "ACL110-DENY-ALL "
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -d 10.0.0.0/8 -j DROP

# 7. PERMIT: IoT -> ICMP echo CUOI CUNG (chi con match Internet)
ip netns exec r6 iptables -A FORWARD -i r6-eth2 -s 192.168.100.0/24 \
    -p icmp --icmp-type echo-request -j ACCEPT


# ----------------------------------------------------------
# ACL 120: DMZ Security (R5, interface r5-eth2, direction IN)
# Muc tieu: Cho phep Internet truy cap DMZ services,
#           Chan DMZ truy cap Inside (chong lateral movement)
# ----------------------------------------------------------
echo "  ACL 120: DMZ Security on R5..."

ip netns exec r5 iptables -F FORWARD 2>/dev/null
ip netns exec r5 iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# 1. PERMIT: Any -> Web Server HTTP (port 80)
ip netns exec r5 iptables -A FORWARD -d 172.16.10.100 -p tcp --dport 80 -j ACCEPT

# 2. PERMIT: Any -> Web Server HTTPS (port 443)
ip netns exec r5 iptables -A FORWARD -d 172.16.10.100 -p tcp --dport 443 -j ACCEPT

# 3. PERMIT: Any -> Email Server SMTP (port 25)
ip netns exec r5 iptables -A FORWARD -d 172.16.10.101 -p tcp --dport 25 -j ACCEPT

# 4. PERMIT: Staff -> DMZ HTTPS (internal portal)
ip netns exec r5 iptables -A FORWARD -s 10.1.1.0/24 -d 172.16.10.0/24 \
    -p tcp --dport 443 -j ACCEPT

# 5. PERMIT: Any -> Syslog Server (UDP 514)
ip netns exec r5 iptables -A FORWARD -d 172.16.10.200 -p udp --dport 514 -j ACCEPT

# 6. DENY: DMZ -> Inside (10.0.0.0/8) - TRUOC ICMP!
ip netns exec r5 iptables -A FORWARD -i r5-eth2 -s 172.16.10.0/24 \
    -d 10.0.0.0/8 -j LOG --log-prefix "ACL120-DENY-INSIDE "
ip netns exec r5 iptables -A FORWARD -i r5-eth2 -s 172.16.10.0/24 \
    -d 10.0.0.0/8 -j DROP

# 7. PERMIT: ICMP (troubleshooting) - CUOI CUNG
ip netns exec r5 iptables -A FORWARD -p icmp -j ACCEPT


# ----------------------------------------------------------
# ACL 130: Staff Policy (R4, interface r4-eth1, direction IN)
# Muc tieu: Staff chi lam viec, khong truy cap zones nhay cam
# Nguyen tac: Least Privilege
# ----------------------------------------------------------
echo "  ACL 130: Staff Policy on R4..."

ip netns exec r4 iptables -F FORWARD 2>/dev/null
ip netns exec r4 iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# 1. PERMIT: Staff -> DMZ HTTPS (443) - internal portal
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -d 172.16.10.0/24 -p tcp --dport 443 -j ACCEPT

# 2. PERMIT: Staff -> DNS (any:53/UDP) - domain resolution
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -p udp --dport 53 -j ACCEPT

# 3. DENY: Staff -> Management - TRUOC ICMP!
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -d 10.1.2.0/24 -j LOG --log-prefix "ACL130-DENY-MGMT "
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -d 10.1.2.0/24 -j DROP

# 4. DENY: Staff -> IoT - TRUOC ICMP!
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -d 192.168.100.0/24 -j LOG --log-prefix "ACL130-DENY-IOT "
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -d 192.168.100.0/24 -j DROP

# 5. PERMIT: Staff -> ICMP echo - CUOI CUNG (Mgmt/IoT da bi DROP)
ip netns exec r4 iptables -A FORWARD -i r4-eth1 -s 10.1.1.0/24 \
    -p icmp --icmp-type echo-request -j ACCEPT

# Management -> anywhere: PERMIT (admin full access)
ip netns exec r4 iptables -A FORWARD -i r4-eth2 -s 10.1.2.0/24 -j ACCEPT


# ----------------------------------------------------------
# ACL 140: SSH Access Control (All routers, INPUT chain)
# Muc tieu: Chi Admin PC (10.1.2.50) duoc SSH vao routers
# ----------------------------------------------------------
echo "  ACL 140: SSH Access Control on all routers..."

for router in r1 r2 r3 r4 r5 r6; do
    # PERMIT: Admin PC -> SSH
    ip netns exec $router iptables -A INPUT -s 10.1.2.50 -p tcp --dport 22 -j ACCEPT
    # DENY: Any -> SSH - LOG
    ip netns exec $router iptables -A INPUT -p tcp --dport 22 \
        -j LOG --log-prefix "ACL140-DENY-SSH "
    ip netns exec $router iptables -A INPUT -p tcp --dport 22 -j DROP
done

echo "=== ACLs deployed successfully ==="
echo ""
echo "Verify commands:"
echo "  r6 iptables -L FORWARD -n -v   # ACL 110 (IoT)"
echo "  r5 iptables -L FORWARD -n -v   # ACL 120 (DMZ)"
echo "  r4 iptables -L FORWARD -n -v   # ACL 130 (Staff)"
echo "  r1 iptables -L INPUT -n -v     # ACL 140 (SSH)"
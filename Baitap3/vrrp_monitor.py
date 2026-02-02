#!/usr/bin/env python3
"""
VRRP Failover Monitor
Quản lý Virtual IPs (.254) và external host routing
"""

import time
import sys

VRRP_VIPS = [
    ('192.168.10.254/24', '10'),
    ('192.168.20.254/24', '20'),
    ('192.168.30.254/24', '30'),
    ('192.168.99.254/24', '99')
]

def check_r1_alive(net):
    """Kiểm tra R1 còn hoạt động không"""
    try:
        r1 = net.get('r1')
        # Check cả 2 trunk interfaces
        result0 = r1.cmd('ip link show r1-eth0')
        result1 = r1.cmd('ip link show r1-eth1')
        
        # Nếu cả 2 interfaces đều DOWN thì R1 coi như fail
        if 'UP' not in result0 and 'UP' not in result1:
            return False
        
        # Nếu ít nhất 1 interface UP thì R1 còn sống
        if 'state UP' in result0 or 'state UP' in result1:
            return True
        
        return False
    except:
        return False

def add_vips_to_r2(net):
    """Thêm Virtual IPs vào R2 và update external routes"""
    print("\n[VRRP] *** R1 DOWN DETECTED! Promoting R2 to MASTER... ***")
    r2 = net.get('r2')
    internet = net.get('internet')
    serverq7 = net.get('serverq7')
    
    # Add Virtual IPs to R2
    for vip, vlan_id in VRRP_VIPS:
        try:
            r2.cmd(f'ip addr add {vip} dev r2-eth0.{vlan_id}')
            print(f"[VRRP] + Added {vip} to R2")
        except:
            pass
    
    # Update external hosts' routes to point to R2 via eth1
    try:
        internet.cmd('ip route del default')
        internet.cmd('ip route add default via 8.8.8.2 dev internet-eth1')
        print("[VRRP] + Updated Internet default route to R2 (8.8.8.2 via eth1)")
    except:
        pass
    
    try:
        serverq7.cmd('ip route del default')
        serverq7.cmd('ip route add default via 1.1.1.253 dev serverq7-eth1')
        print("[VRRP] + Updated ServerQ7 default route to R2 (1.1.1.253 via eth1)")
    except:
        pass
    
    print("[VRRP] *** R2 is now ACTIVE (MASTER) ***")
    print("[VRRP] All routes updated successfully!\n")

def remove_vips_from_r2(net):
    """Xóa Virtual IPs khỏi R2 và restore external routes về R1"""
    print("\n[VRRP] *** R1 RECOVERED! Demoting R2 to BACKUP... ***")
    r2 = net.get('r2')
    internet = net.get('internet')
    serverq7 = net.get('serverq7')
    
    # Remove Virtual IPs from R2
    for vip, vlan_id in VRRP_VIPS:
        try:
            r2.cmd(f'ip addr del {vip} dev r2-eth0.{vlan_id}')
            print(f"[VRRP] - Removed {vip} from R2")
        except:
            pass
    
    # Restore external hosts' routes to point back to R1 via eth0
    try:
        internet.cmd('ip route del default')
        internet.cmd('ip route add default via 8.8.8.1 dev internet-eth0')
        print("[VRRP] + Restored Internet default route to R1 (8.8.8.1 via eth0)")
    except:
        pass
    
    try:
        serverq7.cmd('ip route del default')
        serverq7.cmd('ip route add default via 1.1.1.254 dev serverq7-eth0')
        print("[VRRP] + Restored ServerQ7 default route to R1 (1.1.1.254 via eth0)")
    except:
        pass
    
    print("[VRRP] *** R2 is now BACKUP ***")
    print("[VRRP] All routes restored to R1!\n")

def monitor_vrrp(net):
    """Monitor VRRP và tự động failover Virtual IPs + External Routes"""
    print("\n[VRRP] VRRP Failover Monitor started")
    print("[VRRP] Monitoring R1 health (checking r1-eth0 and r1-eth1)...")
    print("[VRRP] Will auto-update:")
    print("[VRRP]   • Virtual IPs (.254) on VLANs")
    print("[VRRP]   • Internet and ServerQ7 default routes")
    print("[VRRP] Press Ctrl+D in CLI to stop\n")
    
    r2_is_active = False
    
    while True:
        try:
            r1_alive = check_r1_alive(net)
            
            if not r1_alive and not r2_is_active:
                # R1 down và R2 chưa active -> failover
                add_vips_to_r2(net)
                r2_is_active = True
            
            elif r1_alive and r2_is_active:
                # R1 up lại và R2 đang active -> failback
                remove_vips_from_r2(net)
                r2_is_active = False
            
            time.sleep(2)  # Check every 2 seconds
        
        except KeyboardInterrupt:
            print("\n[VRRP] Monitor stopped")
            break
        except:
            # Network stopped, exit gracefully
            break

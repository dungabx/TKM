#!/usr/bin/env python3
"""
Script vẽ sơ đồ hạ tầng Spine-Leaf tinh chỉnh theo logic_network.png.
Chạy: python3 draw_topology.py
Kết quả: Xuất file topology_v3.png
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

def draw_topology(save_path='topology_v3.png'):
    G = nx.Graph()

    # Định nghĩa các node và thuộc tính
    nodes = {
        's7': {'label': 's7\n(Border Leaf)', 'zone': 'border', 'shape': 's'},
        'r1': {'label': 'r1\n(Router NAT64)', 'zone': 'router', 'shape': 'o'},
        
        's1': {'label': 's1\n(Spine)', 'zone': 'spine', 'shape': 's'},
        's2': {'label': 's2\n(Spine)', 'zone': 'spine', 'shape': 's'},
        
        's3': {'label': 's3\n(Leaf)', 'zone': 'leaf', 'shape': 's'},
        's4': {'label': 's4\n(Leaf)', 'zone': 'leaf', 'shape': 's'},
        's5': {'label': 's5\n(Leaf)', 'zone': 'leaf', 'shape': 's'},
        
        'web_server1': {'label': 'web_server1\n(IPv6)', 'zone': 'web', 'shape': 'c'},
        'web_server2': {'label': 'web_server2\n(IPv6)', 'zone': 'web', 'shape': 'c'},
        
        'dns_server1': {'label': 'dns_server1\n(IPv6)', 'zone': 'dns', 'shape': 'c'},
        'dns_server2': {'label': 'dns_server2\n(IPv6)', 'zone': 'dns', 'shape': 'c'},
        
        'db_server1': {'label': 'db_server1\n(IPv6)', 'zone': 'db', 'shape': 'c'},
        'db_server2': {'label': 'db_server2\n(IPv6)', 'zone': 'db', 'shape': 'c'},
        
        'serverhcm': {'label': 'serverhcm\n(IPv4)', 'zone': 'wan', 'shape': 'c'},
        'internet': {'label': 'internet\n(IPv4)', 'zone': 'wan', 'shape': 'c'},
    }
    
    for n, d in nodes.items():
        G.add_node(n, **d)

    edges = [
        ('s7', 's1'), ('s7', 's2'), ('s7', 'r1'),
        ('s1', 's3'), ('s1', 's4'), ('s1', 's5'),
        ('s2', 's3'), ('s2', 's4'), ('s2', 's5'),
        ('s3', 'web_server1'), ('s3', 'web_server2'),
        ('s4', 'dns_server1'), ('s4', 'dns_server2'),
        ('s5', 'db_server1'), ('s5', 'db_server2'),
        ('r1', 'serverhcm'), ('r1', 'internet')
    ]
    
    for s, d in edges:
        G.add_edge(s, d)

    COLORS = {
        'border': '#F39C12',  
        'spine': '#D9534F',   
        'leaf': '#2ECC71',    
        'router': '#9B59B6',  
        'web': '#3498DB',     
        'dns': '#9B59B6',     
        'db': '#1ABC9C',    
        'wan': '#E74C3C',     
    }

    pos = {
        's7': (1, 6),
        's1': (-2, 4), 's2': (1, 4),
        's3': (-4, 2), 's4': (-1, 2), 's5': (2, 2),
        'web_server1': (-5, 0), 'web_server2': (-3, 0),
        'dns_server1': (-2, 0), 'dns_server2': (0, 0),
        'db_server1': (1, 0), 'db_server2': (3, 0),
        'r1': (4, 4),
        'serverhcm': (3.5, 2), 'internet': (5.5, 2),
    }

    fig, ax = plt.subplots(figsize=(15, 10))
    fig.patch.set_facecolor('#1A1A2E')
    ax.set_facecolor('#1A1A2E')

    squares = [n for n in G.nodes if nodes[n]['shape'] == 's']
    circles = [n for n in G.nodes if nodes[n]['shape'] in ['o', 'c']]

    nx.draw_networkx_nodes(G, pos, nodelist=squares,
        node_color=[COLORS[nodes[n]['zone']] for n in squares],
        node_size=3200, node_shape='s', ax=ax, linewidths=2, edgecolors='white')
        
    nx.draw_networkx_nodes(G, pos, nodelist=circles,
        node_color=[COLORS[nodes[n]['zone']] for n in circles],
        node_size=2500, node_shape='o', ax=ax, linewidths=1.5, edgecolors='white')

    nx.draw_networkx_edges(G, pos, edge_color='#BDC3C7', width=1.5, ax=ax)

    labels = {n: nodes[n]['label'] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=8, font_color='black', font_weight='bold', ax=ax)
              
    ax.set_title("Mô hình mạng SPINE-LEAF IPv6 (NAT64 tới IPv4) - logic_network",
                 color='white', fontsize=18, fontweight='bold', pad=20)
    ax.axis('off')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[SUCCESS] Đã lưu đồ thị mới: {save_path}")

if __name__ == '__main__':
    draw_topology()

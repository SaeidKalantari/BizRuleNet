"""
PyTorch Geometric Graph Loader

This script loads heterogeneous graph data exported from the KG Builder
and converts it to PyTorch Geometric's HeteroData format.

Usage:
    python load_pyg_graph.py graph_pyg.json
    
    Or in Python:
    >>> from load_pyg_graph import load_hetero_graph
    >>> data = load_hetero_graph('graph_pyg.json')
"""

import json
import argparse
from typing import Optional

try:
    import torch
    from torch_geometric.data import HeteroData
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: torch and torch_geometric not installed.")
    print("Install with: pip install torch torch_geometric")


def load_hetero_graph(json_path: str) -> Optional['HeteroData']:
    """
    Load a heterogeneous graph from JSON exported by KG Builder.
    
    Args:
        json_path: Path to the exported JSON file
        
    Returns:
        HeteroData object ready for use in PyTorch Geometric models
    """
    if not TORCH_AVAILABLE:
        raise ImportError("torch and torch_geometric are required")
    
    with open(json_path, 'r') as f:
        export = json.load(f)
    
    data = HeteroData()
    
    # Load node features for each node type
    for node_type, features in export['nodeFeatures'].items():
        data[node_type].x = torch.tensor(features, dtype=torch.float)
        
        # Store node labels as metadata
        if 'nodeLabels' in export and node_type in export['nodeLabels']:
            data[node_type].labels = export['nodeLabels'][node_type]
    
    # Load edge indices for each (src_type, rel_type, dst_type) triplet
    for triplet_str, indices in export['edgeIndices'].items():
        src_type, rel_type, dst_type = triplet_str.split(',')
        data[src_type, rel_type, dst_type].edge_index = torch.tensor(
            indices, dtype=torch.long
        )
        
        # Load edge features if available
        if 'edgeFeatures' in export and triplet_str in export['edgeFeatures']:
            edge_feats = export['edgeFeatures'][triplet_str]
            if edge_feats and len(edge_feats) > 0 and len(edge_feats[0]) > 0:
                data[src_type, rel_type, dst_type].edge_attr = torch.tensor(
                    edge_feats, dtype=torch.float
                )
    
    return data


def print_graph_info(data: 'HeteroData') -> None:
    """Print information about the loaded heterogeneous graph."""
    print("\n" + "=" * 50)
    print("Heterogeneous Graph Summary")
    print("=" * 50)
    
    print("\nNode Types:")
    for node_type in data.node_types:
        num_nodes = data[node_type].x.shape[0]
        num_features = data[node_type].x.shape[1]
        print(f"  - {node_type}: {num_nodes} nodes, {num_features} features")
        if hasattr(data[node_type], 'labels'):
            print(f"    Labels: {data[node_type].labels}")
    
    print("\nEdge Types:")
    for edge_type in data.edge_types:
        src, rel, dst = edge_type
        num_edges = data[edge_type].edge_index.shape[1]
        edge_info = f"  - ({src}) --[{rel}]--> ({dst}): {num_edges} edges"
        if hasattr(data[edge_type], 'edge_attr'):
            num_features = data[edge_type].edge_attr.shape[1]
            edge_info += f", {num_features} features"
        print(edge_info)
    
    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description='Load heterogeneous graph from KG Builder export'
    )
    parser.add_argument(
        'json_file', 
        help='Path to the exported JSON file'
    )
    parser.add_argument(
        '--save-pt', 
        help='Save as .pt file for faster loading',
        metavar='OUTPUT_PATH'
    )
    
    args = parser.parse_args()
    
    print(f"Loading graph from: {args.json_file}")
    data = load_hetero_graph(args.json_file)
    print_graph_info(data)
    
    if args.save_pt:
        torch.save(data, args.save_pt)
        print(f"\nSaved to: {args.save_pt}")
        print("Load with: data = torch.load('{}')"
              .format(args.save_pt))


if __name__ == '__main__':
    main()

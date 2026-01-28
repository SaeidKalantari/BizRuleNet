# BizRuleNet

A framework for building, managing, and querying knowledge graphs to enforce business rules in machine learning pipelines. This project integrates Neo4j graph databases with PyTorch Geometric for graph neural network (GNN) based learning and provides an MCP (Model Context Protocol) server for AI-powered natural language graph querying.

## Overview

BizRuleNet enables:
- **Knowledge Graph Management**: Load and manage graph data in Neo4j
- **GNN Integration**: Convert graphs to PyTorch Geometric's HeteroData format for heterogeneous graph neural networks
- **AI-Powered Querying**: Natural language to Cypher query conversion via MCP server
- **Business Rule Enforcement**: Use feasibility graphs and action masking in ML training pipelines

## Project Structure

```
BizRuleNet/
├── data/                           # Graph data exports and datasets
│   ├── graph_neo4j.json           # Neo4j Cypher format export
│   ├── graph_pyg.json             # PyTorch Geometric format export
│   ├── graph_pyg_wfeatures.json   # PyG export with features
│   ├── graph.pt                   # Saved PyTorch HeteroData object
│   └── *.csv                      # Raw datasets
├── mcp/                           # MCP server for AI agent integration
│   ├── mcp_server.py             # MCP server with graph query tools
│   └── mcp_agent.py              # Example agent using smolagents
├── load_neo4j_graph.py           # Load graphs into Neo4j database
├── load_pyg_graph.py             # Convert graphs to PyTorch Geometric
├── Neo4j_Cypher.ipynb            # Neo4j tutorial notebook
└── Pytorch_hetrodata.ipynb       # PyTorch Geometric HeteroData tutorial
```

## Installation

### Prerequisites

- Python 3.10+
- Neo4j Database (Desktop or Server)

### Install Dependencies

```bash
# Core dependencies
pip install neo4j torch torch_geometric

# For MCP server
pip install mcp smolagents litellm

# For notebooks
pip install pandas networkx matplotlib tqdm osmnx
```

## Usage

### 1. Loading Graphs into Neo4j

Load a graph export from RuleNet into your local Neo4j database:

```bash
# Basic usage
python load_neo4j_graph.py data/graph_neo4j.json

# With custom credentials
python load_neo4j_graph.py data/graph_neo4j.json --uri bolt://localhost:7687 --user neo4j --password yourpassword

# Clear existing data before loading
python load_neo4j_graph.py data/graph_neo4j.json --clear

# Show quick start guide
python load_neo4j_graph.py --guide
```

### 2. Converting to PyTorch Geometric Format

Convert graph exports to PyTorch Geometric's HeteroData for GNN training:

```bash
# Load and display graph info
python load_pyg_graph.py data/graph_pyg.json

# Save as .pt file for faster loading
python load_pyg_graph.py data/graph_pyg.json --save-pt data/graph.pt
```

In Python:

```python
from load_pyg_graph import load_hetero_graph

# Load heterogeneous graph
data = load_hetero_graph('data/graph_pyg.json')

# Access node features by type
paper_features = data['paper'].x
author_features = data['author'].x

# Access edges
edge_index = data['author', 'writes', 'paper'].edge_index
```

### 3. MCP Server for AI-Powered Queries

Start the MCP server to enable natural language graph queries:

```bash
cd mcp
python mcp_server.py
```

The server provides these tools:
- `get_graph_schema()` - Get node labels, relationship types, and properties
- `get_graph_stats()` - Get node and edge counts
- `sample_nodes(label)` - Sample nodes of a specific type
- `query_runner(cypher)` - Execute read-only Cypher queries

Example with smolagents:

```python
from smolagents import ToolCallingAgent, ToolCollection, LiteLLMModel
from mcp import StdioServerParameters

model = LiteLLMModel(model_id="ollama_chat/qwen2.5:14b", num_ctx=8192)

server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "mcp_server.py"],
)

with ToolCollection.from_mcp(server_parameters, trust_remote_code=True) as tools:
    agent = ToolCallingAgent(tools=[*tools.tools], model=model)
    agent.run("What are the most connected nodes in the graph?")
```

## Notebooks

### Neo4j_Cypher.ipynb

Tutorial on working with Neo4j graph databases:
- Creating nodes and relationships
- Executing Cypher queries
- Analyzing bikeshare trip data as a graph

### Pytorch_hetrodata.ipynb

Tutorial on PyTorch Geometric HeteroData:
- Creating heterogeneous graphs
- Building GNN models with `HeteroConv` and `TransformerConv`
- Node embedding and decoding
- **Action masking** for business rule enforcement in RL/ML pipelines

## Key Concepts

### Heterogeneous Graphs

BizRuleNet works with heterogeneous graphs containing multiple node and edge types:

```python
data = HeteroData()

# Different node types with their features
data['person'].x = torch.tensor([[21, 20], [31, 500]])
data['paper'].x = torch.tensor([[1.0], [2.0]])
data['institution'].x = torch.tensor([[100.0]])

# Typed relationships
data['person', 'authored', 'paper'].edge_index = torch.tensor([[0, 1], [0, 1]])
data['person', 'affiliated', 'institution'].edge_index = torch.tensor([[0], [0]])
```

### Business Rule Enforcement via Action Masking

Filter feasible actions based on graph constraints:

```python
def filter_nodes_by_feature(data, node_type, feature_index, threshold):
    """Filter nodes based on feature constraints."""
    x = data[node_type].x
    mask = x[:, feature_index] > threshold
    return mask.nonzero(as_tuple=True)[0]

def feasibility_mask(scores, feasible_indices):
    """Create mask for feasible nodes only."""
    mask = torch.zeros_like(scores, dtype=torch.bool)
    mask[feasible_indices] = True
    return mask

# Apply masking to enforce business rules
feasible_indices = filter_nodes_by_feature(data, 'person', 0, threshold=25)
mask = feasibility_mask(scores, feasible_indices)
masked_scores = scores.masked_fill(mask, -1e9)
```

## Configuration

### Neo4j Connection

Default connection settings (customize via command line or environment):

```python
uri = "bolt://localhost:7687"
username = "neo4j"
password = "password"
```

### MCP Server Configuration

Edit `mcp/mcp_server.py` to update connection settings:

```python
uri = "bolt://127.0.0.1:7687"
username = "neo4j"
password = "your_password"
```

## Sample Cypher Queries

```cypher
-- Show all nodes
MATCH (n) RETURN n

-- Show relationships
MATCH (a)-[r]->(b) RETURN a, r, b

-- Find nodes by type
MATCH (p:person) RETURN p

-- Find paths between nodes
MATCH path = (a)-[*1..3]->(b)
WHERE a.label = 'Dr. Smith'
RETURN path

-- Count nodes by type
MATCH (n) RETURN labels(n)[0] as type, count(n) as count
```

## References

- [PyTorch Geometric HeteroData](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.data.HeteroData.html)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [A Closer Look at Invalid Action Masking in Policy Gradient Algorithms](https://arxiv.org/abs/2006.14171)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## License

MIT 

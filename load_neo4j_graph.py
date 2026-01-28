#!/usr/bin/env python3
"""
Load Neo4j Graph from RuleNet Export

This script loads a graph exported from RuleNet (Neo4j Cypher format)
into a local Neo4j database.

Prerequisites:
    1. Neo4j Desktop or Neo4j Community Server running locally
       - Download: https://neo4j.com/download/
       - Default: bolt://localhost:7687
    
    2. Python neo4j driver:
       pip install neo4j

Usage:
    python load_neo4j_graph.py graph_export.json
    
    # With custom connection:
    python load_neo4j_graph.py graph_export.json --uri bolt://localhost:7687 --user neo4j --password your_password
    
    # Clear database before loading:
    python load_neo4j_graph.py graph_export.json --clear

Example:
    # Export from RuleNet, then:
    python load_neo4j_graph.py my_knowledge_graph.json --password mypassword
"""

import json
import argparse
import sys
from typing import Optional

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️  neo4j driver not installed.")
    print("   Install with: pip install neo4j")
    print()


class Neo4jLoader:
    """Load RuleNet exports into Neo4j database."""
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize connection to Neo4j.
        
        Args:
            uri: Bolt URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._verify_connection()
    
    def _verify_connection(self):
        """Verify database connection."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            print("✅ Connected to Neo4j successfully!")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            print("\nTroubleshooting:")
            print("  1. Is Neo4j running? (Check Neo4j Desktop or service)")
            print("  2. Is the bolt port correct? (default: 7687)")
            print("  3. Are credentials correct?")
            sys.exit(1)
    
    def close(self):
        """Close the database connection."""
        self.driver.close()
    
    def clear_database(self):
        """Remove all nodes and relationships from the database."""
        with self.driver.session() as session:
            # Delete all relationships first, then nodes
            session.run("MATCH (n) DETACH DELETE n")
            print("🗑️  Cleared all existing data from database")
    
    def get_stats(self) -> dict:
        """Get current database statistics."""
        with self.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # Get node labels
            labels_result = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
            labels = labels_result.single()["labels"]
            
            # Get relationship types
            rel_result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types")
            rel_types = rel_result.single()["types"]
            
            return {
                "nodes": node_count,
                "relationships": rel_count,
                "labels": labels,
                "relationship_types": rel_types
            }
    
    def load_from_json(self, json_path: str) -> dict:
        """
        Load graph from RuleNet Neo4j export JSON.
        
        Args:
            json_path: Path to the exported JSON file
            
        Returns:
            Dictionary with load statistics
        """
        with open(json_path, 'r') as f:
            export = json.load(f)
        
        nodes = export.get('nodes', [])
        relationships = export.get('relationships', [])
        
        print(f"\n📊 Export contains: {len(nodes)} nodes, {len(relationships)} relationships")
        
        nodes_created = 0
        rels_created = 0
        
        with self.driver.session() as session:
            # Create nodes
            print("\n📦 Creating nodes...")
            for node in nodes:
                labels = ':'.join(node.get('labels', ['Node']))
                props = node.get('properties', {})
                node_id = node.get('id')
                
                # Add internal ID for relationship mapping
                props['_rulenet_id'] = node_id
                
                # Build Cypher query
                props_str = ', '.join([f"{k}: ${k}" for k in props.keys()])
                query = f"CREATE (n:{labels} {{{props_str}}})"
                
                try:
                    session.run(query, **props)
                    nodes_created += 1
                    print(f"  ✓ Created {labels}: {props.get('label', node_id)}")
                except Exception as e:
                    print(f"  ✗ Failed to create node {node_id}: {e}")
            
            # Create relationships
            print("\n🔗 Creating relationships...")
            for rel in relationships:
                rel_type = rel.get('type', 'RELATED_TO')
                start_id = rel.get('startNodeId')
                end_id = rel.get('endNodeId')
                props = rel.get('properties', {})
                
                # Build Cypher query to match by internal ID
                props_str = ''
                if props:
                    props_str = ' {' + ', '.join([f"{k}: ${k}" for k in props.keys()]) + '}'
                
                query = f"""
                MATCH (a {{_rulenet_id: $start_id}})
                MATCH (b {{_rulenet_id: $end_id}})
                CREATE (a)-[r:{rel_type}{props_str}]->(b)
                RETURN r
                """
                
                try:
                    result = session.run(query, start_id=start_id, end_id=end_id, **props)
                    if result.single():
                        rels_created += 1
                        print(f"  ✓ Created [{rel_type}]: {start_id} → {end_id}")
                    else:
                        print(f"  ✗ Could not find nodes for: {start_id} → {end_id}")
                except Exception as e:
                    print(f"  ✗ Failed to create relationship: {e}")
            
            # Optionally remove internal IDs (cleaner graph)
            # session.run("MATCH (n) REMOVE n._rulenet_id")
        
        return {
            "nodes_created": nodes_created,
            "relationships_created": rels_created
        }
    
    def load_from_cypher_script(self, json_path: str) -> dict:
        """
        Alternative: Execute the Cypher script directly.
        
        Args:
            json_path: Path to the exported JSON file
            
        Returns:
            Dictionary with execution status
        """
        with open(json_path, 'r') as f:
            export = json.load(f)
        
        cypher_script = export.get('cypherScript', '')
        
        if not cypher_script:
            print("❌ No cypherScript found in export")
            return {"success": False}
        
        print(f"\n📜 Executing Cypher script ({len(cypher_script)} characters)...")
        
        # Split into individual statements
        statements = [s.strip() for s in cypher_script.split(';') if s.strip()]
        
        executed = 0
        with self.driver.session() as session:
            for stmt in statements:
                if stmt:
                    try:
                        session.run(stmt)
                        executed += 1
                    except Exception as e:
                        print(f"  ✗ Error executing: {stmt[:50]}...")
                        print(f"    {e}")
        
        print(f"  ✓ Executed {executed} statements")
        return {"statements_executed": executed}


def print_quick_start():
    """Print quick start guide for Neo4j."""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                    🚀 Quick Start Guide                               ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  1. INSTALL NEO4J                                                     ║
║     • Download Neo4j Desktop: https://neo4j.com/download/             ║
║     • Or use Docker:                                                  ║
║       docker run -p 7474:7474 -p 7687:7687 \\                          ║
║         -e NEO4J_AUTH=neo4j/password neo4j:latest                     ║
║                                                                       ║
║  2. INSTALL PYTHON DRIVER                                             ║
║     pip install neo4j                                                 ║
║                                                                       ║
║  3. EXPORT FROM RULENET                                               ║
║     • Select "Neo4j Cypher" format                                    ║
║     • Click "Export" → saves .json file                               ║
║                                                                       ║
║  4. LOAD INTO NEO4J                                                   ║
║     python load_neo4j_graph.py my_graph.json --password yourpassword  ║
║                                                                       ║
║  5. EXPLORE IN NEO4J BROWSER                                          ║
║     • Open http://localhost:7474                                      ║
║     • Run: MATCH (n) RETURN n                                         ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
""")


def print_sample_queries():
    """Print useful Cypher queries for the loaded graph."""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                    📝 Sample Cypher Queries                           ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  -- Show all nodes                                                    ║
║  MATCH (n) RETURN n                                                   ║
║                                                                       ║
║  -- Show all relationships                                            ║
║  MATCH (a)-[r]->(b) RETURN a, r, b                                    ║
║                                                                       ║
║  -- Find nodes by type                                                ║
║  MATCH (p:person) RETURN p                                            ║
║                                                                       ║
║  -- Find paths between nodes                                          ║
║  MATCH path = (a)-[*1..3]->(b)                                        ║
║  WHERE a.label = 'Dr. Smith'                                          ║
║  RETURN path                                                          ║
║                                                                       ║
║  -- Count nodes by type                                               ║
║  MATCH (n) RETURN labels(n)[0] as type, count(n) as count             ║
║                                                                       ║
║  -- Find authors and their papers                                     ║
║  MATCH (p:person)-[:authored]->(paper:paper)                          ║
║  RETURN p.label as author, paper.label as paper                       ║
║                                                                       ║
║  -- Graph statistics                                                  ║
║  CALL apoc.meta.stats() YIELD labels, relTypes                        ║
║  RETURN labels, relTypes                                              ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description='Load RuleNet graph export into local Neo4j database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python load_neo4j_graph.py graph.json
  python load_neo4j_graph.py graph.json --password mypassword
  python load_neo4j_graph.py graph.json --clear --uri bolt://localhost:7687
  python load_neo4j_graph.py --guide
        """
    )
    
    parser.add_argument(
        'json_file',
        nargs='?',
        help='Path to the exported Neo4j JSON file from RuleNet'
    )
    parser.add_argument(
        '--uri',
        default='bolt://localhost:7687',
        help='Neo4j Bolt URI (default: bolt://localhost:7687)'
    )
    parser.add_argument(
        '--user',
        default='neo4j',
        help='Neo4j username (default: neo4j)'
    )
    parser.add_argument(
        '--password',
        default='password',
        help='Neo4j password (default: password)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear all existing data before loading'
    )
    parser.add_argument(
        '--use-script',
        action='store_true',
        help='Execute the cypherScript directly instead of node-by-node loading'
    )
    parser.add_argument(
        '--guide',
        action='store_true',
        help='Show quick start guide'
    )
    parser.add_argument(
        '--queries',
        action='store_true',
        help='Show sample Cypher queries'
    )
    
    args = parser.parse_args()
    
    if args.guide:
        print_quick_start()
        return
    
    if args.queries:
        print_sample_queries()
        return
    
    if not args.json_file:
        parser.print_help()
        print("\n❌ Error: Please provide a JSON file to load")
        print("   Run with --guide for setup instructions")
        return
    
    if not NEO4J_AVAILABLE:
        print("❌ Cannot proceed without neo4j driver")
        print("   Install with: pip install neo4j")
        return
    
    print("=" * 60)
    print("🔷 RuleNet → Neo4j Graph Loader")
    print("=" * 60)
    
    # Initialize loader
    loader = Neo4jLoader(args.uri, args.user, args.password)
    
    try:
        # Show current stats
        stats = loader.get_stats()
        print(f"\n📊 Current database: {stats['nodes']} nodes, {stats['relationships']} relationships")
        if stats['labels']:
            print(f"   Labels: {', '.join(stats['labels'])}")
        
        # Clear if requested
        if args.clear:
            loader.clear_database()
        
        # Load the graph
        if args.use_script:
            result = loader.load_from_cypher_script(args.json_file)
        else:
            result = loader.load_from_json(args.json_file)
        
        # Show final stats
        final_stats = loader.get_stats()
        
        print("\n" + "=" * 60)
        print("✅ Loading Complete!")
        print("=" * 60)
        print(f"\n📊 Final database stats:")
        print(f"   Nodes: {final_stats['nodes']}")
        print(f"   Relationships: {final_stats['relationships']}")
        print(f"   Labels: {', '.join(final_stats['labels']) if final_stats['labels'] else 'none'}")
        print(f"   Relationship Types: {', '.join(final_stats['relationship_types']) if final_stats['relationship_types'] else 'none'}")
        
        print("\n🌐 Open Neo4j Browser: http://localhost:7474")
        print("   Try: MATCH (n) RETURN n")
        
    finally:
        loader.close()


if __name__ == '__main__':
    main()

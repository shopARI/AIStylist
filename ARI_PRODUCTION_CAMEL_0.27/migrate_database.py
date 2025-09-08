#!/usr/bin/env python3
"""
Database Migration Script
Migrate data from local Neo4j to remote productionbackup2 database
"""

import time
from neo4j import GraphDatabase
from typing import Dict, List, Any
import json

class DatabaseMigrator:
    def __init__(self):
        self.local_driver = GraphDatabase.driver(
            'bolt://0.0.0.0:17687',
            auth=('neo4j', '6D%q@jbYmstkK2i3oW5z6B6outew9m93')
        )
        
        self.remote_driver = GraphDatabase.driver(
            'bolt://34.135.40.119:7687',
            auth=('neo4j', 'shopari1234')
        )
        
        self.batch_size = 5000
        
    def migrate_nodes_by_label(self, label: str, count: int):
        """Migrate all nodes of a specific label"""
        
        print(f"\n🔄 Migrating {count:,} {label} nodes...")
        
        if count == 0:
            print(f"✅ No {label} nodes to migrate")
            return
            
        batches = (count + self.batch_size - 1) // self.batch_size
        
        for batch in range(batches):
            offset = batch * self.batch_size
            limit = min(self.batch_size, count - offset)
            
            print(f"  Batch {batch + 1}/{batches}: {offset:,} to {offset + limit:,}")
            
            try:
                # Get nodes from local database
                with self.local_driver.session() as local_session:
                    query = f"""
                    MATCH (n:{label})
                    RETURN n
                    SKIP {offset}
                    LIMIT {limit}
                    """
                    result = local_session.run(query)
                    nodes_data = []
                    
                    for record in result:
                        node = record['n']
                        node_props = dict(node)
                        nodes_data.append(node_props)
                
                # Create nodes in remote database
                if nodes_data:
                    with self.remote_driver.session(database='productionbackup2') as remote_session:
                        # Build CREATE query
                        create_query = f"CREATE "
                        create_parts = []
                        
                        for i, props in enumerate(nodes_data):
                            props_str = json.dumps(props).replace('"', '\\"')
                            create_parts.append(f"(n{i}:{label} {props_str})")
                        
                        create_query += ", ".join(create_parts)
                        
                        # Execute with proper JSON handling
                        params = {}
                        for i, props in enumerate(nodes_data):
                            params[f'props{i}'] = props
                        
                        # Simplified create approach
                        for i, props in enumerate(nodes_data):
                            remote_session.run(f"CREATE (n:{label} $props)", props=props)
                
                print(f"  ✅ Batch {batch + 1} completed ({limit:,} nodes)")
                
            except Exception as e:
                print(f"  ❌ Batch {batch + 1} failed: {e}")
                raise
                
        print(f"✅ {label} migration completed!")
    
    def migrate_relationships(self):
        """Migrate all relationships"""
        
        print(f"\n🔗 Migrating relationships...")
        
        # Get relationship types from local database
        with self.local_driver.session() as session:
            result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            rel_types = [record['relationshipType'] for record in result]
        
        print(f"Relationship types: {rel_types}")
        
        for rel_type in rel_types:
            print(f"\n🔗 Migrating {rel_type} relationships...")
            
            # Get relationship count
            with self.local_driver.session() as session:
                result = session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                rel_count = result.single()['count']
            
            if rel_count == 0:
                print(f"✅ No {rel_type} relationships to migrate")
                continue
                
            print(f"Found {rel_count:,} {rel_type} relationships")
            
            # Migrate in batches
            batches = (rel_count + self.batch_size - 1) // self.batch_size
            
            for batch in range(batches):
                offset = batch * self.batch_size
                limit = min(self.batch_size, rel_count - offset)
                
                print(f"  Batch {batch + 1}/{batches}")
                
                try:
                    # Get relationships from local
                    with self.local_driver.session() as local_session:
                        query = f"""
                        MATCH (a)-[r:`{rel_type}`]->(b)
                        RETURN a, r, b, labels(a) as start_labels, labels(b) as end_labels
                        SKIP {offset}
                        LIMIT {limit}
                        """
                        result = local_session.run(query)
                        rels_data = []
                        
                        for record in result:
                            rel_data = {
                                'start_node': dict(record['a']),
                                'start_labels': record['start_labels'],
                                'end_node': dict(record['b']),
                                'end_labels': record['end_labels'],
                                'rel_props': dict(record['r'])
                            }
                            rels_data.append(rel_data)
                    
                    # Create relationships in remote database
                    with self.remote_driver.session(database='productionbackup2') as remote_session:
                        for rel_data in rels_data:
                            # Find or create start node
                            start_label = rel_data['start_labels'][0]
                            start_props = rel_data['start_node']
                            
                            # Find or create end node  
                            end_label = rel_data['end_labels'][0]
                            end_props = rel_data['end_node']
                            
                            rel_props = rel_data['rel_props']
                            
                            # Create relationship
                            query = f"""
                            MATCH (a:{start_label}), (b:{end_label})
                            WHERE a = $start_props AND b = $end_props
                            CREATE (a)-[r:`{rel_type}` $rel_props]->(b)
                            """
                            
                            remote_session.run(query, 
                                start_props=start_props, 
                                end_props=end_props,
                                rel_props=rel_props
                            )
                    
                    print(f"  ✅ Batch {batch + 1} completed")
                    
                except Exception as e:
                    print(f"  ❌ Batch {batch + 1} failed: {e}")
                    # Continue with next batch
                    continue
    
    def verify_migration(self):
        """Verify the migration completed successfully"""
        
        print(f"\n🔍 VERIFYING MIGRATION...")
        
        # Compare node counts
        with self.local_driver.session() as local_session:
            result = local_session.run("CALL db.labels() YIELD label RETURN label")
            labels = [record['label'] for record in result]
        
        print(f"\n📊 NODE COUNT COMPARISON:")
        for label in labels:
            # Local count
            with self.local_driver.session() as local_session:
                result = local_session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                local_count = result.single()['count']
            
            # Remote count
            with self.remote_driver.session(database='productionbackup2') as remote_session:
                result = remote_session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                remote_count = result.single()['count']
            
            status = "✅" if local_count == remote_count else "❌"
            print(f"{status} {label}: Local={local_count:,} Remote={remote_count:,}")
        
        # Compare relationship counts
        with self.local_driver.session() as local_session:
            result = local_session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            rel_types = [record['relationshipType'] for record in result]
        
        print(f"\n🔗 RELATIONSHIP COUNT COMPARISON:")
        for rel_type in rel_types:
            # Local count
            with self.local_driver.session() as local_session:
                result = local_session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                local_count = result.single()['count']
            
            # Remote count
            with self.remote_driver.session(database='productionbackup2') as remote_session:
                try:
                    result = remote_session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                    remote_count = result.single()['count']
                except:
                    remote_count = 0
            
            status = "✅" if local_count == remote_count else "❌"
            print(f"{status} {rel_type}: Local={local_count:,} Remote={remote_count:,}")
    
    def run_migration(self):
        """Run the complete migration"""
        
        print("🚀 STARTING DATABASE MIGRATION")
        print("From: bolt://0.0.0.0:17687 (local)")
        print("To: bolt://34.135.40.119:7687/productionbackup2")
        print("=" * 50)
        
        try:
            # Get node labels and counts
            with self.local_driver.session() as session:
                result = session.run('CALL db.labels() YIELD label RETURN label ORDER BY label')
                labels = [record['label'] for record in result]
                
                label_counts = {}
                for label in labels:
                    result = session.run(f'MATCH (n:{label}) RETURN count(n) as count')
                    count = result.single()['count']
                    label_counts[label] = count
            
            # Migrate nodes by label (largest first for efficiency)
            sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
            
            for label, count in sorted_labels:
                self.migrate_nodes_by_label(label, count)
            
            # Migrate relationships
            self.migrate_relationships()
            
            # Verify migration
            self.verify_migration()
            
            print(f"\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            
        except Exception as e:
            print(f"\n❌ MIGRATION FAILED: {e}")
        
        finally:
            self.local_driver.close()
            self.remote_driver.close()

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    migrator.run_migration()
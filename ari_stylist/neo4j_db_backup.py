import os
import json
import datetime
import logging
import sys
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("neo4j_backup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Neo4j connection details - MODIFY THESE
URI = "bolt://34.135.40.119:7687"  # Your Neo4j server URI
USERNAME = "neo4j"                 # Your username
PASSWORD = "shopari1234"         # Your password

# Backup directory
BACKUP_DIR = "./neo4j_backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_FILENAME = f"neo4j_backup_{TIMESTAMP}.json"

class Neo4jBackup:
    def __init__(self, uri, username, password):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        if hasattr(self, 'driver'):
            self.driver.close()
            logger.info("Closed Neo4j connection")

    def export_nodes(self, labels=None):
        """Export all nodes with given labels or all nodes if labels is None"""
        try:
            with self.driver.session() as session:
                if labels:
                    label_match = " OR ".join([f"n:{label}" for label in labels])
                    query = f"MATCH (n) WHERE {label_match} RETURN n"
                else:
                    query = "MATCH (n) RETURN n"
                
                result = session.run(query)
                nodes = []
                
                for record in result:
                    node = record["n"]
                    node_data = dict(node.items())
                    node_data["_labels"] = list(node.labels)
                    nodes.append(node_data)
                
                logger.info(f"Exported {len(nodes)} nodes")
                return nodes
        except Exception as e:
            logger.error(f"Failed to export nodes: {e}")
            return []

    def export_relationships(self):
        """Export all relationships with their start and end nodes"""
        try:
            with self.driver.session() as session:
                query = """
                MATCH (start)-[r]->(end)
                RETURN 
                    id(start) as start_id, 
                    labels(start) as start_labels,
                    id(end) as end_id, 
                    labels(end) as end_labels,
                    type(r) as rel_type,
                    properties(r) as rel_props,
                    start.id as start_prop_id,
                    end.id as end_prop_id
                """
                
                result = session.run(query)
                relationships = []
                
                for record in result:
                    rel_data = {
                        "start_id": record["start_id"],
                        "start_labels": record["start_labels"],
                        "start_prop_id": record["start_prop_id"],
                        "end_id": record["end_id"],
                        "end_labels": record["end_labels"],
                        "end_prop_id": record["end_prop_id"],
                        "type": record["rel_type"],
                        "properties": record["rel_props"]
                    }
                    relationships.append(rel_data)
                
                logger.info(f"Exported {len(relationships)} relationships")
                return relationships
        except Exception as e:
            logger.error(f"Failed to export relationships: {e}")
            return []

    def backup_database(self):
        """Backup the entire database to a JSON file"""
        try:
            # Create backup directory if it doesn't exist
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
                logger.info(f"Created backup directory: {BACKUP_DIR}")
            
            # Export nodes and relationships
            nodes = self.export_nodes()
            relationships = self.export_relationships()
            
            # Create backup data structure
            backup_data = {
                "metadata": {
                    "timestamp": TIMESTAMP,
                    "node_count": len(nodes),
                    "relationship_count": len(relationships)
                },
                "nodes": nodes,
                "relationships": relationships
            }
            
            # Write to JSON file
            backup_path = os.path.join(BACKUP_DIR, BACKUP_FILENAME)
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"Backup successful: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

if __name__ == "__main__":
    try:
        backup = Neo4jBackup(URI, USERNAME, PASSWORD)
        success = backup.backup_database()
        backup.close()
        
        if success:
            print(f"\nDatabase backup completed successfully! Saved to {os.path.join(BACKUP_DIR, BACKUP_FILENAME)}")
        else:
            print("\nDatabase backup failed. Check the log file for details.")
            sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
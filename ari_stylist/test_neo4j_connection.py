from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Neo4j credentials from environment variables
uri = os.getenv("NEO4J_URL")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

def test_connection():
    try:
        # Create a driver instance
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        # Verify the connection with a simple query
        with driver.session() as session:
            result = session.run("RETURN 'Connection successful!' as message")
            message = result.single()["message"]
            print(message)
            
            # Get database stats
            result = session.run("""
            MATCH (p:Product) RETURN COUNT(p) as product_count
            """)
            product_count = result.single()["product_count"]
            print(f"Database contains {product_count} products")
        
        # Close the driver
        driver.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
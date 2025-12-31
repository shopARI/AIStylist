"""
Quick schema check
"""
from neo4j import GraphDatabase
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

print("Sample product properties:\n")

with driver.session() as session:
    result = session.run('MATCH (p:Product) RETURN p LIMIT 1')
    record = result.single()
    if record:
        product = record['p']
        for key in sorted(product.keys()):
            value = product[key]
            if isinstance(value, str):
                value_str = value[:50] + "..." if len(value) > 50 else value
            else:
                value_str = str(value)
            print(f'{key}: {value_str}')

driver.close()

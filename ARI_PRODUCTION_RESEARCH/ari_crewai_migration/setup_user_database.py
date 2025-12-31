#!/usr/bin/env python3
"""
Setup User Graph Database

This script creates the productionbackup2_user database and initializes
the user graph schema with all node types, constraints, and indexes.

Usage:
    python setup_user_database.py
"""

import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
USER_DATABASE = os.getenv("NEO4J_USER_DATABASE", "users")


class UserDatabaseSetup:
    """Setup and initialize the user graph database."""

    def __init__(self, uri, username, password, database_name):
        self.uri = uri
        self.username = username
        self.password = password
        self.database_name = database_name
        self.driver = None

    def connect(self):
        """Connect to Neo4j."""
        print(f"Connecting to Neo4j at {self.uri}...")
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )
        print("Connected successfully!")

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            print("Connection closed.")

    def create_database(self):
        """Create the user database."""
        print(f"\nCreating database '{self.database_name}'...")

        try:
            with self.driver.session(database="system") as session:
                # Check if database exists
                result = session.run("SHOW DATABASES")
                databases = [record["name"] for record in result]

                if self.database_name in databases:
                    print(f"Database '{self.database_name}' already exists.")

                    # Ask user if they want to recreate
                    response = input("Do you want to drop and recreate it? (yes/no): ")
                    if response.lower() in ['yes', 'y']:
                        print(f"Dropping database '{self.database_name}'...")
                        session.run(f"DROP DATABASE {self.database_name} IF EXISTS")
                        print("Database dropped.")

                        print(f"Creating database '{self.database_name}'...")
                        session.run(f"CREATE DATABASE {self.database_name}")
                        print("Database created successfully!")
                    else:
                        print("Using existing database.")
                else:
                    # Create database
                    session.run(f"CREATE DATABASE {self.database_name}")
                    print(f"Database '{self.database_name}' created successfully!")

        except Exception as e:
            print(f"Error creating database: {e}")
            raise

    def run_cypher_file(self, file_path):
        """Run a Cypher script file."""
        print(f"\nRunning Cypher script: {file_path}")

        # Read the file
        with open(file_path, 'r') as f:
            cypher_script = f.read()

        # Split into individual statements
        statements = []
        current_statement = []

        for line in cypher_script.split('\n'):
            # Skip comments and empty lines
            line = line.strip()
            if not line or line.startswith('//'):
                continue

            current_statement.append(line)

            # If line ends with semicolon, it's the end of a statement
            if line.endswith(';'):
                statements.append(' '.join(current_statement))
                current_statement = []

        # Add any remaining statement
        if current_statement:
            statements.append(' '.join(current_statement))

        # Execute statements
        print(f"Executing {len(statements)} statements...")

        with self.driver.session(database=self.database_name) as session:
            for i, statement in enumerate(statements, 1):
                # Clean up statement
                statement = statement.strip().rstrip(';')

                if not statement:
                    continue

                try:
                    result = session.run(statement)
                    result.consume()
                    print(f"  [{i}/{len(statements)}] Success")
                except Exception as e:
                    print(f"  [{i}/{len(statements)}] Error: {e}")
                    print(f"  Statement: {statement[:100]}...")

        print("Schema setup complete!")

    def verify_setup(self):
        """Verify the database setup."""
        print("\nVerifying database setup...")

        with self.driver.session(database=self.database_name) as session:
            # Count nodes by type
            node_types = [
                "User", "StyleAdjective", "FitPreference", "LifeStage",
                "Occasion", "ValuePriority", "StyleMotivation", "BudgetCategory"
            ]

            print("\nNode counts:")
            for node_type in node_types:
                result = session.run(f"MATCH (n:{node_type}) RETURN count(n) as count")
                count = result.single()["count"]
                print(f"  {node_type}: {count}")

            # Check test user
            result = session.run(
                "MATCH (u:User {username: 'test_user'})-[r]->(n) "
                "RETURN count(r) as relationship_count"
            )
            rel_count = result.single()["relationship_count"]
            print(f"\nTest user relationships: {rel_count}")

            if rel_count > 0:
                print("\nDatabase setup verified successfully!")
            else:
                print("\nWarning: Test user has no relationships")

    def setup(self):
        """Run complete setup."""
        try:
            self.connect()
            self.create_database()

            # Get schema file path
            schema_file = Path(__file__).parent / "config" / "user_graph_schema.cypher"

            if not schema_file.exists():
                print(f"\nError: Schema file not found: {schema_file}")
                return False

            self.run_cypher_file(schema_file)
            self.verify_setup()

            return True

        except Exception as e:
            print(f"\nSetup failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


def main():
    """Main entry point."""
    print("="*70)
    print("ARI USER GRAPH DATABASE SETUP")
    print("="*70)
    print()
    print(f"Neo4j URI: {NEO4J_URI}")
    print(f"Database Name: {USER_DATABASE}")
    print()

    # Confirm setup
    response = input("Continue with setup? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Setup cancelled.")
        return

    # Run setup
    setup = UserDatabaseSetup(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database_name=USER_DATABASE
    )

    success = setup.setup()

    if success:
        print("\n" + "="*70)
        print("SETUP COMPLETE!")
        print("="*70)
        print()
        print(f"User database '{USER_DATABASE}' is ready to use.")
        print()
        print("Next steps:")
        print("  1. Implement user services (user_service.py, user_graph_manager.py)")
        print("  2. Build onboarding flow (onboarding_service.py, onboarding_cli.py)")
        print("  3. Integrate with chat interface (chat_interface_v2.py)")
        print()
    else:
        print("\n" + "="*70)
        print("SETUP FAILED")
        print("="*70)
        print()
        print("Please check the error messages above and try again.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()

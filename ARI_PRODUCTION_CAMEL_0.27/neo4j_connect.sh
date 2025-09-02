#!/usr/bin/env bash
set -euo pipefail

# Bastion connection details
CONTROL_TOWER_HOSTNAME="tower.ari.shopari.com"
CONTROL_TOWER_KEY_PAIR_PATH="/home/leo/.aws/key-pair/ari-prod.pem"

echo "*** Getting Neo4j connection details...***"

# Ask the bastion to run the helper and extract the writer IP
writer_ip=$(ssh -i "${CONTROL_TOWER_KEY_PAIR_PATH}" ec2-user@"${CONTROL_TOWER_HOSTNAME}" \
  "neo4j_neo4j_servers neo4j | jq -r '.[] | select(.writer==true) | .ip' | head -n1")

if [[ -z "$writer_ip" ]]; then
  echo "❌ Failed to determine writer IP"
  exit 1
fi

echo "*** Writer IP is $writer_ip ***"
echo "*** Started Neo4j tunnel via Tower...***"

ssh -N -L 17687:"$writer_ip":7687 \
  -A -i "${CONTROL_TOWER_KEY_PAIR_PATH}" \
  ec2-user@"${CONTROL_TOWER_HOSTNAME}"
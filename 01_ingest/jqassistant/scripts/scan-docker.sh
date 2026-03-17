#!/bin/bash
# Run jQAssistant scanner via Docker

set -e

TARGET_REPO="${TARGET_REPO:-../../00_target-app}"
NEO4J_URI="${NEO4J_URI:-bolt://host.docker.internal:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

echo "╔════════════════════════════════════════╗"
echo "║   jQAssistant Docker Scanner          ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check target repo
if [ ! -d "$TARGET_REPO" ]; then
    echo "❌ Target repository not found: $TARGET_REPO"
    exit 1
fi

# Resolve absolute paths
TARGET_ABS=$(cd "$TARGET_REPO" && pwd)
CONFIG_ABS=$(cd ../configs && pwd)

echo "Target:   $TARGET_ABS"
echo "Neo4j:    $NEO4J_URI"
echo "Config:   $CONFIG_ABS/jqassistant.yml"
echo ""

# Run Docker
docker run --rm \
    -v "$TARGET_ABS:/project" \
    -v "$CONFIG_ABS:/config" \
    -v ~/.m2:/root/.m2 \
    -e JQASSISTANT_OPTS="-Xmx2G" \
    jqassistant/cli:latest \
    analyze \
    -f /config/jqassistant.yml \
    -Djqassistant.store.uri="$NEO4J_URI" \
    -Djqassistant.store.username="$NEO4J_USER" \
    -Djqassistant.store.password="$NEO4J_PASSWORD"

echo ""
echo "✅ Docker scan complete!"

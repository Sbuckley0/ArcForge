#!/bin/bash
# jQAssistant scan script for Archim8

set -e

# Configuration
TARGET_REPO="${TARGET_REPO:-../../00_target-app}"
CONFIG_FILE="../configs/jqassistant.yml"
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

echo "╔════════════════════════════════════════╗"
echo "║   Archim8 - jQAssistant Scanner      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET_REPO"
echo "Neo4j:  $NEO4J_URI"
echo ""

# Check prerequisites
if ! command -v jqassistant &> /dev/null; then
    echo "❌ jQAssistant CLI not found"
    echo ""
    echo "Install options:"
    echo "  1. Download: https://jqassistant.org/get-started/"
    echo "  2. SDKMAN: sdk install jqassistant"
    echo "  3. Docker: Use scanners/jqassistant/scripts/scan-docker.sh"
    exit 1
fi

# Check target repo exists
if [ ! -d "$TARGET_REPO" ]; then
    echo "❌ Target repository not found: $TARGET_REPO"
    exit 1
fi

# Check if Neo4j is accessible (if using external)
if [[ "$NEO4J_URI" == bolt://* ]]; then
    echo "🔍 Checking Neo4j connectivity..."
    if ! nc -z localhost 7687 2>/dev/null; then
        echo "⚠️  Neo4j not accessible on port 7687"
        echo "    Start with: cd ../../02_docker/neo4j && docker-compose up -d"
        echo "    Or use embedded mode (edit configs/jqassistant.yml)"
        exit 1
    fi
    echo "✅ Neo4j is running"
fi

# Navigate to target repo
cd "$TARGET_REPO"

# Ensure project is built
echo ""
echo "📦 Checking build artifacts..."
if [ -f "pom.xml" ]; then
    if [ ! -d "target/classes" ]; then
        echo "⚠️  No build artifacts found. Running Maven build..."
        mvn clean install -DskipTests
    fi
elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
    if [ ! -d "build/classes" ]; then
        echo "⚠️  No build artifacts found. Running Gradle build..."
        ./gradlew clean build -x test
    fi
else
    echo "⚠️  No Maven or Gradle build file found"
fi

# Run scan
echo ""
echo "🔍 Starting jQAssistant scan..."
echo ""

jqassistant analyze \
    -f "$(realpath $CONFIG_FILE)" \
    -Djqassistant.store.uri="$NEO4J_URI" \
    -Djqassistant.store.username="$NEO4J_USER" \
    -Djqassistant.store.password="$NEO4J_PASSWORD" \
    -s archim8-scan

SCAN_EXIT=$?

echo ""
if [ $SCAN_EXIT -eq 0 ]; then
    echo "✅ Scan complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Query: Open Neo4j browser at http://localhost:7474"
    echo "  2. Generate: cd ../../archim8 && python 12_cli/archim8 generate"
else
    echo "❌ Scan failed with exit code $SCAN_EXIT"
    echo "   Check logs in target/jqassistant/"
    exit $SCAN_EXIT
fi

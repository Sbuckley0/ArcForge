# =============================================================================
# Archim8 — jQAssistant CLI container
#
# Downloads jQAssistant 2.x (Neo4j v5 distribution) from GitHub releases
# and packages it into a JRE-based Alpine image.
#
# Build:  make jqa-install     (or: docker compose -f ... build jqa)
# Run:    make jqa-scan        (via docker compose run)
#
# The container expects:
#   /scan        — read-only mount of the Maven reactor root to scan
#   /jqassistant/config/jqassistant.yml — Archim8 jQA config (mounted by compose)
#
# Neo4j is reached via the shared Docker network using the service hostname 'neo4j'.
# =============================================================================

FROM eclipse-temurin:17-jre-alpine

ARG JQA_VERSION=2.9.1
ARG JQA_DIST=jqassistant-commandline-neo4jv5-${JQA_VERSION}
ARG JQA_URL=https://github.com/jQAssistant/jqassistant/releases/download/${JQA_VERSION}/${JQA_DIST}-distribution.zip

RUN apk add --no-cache curl unzip \
 && echo "Downloading jQAssistant ${JQA_VERSION}..." \
 && curl -fsSL "${JQA_URL}" -o /tmp/jqa.zip \
 && echo "Extracting..." \
 && unzip -q /tmp/jqa.zip -d /opt \
 && mv "/opt/${JQA_DIST}" /opt/jqassistant \
 && rm /tmp/jqa.zip \
 && apk del curl unzip \
 && chmod +x /opt/jqassistant/bin/jqassistant.sh \
 && echo "jQAssistant ${JQA_VERSION} installed at /opt/jqassistant"

WORKDIR /jqassistant

ENTRYPOINT ["/opt/jqassistant/bin/jqassistant.sh"]

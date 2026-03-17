"""
Archim8 — docker_health MCP tool

Reports health status of Archim8 Docker containers.
Uses `docker inspect` subprocess to avoid a hard dependency on the Docker SDK.
"""

import json
import subprocess

# Containers that Archim8 manages — agents may only inspect these.
_KNOWN_CONTAINERS = frozenset({
    "archim8-neo4j",
    "archim8-jqa",
    "neo4j",
})


def check_docker_health(container_names: str) -> str:
    """Check the health and running status of one or more Docker containers.

    Accepts a comma-separated list of container names. Only containers within
    the Archim8 stack are permitted (archim8-neo4j, archim8-jqa, neo4j).

    Args:
        container_names: Comma-separated container names to inspect,
                         e.g. "archim8-neo4j" or "archim8-neo4j,archim8-jqa".

    Returns:
        Markdown table with Name, Status, Health, and Ports for each container.
    """
    names = [n.strip() for n in container_names.split(",") if n.strip()]
    if not names:
        return "ERROR: No container names provided."

    unknown = [n for n in names if n not in _KNOWN_CONTAINERS]
    if unknown:
        allowed = ", ".join(f"`{c}`" for c in sorted(_KNOWN_CONTAINERS))
        return (
            f"ERROR: Unknown container(s): {', '.join(unknown)}.\n"
            f"Allowed containers: {allowed}"
        )

    rows = []
    for name in names:
        try:
            result = subprocess.run(
                ["docker", "inspect", name],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return "ERROR: `docker` not found on PATH. Ensure Docker Desktop is running."
        except subprocess.TimeoutExpired:
            return f"ERROR: `docker inspect {name}` timed out."

        if result.returncode != 0:
            rows.append({
                "name": name,
                "status": "not found",
                "health": "—",
                "ports": "—",
            })
            continue

        try:
            info = json.loads(result.stdout)
            if not info:
                rows.append({"name": name, "status": "not found", "health": "—", "ports": "—"})
                continue

            state = info[0].get("State", {})
            status = state.get("Status", "unknown")
            health = state.get("Health", {}).get("Status", "—") if "Health" in state else "—"

            port_bindings = info[0].get("HostConfig", {}).get("PortBindings", {})
            port_strings = []
            for container_port, host_bindings in port_bindings.items():
                if host_bindings:
                    for hb in host_bindings:
                        port_strings.append(f"{hb.get('HostPort', '?')}→{container_port}")
            ports = ", ".join(port_strings) if port_strings else "—"

            rows.append({"name": name, "status": status, "health": health, "ports": ports})

        except (json.JSONDecodeError, IndexError, KeyError) as exc:
            rows.append({"name": name, "status": f"parse error: {exc}", "health": "—", "ports": "—"})

    # Format as Markdown table
    header = "| Container | Status | Health | Ports |"
    sep    = "|-----------|--------|--------|-------|"
    lines  = [header, sep]
    for row in rows:
        lines.append(f"| {row['name']} | {row['status']} | {row['health']} | {row['ports']} |")

    return "\n".join(lines)

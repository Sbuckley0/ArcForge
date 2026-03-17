"""
Archim8 — shell_exec MCP tools

Provides controlled shell execution for Archim8 pipeline management.
All tools are strictly allowlisted — no arbitrary command execution.
"""

import subprocess
from pathlib import Path

_archim8_root: Path = None

# Allowlisted Make targets that agents may invoke.
# These are read-only status/check targets plus pipeline targets that have
# human approval as a prerequisite (enforced at the orchestrator level).
_ALLOWED_TARGETS = frozenset({
    # Infrastructure
    "docker-up",
    "docker-down",
    "docker-restart",
    "docker-logs",
    "neo4j-wait",
    # Ingestion
    "jdeps",
    "jdeps-pipeline",
    "jdeps-filter",
    # jQAssistant
    "jqa-install",
    "jqa-scan",
    "jqa-analyze",
    "jqa-pipeline",
    "jqa-reset",
    "jqa-verify",
    "jqa-export",
    # Neo4j
    "neo4j-init",
    "neo4j-migrate",
    "neo4j-ingest",
    "neo4j-setup",
    "neo4j-export",
    "neo4j-verify",
    # Generation
    "generate-views",
    "generate-diagrams",
    "generate-all",
    "generate-pipeline",
    # Composite
    "ingest-pipeline",
    "full-pipeline",
    # Status / help (safe, read-only)
    "help",
})

# Root of log files the agent is allowed to read.
_LOG_DIRS: list[str] = [
    "05_deliver/input/01_ingest",
    "02_store/neo4j/docker/logs",
]

_MAX_LOG_LINES = 200


def init_paths(archim8_root: Path):
    global _archim8_root
    _archim8_root = archim8_root


def run_make_target(target: str) -> str:
    """Run an allowlisted Archim8 Makefile target.

    Only pre-approved targets may be executed. Attempting to run any target
    not on the allowlist will be rejected with an error message.

    Available targets:
      Infrastructure: docker-up, docker-down, docker-restart, docker-logs, neo4j-wait
      Ingestion:      jdeps, jdeps-pipeline, jdeps-filter
      jQAssistant:    jqa-install, jqa-scan, jqa-analyze, jqa-pipeline, jqa-reset
      Neo4j:          neo4j-init
      Generation:     generate-pipeline
      Composite:      ingest-pipeline, full-pipeline
      Info:           help

    Args:
        target: The Makefile target name (e.g. "docker-up", "jqa-pipeline").

    Returns:
        Combined stdout/stderr output from make, or an error message.
    """
    if _archim8_root is None:
        return "ERROR: archim8 root not configured. Call init_paths() first."

    if target not in _ALLOWED_TARGETS:
        allowed = ", ".join(sorted(_ALLOWED_TARGETS))
        return (
            f"ERROR: Target '{target}' is not on the allowlist.\n"
            f"Allowed targets: {allowed}"
        )

    makefile = _archim8_root / "Makefile"
    if not makefile.exists():
        return f"ERROR: Makefile not found at {makefile}"

    try:
        result = subprocess.run(
            ["make", "-C", str(_archim8_root), target],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        output = result.stdout + result.stderr
        return (
            f"## make {target}\n\n"
            f"Exit code: {result.returncode}\n\n"
            f"```\n{output.strip()}\n```"
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: `make {target}` timed out after 300 seconds."
    except FileNotFoundError:
        return "ERROR: `make` not found on PATH. Ensure GNU Make is installed."
    except Exception as exc:
        return f"ERROR: Unexpected failure running `make {target}`: {exc}"


def check_file_exists(file_path: str) -> str:
    """Check whether a file or directory exists within the Archim8 workspace.

    The path is resolved relative to the archim8 root. Absolute paths outside
    the workspace root are rejected.

    Args:
        file_path: Workspace-relative path (e.g. "05_deliver/output/manifest.json").

    Returns:
        Markdown-formatted status indicating whether the path exists, its type
        (file/directory), and its size in bytes if it is a file.
    """
    if _archim8_root is None:
        return "ERROR: archim8 root not configured. Call init_paths() first."

    target = (_archim8_root / file_path).resolve()

    # Security guard: must stay inside workspace
    try:
        target.relative_to(_archim8_root.resolve())
    except ValueError:
        return f"ERROR: Path '{file_path}' resolves outside the workspace root."

    if not target.exists():
        return f"**Not found:** `{file_path}`"

    if target.is_dir():
        child_count = len(list(target.iterdir()))
        return f"**Directory exists:** `{file_path}` ({child_count} entries)"

    size = target.stat().st_size
    return f"**File exists:** `{file_path}` ({size:,} bytes)"


def read_log_file(log_name: str, lines: int = 50) -> str:
    """Read the last N lines of a named log file from an Archim8 log directory.

    Searches within the allowed log directories:
      - 05_deliver/input/01_ingest/
      - 02_store/neo4j/docker/logs/

    Args:
        log_name: Filename of the log (e.g. "jdeps-output.txt", "neo4j.log").
                  Must not contain path separators.
        lines:    Number of lines to return from the end of the file (default 50,
                  max 200).

    Returns:
        The last `lines` lines of the log file, or an error message.
    """
    if _archim8_root is None:
        return "ERROR: archim8 root not configured. Call init_paths() first."

    # Reject any path traversal attempts
    if "/" in log_name or "\\" in log_name or ".." in log_name:
        return f"ERROR: log_name must be a plain filename without path separators. Got: '{log_name}'"

    lines = min(max(1, lines), _MAX_LOG_LINES)

    for log_dir in _LOG_DIRS:
        candidate = (_archim8_root / log_dir / log_name).resolve()
        try:
            candidate.relative_to(_archim8_root.resolve())
        except ValueError:
            continue  # shouldn't happen given plain filename, but be safe
        if candidate.exists() and candidate.is_file():
            try:
                all_lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                tail = all_lines[-lines:]
                return (
                    f"## {log_name} (last {len(tail)} lines)\n\n"
                    f"```\n" + "\n".join(tail) + "\n```"
                )
            except Exception as exc:
                return f"ERROR: Could not read '{log_name}': {exc}"

    searched = ", ".join(f"`{d}`" for d in _LOG_DIRS)
    return f"**Not found:** `{log_name}` in {searched}"

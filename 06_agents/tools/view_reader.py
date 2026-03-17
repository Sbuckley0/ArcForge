"""
Archim8 — view_reader MCP tools
Manifest-aware tools for reading pre-generated architecture views.
Checks manifest.json before serving content to honour the anti-regeneration contract.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — set by archim8_agent.py at startup
# ---------------------------------------------------------------------------
_manifest_path: Path = None
_views_dir: Path = None

# Maximum characters to return from a single view (avoid LLM context overflow)
_MAX_CHARS = 12_000


def init_paths(manifest_path: Path, views_dir: Path):
    global _manifest_path, _views_dir
    _manifest_path = manifest_path
    _views_dir = views_dir


def _load_manifest() -> dict:
    if _manifest_path and _manifest_path.exists():
        with open(_manifest_path, encoding="utf-8") as f:
            return json.load(f)
    return {"views": {}}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def list_available_views() -> str:
    """List all pre-generated architecture views from the Archim8 manifest.

    Returns view names, row counts, scope descriptions, and generation timestamps.
    Use this before calling read_architecture_view to confirm which views exist.

    Returns:
        Markdown table of available views and their metadata.
    """
    manifest = _load_manifest()
    views = manifest.get("views", {})
    if not views:
        return "No views found in manifest. Run `make generate-views` to generate them."

    lines = [
        "| view_name | rows | scope | generated |",
        "| --- | --- | --- | --- |",
    ]
    for name, meta in sorted(views.items()):
        lines.append(
            f"| {name} | {meta.get('row_count', '?')} | {meta.get('scope', '')} | {meta.get('generated', '')} |"
        )
    lines.append(f"\n_Last manifest update: {manifest.get('last_updated', 'unknown')}_")
    return "\n".join(lines)


def read_architecture_view(view_name: str) -> str:
    """Read the content of a pre-generated architecture view.

    Available views: module-deps, grpc-services, pekka-http-api,
    spring-components, observability-coverage, violations,
    key-abstractions, cobol-subsystem.

    For large views (spring-components has 1056 rows), summary statistics are
    returned first followed by the data. If the view is very large, only the
    first portion is returned — use run_cypher_query for targeted follow-up.

    Args:
        view_name: Name of the view (without .md extension).

    Returns:
        The view's YAML frontmatter + Markdown table, or an error message.
    """
    if _views_dir is None:
        return "ERROR: Views directory not configured. Call init_paths() first."

    manifest = _load_manifest()
    if view_name not in manifest.get("views", {}):
        available = ", ".join(sorted(manifest.get("views", {}).keys()))
        return (f"ERROR: View '{view_name}' not found in manifest.\n"
                f"Available: {available}\n"
                f"Run `make generate-views` to regenerate views.")

    view_file = _views_dir / f"{view_name}.md"
    if not view_file.exists():
        return (f"ERROR: View file '{view_name}.md' missing from disk but present in manifest.\n"
                f"Run `make generate-views --force` to regenerate.")

    content = view_file.read_text(encoding="utf-8")
    meta = manifest["views"][view_name]

    if len(content) <= _MAX_CHARS:
        return content

    # Large view: return header + truncated data with guidance
    truncated = content[:_MAX_CHARS]
    last_newline = truncated.rfind("\n")
    truncated = truncated[:last_newline]
    rows = meta.get("row_count", "?")
    return (
        f"{truncated}\n\n"
        f"_(View truncated — {rows} total rows. Use `run_cypher_query` with a "
        f"filtered query for specific data within this view.)_"
    )

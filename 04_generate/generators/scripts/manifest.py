"""
Archim8 Phase 4 — Manifest helpers
Shared by generate_views.py and generate_plantuml.py.

Schema:
{
  "last_updated": "ISO-8601",
  "views": {
    "<view_name>": {
      "file":       "relative/path/to/output.md",
      "generated":  "ISO-8601",
      "row_count":  42,
      "cypher":     "03_query/cypher/library/jqa/<file>.cypher",
      "scope":      "human-readable scope description"
    }
  },
  "diagrams": {
    "<diagram_name>": {
      "file":      "relative/path/to/output.puml",
      "generated": "ISO-8601"
    }
  }
}
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def load(manifest_path: Path) -> dict:
    """Load manifest from disk, returning empty structure if absent."""
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("views", {})
        data.setdefault("diagrams", {})
        return data
    return {"views": {}, "diagrams": {}, "last_updated": ""}


def save(manifest_path: Path, manifest: dict):
    """Write manifest to disk, stamping last_updated."""
    manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def view_is_current(manifest: dict, view_name: str, out_path: Path) -> bool:
    """Return True if the view exists in manifest AND the output file is present."""
    return view_name in manifest.get("views", {}) and out_path.exists()


def diagram_is_current(manifest: dict, diagram_name: str, out_path: Path) -> bool:
    """Return True if the diagram exists in manifest AND the output file is present."""
    return diagram_name in manifest.get("diagrams", {}) and out_path.exists()


def file_hash(path: Path) -> str:
    """SHA-256 of a file's contents (for staleness checking)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def set_view(manifest: dict, view_name: str, meta: dict):
    """Upsert a view entry."""
    manifest.setdefault("views", {})[view_name] = meta


def set_diagram(manifest: dict, diagram_name: str, meta: dict):
    """Upsert a diagram entry."""
    manifest.setdefault("diagrams", {})[diagram_name] = meta


def summary(manifest: dict) -> str:
    """Human-readable summary of manifest contents."""
    views    = manifest.get("views", {})
    diagrams = manifest.get("diagrams", {})
    lines = [
        f"Manifest last updated: {manifest.get('last_updated', 'never')}",
        f"Views ({len(views)}): {', '.join(sorted(views)) or 'none'}",
        f"Diagrams ({len(diagrams)}): {', '.join(sorted(diagrams)) or 'none'}",
    ]
    return "\n".join(lines)

"""
Archim8 — diagram_gen MCP tool
Triggers the PlantUML C4 generator and returns the path to the output file.
"""

import subprocess
import sys
from pathlib import Path

_archim8_root: Path = None
_python_exe: str = sys.executable


def init_paths(archim8_root: Path, python_exe: str = None):
    global _archim8_root, _python_exe
    _archim8_root = archim8_root
    if python_exe:
        _python_exe = python_exe


def generate_architecture_diagram(diagram_type: str) -> str:
    """Generate a PlantUML C4 architecture diagram from the live Neo4j graph.

    Available diagram types:
    - "containers"  — full module topology grouped by layer
    - "cobol"       — COBOL emulation subsystem (runtime-cobol-* modules)
    - "all"         — both diagrams

    The diagrams are written to 05_deliver/output/ as .puml files.
    Open them with the PlantUML VS Code extension (Alt+D to render).

    Args:
        diagram_type: One of "containers", "cobol", or "all".

    Returns:
        Confirmation message with output file paths.
    """
    if _archim8_root is None:
        return "ERROR: archim8 root not configured. Call init_paths() first."

    valid = {"containers", "cobol", "all"}
    if diagram_type not in valid:
        return f"ERROR: diagram_type must be one of {valid}. Got: '{diagram_type}'"

    script = _archim8_root / "04_generate" / "generators" / "scripts" / "generate_plantuml.py"
    if not script.exists():
        return f"ERROR: Generator script not found at {script}"

    try:
        result = subprocess.run(
            [_python_exe, str(script), "--diagram", diagram_type, "--force"],
            capture_output=True,
            text=True,
            cwd=str(_archim8_root),
            timeout=120,
        )
        if result.returncode != 0:
            return f"ERROR generating diagram:\n{result.stderr}"

        output_dir = _archim8_root / "05_deliver" / "output"
        files = []
        if diagram_type in ("containers", "all"):
            f = output_dir / "arc-containers.puml"
            if f.exists():
                files.append(str(f.relative_to(_archim8_root)))
        if diagram_type in ("cobol", "all"):
            f = output_dir / "arc-cobol-emulation.puml"
            if f.exists():
                files.append(str(f.relative_to(_archim8_root)))

        file_list = "\n".join(f"  - {p}" for p in files)
        return (
            f"Diagram(s) generated successfully:\n{file_list}\n\n"
            "Open in VS Code and press **Alt+D** to render (PlantUML extension required)."
        )
    except subprocess.TimeoutExpired:
        return "ERROR: Diagram generation timed out after 120s."
    except Exception as exc:
        return f"ERROR: {exc}"

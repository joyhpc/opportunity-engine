import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_package_has_expected_layer_directories():
    expected = {
        "api",
        "core",
        "data",
        "engine",
        "heuristics",
        "imports",
        "integrations",
        "tools",
        "web",
    }

    present = {path.name for path in (ROOT / "ode").iterdir() if path.is_dir()}

    assert expected <= present


def test_runtime_code_does_not_import_top_level_experimental_areas():
    forbidden_roots = {"imports", "prototypes"}
    offenders: list[str] = []

    for path in (ROOT / "ode").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden_roots:
                        offenders.append(f"{path.relative_to(ROOT)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                root = node.module.split(".", 1)[0]
                if root in forbidden_roots:
                    offenders.append(f"{path.relative_to(ROOT)} imports from {node.module}")

    assert offenders == []


def test_git_does_not_track_runtime_artifacts():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = result.stdout.splitlines()
    artifacts = [
        path
        for path in tracked
        if "__pycache__" in path or ".pytest_cache" in path or path.endswith(".pyc")
    ]

    assert artifacts == []

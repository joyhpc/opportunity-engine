"""Pipeline DAG scheduler — wraps project-tracker engine.py for ODE.

Provides DAG-based pipeline execution: build graph, topological sort,
schedule workers based on dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Try to import pt engine for advanced scheduling
_pt_path = Path.home() / "project-tracker"
if _pt_path.exists():
    sys.path.insert(0, str(_pt_path))
    try:
        from tracker.engine import (
            build_graph,
            topo_sort,
            compute_cpm,
            classify_tasks,
        )
    except ImportError:
        pass
    finally:
        if str(_pt_path) in sys.path:
            sys.path.remove(str(_pt_path))


# ---------------------------------------------------------------------------
# ODE Pipeline DAG (standalone if pt not available)
# ---------------------------------------------------------------------------

# Default 7-stage pipeline as a simple DAG
DEFAULT_PIPELINE = {
    "stages": [
        {"id": "SENSE", "deps": [], "workers": ["scan"]},
        {"id": "SCREEN", "deps": ["SENSE"], "workers": ["eval"], "gate": {"min_score": 50}},
        {"id": "ANALYZE", "deps": ["SCREEN"], "workers": ["eval"], "gate": {"min_score": 70}},
        {"id": "VALIDATE", "deps": ["ANALYZE"], "workers": ["eval"]},
        {"id": "PLAN", "deps": ["VALIDATE"], "workers": ["report"]},
        {"id": "LAUNCH", "deps": ["PLAN"], "workers": []},
        {"id": "MONITOR", "deps": ["LAUNCH"], "workers": []},
    ]
}


class PipelineDAG:
    """Simple DAG scheduler for the opportunity pipeline."""

    def __init__(self, pipeline: dict | None = None):
        self.pipeline = pipeline or DEFAULT_PIPELINE
        self.stages = {s["id"]: s for s in self.pipeline["stages"]}
        self._build()

    def _build(self):
        """Build adjacency lists."""
        self.deps: dict[str, list[str]] = {}
        self.rdeps: dict[str, list[str]] = {}

        for stage in self.pipeline["stages"]:
            sid = stage["id"]
            self.deps[sid] = stage.get("deps", [])
            self.rdeps[sid] = []

        for sid, dep_list in self.deps.items():
            for dep in dep_list:
                if dep in self.rdeps:
                    self.rdeps[dep].append(sid)

    def topo_order(self) -> list[str]:
        """Return stages in topological order (Kahn's algorithm)."""
        in_degree = {sid: len(deps) for sid, deps in self.deps.items()}
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            queue.sort()  # stable order
            node = queue.pop(0)
            result.append(node)
            for succ in self.rdeps.get(node, []):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(result) != len(self.stages):
            raise ValueError("Pipeline has cycles")

        return result

    def next_stages(self, completed: set[str]) -> list[str]:
        """Return stages that are ready to execute (all deps completed)."""
        ready = []
        for sid, dep_list in self.deps.items():
            if sid in completed:
                continue
            if all(d in completed for d in dep_list):
                ready.append(sid)
        return sorted(ready)

    def workers_for_stage(self, stage_id: str) -> list[str]:
        """Return worker names needed for a given stage."""
        stage = self.stages.get(stage_id)
        return stage.get("workers", []) if stage else []

    def gate_for_stage(self, stage_id: str) -> dict | None:
        """Return gate config for a stage, if any."""
        stage = self.stages.get(stage_id)
        return stage.get("gate") if stage else None


def create_pipeline(template: str = "default") -> PipelineDAG:
    """Create a pipeline from a template name."""
    if template == "default":
        return PipelineDAG(DEFAULT_PIPELINE)

    # Try loading from flows/ directory (respects ODE_ROOT)
    import os
    from ..core.store import _project_root
    flows_dir = _project_root() / "flows"
    flow_file = flows_dir / f"{template}.yaml"
    if flow_file.exists():
        import yaml
        with open(flow_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return PipelineDAG(data)

    return PipelineDAG(DEFAULT_PIPELINE)

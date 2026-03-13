"""BM25 knowledge index — wraps project-tracker knowledge.py for ODE.

Indexes historical opportunity research data for LLM context enrichment.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass


# Try to import pt knowledge
_PT_KNOWLEDGE = None
_pt_path = Path.home() / "project-tracker"
if _pt_path.exists():
    sys.path.insert(0, str(_pt_path))
    try:
        from tracker.knowledge import BM25, KnowledgeChunk, tokenize, parse_markdown
        _PT_KNOWLEDGE = True
    except ImportError:
        _PT_KNOWLEDGE = False
    finally:
        if str(_pt_path) in sys.path:
            sys.path.remove(str(_pt_path))


@dataclass
class KnowledgeEntry:
    """A searchable knowledge entry."""
    id: str
    source: str  # opportunity_id, file path, etc.
    title: str
    content: str
    path: list[str] | None = None


class KnowledgeBase:
    """BM25-based knowledge index for opportunity research data."""

    def __init__(self):
        self.entries: list[KnowledgeEntry] = []
        self._bm25 = None

    def add_entry(self, entry: KnowledgeEntry):
        """Add an entry to the knowledge base."""
        self.entries.append(entry)
        self._bm25 = None  # invalidate index

    def add_from_file(self, filepath: str | Path, source: str = ""):
        """Index a markdown file."""
        p = Path(filepath)
        if not p.exists():
            return

        content = p.read_text(encoding="utf-8")
        if _PT_KNOWLEDGE:
            chunks = parse_markdown(source or p.stem, p.stem, content)
            for chunk in chunks:
                self.add_entry(KnowledgeEntry(
                    id=f"{source}:{chunk.task_id}",
                    source=source or str(p),
                    title=chunk.task_name,
                    content=chunk.content,
                    path=chunk.path,
                ))
        else:
            # Fallback: treat whole file as one entry
            self.add_entry(KnowledgeEntry(
                id=source or p.stem,
                source=source or str(p),
                title=p.stem,
                content=content[:3000],
            ))

        self._bm25 = None

    def add_from_opportunity(self, opp_id: str, reports_dir: str | Path):
        """Index all reports for an opportunity."""
        rdir = Path(reports_dir)
        for f in rdir.glob(f"{opp_id}_*.md"):
            self.add_from_file(f, source=opp_id)

    def _build_index(self):
        """Build BM25 index from entries."""
        if _PT_KNOWLEDGE and self.entries:
            chunks = [
                KnowledgeChunk(
                    task_id=e.id,
                    task_name=e.title,
                    path=e.path or [],
                    content=e.content,
                )
                for e in self.entries
            ]
            self._bm25 = BM25(chunks)
        else:
            self._bm25 = None

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeEntry]:
        """Search the knowledge base with BM25."""
        if not self.entries:
            return []

        if self._bm25 is None:
            self._build_index()

        if self._bm25 is None:
            # Fallback: simple substring matching
            query_lower = query.lower()
            scored = []
            for e in self.entries:
                text = f"{e.title} {e.content}".lower()
                score = sum(1 for w in query_lower.split() if w in text)
                if score > 0:
                    scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:top_k]]

        results = self._bm25.search(query, top_k=top_k)
        # Map back to KnowledgeEntry
        entry_map = {e.id: e for e in self.entries}
        return [
            entry_map.get(chunk.task_id, KnowledgeEntry(
                id=chunk.task_id,
                source="",
                title=chunk.task_name,
                content=chunk.content,
            ))
            for chunk in results
            if chunk.task_id in entry_map
        ]

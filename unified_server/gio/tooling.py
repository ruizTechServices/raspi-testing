from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any


WEB_HINTS = (
    "latest",
    "today",
    "current",
    "currently",
    "right now",
    "news",
    "recent",
    "just happened",
    "live",
    "price",
    "weather",
    "stock",
    "score",
    "search the web",
    "look up",
    "google",
)

RAG_HINTS = (
    "docs",
    "documentation",
    "readme",
    "knowledge base",
    "knowledgebase",
    "notes",
    "from the files",
    "in the files",
    "in the repo",
    "in the repository",
    "in the codebase",
    "project",
    "codebase",
    "repo",
    "based on the docs",
    "based on the codebase",
    "based on the project",
    "from the project files",
    "from the code",
    "which file",
    "what file",
    "streaming",
    "route",
    "routing",
    "implementation",
)

OPT_OUT_HINTS = (
    "no web",
    "don't search the web",
    "do not search the web",
    "without web",
    "no rag",
    "without rag",
    "without retrieval",
)


@dataclass(slots=True)
class GioToolPlan:
    use_rag: bool = False
    use_web: bool = False
    reasons: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = self.reasons or []
        return payload


@dataclass(slots=True)
class GioContextSource:
    kind: str
    label: str
    title: str
    source: str
    snippet: str
    score: float | None = None
    url: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = self.metadata or {}
        return payload


def extract_query_terms(text: str) -> list[str]:
    lowered = (text or "").lower()
    raw_terms = re.findall(r"[a-z0-9_./-]+", lowered)
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "into", "your", "what", "where", "when", "which",
        "does", "how", "who", "why", "are", "was", "were", "have", "has", "had", "about", "based", "only",
        "latest", "project", "files", "codebase", "repo", "docs", "documentation", "please",
    }
    seen: set[str] = set()
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip("./-")
        if len(normalized) < 2 or normalized in stop_words:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return terms


class GioToolRouter:
    def plan(self, user_text: str) -> GioToolPlan:
        cleaned = (user_text or "").strip().lower()
        if not cleaned:
            return GioToolPlan(reasons=[])

        if any(hint in cleaned for hint in OPT_OUT_HINTS):
            return GioToolPlan(reasons=["User explicitly opted out of tools."])

        force_web = "#web" in cleaned
        force_rag = "#rag" in cleaned
        force_both = "#tools" in cleaned

        reasons: list[str] = []
        use_web = force_web or force_both or any(hint in cleaned for hint in WEB_HINTS)
        use_rag = force_rag or force_both or any(hint in cleaned for hint in RAG_HINTS)

        if force_web:
            reasons.append("User explicitly requested web search.")
        elif use_web:
            reasons.append("Fresh or live information likely matters.")

        if force_rag:
            reasons.append("User explicitly requested knowledge retrieval.")
        elif use_rag:
            reasons.append("Stored project knowledge likely matters.")

        return GioToolPlan(use_rag=use_rag, use_web=use_web, reasons=reasons)


def build_sources_block(title: str, intro: str, sources: list[GioContextSource]) -> str | None:
    if not sources:
        return None
    lines = [title, intro]
    for source in sources:
        header = f"{source.label} | {source.title}"
        if source.url:
            header += f" | {source.url}"
        elif source.source:
            header += f" | {source.source}"
        lines.append(header)
        lines.append(source.snippet)
    return "\n".join(lines)


def build_citation_instruction(has_rag: bool, has_web: bool) -> str | None:
    if not has_rag and not has_web:
        return None
    kinds: list[str] = []
    if has_rag:
        kinds.append("[R#] for retrieved knowledge")
    if has_web:
        kinds.append("[W#] for web results")
    return (
        "When you rely on the provided external context, cite it inline using "
        + " and ".join(kinds)
        + ". If the context is thin or conflicting, say that plainly instead of guessing. Never invent filenames, modules, routes, APIs, or behavior that are not supported by the provided context."
    )


def build_project_evidence_instruction(plan: GioToolPlan, rag_sources: list[GioContextSource]) -> str | None:
    if not plan.use_rag:
        return None
    if not rag_sources:
        return (
            "The user asked for project or stored-knowledge grounding, but no reliable retrieved project context was found. "
            "Say that clearly. Do not answer from generic coding assumptions, do not infer missing filenames, and do not claim code behavior you cannot support."
        )
    return (
        "Project-evidence mode is active. For codebase, project-file, route, implementation, or behavior questions, answer only from the retrieved project knowledge and the visible recent conversation. "
        "Prefer exact file paths, route names, class names, and function names when they are present in the sources. If the sources do not support a claim, say the evidence is insufficient instead of filling gaps with guesses."
    )

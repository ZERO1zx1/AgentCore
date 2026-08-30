"""Adaptive orchestration with evidence-first local learning."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set
import hashlib
import json
from src.memory.governance import POLICY_VERSION

SKILL_ADAPTIVE = "adaptive-omni-agent"
SKILL_ENGINEER = "code-engineer"
SKILL_CREDIT = "credit-safe-agent"
PUBLIC_SKILLS = (SKILL_ADAPTIVE, SKILL_ENGINEER, SKILL_CREDIT)

CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".cs", ".php", ".rb", ".swift", ".kt"}
WEB_EXTENSIONS = {".html", ".css", ".scss", ".sass", ".vue", ".svelte"}
DATA_EXTENSIONS = {".json", ".jsonl", ".csv", ".tsv", ".parquet", ".sql", ".db", ".sqlite"}
DOC_EXTENSIONS = {".md", ".txt", ".pdf", ".doc", ".docx", ".odt", ".ppt", ".pptx", ".xls", ".xlsx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".psd", ".fig"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
INFRA_NAMES = {"dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml", "terraform.tf", "vercel.json", "netlify.toml", "wrangler.toml"}


@dataclass
class OrchestrationProfile:
    primary_skill: str
    active_skills: List[str]
    objective: str
    artifact_types: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    validation_routes: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    memory_query: str = ""
    memory_policy: str = "evidence-first-bounded-local-lessons"
    memory_policy_version: str = POLICY_VERSION
    memory_scope: str = "project"
    task_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_skill": self.primary_skill,
            "active_skills": list(self.active_skills),
            "objective": self.objective,
            "artifact_types": list(self.artifact_types),
            "required_capabilities": list(self.required_capabilities),
            "validation_routes": list(self.validation_routes),
            "assumptions": list(self.assumptions),
            "memory_query": self.memory_query,
            "memory_policy": self.memory_policy,
            "memory_policy_version": self.memory_policy_version,
            "memory_scope": self.memory_scope,
            "task_fingerprint": self.task_fingerprint,
        }


class AdaptiveOrchestrator:
    """Turn prompt and observed artifacts into bounded work with fallible local lessons.

    The adaptive-omni-agent role owns both orchestration and memory recall.
    Recalled lessons help choose a route, but current files, instructions, and
    validation evidence always take precedence.
    """

    @staticmethod
    def profile(prompt: str, context, requested_skill: str = SKILL_ADAPTIVE) -> OrchestrationProfile:
        primary = requested_skill if requested_skill in PUBLIC_SKILLS else SKILL_ADAPTIVE
        artifacts = AdaptiveOrchestrator._artifact_types(context)
        capabilities: Set[str] = {"deterministic"}
        validations: Set[str] = set()

        if artifacts & {"code", "web", "app", "server", "infrastructure"}:
            capabilities.add("coding")
            validations.add("tests/build/smoke")
        if "document" in artifacts or "data" in artifacts:
            capabilities.add("text")
            validations.add("schema/render/content")
        if "image" in artifacts:
            capabilities.update({"vision", "multimodal"})
            validations.add("visual inspection")
        if "audio" in artifacts:
            capabilities.update({"audio", "multimodal"})
            validations.add("metadata/playback sample")
        if "video" in artifacts:
            capabilities.update({"video", "multimodal"})
            validations.add("metadata/frame/playback sample")

        lower = prompt.lower()
        if any(word in lower for word in ("analyze", "explain", "summar", "review", "translate")):
            capabilities.add("text")
        if primary == SKILL_CREDIT:
            active = [SKILL_CREDIT]
        elif primary == SKILL_ENGINEER:
            active = [SKILL_ENGINEER, SKILL_CREDIT]
        else:
            active = [SKILL_ADAPTIVE, SKILL_ENGINEER, SKILL_CREDIT]

        objective = " ".join(prompt.split()).strip() or "Inspect the supplied workspace and identify a bounded useful outcome"
        query_terms = [objective] + sorted(artifacts) + sorted(capabilities)
        source_fingerprints = getattr(context, "source_fingerprints", {}) or {}
        fingerprint_data = {"objective": objective.lower(), "artifacts": sorted(artifacts),
                            "capabilities": sorted(capabilities), "sources": sorted(source_fingerprints.items())}
        task_fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode("utf-8")).hexdigest()
        memory_scope = str((getattr(context, "metadata", {}) or {}).get("memory_scope", "project"))
        return OrchestrationProfile(
            primary_skill=primary,
            active_skills=active,
            objective=objective,
            artifact_types=sorted(artifacts or {"text"}),
            required_capabilities=sorted(capabilities),
            validation_routes=sorted(validations or {"observable output check"}),
            assumptions=[] if prompt.strip() else ["No explicit prompt was supplied; inspection remains read-only."],
            memory_query=" ".join(query_terms)[:500],
            memory_scope=memory_scope,
            task_fingerprint=task_fingerprint,
        )

    @staticmethod
    def _artifact_types(context) -> Set[str]:
        result: Set[str] = set()
        source_types = set(getattr(context, "source_types", {}).values())
        if "pdf" in source_types or "text" in source_types:
            result.add("document")
        if "structured" in source_types:
            result.add("data")
        if "repository" in source_types:
            result.add("code")

        repo = getattr(context, "repository_context", {}) or {}
        extensions = {str(ext).lower() for ext in repo.get("extensions", {})}
        names = {Path(str(path)).name.lower() for path in repo.get("file_tree", [])}
        if extensions & CODE_EXTENSIONS: result.add("code")
        if extensions & WEB_EXTENSIONS or {"package.json", "next.config.js", "vite.config.js"} & names: result.add("web")
        if {"server.py", "server.js", "server.ts", "app.py"} & names: result.add("server")
        if extensions & DATA_EXTENSIONS: result.add("data")
        if extensions & DOC_EXTENSIONS: result.add("document")
        if extensions & IMAGE_EXTENSIONS: result.add("image")
        if extensions & AUDIO_EXTENSIONS: result.add("audio")
        if extensions & VIDEO_EXTENSIONS: result.add("video")
        if INFRA_NAMES & names or ".tf" in extensions or ".yaml" in extensions and any(".github/workflows" in str(x).replace("\\", "/") for x in repo.get("file_tree", [])):
            result.add("infrastructure")
        return result

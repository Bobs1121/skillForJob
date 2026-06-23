from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BLOCK_RE = re.compile(r"```requirement-json\s*(\{.*?\})\s*```", re.DOTALL)
REQUIRED_META = {
    "requirement_id",
    "feature",
    "source_document",
    "source_version",
    "source_pages",
    "review_status",
    "implementation_status",
    "verification_status",
}


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return [part.strip() for part in value[1:-1].split(",") if part.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value.strip("\"'")


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    result: dict[str, Any] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = _parse_scalar(value)
    return result


def _terms(query: str) -> list[str]:
    words = [
        part.lower()
        for part in re.findall(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]+", query)
    ]
    expanded: list[str] = []
    for word in words:
        expanded.append(word)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", word):
            expanded.extend(word[index:index + 2] for index in range(len(word) - 1))
    return list(dict.fromkeys(expanded))


@dataclass
class RequirementRecord:
    path: Path
    metadata: dict[str, Any]
    data: dict[str, Any]
    text: str

    def public(self, vault: Path) -> dict[str, Any]:
        result = dict(self.data)
        result["_metadata"] = self.metadata
        result["_note"] = self.path.relative_to(vault).as_posix()
        return result


class RequirementStore:
    def __init__(self, vault: str | Path):
        self.vault = Path(vault).expanduser().resolve()
        self.atomic_dir = self.vault / "Requirements" / "Atomic"

    def records(self) -> list[RequirementRecord]:
        records: list[RequirementRecord] = []
        if not self.atomic_dir.exists():
            return records
        for path in sorted(self.atomic_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            match = BLOCK_RE.search(text)
            if not match:
                continue
            records.append(RequirementRecord(
                path=path,
                metadata=parse_frontmatter(text),
                data=json.loads(match.group(1)),
                text=text,
            ))
        return records

    def get(self, requirement_id: str) -> dict[str, Any] | None:
        wanted = requirement_id.lower()
        for record in self.records():
            if str(record.data.get("requirement_id", "")).lower() == wanted:
                return record.public(self.vault)
        return None

    def search(
        self,
        query: str,
        feature: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        ranked: list[tuple[int, RequirementRecord]] = []
        query_terms = _terms(query)
        for record in self.records():
            if feature and feature.lower() not in json.dumps(
                record.data.get("feature"), ensure_ascii=False
            ).lower():
                continue
            haystack = record.text.lower()
            requirement_id = str(record.data.get("requirement_id", "")).lower()
            score = sum(
                4 if term in requirement_id else 1
                for term in query_terms
                if term in haystack
            )
            if score:
                ranked.append((score, record))
        ranked.sort(
            key=lambda item: (-item[0], str(item[1].data.get("requirement_id")))
        )
        return [
            dict(record.public(self.vault), _score=score)
            for score, record in ranked[:max(1, min(limit, 100))]
        ]

    def list_features(self) -> list[str]:
        features: set[str] = set()
        for record in self.records():
            value = record.data.get("feature")
            if isinstance(value, list):
                features.update(str(item) for item in value)
            elif value:
                features.add(str(value))
        return sorted(features)

    def validate(self) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        seen: set[str] = set()
        files = sorted(self.atomic_dir.glob("*.md")) if self.atomic_dir.exists() else []
        for path in files:
            text = path.read_text(encoding="utf-8")
            metadata = parse_frontmatter(text)
            for field in sorted(REQUIRED_META - metadata.keys()):
                errors.append({
                    "file": path.name,
                    "error": f"missing frontmatter field: {field}",
                })
            match = BLOCK_RE.search(text)
            if not match:
                errors.append({
                    "file": path.name,
                    "error": "missing requirement-json block",
                })
                continue
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                errors.append({
                    "file": path.name,
                    "error": f"invalid requirement-json: {exc}",
                })
                continue
            requirement_id = str(data.get("requirement_id", ""))
            if not requirement_id:
                errors.append({
                    "file": path.name,
                    "error": "requirement-json missing requirement_id",
                })
            elif requirement_id in seen:
                errors.append({
                    "file": path.name,
                    "error": f"duplicate requirement_id: {requirement_id}",
                })
            seen.add(requirement_id)
            if metadata.get("requirement_id") != requirement_id:
                errors.append({
                    "file": path.name,
                    "error": "frontmatter and JSON IDs differ",
                })
        return {
            "valid": not errors,
            "vault": str(self.vault),
            "atomic_notes": len(files),
            "parsed_requirements": len(seen),
            "errors": errors,
        }


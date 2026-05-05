"""Structured local memory store for self-improving assistant behavior."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(bearer)\s+[a-z0-9._\-]+"),
    re.compile(r"\b\d{12,19}\b"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower()) if t}


def redact_sensitive(text: str) -> str:
    redacted = text or ""
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(lambda m: m.group(0).split(":", 1)[0].split("=", 1)[0] + ": [REDACTED]", redacted)
    return redacted[:1600]


@dataclass
class MemoryRecord:
    id: str
    kind: str
    text: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    confidence: float = 1.0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    used_count: int = 0
    helped_count: int = 0
    failed_count: int = 0
    fingerprint: str = ""

    def to_public(self, score: float | None = None) -> dict:
        data = asdict(self)
        if score is not None:
            data["_score"] = round(score, 4)
        return data


class LocalMemoryStore:
    """Compact JSON memory with dedupe, confidence, metadata, and ranking."""

    def __init__(self, path: str, max_records: int = 500):
        self.path = path
        self.max_records = max_records
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def remember(self, text: str, kind: str = "note", tags: list[str] | None = None,
                 metadata: dict | None = None, confidence: float = 1.0) -> dict:
        text = redact_sensitive((text or "").strip())
        if not text:
            return {"success": False, "error": "Empty memory text"}
        kind = self._clean_kind(kind)
        tags = self._clean_tags(tags or [])
        metadata = self._clean_metadata(metadata or {})
        fingerprint = self._fingerprint(kind, text, metadata)

        with self._lock:
            records = self._load_records()
            existing = next((r for r in records if r.fingerprint == fingerprint), None)
            if existing:
                existing.confidence = min(2.0, existing.confidence + 0.08)
                existing.updated_at = _now()
                existing.tags = sorted(set(existing.tags + tags))
                existing.metadata.update(metadata)
                self._save_records(records)
                return {"success": True, "memory": existing.to_public(), "deduped": True}

            record = MemoryRecord(
                id=self._new_id(kind, text),
                kind=kind,
                text=text,
                tags=tags,
                metadata=metadata,
                confidence=max(0.1, min(2.0, confidence)),
                fingerprint=fingerprint,
            )
            records.append(record)
            self._save_records(self._trim(records))
            return {"success": True, "memory": record.to_public(), "deduped": False}

    def recall(self, query: str, limit: int = 5, kinds: Iterable[str] | None = None,
               metadata: dict | None = None) -> list[dict]:
        query_tokens = _tokenize(query or "")
        kinds_set = {self._clean_kind(k) for k in kinds} if kinds else set()
        metadata = self._clean_metadata(metadata or {})
        with self._lock:
            records = self._load_records()
            scored = []
            for record in records:
                if kinds_set and record.kind not in kinds_set:
                    continue
                score = self._score(record, query_tokens, metadata)
                if score > 0:
                    scored.append((score, record))
            scored.sort(key=lambda item: item[0], reverse=True)
            selected = scored[:limit]
            selected_ids = {r.id for _, r in selected}
            if selected_ids:
                for record in records:
                    if record.id in selected_ids:
                        record.used_count += 1
                        record.updated_at = _now()
                self._save_records(records)
            return [record.to_public(score) for score, record in selected]

    def mark_helped(self, memory_id: str) -> dict:
        return self._adjust(memory_id, 0.12, helped=True)

    def mark_failed(self, memory_id: str) -> dict:
        return self._adjust(memory_id, -0.2, failed=True)

    def stats(self) -> dict:
        records = self._load_records()
        by_kind: dict[str, int] = {}
        for record in records:
            by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
        avg = sum(r.confidence for r in records) / len(records) if records else 0.0
        return {"records": len(records), "by_kind": by_kind, "avg_confidence": round(avg, 3), "path": self.path}

    def _score(self, record: MemoryRecord, query_tokens: set[str], metadata: dict) -> float:
        text_tokens = _tokenize(" ".join([record.text, record.kind, " ".join(record.tags)]))
        overlap = len(query_tokens & text_tokens)
        base = overlap / max(1, len(query_tokens)) if query_tokens else 0.25
        if query_tokens and overlap == 0:
            base = 0.0
        meta_boost = 0.0
        for key, value in metadata.items():
            stored = str(record.metadata.get(key, "")).lower()
            if stored and stored == str(value).lower():
                meta_boost += 0.35
        reliability = record.confidence + min(0.3, record.helped_count * 0.05) - min(0.5, record.failed_count * 0.1)
        return max(0.0, base * reliability + meta_boost)

    def _adjust(self, memory_id: str, delta: float, helped: bool = False, failed: bool = False) -> dict:
        with self._lock:
            records = self._load_records()
            for record in records:
                if record.id == memory_id:
                    record.confidence = max(0.1, min(2.0, record.confidence + delta))
                    record.updated_at = _now()
                    record.helped_count += 1 if helped else 0
                    record.failed_count += 1 if failed else 0
                    self._save_records(records)
                    return {"success": True, "memory": record.to_public()}
        return {"success": False, "error": f"Memory not found: {memory_id}"}

    def _load_records(self) -> list[MemoryRecord]:
        try:
            if not os.path.exists(self.path):
                return []
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            records = raw.get("records", raw if isinstance(raw, list) else [])
            return [self._from_dict(item) for item in records if isinstance(item, dict)]
        except Exception:
            return []

    def _save_records(self, records: list[MemoryRecord]):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "updated_at": _now(), "records": [asdict(r) for r in records]}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def _trim(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        if len(records) <= self.max_records:
            return records
        records.sort(key=lambda r: (r.confidence, r.used_count, r.updated_at), reverse=True)
        return records[: self.max_records]

    @staticmethod
    def _from_dict(item: dict) -> MemoryRecord:
        return MemoryRecord(
            id=str(item.get("id") or item.get("created_at") or _now()),
            kind=str(item.get("kind", "note")),
            text=str(item.get("text", "")),
            tags=list(item.get("tags", [])),
            metadata=dict(item.get("metadata", {})),
            confidence=float(item.get("confidence", 1.0)),
            created_at=str(item.get("created_at", _now())),
            updated_at=str(item.get("updated_at", item.get("created_at", _now()))),
            used_count=int(item.get("used_count", 0)),
            helped_count=int(item.get("helped_count", 0)),
            failed_count=int(item.get("failed_count", 0)),
            fingerprint=str(item.get("fingerprint") or ""),
        )

    @staticmethod
    def _fingerprint(kind: str, text: str, metadata: dict) -> str:
        app = str(metadata.get("app", "")).lower()
        action = str(metadata.get("action", "")).lower()
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(f"{kind}|{app}|{action}|{normalized}".encode("utf-8")).hexdigest()

    @staticmethod
    def _new_id(kind: str, text: str) -> str:
        return f"mem_{hashlib.md5(f'{kind}:{text}:{_now()}'.encode('utf-8')).hexdigest()[:12]}"

    @staticmethod
    def _clean_kind(kind: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]+", "_", (kind or "note").lower()).strip("_") or "note"

    @staticmethod
    def _clean_tags(tags: list[str]) -> list[str]:
        cleaned = []
        for tag in tags[:12]:
            value = re.sub(r"[^a-zA-Z0-9_]+", "_", str(tag).lower()).strip("_")
            if value:
                cleaned.append(value)
        return sorted(set(cleaned))

    @staticmethod
    def _clean_metadata(metadata: dict) -> dict:
        allowed = {}
        for key in ("app", "window", "action", "domain", "tool", "task"):
            value = metadata.get(key)
            if value:
                allowed[key] = str(value)[:160]
        return allowed

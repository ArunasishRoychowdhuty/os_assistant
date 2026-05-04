"""
Self-Enrollment Engine v2 — AI-Written Lessons + Semantic Search + Confidence Scoring

Improvements over v1:
1. AI (GPT/Claude) writes the lesson — not hardcoded templates
2. ChromaDB proper EmbeddingFunction API (fully offline)
3. Lesson confidence scoring — tracks effectiveness over time
4. Bi-directional learning — lessons get stronger or weaker with usage
"""
import os
import json
import math
import struct
import hashlib
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any

try:
    import chromadb
    from chromadb import EmbeddingFunction, Documents, Embeddings
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from config import Config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Offline Embedder — proper ChromaDB 1.5+ API
# ═══════════════════════════════════════════════════════════

class _OfflineHashEmbedder(EmbeddingFunction if HAS_CHROMADB else object):
    """
    Fully offline n-gram hash embedder.
    Implements the full ChromaDB 1.5+ EmbeddingFunction protocol.
    """

    def __init__(self, dim: int = 128):
        self._dim = dim

    def __call__(self, input: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in input]

    @staticmethod
    def name() -> str:
        return "offline_hash_embedder_v2"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self._dim}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "_OfflineHashEmbedder":
        return _OfflineHashEmbedder(dim=config.get("dim", 128))

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self._dim
        text = text.lower()[:1024]
        # Unigrams
        for ch in text:
            h = struct.unpack("I", hashlib.md5(ch.encode()).digest()[:4])[0]
            vec[h % self._dim] += 0.5
        # Bigrams
        for i in range(len(text) - 1):
            bg = text[i:i+2]
            h = struct.unpack("I", hashlib.md5(bg.encode()).digest()[:4])[0]
            vec[h % self._dim] += 1.0
        # Trigrams
        for i in range(len(text) - 2):
            tg = text[i:i+3]
            h = struct.unpack("I", hashlib.md5(tg.encode()).digest()[:4])[0]
            vec[h % self._dim] += 0.8
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]


# ═══════════════════════════════════════════════════════════
# Self-Enrollment Engine
# ═══════════════════════════════════════════════════════════

class SelfEnrollmentEngine:
    """
    Converts failures into AI-written permanent lessons.

    Key design:
    - Errors expire (3 days) → Lessons are permanent
    - Lessons are written by AI (context-aware, not templates)
    - Lessons have confidence scores — good lessons get stronger
    - ChromaDB for semantic search, JSON as offline fallback
    """

    CATEGORY_ACTION_FAIL = "action_failure"
    CATEGORY_COORD_MISS  = "coordinate_miss"
    CATEGORY_WRONG_STEP  = "wrong_approach"
    CATEGORY_TIMEOUT     = "timeout"
    CATEGORY_BLOCKED     = "safety_blocked"
    CATEGORY_SCREEN_MISS = "screen_no_change"
    CATEGORY_TASK_FAIL   = "task_failure"

    def __init__(self, vision_ai=None):
        """
        Args:
            vision_ai: VisionAI instance for AI-written lessons.
                       If None, falls back to smart templates.
        """
        self._vision = vision_ai
        self._embedder = _OfflineHashEmbedder()
        self._client = None
        self._lessons = None
        self._improvements = None
        self._json_path = os.path.join(Config.MEMORY_DIR, "lessons_db.json")
        self._lock = threading.Lock()

        db_path = os.path.join(Config.MEMORY_DIR, "vectordb")
        os.makedirs(db_path, exist_ok=True)

        if HAS_CHROMADB:
            try:
                self._client = chromadb.PersistentClient(
                    path=db_path,
                    settings=Settings(anonymized_telemetry=False),
                )
                self._lessons = self._client.get_or_create_collection(
                    name="lessons_v2",
                    embedding_function=self._embedder,
                    metadata={"hnsw:space": "cosine"},
                )
                self._improvements = self._client.get_or_create_collection(
                    name="improvements_v2",
                    embedding_function=self._embedder,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"[SelfEnroll] ChromaDB ready. Lessons: {self._lessons.count()}")
            except Exception as e:
                logger.warning(f"[SelfEnroll] ChromaDB failed, using JSON: {e}")
                self._client = None

    @property
    def available(self) -> bool:
        return True  # JSON fallback always works

    # ── Core Learning ───────────────────────────────────────

    def learn_from_error(self, action: dict, error: str,
                         task: str = "", screenshot_b64: str = "") -> dict:
        """Learn from a single action failure — AI writes the lesson."""
        category = self._categorize_error(action, error)

        # Try AI-written lesson first
        lesson_text = self._ai_write_lesson(
            context=f"Task: {task}\nAction: {json.dumps(action)}\nError: {error}",
            prompt="Analyze this action failure. In 2-3 sentences: (1) Why did it fail? (2) What should be done differently next time? Be specific and practical.",
        )
        if not lesson_text:
            lesson_text = self._template_lesson(action, error, category)

        lesson = {
            "title": f"{action.get('action','?')} failed — {error[:50]}",
            "category": category,
            "action": action,
            "task": task,
            "error": error,
            "do_differently": lesson_text,
            "confidence": 1.0,        # Starts at 1.0
            "used_count": 0,          # How many times retrieved
            "helped_count": 0,        # How many times it actually helped
            "timestamp": datetime.now().isoformat(),
            "permanent": True,
            "ai_written": bool(lesson_text and self._vision),
        }

        lesson_id = self._save_lesson(lesson)
        return {"lesson_id": lesson_id, "lesson": lesson}

    def learn_from_task_failure(self, task: str, steps: list,
                                errors: list[str]) -> dict:
        """Analyze full task failure — AI writes strategic lesson."""
        if not errors:
            return {}

        step_summary = " → ".join(
            f"{s.get('action',{}).get('action','?')}" for s in steps[-5:]
        )
        context = (
            f"Task: {task}\n"
            f"Steps taken: {step_summary}\n"
            f"Errors: {'; '.join(errors[:3])}"
        )

        lesson_text = self._ai_write_lesson(
            context=context,
            prompt=(
                "Analyze this failed task. In 3-4 sentences: "
                "(1) What was the root cause of failure? "
                "(2) What steps were wrong? "
                "(3) What is the better strategy next time? "
                "Be specific and actionable."
            ),
        )
        if not lesson_text:
            lesson_text = self._template_task_lesson(task, errors, steps)

        lesson = {
            "title": f"Task failed: {task[:60]}",
            "category": self.CATEGORY_TASK_FAIL,
            "task": task,
            "steps_taken": step_summary,
            "errors": errors[:3],
            "do_differently": lesson_text,
            "confidence": 1.0,
            "used_count": 0,
            "helped_count": 0,
            "timestamp": datetime.now().isoformat(),
            "permanent": True,
            "ai_written": bool(lesson_text and self._vision),
        }

        lesson_id = self._save_lesson(lesson)
        self._log_improvement(task, lesson)
        return {"lesson_id": lesson_id, "lesson": lesson}

    def learn_screen_no_change(self, action: dict, task: str = "") -> dict:
        """Learn when screen didn't react — AI explains why."""
        context = f"Task: {task}\nAction that had no visual effect: {json.dumps(action)}"
        lesson_text = self._ai_write_lesson(
            context=context,
            prompt="This action executed successfully but the screen didn't change. In 2 sentences: why might this happen and what should be tried instead?",
        )
        if not lesson_text:
            lesson_text = (
                "Action had no visual effect. Try: double-click, keyboard shortcut, "
                "ensure window focus, or scroll to reveal the element."
            )

        lesson = {
            "title": f"Screen unchanged after {action.get('action','?')}",
            "category": self.CATEGORY_SCREEN_MISS,
            "action": action,
            "task": task,
            "do_differently": lesson_text,
            "confidence": 1.0,
            "used_count": 0,
            "helped_count": 0,
            "timestamp": datetime.now().isoformat(),
            "permanent": True,
            "ai_written": bool(lesson_text and self._vision),
        }

        lesson_id = self._save_lesson(lesson)
        return {"lesson_id": lesson_id, "lesson": lesson}

    # ── Confidence Scoring ──────────────────────────────────

    def mark_lesson_helped(self, lesson_id: str):
        """Call this when a lesson's advice was followed and succeeded."""
        self._update_confidence(lesson_id, delta=+0.1, helped=True)

    def mark_lesson_failed(self, lesson_id: str):
        """Call this when a lesson's advice was followed but still failed."""
        self._update_confidence(lesson_id, delta=-0.15, helped=False)

    def _update_confidence(self, lesson_id: str, delta: float, helped: bool):
        """Update lesson confidence score."""
        try:
            db = self._json_load()
            if lesson_id in db:
                lesson = db[lesson_id]
                lesson["confidence"] = max(0.1, min(2.0,
                    lesson.get("confidence", 1.0) + delta))
                lesson["used_count"] = lesson.get("used_count", 0) + 1
                if helped:
                    lesson["helped_count"] = lesson.get("helped_count", 0) + 1
                self._json_save(db)
        except Exception as e:
            logger.warning(f"Confidence update failed: {e}")

    # ── Retrieve Lessons ────────────────────────────────────

    def get_relevant_lessons(self, query: str, n: int = 3) -> list[dict]:
        """Get most relevant lessons, sorted by confidence × relevance."""
        if self._client and self._lessons:
            try:
                count = self._lessons.count()
                if count > 0:
                    results = self._lessons.query(
                        query_texts=[query],
                        n_results=min(n * 2, count),
                    )
                    lessons = self._parse(results)
                    # Re-rank by confidence
                    for l in lessons:
                        dist = l.get("_distance", 1.0) or 1.0
                        l["_score"] = l.get("confidence", 1.0) / (dist + 0.01)
                    lessons.sort(key=lambda x: x.get("_score", 0), reverse=True)
                    return lessons[:n]
            except Exception as e:
                logger.warning(f"ChromaDB query failed: {e}")
        return self._json_search(query, n)

    def get_lessons_for_action(self, action_type: str, n: int = 2) -> list[dict]:
        return self.get_relevant_lessons(f"action {action_type} failed error", n)

    def build_context_hint(self, task: str, action_type: str = "") -> str:
        """Build AI context hint string from relevant lessons."""
        hints = []

        task_lessons = self.get_relevant_lessons(task, n=2)
        for l in task_lessons:
            conf = l.get("confidence", 1.0)
            diff = l.get("do_differently", "")
            if diff and conf > 0.3:
                ai_tag = "🤖" if l.get("ai_written") else "📋"
                hints.append(
                    f"[LESSON {ai_tag} conf={conf:.1f}] {l.get('title','?')}: {diff}"
                )

        if action_type:
            action_lessons = self.get_lessons_for_action(action_type, n=1)
            for l in action_lessons:
                conf = l.get("confidence", 1.0)
                diff = l.get("do_differently", "")
                if diff and conf > 0.3:
                    hints.append(f"[LESSON/{action_type}] {diff}")

        return "\n".join(hints)

    # ── Stats & UI Data ─────────────────────────────────────

    def get_stats(self) -> dict:
        lessons = self._json_load()
        ai_written = sum(1 for l in lessons.values() if l.get("ai_written"))
        total = len(lessons)
        avg_conf = (sum(l.get("confidence", 1.0) for l in lessons.values()) / total
                    if total else 0)
        chroma_count = 0
        if self._client and self._lessons:
            try:
                chroma_count = self._lessons.count()
            except Exception:
                pass
        return {
            "available": True,
            "mode": "chromadb+json" if self._client else "json_only",
            "lessons_total": total,
            "lessons_chromadb": chroma_count,
            "ai_written": ai_written,
            "template_written": total - ai_written,
            "avg_confidence": round(avg_conf, 2),
        }

    def get_all_lessons(self, sort_by: str = "timestamp") -> list[dict]:
        """Get all lessons for UI display, with confidence scores."""
        db = self._json_load()
        lessons = list(db.items())
        lessons_list = []
        for lid, l in lessons:
            l["_id"] = lid
            lessons_list.append(l)

        if sort_by == "confidence":
            lessons_list.sort(key=lambda x: x.get("confidence", 1.0), reverse=True)
        elif sort_by == "used":
            lessons_list.sort(key=lambda x: x.get("used_count", 0), reverse=True)
        else:  # timestamp
            lessons_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return lessons_list

    def delete_lesson(self, lesson_id: str):
        """Delete a specific lesson (user-controlled)."""
        db = self._json_load()
        if lesson_id in db:
            del db[lesson_id]
            self._json_save(db)
        if self._client and self._lessons:
            try:
                self._lessons.delete(ids=[lesson_id])
            except Exception:
                pass

    def purge_low_confidence(self, threshold: float = 0.2):
        """Auto-remove lessons that consistently didn't help."""
        db = self._json_load()
        to_delete = [lid for lid, l in db.items()
                     if l.get("confidence", 1.0) < threshold
                     and l.get("used_count", 0) >= 3]
        for lid in to_delete:
            self.delete_lesson(lid)
        return len(to_delete)

    # ── AI Lesson Writing ───────────────────────────────────

    def _ai_write_lesson(self, context: str, prompt: str) -> str:
        """Ask AI to write a lesson. Falls back to template if AI unavailable."""
        if not self._vision:
            return ""
        try:
            # Use a minimal, fast AI call — no screenshot needed
            result = self._vision.analyze_screen(
                screenshot_b64=None,
                user_task=f"{prompt}\n\nContext:\n{context}\n\nRespond with ONLY the lesson text, no JSON, no action.",
                context="You are analyzing agent failures to extract learning lessons.",
                conversation_history=[],
                text_only=True,  # No image needed
            )
            lesson = result.get("thought", "").strip()
            # Clean up — remove JSON artifacts if any
            if lesson.startswith("{") or not lesson:
                return ""
            return lesson[:500]
        except Exception as e:
            logger.warning(f"AI lesson writing failed: {e}")
            return ""

    # ── Template Fallback ───────────────────────────────────

    def _template_lesson(self, action: dict, error: str, category: str) -> str:
        atype = action.get("action", "")
        if category == self.CATEGORY_COORD_MISS:
            return (f"Coordinates went out of screen bounds. "
                    f"Always verify coordinates are within screen resolution "
                    f"before executing. Use visual element search instead of hardcoded positions.")
        if category == self.CATEGORY_TIMEOUT:
            return (f"Operation timed out. Add a wait step before this action, "
                    f"or check if the target application is still responding.")
        if category == self.CATEGORY_SCREEN_MISS:
            return (f"Action had no visual effect. Try: double-click, "
                    f"keyboard shortcut equivalent, or ensure window is focused first.")
        if atype in ("click", "double_click"):
            return (f"Click on target failed: '{error[:60]}'. "
                    f"Try scrolling to make element visible, use keyboard navigation, "
                    f"or verify the element is enabled and not obscured.")
        if atype == "type_text":
            return (f"Text input failed. Click the target field first to focus it, "
                    f"then type. Check if the field has input restrictions.")
        if atype == "hotkey":
            keys = action.get("keys", [])
            return (f"Hotkey {keys} didn't work. "
                    f"Verify the shortcut is correct for this application version. "
                    f"Try pressing keys individually or use menu navigation instead.")
        return (f"Action '{atype}' failed: {error[:80]}. "
                f"Try an alternative approach or decompose into smaller steps.")

    def _template_task_lesson(self, task: str, errors: list, steps: list) -> str:
        advice = []
        if any("coordinate" in e.lower() for e in errors):
            advice.append("Use visual element detection instead of fixed coordinates.")
        if any("timeout" in e.lower() for e in errors):
            advice.append("Add wait steps between actions.")
        if any("focus" in e.lower() or "screen" in e.lower() for e in errors):
            advice.append("Ensure window focus before each interaction.")
        if not advice:
            advice.append("Decompose the task into smaller verified steps.")
        return f"Task '{task[:40]}' failed. Strategy for next time: " + " ".join(advice)

    def _categorize_error(self, action: dict, error: str) -> str:
        e = error.lower()
        atype = action.get("action", "")
        if "coordinate" in e or "bounds" in e or "screen" in e:
            return self.CATEGORY_COORD_MISS
        if "timeout" in e or "timed out" in e:
            return self.CATEGORY_TIMEOUT
        if "blocked" in e or "denied" in e:
            return self.CATEGORY_BLOCKED
        if atype in ("click", "right_click", "double_click"):
            return self.CATEGORY_ACTION_FAIL
        return self.CATEGORY_WRONG_STEP

    # ── Persistence ─────────────────────────────────────────

    def _save_lesson(self, lesson: dict) -> str:
        lesson_id = hashlib.md5(
            f"{lesson.get('title','')}_{lesson.get('timestamp','')}".encode()
        ).hexdigest()

        # Always save to JSON (permanent, offline)
        db = self._json_load()
        db[lesson_id] = lesson
        self._json_save(db)

        # Also save to ChromaDB if available (for semantic search)
        if self._client and self._lessons:
            try:
                search_text = (
                    f"{lesson.get('title','')} {lesson.get('task','')} "
                    f"{lesson.get('error','')} {lesson.get('do_differently','')}"
                )
                self._lessons.upsert(
                    ids=[lesson_id],
                    documents=[search_text],
                    metadatas=[{
                        "lesson_id": lesson_id,
                        "title": lesson.get("title", "")[:200],
                        "category": lesson.get("category", ""),
                        "confidence": str(lesson.get("confidence", 1.0)),
                        "timestamp": lesson.get("timestamp", ""),
                    }],
                )
            except Exception as e:
                logger.warning(f"ChromaDB lesson save failed: {e}")

        return lesson_id

    def _log_improvement(self, task: str, lesson: dict):
        if not self._client or not self._improvements:
            return
        try:
            log_id = hashlib.md5(
                f"{task}_{datetime.now().isoformat()}".encode()
            ).hexdigest()
            self._improvements.upsert(
                ids=[log_id],
                documents=[f"task improvement: {task}"],
                metadatas=[{"task": task[:200], "timestamp": datetime.now().isoformat()}],
            )
        except Exception as e:
            logger.warning(f"Improvement log failed: {e}")

    def _json_load(self) -> dict:
        with self._lock:
            if not os.path.exists(self._json_path):
                return {}
            try:
                with open(self._json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def _json_save(self, db: dict):
        with self._lock:
            try:
                tmp_path = self._json_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._json_path)
            except Exception as e:
                logger.error(f"JSON save failed: {e}")

    def _json_search(self, query: str, n: int = 3) -> list[dict]:
        """Keyword + confidence ranked search on JSON store."""
        lessons = self._json_load()
        query_words = set(query.lower().split())
        scored = []
        for lid, l in lessons.items():
            text = " ".join([
                l.get("title", ""), l.get("task", ""),
                l.get("do_differently", ""), l.get("error", ""),
            ]).lower()
            keyword_score = sum(1 for w in query_words if w in text)
            if keyword_score > 0:
                conf = l.get("confidence", 1.0)
                final_score = keyword_score * conf
                l["_id"] = lid
                scored.append((final_score, l))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [l for _, l in scored[:n]]

    @staticmethod
    def _parse(results) -> list[dict]:
        parsed = []
        if not results or not results.get("documents"):
            return parsed
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            dist = results["distances"][0][i] if results.get("distances") else 1.0
            parsed.append({
                "_id": meta.get("lesson_id", ""),
                "title": meta.get("title", doc[:80]),
                "category": meta.get("category", ""),
                "confidence": float(meta.get("confidence", "1.0")),
                "_distance": dist,
                "do_differently": "",  # Will be loaded from JSON
            })
        return parsed

"""
FEDDA Brain Memory Store — in-memory + SQLite persistence
"""
import sqlite3
from pathlib import Path
from typing import Dict, List
from brain_models import MemoryEntry, TaskEntry, ProjectEntry, AssetEntry
from datetime import datetime
import uuid

_DB_PATH = Path(__file__).parent / "brain_db.sqlite"

class BrainMemoryStore:
    def __init__(self):
        self.memories: Dict[str, MemoryEntry] = {}
        self.tasks: Dict[str, TaskEntry] = {}
        self.projects: Dict[str, ProjectEntry] = {}
        self.assets: Dict[str, AssetEntry] = {}
        self._conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        self._init_db()
        self._load_from_db()

    def _init_db(self):
        c = self._conn
        c.execute("""CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            user_id TEXT,
            kind TEXT,
            content TEXT,
            summary TEXT,
            tags TEXT,
            project_id TEXT,
            pinned INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            version INTEGER DEFAULT 1,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            status TEXT,
            tags TEXT,
            project_id TEXT,
            archived INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            tags TEXT,
            archived INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            tags TEXT,
            deleted INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        c.commit()

    def _load_from_db(self):
        import json as _json
        cur = self._conn.execute("SELECT * FROM memories WHERE deleted=0")
        for row in cur.fetchall():
            (memory_id, user_id, kind, content, summary, tags_json,
             project_id, pinned, archived, deleted, deleted_at, version, created_at) = row
            try:
                tags = _json.loads(tags_json) if tags_json else []
                entry = MemoryEntry(
                    memory_id=memory_id,
                    user_id=user_id or "",
                    kind=kind or "note",
                    content=content or "",
                    summary=summary,
                    tags=tags,
                    project_id=project_id,
                    pinned=bool(pinned),
                    archived=bool(archived),
                    deleted=bool(deleted),
                    version=version or 1,
                    created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
                )
                self.memories[memory_id] = entry
            except Exception:
                pass

    # --- Memory Operations ---
    def add_memory(self, entry: MemoryEntry):
        import json as _json
        self.memories[entry.memory_id] = entry
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO memories
                   (memory_id, user_id, kind, content, summary, tags, project_id,
                    pinned, archived, deleted, deleted_at, version, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (entry.memory_id, entry.user_id, entry.kind, entry.content,
                 entry.summary, _json.dumps(entry.tags), entry.project_id,
                 int(entry.pinned), int(entry.archived), int(entry.deleted),
                 str(entry.deleted_at) if getattr(entry, "deleted_at", None) else None,
                 entry.version,
                 str(entry.created_at))
            )
            self._conn.commit()
        except Exception:
            pass
        return entry

    def search_memory(self, user_id: str, query: str = None, kind: str = None, tags: List[str] = None, project_id: str = None, archived: bool = None, pinned: bool = None, limit: int = 20):
        results = [m for m in self.memories.values() if m.user_id == user_id and not m.deleted]
        if kind:
            results = [m for m in results if m.kind == kind]
        if tags:
            results = [m for m in results if any(tag in m.tags for tag in tags)]
        if project_id:
            results = [m for m in results if m.project_id == project_id]
        if archived is not None:
            results = [m for m in results if m.archived == archived]
        if pinned is not None:
            results = [m for m in results if m.pinned == pinned]
        if query:
            results = [m for m in results if query.lower() in m.content.lower() or (m.summary and query.lower() in m.summary.lower())]
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results[:limit]

    def update_memory(self, user_id: str, memory_id: str, **fields):
        entry = self.memories.get(memory_id)
        if not entry or entry.user_id != user_id or entry.deleted:
            return None
        for k, v in fields.items():
            setattr(entry, k, v)
        entry.version += 1
        return entry

    def delete_memory(self, user_id: str, memory_id: str, hard_delete: bool = False):
        entry = self.memories.get(memory_id)
        if not entry or entry.user_id != user_id:
            return False
        if hard_delete:
            del self.memories[memory_id]
        else:
            entry.deleted = True
            entry.deleted_at = datetime.utcnow()
        return True

    # --- Task Operations (similar pattern) ---
    def add_task(self, entry: TaskEntry):
        self.tasks[entry.task_id] = entry
        return entry

    def update_task(self, user_id: str, task_id: str, **fields):
        entry = self.tasks.get(task_id)
        if not entry or entry.user_id != user_id or entry.deleted:
            return None
        for k, v in fields.items():
            setattr(entry, k, v)
        return entry

    def delete_task(self, user_id: str, task_id: str, hard_delete: bool = False):
        entry = self.tasks.get(task_id)
        if not entry or entry.user_id != user_id:
            return False
        if hard_delete:
            del self.tasks[task_id]
        else:
            entry.deleted = True
            entry.deleted_at = datetime.utcnow()
        return True

    def list_tasks(self, user_id: str, status: str = None, project_id: str = None, tags: List[str] = None, archived: bool = None, limit: int = 20):
        results = [t for t in self.tasks.values() if t.user_id == user_id and not t.deleted]
        if status:
            results = [t for t in results if t.status == status]
        if project_id:
            results = [t for t in results if t.project_id == project_id]
        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]
        if archived is not None:
            results = [t for t in results if t.archived == archived]
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results[:limit]

    # --- Project Operations ---
    def add_project(self, entry: ProjectEntry):
        self.projects[entry.project_id] = entry
        return entry

    def update_project(self, user_id: str, project_id: str, **fields):
        entry = self.projects.get(project_id)
        if not entry or entry.user_id != user_id or entry.deleted:
            return None
        for k, v in fields.items():
            setattr(entry, k, v)
        return entry

    def delete_project(self, user_id: str, project_id: str, hard_delete: bool = False):
        entry = self.projects.get(project_id)
        if not entry or entry.user_id != user_id:
            return False
        if hard_delete:
            del self.projects[project_id]
        else:
            entry.deleted = True
            entry.deleted_at = datetime.utcnow()
        return True

    def list_projects(self, user_id: str, archived: bool = None, tags: List[str] = None, limit: int = 20):
        results = [p for p in self.projects.values() if p.user_id == user_id and not p.deleted]
        if archived is not None:
            results = [p for p in results if p.archived == archived]
        if tags:
            results = [p for p in results if any(tag in p.tags for tag in tags)]
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results[:limit]

    # --- Asset Operations ---
    def add_asset(self, entry: AssetEntry):
        self.assets[entry.asset_id] = entry
        return entry

    def list_assets(self, user_id: str, type: str = None, tags: List[str] = None, limit: int = 20):
        results = [a for a in self.assets.values() if a.user_id == user_id and not a.deleted]
        if type:
            results = [a for a in results if a.type == type]
        if tags:
            results = [a for a in results if any(tag in a.tags for tag in tags)]
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[:limit]

# Singleton for demo
brain_store = BrainMemoryStore()

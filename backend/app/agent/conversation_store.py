"""
Per-dataset conversation history, mirroring storage.py's DatasetStore shape
(in-memory, TTL-evicted, thread-safe). Kept as a separate store rather than
bolted onto DatasetRecord — a dataset can outlive many conversations about
it, and the two have different natural lifecycles.
"""
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..config import settings


@dataclass
class ConversationRecord:
    dataset_id: str
    messages: list[dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationStore:
    def __init__(self, ttl_hours: float = settings.DATASET_TTL_HOURS):
        self._store: dict[str, ConversationRecord] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(hours=ttl_hours)

    def get_history(self, dataset_id: str) -> list[dict]:
        with self._lock:
            self._evict_expired_locked()
            record = self._store.get(dataset_id)
            return list(record.messages) if record else []

    def save_history(self, dataset_id: str, messages: list[dict]) -> None:
        with self._lock:
            self._evict_expired_locked()
            self._store[dataset_id] = ConversationRecord(
                dataset_id=dataset_id, messages=messages, updated_at=datetime.now(timezone.utc)
            )

    def clear(self, dataset_id: str) -> None:
        with self._lock:
            self._store.pop(dataset_id, None)

    def _evict_expired_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._store.items() if now - v.updated_at > self._ttl]
        for k in expired:
            del self._store[k]


conversation_store = ConversationStore()

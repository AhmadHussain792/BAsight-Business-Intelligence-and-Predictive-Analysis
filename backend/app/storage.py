# in-memory dataset store, keyed by dataset_id to prevent concurrent users/tabs from clobbering each other's data.

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import settings
from .models import ColumnSchema, DataQualityReport


@dataclass
class DatasetRecord:
    dataset_id: str
    filename: str
    df: pd.DataFrame
    columns: list[ColumnSchema]
    core_columns: dict[str, str]
    data_quality: DataQualityReport
    created_at: datetime


class DatasetNotFoundError(LookupError):
    pass


class DatasetStore:
    def __init__(self, ttl_hours: float = settings.DATASET_TTL_HOURS):
        self._store: dict[str, DatasetRecord] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(hours=ttl_hours)

    def put(
        self,
        filename: str,
        df: pd.DataFrame,
        columns: list[ColumnSchema],
        core_columns: dict[str, str],
        data_quality: DataQualityReport,
    ) -> str:
        dataset_id = str(uuid.uuid4())
        record = DatasetRecord(
            dataset_id=dataset_id,
            filename=filename,
            df=df,
            columns=columns,
            core_columns=core_columns,
            data_quality=data_quality,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._evict_expired_locked()
            self._store[dataset_id] = record
        return dataset_id

    def get(self, dataset_id: str) -> DatasetRecord:
        with self._lock:
            self._evict_expired_locked()
            record = self._store.get(dataset_id)
        if record is None:
            raise DatasetNotFoundError(
                f"Dataset '{dataset_id}' was not found. It may have expired "
                f"(datasets are kept for {settings.DATASET_TTL_HOURS} hours) or never existed."
            )
        return record

    def delete(self, dataset_id: str) -> None:
        with self._lock:
            if dataset_id not in self._store:
                raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.")
            del self._store[dataset_id]

    def list_all(self) -> list[DatasetRecord]:
        with self._lock:
            self._evict_expired_locked()
            return list(self._store.values())

    def _evict_expired_locked(self) -> None:
        # Must be called while holding self._lock
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._store.items() if now - v.created_at > self._ttl]
        for k in expired:
            del self._store[k]


# single process-wide store instance, imported by the routes.
dataset_store = DatasetStore()

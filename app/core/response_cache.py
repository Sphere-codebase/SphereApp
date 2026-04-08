"""Small in-process TTL cache for read-heavy response payloads."""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
CacheKey = tuple[Hashable, ...]


@dataclass
class _CacheEntry:
    expires_at: float
    value: object


class TTLResponseCache:
    def __init__(self) -> None:
        self._entries: dict[CacheKey, _CacheEntry] = {}
        self._locks: dict[CacheKey, threading.Lock] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: CacheKey, ttl_seconds: float, loader: Callable[[], T]) -> T:
        ttl = float(ttl_seconds)
        if ttl <= 0:
            return loader()

        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                return copy.deepcopy(entry.value)  # type: ignore[return-value]
            key_lock = self._locks.setdefault(key, threading.Lock())

        with key_lock:
            now = time.monotonic()
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > now:
                    return copy.deepcopy(entry.value)  # type: ignore[return-value]
            value = loader()
            with self._lock:
                self._entries[key] = _CacheEntry(
                    expires_at=time.monotonic() + ttl,
                    value=copy.deepcopy(value),
                )
            return copy.deepcopy(value)

    def invalidate_prefix(self, prefix: CacheKey) -> None:
        with self._lock:
            keys_to_delete = [key for key in self._entries if key[: len(prefix)] == prefix]
            for key in keys_to_delete:
                self._entries.pop(key, None)


auth_me_response_cache = TTLResponseCache()
admin_ref_response_cache = TTLResponseCache()
chat_sessions_response_cache = TTLResponseCache()


def chat_session_messages_cache_key(
    *,
    user_id: int,
    clinic_id: int,
    role: str,
    session_id: int,
) -> CacheKey:
    return (
        "chat_sessions",
        user_id,
        clinic_id,
        role,
        "messages",
        session_id,
    )


def invalidate_chat_session_messages_cache(
    *,
    user_id: int,
    clinic_id: int,
    role: str,
    session_id: int,
) -> None:
    chat_sessions_response_cache.invalidate_prefix(
        chat_session_messages_cache_key(
            user_id=user_id,
            clinic_id=clinic_id,
            role=role,
            session_id=session_id,
        )
    )

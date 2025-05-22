
from __future__ import annotations

from typing import List, Generic, TypeVar, Iterable, Iterator, Optional
from threading import Lock

T = TypeVar('T')


class SafeList(Generic[T]):
    """A thread-safe list implementation for multithread tests."""

    def __init__(self, initial_items: Optional[Iterable[T]] = None):
        self._lock = Lock()
        self._items: List[T] = list(initial_items or [])

    def append(self, item: T) -> None:
        with self._lock:
            self._items.append(item)

    def extend(self, items: Iterable[T]) -> None:
        with self._lock:
            self._items.extend(items)

    def index(self, item: T) -> int:
        with self._lock:
            return self._items.index(item)

    def __getitem__(self, index: int) -> T:
        with self._lock:
            return self._items[index]

    def __contains__(self, item: T) -> bool:
        with self._lock:
            return item in self._items

    def __iter__(self) -> Iterator[T]:
        with self._lock:
            # Return a copy to avoid iteration issues if the list changes
            return iter(self._items.copy())

    def to_list(self) -> List[T]:
        with self._lock:
            return self._items.copy()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

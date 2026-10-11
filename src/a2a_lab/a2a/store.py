"""Bound retained SDK tasks while preserving native owner-scoped storage."""

import asyncio

from a2a.server.context import ServerCallContext
from a2a.server.tasks import InMemoryTaskStore, TaskStore
from a2a.types import ListTasksRequest, ListTasksResponse, Task
from a2a.utils.errors import InternalError


class BoundedTaskStore(TaskStore):
    """Delegate schema, copying, filtering, and pagination to the SDK."""

    def __init__(self, maximum: int) -> None:
        self._inner = InMemoryTaskStore()
        self._maximum = maximum
        self._keys: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()

    async def save(self, task: Task, context: ServerCallContext) -> None:
        """Refuse a new record at capacity without evicting active tasks."""
        key = (context.user.user_name, task.id)
        async with self._lock:
            if key not in self._keys and len(self._keys) >= self._maximum:
                raise InternalError(message="Retained task capacity reached.")
            await self._inner.save(task, context)
            self._keys.add(key)

    async def get(self, task_id: str, context: ServerCallContext) -> Task | None:
        """Return only records in the SDK identity's scope."""
        return await self._inner.get(task_id, context)

    async def list(self, params: ListTasksRequest, context: ServerCallContext) -> ListTasksResponse:
        """Use SDK ownership filtering and bounded page semantics."""
        return await self._inner.list(params, context)

    async def delete(self, task_id: str, context: ServerCallContext) -> None:
        """Remove only an owned record and its capacity entry."""
        async with self._lock:
            await self._inner.delete(task_id, context)
            self._keys.discard((context.user.user_name, task_id))

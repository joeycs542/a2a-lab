"""Bounded, owner-authorized discovery traces alongside SDK tasks."""

from contextvars import ContextVar

from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskStore
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a_lab.a2a.identity import LabUser

captured_trace: ContextVar[list[str] | None] = ContextVar("captured_trace", default=None)


class TraceStore:
    """Retain at most one finite trace per retained SDK task, never raw input."""

    def __init__(self, tasks: TaskStore, capacity: int) -> None:
        self.tasks = tasks
        self.capacity = capacity
        self.records: dict[str, list[str]] = {}

    def start(self, task_id: str) -> list[str]:
        """Fail closed at capacity rather than discarding decision evidence."""
        if len(self.records) >= self.capacity:
            raise ValueError("Trace capacity reached.")
        events: list[str] = []
        self.records[task_id] = events
        return events

    async def read(self, request: Request) -> JSONResponse:
        """Authorize against the same SDK actor/owner scope before trace access."""
        try:
            body = await request.json()
            if not isinstance(body, dict) or set(body) != {"task_id"}:
                raise ValueError
            task_id = body["task_id"]
            if not isinstance(task_id, str) or not 1 <= len(task_id) <= 128:
                raise ValueError
        except ValueError:
            return JSONResponse({"error": "Invalid trace request."}, status_code=422)
        principal = request.scope["lab_principal"]
        task = await self.tasks.get(task_id, ServerCallContext(user=LabUser(principal)))
        if task is None:
            return JSONResponse({"error": "Task not available."}, status_code=404)
        return JSONResponse({"events": list(self.records.get(task_id, ()))})

    def routes(self) -> list[Route]:
        """This is an application read API, not an additional A2A operation."""
        return [Route("/discovery/trace", self.read, methods=["POST"])]

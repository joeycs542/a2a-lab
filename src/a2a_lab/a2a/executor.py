"""Map bounded workflow ownership onto the SDK lifecycle and cancellation."""

import asyncio
from dataclasses import dataclass, field

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Role, Task, TaskState, TaskStatus
from a2a.utils.errors import InternalError, InvalidParamsError, UnsupportedOperationError
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value

from a2a_lab.a2a.client import LookupFailure, TraceSink
from a2a_lab.a2a.traces import TraceStore, captured_trace
from a2a_lab.config import Settings
from a2a_lab.domain.models import Answer
from a2a_lab.domain.ports import KnowledgeLookup


@dataclass
class _Run:
    work: asyncio.Task[Answer] | None = None
    cancel_requested: bool = False
    finished: bool = False
    cancel_done: asyncio.Event = field(default_factory=asyncio.Event)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class WorkflowExecutor(AgentExecutor):
    """Own child work and use native SDK events for every terminal result."""

    def __init__(
        self,
        workflow: KnowledgeLookup,
        settings: Settings,
        trace: TraceSink,
        traces: TraceStore | None = None,
    ) -> None:
        self._workflow = workflow
        self._settings = settings
        self._trace = trace
        self._traces = traces
        self._active = 0
        self._runs: dict[str, _Run] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Bound active SDK executions, including return-immediately requests."""
        if self._active >= self._settings.max_concurrent_requests:
            raise InternalError(message="Workflow capacity reached; retry later.")
        self._active += 1
        try:
            await self._execute(context, event_queue)
        finally:
            self._active -= 1

    async def _execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        if (
            message is None
            or message.role != Role.ROLE_USER
            or not message.parts
            or any(part.WhichOneof("content") != "text" for part in message.parts)
        ):
            raise InvalidParamsError(message="A nonempty user text message is required.")
        question = context.get_user_input()
        if not question.strip() or len(question) > self._settings.max_input_characters:
            raise InvalidParamsError(message="Text is empty or exceeds the configured limit.")
        if context.current_task is not None:
            raise UnsupportedOperationError(message="Task continuation is not a lab capability.")
        if (
            not context.task_id
            or not context.context_id
            or len(context.task_id) > 128
            or len(context.context_id) > 128
        ):
            raise InvalidParamsError(message="SDK task identifiers are missing.")
        task_id = context.task_id
        marker = captured_trace.set(self._traces.start(task_id) if self._traces else None)
        run = _Run()
        self._runs[task_id] = run
        updater = TaskUpdater(event_queue, task_id, context.context_id)
        try:
            async with run.lock:
                if run.cancel_requested:
                    return
                await event_queue.enqueue_event(
                    Task(
                        id=task_id,
                        context_id=context.context_id,
                        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                    )
                )
                await updater.start_work()
            self._trace(
                f"workflow.started task={task_id!r} "
                f"request={context.call_context.state.get('correlation_id', 'local-demo')}"
            )
            if run.cancel_requested:
                await run.cancel_done.wait()
                return
            run.work = asyncio.create_task(self._workflow.answer(question))
            try:
                async with asyncio.timeout(self._settings.request_timeout_seconds):
                    answer = await run.work
                async with run.lock:
                    if run.cancel_requested:
                        return
                    data = ParseDict(answer.model_dump(mode="json"), Value())
                    await updater.add_artifact(
                        parts=[Part(data=data, media_type="application/json")],
                        name="engineering-answer",
                    )
                    await updater.complete()
                    run.finished = True
                    self._trace(f"workflow.completed task={task_id!r}")
            except asyncio.CancelledError:
                if run.cancel_requested:
                    await run.cancel_done.wait()
                    return
                raise
            except (LookupFailure, TimeoutError, ValueError) as error:
                async with run.lock:
                    if run.cancel_requested:
                        return
                    await updater.failed(
                        updater.new_agent_message(
                            [Part(text="The configured workflow failed or exceeded its deadline.")]
                        )
                    )
                    run.finished = True
                    self._trace(f"workflow.failed task={task_id!r} category={type(error).__name__}")
        finally:
            if run.work is not None and not run.work.done():
                run.work.cancel()
                await asyncio.gather(run.work, return_exceptions=True)
            self._runs.pop(task_id, None)
            captured_trace.reset(marker)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Stop owned child work before emitting cancellation; prevent late writes."""
        if not context.task_id or not context.context_id:
            return
        run = self._runs.get(context.task_id)
        if run is None:
            return
        async with run.lock:
            if run.finished:
                return
            run.cancel_requested = True
            try:
                if run.work is not None:
                    run.work.cancel()
                    await asyncio.gather(run.work, return_exceptions=True)
                await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()
                self._trace(f"workflow.cancelled task={context.task_id!r}")
            finally:
                run.cancel_done.set()

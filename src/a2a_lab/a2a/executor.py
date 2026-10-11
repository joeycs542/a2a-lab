"""Map one bounded workflow onto the SDK task and artifact lifecycle."""

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Role, Task, TaskState, TaskStatus
from a2a.utils.errors import InternalError, InvalidParamsError, UnsupportedOperationError
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value
from pydantic import ValidationError

from a2a_lab.a2a.client import LookupFailure, TraceSink
from a2a_lab.config import Settings
from a2a_lab.domain.ports import KnowledgeLookup


class WorkflowExecutor(AgentExecutor):
    """Create one task and publish a validated answer or a safe failure."""

    def __init__(self, workflow: KnowledgeLookup, settings: Settings, trace: TraceSink) -> None:
        self._workflow = workflow
        self._settings = settings
        self._trace = trace
        self._active = 0

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Bound active SDK executions even for return-immediately requests."""
        if self._active >= self._settings.max_concurrent_requests:
            raise InternalError(message="Workflow capacity reached; retry later.")
        self._active += 1
        try:
            await self._execute(context, event_queue)
        finally:
            self._active -= 1

    async def _execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Validate text before starting work; bound the whole workflow."""
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
            raise UnsupportedOperationError(
                message="M2 handles new questions, not task continuation."
            )
        if (
            not context.task_id
            or not context.context_id
            or len(context.task_id) > 128
            or len(context.context_id) > 128
        ):
            raise InvalidParamsError(message="SDK task identifiers are missing.")
        await event_queue.enqueue_event(
            Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            )
        )
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()
        self._trace(f"workflow.started task={context.task_id!r}")
        try:
            async with asyncio.timeout(self._settings.request_timeout_seconds):
                answer = await self._workflow.answer(question)
            data = ParseDict(answer.model_dump(mode="json"), Value())
            await updater.add_artifact(
                parts=[Part(data=data, media_type="application/json")],
                name="engineering-answer",
            )
            await updater.complete()
            self._trace(f"workflow.completed task={context.task_id!r}")
        except (LookupFailure, TimeoutError, ValidationError) as error:
            await updater.failed(
                updater.new_agent_message(
                    [Part(text="The configured knowledge lookup failed or exceeded its deadline.")]
                )
            )
            self._trace(f"workflow.failed task={context.task_id!r} category={type(error).__name__}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Defer the user-facing cancellation exercise to M3."""
        raise UnsupportedOperationError(message="Cancellation is not an M2 teaching capability.")

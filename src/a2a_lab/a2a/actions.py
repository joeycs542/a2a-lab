"""HTTP controls around an owned completed artifact and approval ledger."""

from typing import Literal

from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskStore
from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a_lab.a2a.client import TraceSink, read_answer
from a2a_lab.a2a.identity import LabUser
from a2a_lab.domain.models import Answer
from a2a_lab.security.approval import ApprovalRequest, ApprovalStore, ExecutionRequest, ReleaseTerms
from a2a_lab.security.identity import Principal, SecurityError


class ActionRoutes:
    """Keep human approval outside A2A agent capabilities and generated text."""

    def __init__(self, tasks: TaskStore, approvals: ApprovalStore, trace: TraceSink) -> None:
        self._tasks = tasks
        self._approvals = approvals
        self._trace = trace

    async def _artifact(self, principal: Principal, terms: ReleaseTerms) -> Answer:
        context = ServerCallContext(user=LabUser(principal))
        task = await self._tasks.get(terms.task_id, context)
        if (
            task is None
            or len(task.artifacts) != 1
            or task.artifacts[0].artifact_id != terms.artifact_id
        ):
            raise SecurityError("Owned completed artifact required.")
        try:
            return read_answer(task).answer
        except ValueError as error:
            raise SecurityError("Owned completed artifact required.") from error

    async def _handle(
        self, request: Request, operation: Literal["propose", "approve", "execute"]
    ) -> Response:
        principal: Principal = request.scope["lab_principal"]
        try:
            data = await request.json()
            result: BaseModel
            if operation == "propose":
                terms = ReleaseTerms.model_validate(data)
                result = await self._approvals.propose(
                    principal, terms, await self._artifact(principal, terms)
                )
            elif operation == "approve":
                result = await self._approvals.approve(
                    principal, ApprovalRequest.model_validate(data)
                )
            else:
                execution = ExecutionRequest.model_validate(data)
                result = await self._approvals.execute(
                    principal, execution, await self._artifact(principal, execution.terms)
                )
            self._trace(
                f"action.allowed operation={operation} actor={principal.actor} "
                f"request={request.scope['lab_correlation']}"
            )
            return JSONResponse(result.model_dump(mode="json"))
        except SecurityError:
            self._trace(
                f"action.denied operation={operation} actor={principal.actor} "
                f"request={request.scope['lab_correlation']}"
            )
            return JSONResponse(
                {"error": "Action not authorized for these exact terms."}, status_code=403
            )
        except (ValidationError, ValueError):
            return JSONResponse({"error": "Invalid action request."}, status_code=422)

    async def propose(self, request: Request) -> Response:
        """Create a reviewable proposal without granting execution authority."""
        return await self._handle(request, "propose")

    async def approve(self, request: Request) -> Response:
        """Accept only the distinct human-control credential."""
        return await self._handle(request, "approve")

    async def execute(self, request: Request) -> Response:
        """Validate current resource state before atomic authorization consumption."""
        return await self._handle(request, "execute")

    def routes(self) -> list[Route]:
        """Expose a narrow synthetic control API on the secure coordinator only."""
        return [
            Route("/actions/proposals", self.propose, methods=["POST"]),
            Route("/control/approve", self.approve, methods=["POST"]),
            Route("/actions/execute", self.execute, methods=["POST"]),
        ]

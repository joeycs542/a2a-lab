"""Map verifier-derived application identity to the SDK's owner scope."""

from a2a.auth.user import User
from a2a.server.context import ServerCallContext
from starlette.requests import Request

from a2a_lab.a2a.protocol import PinnedVersionContextBuilder
from a2a_lab.security.identity import Principal


class LabUser(User):
    """SDK identity scoped to an acting principal and represented owner."""

    def __init__(self, principal: Principal) -> None:
        self._principal = principal

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def user_name(self) -> str:
        return self._principal.scope


class AuthenticatedContextBuilder(PinnedVersionContextBuilder):
    """Exclude bearer headers from SDK state and carry trusted correlation."""

    def build(self, request: Request) -> ServerCallContext:
        context = super().build(request)
        principal = request.scope["lab_principal"]
        context.user = LabUser(principal)
        context.state = {
            "headers": {"a2a-version": request.headers["A2A-Version"]},
            "principal": principal,
            "correlation_id": request.scope["lab_correlation"],
        }
        return context

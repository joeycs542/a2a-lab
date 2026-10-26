"""The released protocol baseline shared by the probe and teaching agents."""

import re

from a2a.server.context import ServerCallContext
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.utils.errors import VersionNotSupportedError
from starlette.requests import Request

PROTOCOL_VERSION = "1.0"


class PinnedVersionContextBuilder(DefaultServerCallContextBuilder):
    """Restrict the SDK's major-version policy to the tested minor version."""

    def build(self, request: Request) -> ServerCallContext:
        """Reject untested versions while preserving compatible patch numbers."""
        actual = request.headers.get("A2A-Version", "")
        if re.fullmatch(rf"{re.escape(PROTOCOL_VERSION)}(?:\.[0-9]+)?", actual) is None:
            raise VersionNotSupportedError(message="This lab interface supports A2A 1.0 only.")
        return super().build(request)

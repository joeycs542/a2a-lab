"""Initialize distinct private Docker volumes without printing credential values."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from a2a_lab.config import Settings
from a2a_lab.domain.roles import Topology, services_for
from a2a_lab.security.identity import (
    SecurityError,
    initialize_security,
    load_client_keys,
    load_server_keys,
)


def prepare_credentials(root: Path, topology: Topology = "baseline") -> None:
    """Create once or verify a complete, current issuer set; never overwrite it.

    The image pre-creates volume mountpoints owned by the unprivileged lab user.
    Only the initializer mounts the selected topology's complete writable set.
    """
    audiences = services_for(topology)
    destinations = {"clients.json": root / "operator"}
    destinations.update({f"{audience}.json": root / audience for audience in audiences})
    paths = [directory / name for name, directory in destinations.items()]
    if any(path.exists() for path in paths):
        clients = load_client_keys(root / "operator")
        servers = {audience: load_server_keys(root / audience, audience) for audience in audiences}
        if len(clients.credentials) != 2 * len(audiences) + 2 or len(
            servers["coordinator"].outbound
        ) != 2 * (len(audiences) - 1):
            raise SecurityError("Container credential set is incomplete.")
        for credential in (*clients.credentials, *servers["coordinator"].outbound):
            principal = servers[credential.principal.audience].authenticate(
                credential.bearer(), credential.principal.audience
            )
            if principal != credential.principal:
                raise SecurityError("Container credential set does not match.")
        return

    for directory in destinations.values():
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
    with TemporaryDirectory(prefix="a2a-lab-issuer-") as temporary:
        source = Path(temporary) / "security"
        initialize_security(source, topology=topology)
        for name, directory in destinations.items():
            descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write((source / name).read_bytes())


def main() -> int:
    """Initialize mounted volumes or report a safe, actionable setup failure."""
    try:
        prepare_credentials(Path("/credentials"), Settings().topology)
    except (SecurityError, OSError):
        print(
            "Container credentials are unavailable, incomplete, or expired. "
            "Stop the lab and reset its teaching volumes as described in the Docker guide.",
            file=sys.stderr,
        )
        return 1
    print("Private container credentials ready; values are not displayed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

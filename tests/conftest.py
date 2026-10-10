"""Keep a developer's local settings out of deterministic fixture tests."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_lab_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in os.environ:
        if key.startswith("A2A_LAB_"):
            monkeypatch.delenv(key)

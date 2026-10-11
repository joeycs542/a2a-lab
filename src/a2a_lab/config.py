"""Validated settings for synthetic, loopback-only lab agents."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RPC_PATH = "/a2a/jsonrpc"


class Settings(BaseSettings):
    """Both local profiles bind to loopback; neither is a network deployment."""

    model_config = SettingsConfigDict(
        env_prefix="A2A_LAB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    profile: Literal["local-demo", "local-secure"] = "local-demo"
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    request_timeout_seconds: float = Field(default=5, gt=0, le=300, allow_inf_nan=False)
    max_input_characters: int = Field(default=1000, ge=1, le=16000)
    coordinator_port: int = Field(default=8101, ge=1, le=65535)
    knowledge_port: int = Field(default=8102, ge=1, le=65535)
    knowledge_workflow: Literal["notes", "release-readiness"] = "notes"
    max_payload_bytes: int = Field(default=65536, ge=1024, le=1048576)
    max_concurrent_requests: int = Field(default=4, ge=1, le=32)
    startup_timeout_seconds: float = Field(default=15, gt=0, le=120, allow_inf_nan=False)
    shutdown_timeout_seconds: float = Field(default=3, gt=0, le=30, allow_inf_nan=False)
    credentials_directory: Path = Path(".runtime/security")
    fixture_delay_seconds: float = Field(default=2, ge=0, le=60, allow_inf_nan=False)
    max_task_polls: int = Field(default=100, ge=1, le=1000)
    max_retained_tasks: int = Field(default=128, ge=1, le=10000)
    max_approval_records: int = Field(default=128, ge=1, le=10000)

    @field_validator("credentials_directory")
    @classmethod
    def absolute_credentials_directory(cls, value: Path) -> Path:
        """Keep subprocess working directories from changing credential lookup."""
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def distinct_agent_ports(self) -> "Settings":
        """Prevent the coordinator from routing back to its own endpoint."""
        if self.coordinator_port == self.knowledge_port:
            raise ValueError("Coordinator and knowledge ports must be distinct.")
        return self

    @property
    def base_url(self) -> str:
        return self.url_for_port(self.port)

    def url_for_port(self, port: int) -> str:
        """Build a URL from the approved literal loopback host."""
        host = f"[{self.host}]" if self.host == "::1" else self.host
        return f"http://{host}:{port}"

    def agent_base_url(self, agent: Literal["coordinator", "knowledge"]) -> str:
        """Return the deployment-configured destination for an agent."""
        port = self.coordinator_port if agent == "coordinator" else self.knowledge_port
        return self.url_for_port(port)

    @property
    def rpc_url(self) -> str:
        return f"{self.base_url}{RPC_PATH}"

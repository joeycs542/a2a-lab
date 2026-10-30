"""Validated settings for synthetic, loopback-only lab agents."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from a2a_lab.agents.prompting import PromptProfile
from a2a_lab.domain.roles import ServiceName, SpecialistName, Topology, services_for
from a2a_lab.domain.scenarios import DemoScenario

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

    demo_scenario: DemoScenario = "engineering"
    inference_backend: Literal["fixture", "ollama"] = "fixture"
    ollama_model: str = Field(default="qwen3:0.6b", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$")
    prompt_profile: PromptProfile = "guided"
    ollama_port: int = Field(default=11434, ge=1, le=65535)

    profile: Literal["local-demo", "local-secure"] = "local-demo"
    topology: Topology = "baseline"
    discovery_mode: Literal["single", "review"] = "single"
    web_bind: Literal["loopback", "container"] = "loopback"
    web_port: int = Field(default=8080, ge=1, le=65535)
    web_origin: str = "http://127.0.0.1:8080"
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    request_timeout_seconds: float = Field(default=5, gt=0, le=300, allow_inf_nan=False)
    max_input_characters: int = Field(default=1000, ge=1, le=16000)
    coordinator_port: int = Field(default=8101, ge=1, le=65535)
    knowledge_port: int = Field(default=8102, ge=1, le=65535)
    runbook_port: int = Field(default=8103, ge=1, le=65535)
    security_port: int = Field(default=8104, ge=1, le=65535)
    release_port: int = Field(default=8105, ge=1, le=65535)
    directory_port: int = Field(default=8110, ge=1, le=65535)
    discovery_peers: tuple[SpecialistName, ...] = Field(
        default=("runbook", "security", "release"), min_length=1, max_length=3
    )
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

    @field_validator("web_origin")
    @classmethod
    def loopback_web_origin(cls, value: str) -> str:
        """Browser exposure is explicitly limited to a local HTTP origin."""
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not parsed.port
        ):
            raise ValueError("The browser origin must be an explicit loopback HTTP host and port.")
        return value

    @field_validator("credentials_directory")
    @classmethod
    def absolute_credentials_directory(cls, value: Path) -> Path:
        """Keep subprocess working directories from changing credential lookup."""
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def distinct_agent_ports(self) -> "Settings":
        """Prevent the coordinator from routing back to its own endpoint."""
        ports = [self.service_port(service) for service in services_for(self.topology)]
        if len(set(ports)) != len(ports):
            raise ValueError("Service ports must be distinct in the selected topology.")
        if len(set(self.discovery_peers)) != len(self.discovery_peers):
            raise ValueError("Discovery peers must be unique.")
        if self.topology == "discovery" and self.profile != "local-secure":
            raise ValueError("Discovery requires the authenticated local-secure profile.")
        if self.demo_scenario == "team-lunch" and self.topology != "discovery":
            raise ValueError("The team lunch scenario requires the discovery topology.")
        return self

    @property
    def base_url(self) -> str:
        return self.url_for_port(self.port)

    def url_for_port(self, port: int) -> str:
        """Build a URL from the approved literal loopback host."""
        host = f"[{self.host}]" if self.host == "::1" else self.host
        return f"http://{host}:{port}"

    def service_port(self, service: ServiceName) -> int:
        """Resolve a fixed role from trusted settings, never card-provided URLs."""
        return {
            "coordinator": self.coordinator_port,
            "knowledge": self.knowledge_port,
            "runbook": self.runbook_port,
            "security": self.security_port,
            "release": self.release_port,
            "directory": self.directory_port,
        }[service]

    def agent_base_url(self, agent: ServiceName) -> str:
        """Return the deployment-configured destination for an agent."""
        return self.url_for_port(self.service_port(agent))

    @property
    def rpc_url(self) -> str:
        return f"{self.base_url}{RPC_PATH}"

"""Validated settings for the explicit M1 loopback-only profile."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RPC_PATH = "/a2a/jsonrpc"


class Settings(BaseSettings):
    """M1 has no authenticated or network deployment profile."""

    model_config = SettingsConfigDict(
        env_prefix="A2A_LAB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    profile: Literal["local-demo"] = "local-demo"
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    request_timeout_seconds: float = Field(default=5, gt=0, le=300, allow_inf_nan=False)
    max_input_characters: int = Field(default=1000, ge=1, le=16000)

    @property
    def base_url(self) -> str:
        host = f"[{self.host}]" if self.host == "::1" else self.host
        return f"http://{host}:{self.port}"

    @property
    def rpc_url(self) -> str:
        return f"{self.base_url}{RPC_PATH}"

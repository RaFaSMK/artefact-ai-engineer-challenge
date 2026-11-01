"""Uma configuração compartilhada por CLI, API e factory de modelos."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: Literal["ollama", "openai"] = "ollama"
    llm_model: str = Field(default="qwen3:14b", min_length=1)
    llm_base_url: str | None = None
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = Field(default=90, ge=1, le=300)
    llm_max_output_tokens: int = Field(default=1200, ge=128, le=8192)
    ollama_context_size: int = Field(default=8192, ge=2048, le=32768)
    ollama_reasoning: bool = False
    demo_customer_id: int = Field(default=2, gt=0)
    diagnostics_enabled: bool = True
    max_model_calls: int = Field(default=4, ge=1, le=8)
    max_tool_calls_per_turn: int = Field(default=8, ge=1, le=16)
    session_ttl_seconds: int = Field(default=3600, ge=60)
    max_sessions: int = Field(default=100, ge=1, le=1000)
    max_history_turns: int = Field(default=8, ge=1, le=20)
    data_dir: Path = ROOT / "data"
    database_path: Path = ROOT / "runtime" / "emporio.sqlite3"
    web_dir: Path = ROOT / "web"

    @model_validator(mode="after")
    def validate_provider(self):
        self.llm_base_url = self.llm_base_url or (
            "http://localhost:11434" if self.llm_provider == "ollama"
            else "https://api.openai.com/v1"
        )
        address = urlparse(self.llm_base_url)
        if address.scheme not in {"http", "https"} or not address.netloc:
            raise ValueError("LLM_BASE_URL deve ser um endereço HTTP/HTTPS válido.")
        if address.username or address.password:
            raise ValueError("Não inclua credenciais no endereço do provedor.")
        if self.llm_provider == "ollama" and address.path.rstrip("/") == "/v1":
            raise ValueError("ChatOllama usa o endereço nativo, sem /v1.")
        if self.llm_provider == "openai" and not self.llm_api_key.get_secret_value():
            raise ValueError("O perfil openai precisa de LLM_API_KEY no ambiente local.")
        return self


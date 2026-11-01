"""API e página local. Nenhuma credencial do provedor é enviada ao navegador."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent import Agent, ChatResponse, SessionBusy, SessionCapacity, SessionNotFound
from .config import Settings
from .ingest import build_database
from .llm import build_model
from .repository import Repository


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


def create_app(settings: Settings | None = None, model=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if not settings.database_path.exists():
            build_database(settings.data_dir, settings.database_path)
        repository = Repository(settings.database_path, settings.demo_customer_id)
        with repository.connect() as db:
            if not db.execute("SELECT 1 FROM customers WHERE customer_id=?", (settings.demo_customer_id,)).fetchone():
                raise ValueError("DEMO_CUSTOMER_ID não existe na base fornecida.")
        app.state.agent = Agent(settings, repository, model if model is not None else build_model(settings))
        app.state.metadata = repository.metadata()
        yield

    app = FastAPI(title="Empório da Música", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "[::1]"])

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        if request.url.path.startswith(("/chat", "/conversations")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "provider": settings.llm_provider, "model": settings.llm_model,
                "diagnostics_enabled": settings.diagnostics_enabled,
                "imported_at": request.app.state.metadata["imported_at"],
                "source": "snapshot fornecido no desafio", "demo": True}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request):
        try:
            return await request.app.state.agent.chat(body.message, body.conversation_id)
        except SessionNotFound:
            raise HTTPException(404, "A conversa expirou. Inicie uma nova conversa.") from None
        except SessionCapacity:
            raise HTTPException(503, "Limite temporário de conversas. Tente novamente mais tarde.") from None
        except SessionBusy:
            raise HTTPException(409, "Aguarde a resposta anterior desta conversa.") from None

    @app.delete("/conversations/{conversation_id}", status_code=204)
    async def reset(conversation_id: str, request: Request):
        try:
            request.app.state.agent.sessions.delete(conversation_id)
        except SessionBusy:
            raise HTTPException(409, "Aguarde a consulta terminar para iniciar outra conversa.") from None
        return Response(status_code=204)

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(settings.web_dir / "index.html")

    @app.get("/manual", include_in_schema=False)
    async def manual():
        return FileResponse(settings.data_dir / "políticas_da_loja.pdf", media_type="application/pdf")

    if settings.web_dir.exists():
        app.mount("/static", StaticFiles(directory=settings.web_dir), name="static")
    return app

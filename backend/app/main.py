"""FastAPI 앱. 서버는 사건을 저장하지 않는다. 사건은 요청에 담겨 오고 응답으로 돌아간다."""
import json
import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent
from .agent import drafts_for
from .engine import apply, next_action, open_case
from .models import Action, Case, Contract, Event, Extracted
from .rules import DATA, RULES

app = FastAPI(title="Reeper")
SAMPLES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "samples").glob("*.json"))}


class OpenRequest(BaseModel):
    contract: Contract
    today: date
    target: int | None = None
    floor: int | None = None


class StepRequest(BaseModel):
    case: Case
    event: Event
    today: date


class StepResponse(BaseModel):
    case: Case
    action: Action
    drafts: dict[str, str]
    llm_fallback: bool = False  # 실제 LLM이 실패해 키워드 판단으로 대체했다. 화면은 버튼 입력을 권한다


class PolishRequest(BaseModel):
    case: Case
    kind: str  # 양식 이름
    tone: Literal["polite", "firm"]


class ExtractRequest(BaseModel):
    # 약 4MB까지. 사진은 저장하지 않고 LLM에만 보낸다
    image: str = Field(max_length=5_500_000, pattern=r"^data:image/(png|jpeg|webp);base64,")


class ExtractResponse(BaseModel):
    fields: dict[str, Extracted]
    llm_fallback: bool


def upload_enabled() -> bool:
    """운영사무국 답을 받기 전까지 꺼 둔다. 켜려면 ALLOW_UPLOAD=1."""
    return os.environ.get("ALLOW_UPLOAD") == "1" and agent.llm is not agent.FAKE


def respond(case: Case, today: date, llm_fallback: bool = False) -> StepResponse:
    action = next_action(case, today)
    return StepResponse(case=case, action=action, drafts=drafts_for(case, action), llm_fallback=llm_fallback)


@app.get("/api/health")
def health() -> dict:
    used = agent.OpenAILLM.usage
    today = used["day"] == date.today()
    return {"ok": True, "llm": type(agent.llm).__name__, "upload": upload_enabled(),
            "calls_left": max(agent.DAILY_LIMIT - (used["calls"] if today else 0), 0),
            "tokens_today": used["tokens"] if today else 0}


@app.get("/api/samples")
def samples() -> list[dict]:
    return [{"id": k, **v} for k, v in SAMPLES.items()]


@app.get("/api/rules")
def rules() -> dict:
    return RULES


@app.post("/api/cases")
def create_case(req: OpenRequest) -> StepResponse:
    try:
        case = open_case(req.contract, req.today, req.target, req.floor)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return respond(case, req.today)


@app.post("/api/cases/step")
def step(req: StepRequest) -> StepResponse:
    event, fallback = req.event, False
    if event.type == "reply_received" and event.reply_type is None:
        # 붙여넣은 답장은 LLM이 읽는다. 버튼으로 고른 경우는 읽지 않는다.
        reply_type, amount, fallback = agent.read_reply(event.text)
        event = event.model_copy(update={"reply_type": reply_type, "amount": event.amount or amount})
    return respond(apply(req.case, event, req.today), req.today, fallback)


@app.post("/api/drafts/polish")
def polish(req: PolishRequest) -> dict:
    """문안은 서버가 양식으로 다시 만든 뒤 다듬는다. 화면이 보낸 글을 그대로 LLM에 넘기지 않는다."""
    if req.kind not in agent.TEMPLATES:
        raise HTTPException(422, "없는 양식이다")
    text, polished = agent.polished(req.kind, req.case, req.tone)
    return {"text": text, "polished": polished}


@app.post("/api/contracts/extract")
def extract(req: ExtractRequest) -> ExtractResponse:
    if not upload_enabled():
        raise HTTPException(403, "계약서 사진 읽기는 꺼져 있다")
    fields, fallback = agent.extract_contract(req.image)
    return ExtractResponse(fields=fields, llm_fallback=fallback)


# 빌드된 화면이 있으면 같은 서버에서 내보낸다(배포용). 개발 중에는 Vite가 /api를 프록시한다.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    import mimetypes

    mimetypes.add_type("text/javascript", ".js")  # Windows 레지스트리가 text/plain으로 주는 경우가 있다
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

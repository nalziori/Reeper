"""FastAPI 앱. 서버는 사건을 저장하지 않는다. 사건은 요청에 담겨 오고 응답으로 돌아간다."""
import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent
from .agent import drafts_for
from .engine import InvalidTransition, apply, next_action, open_case, validate_transition
from .models import Action, Case, Contract, Event
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


def respond(case: Case, today: date, llm_fallback: bool = False) -> StepResponse:
    action = next_action(case, today)
    return StepResponse(case=case, action=action, drafts=drafts_for(case, action), llm_fallback=llm_fallback)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, **agent.status()}


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
    try:
        if event.type == "reply_received" and event.reply_type is None:
            # 현재 단계에서 답장을 받을 수 있을 때만 LLM을 호출한다.
            validate_transition(req.case, event, req.today)
            reply_type, amount, fallback = agent.read_reply(event.text)
            event = event.model_copy(update={"reply_type": reply_type, "amount": event.amount or amount})
        case = apply(req.case, event, req.today)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return respond(case, req.today, fallback)


# 빌드된 화면이 있으면 같은 서버에서 내보낸다(배포용). 개발 중에는 Vite가 /api를 프록시한다.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    import mimetypes

    mimetypes.add_type("text/javascript", ".js")  # Windows 레지스트리가 text/plain으로 주는 경우가 있다
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

"""FastAPI 앱. 서버는 사건을 저장하지 않는다. 사건은 요청에 담겨 오고 응답으로 돌아간다."""
import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import drafts_for, llm
from .engine import apply, next_action, open_case
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


def respond(case: Case, today: date) -> StepResponse:
    action = next_action(case, today)
    return StepResponse(case=case, action=action, drafts=drafts_for(case, action))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm": type(llm).__name__}


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
    event = req.event
    if event.type == "reply_received" and event.reply_type is None:
        # 붙여넣은 답장은 LLM이 읽는다. 버튼으로 고른 경우는 읽지 않는다.
        reply_type, amount = llm.read_reply(event.text[:500])
        event = event.model_copy(update={"reply_type": reply_type, "amount": event.amount or amount})
    return respond(apply(req.case, event, req.today), req.today)


# 빌드된 화면이 있으면 같은 서버에서 내보낸다(배포용). 개발 중에는 Vite가 /api를 프록시한다.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    import mimetypes

    mimetypes.add_type("text/javascript", ".js")  # Windows 레지스트리가 text/plain으로 주는 경우가 있다
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

"""FastAPI 앱. 서버는 사건을 저장하지 않는다. 사건은 요청에 담겨 오고 응답으로 돌아간다."""
import json
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent
from .agent import drafts_for
from .engine import InvalidTransition, apply, next_action, open_case, validate_transition
from .models import Action, Analysis, Case, Contract, Event, Extracted, Refund, Strategy
from .rules import DATA, RULES, calculate

# 요청 본문 상한(바이트). 입력 길이 제한이다. JSON 사건 요청은 이보다 훨씬 작다.
# 계약서 사진(약 4MB base64) 경로는 이 전역 값을 올리지 않고 그 경로만 따로 둔다.
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(256 * 1024)))
PHOTO_PATH = "/api/contracts/extract"
PHOTO_BODY_BYTES = agent.MAX_IMAGE + 4096  # data URL + JSON 껍데기


class BodyLimit:
    """본문이 MAX_BODY_BYTES를 넘으면 413. Content-Length를 먼저 보고, 헤더가 없거나 거짓이어도 읽는 도중에 센다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        limit = PHOTO_BODY_BYTES if scope["path"] == PHOTO_PATH else MAX_BODY_BYTES
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            return await self._reject(scope, receive, send)
        seen, started = 0, False

        async def counted():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    raise _TooLarge
            return msg

        async def tracked(msg):
            nonlocal started
            started = started or msg["type"] == "http.response.start"
            await send(msg)

        try:
            await self.app(scope, counted, tracked)
        except _TooLarge:
            if started:
                raise
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send):
        res = JSONResponse({"detail": "요청 본문이 너무 큽니다."}, status_code=413)
        await res(scope, receive, send)


class _TooLarge(BaseException):  # Exception이면 FastAPI가 본문 오류(400)로 삼킨다
    pass


app = FastAPI(title="Reeper")
app.add_middleware(BodyLimit)
SAMPLES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "samples").glob("*.json"))}


class OpenRequest(BaseModel):
    contract: Contract
    today: date
    target: int | None = None
    floor: int | None = None


class PreviewRequest(BaseModel):
    contract: Contract
    today: date


class StepRequest(BaseModel):
    case: Case
    event: Event
    today: date


class StrategyRequest(BaseModel):
    case: Case
    situation: str = Field(default="", max_length=agent.MAX_SITUATION)
    today: date


class StrategyResponse(BaseModel):
    case: Case
    llm_fallback: bool = False  # 실제 LLM이 실패했다. 전략 없이 고정 양식으로 진행한다


class ExtractRequest(BaseModel):
    image: str  # data:image/png·jpeg·webp;base64,... 서버는 저장하거나 로그로 남기지 않는다


class ExtractResponse(BaseModel):
    fields: dict[str, Extracted]  # 못 읽은 값은 value가 null이다. check가 참인 값은 사람이 확인한다
    llm_fallback: bool = False  # 실제 LLM이 실패했다. 모든 값이 비어 있으니 직접 입력한다


class StepResponse(BaseModel):
    case: Case
    action: Action
    drafts: dict[str, str]
    llm_fallback: bool = False  # 실제 LLM이 실패해 키워드 판단으로 대체했다. 화면은 버튼 입력을 권한다
    analysis: Analysis | None = None  # 붙여넣은 답장에서 짚은 주장. 짚은 것이 없으면 null


def respond(case: Case, today: date, llm_fallback: bool = False, reply: str = "") -> StepResponse:
    action = next_action(case, today)
    analysis = None
    if reply:  # 답장 분류가 이미 대체됐으면 LLM을 다시 부르지 않는다
        found = agent.analyze_reply(case, reply, action, today) if not llm_fallback else {}
        llm_fallback = llm_fallback or found.get("fallback", False)
        if found.get("claims") or found.get("note"):
            analysis = Analysis(claims=found["claims"], note=found["note"])
    return StepResponse(case=case, action=action, drafts=drafts_for(case, action), llm_fallback=llm_fallback,
                        analysis=analysis)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, **agent.status()}


@app.get("/api/samples")
def samples() -> list[dict]:
    return [{"id": k, **v} for k, v in SAMPLES.items()]


@app.get("/api/rules")
def rules() -> dict:
    return RULES


@app.post("/api/refund-preview")
def refund_preview(req: PreviewRequest) -> Refund:
    try:
        return calculate(req.contract, req.today)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/cases")
def create_case(req: OpenRequest) -> StepResponse:
    try:
        case = open_case(req.contract, req.today, req.target, req.floor)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return respond(case, req.today)


@app.post("/api/cases/strategy")
def strategy(req: StrategyRequest) -> StrategyResponse:
    """상황 설명으로 전략을 세워 사건에 싣는다. 단계, 금액, 타임라인은 건드리지 않는다."""
    found = agent.plan(req.case, req.situation, req.today)
    parts = {k: found[k] for k in Strategy.model_fields}
    made = None
    if any(parts.values()):  # 가짜 LLM, 호출 실패, 모두 버려진 경우에는 전략이 없다
        parts["grounds"] = [{**g, "verified": bool(RULES[g["rule_id"]].get("verified"))} for g in parts["grounds"]]
        made = Strategy(**parts)
    case = req.case.model_copy(update={"situation": req.situation, "strategy": made})
    return StrategyResponse(case=case, llm_fallback=found["fallback"])


@app.post(PHOTO_PATH)
def extract_contract(req: ExtractRequest) -> ExtractResponse:
    """계약서 사진에서 계약 값을 읽는다. 사건을 만들지 않는다. 확인된 값으로 화면이 POST /api/cases를 부른다."""
    try:
        fields, failed = agent.extract_contract(req.image)
    except PermissionError as exc:
        raise HTTPException(403, "계약서 사진 읽기가 꺼져 있습니다. 직접 입력해 주세요.") from exc
    except ValueError as exc:
        raise HTTPException(422, "사진 형식이나 크기가 맞지 않습니다. png, jpeg, webp 사진을 올려 주세요.") from exc
    return ExtractResponse(fields=fields, llm_fallback=failed)


@app.post("/api/cases/step")
def step(req: StepRequest) -> StepResponse:
    event, fallback, reply = req.event, False, ""
    try:
        if event.type == "reply_received" and event.reply_type is None:
            # 현재 단계에서 답장을 받을 수 있을 때만 LLM을 호출한다.
            validate_transition(req.case, event, req.today)
            reply = event.text
            reply_type, amount, fallback = agent.read_reply(reply)
            event = event.model_copy(update={"reply_type": reply_type,
                                             "amount": amount if event.amount is None else event.amount})
        case = apply(req.case, event, req.today)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return respond(case, req.today, fallback, reply)


# 빌드된 화면이 있으면 같은 서버에서 내보낸다(배포용). 개발 중에는 Vite가 /api를 프록시한다.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    import mimetypes

    mimetypes.add_type("text/javascript", ".js")  # Windows 레지스트리가 text/plain으로 주는 경우가 있다
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

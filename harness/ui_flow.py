"""화면 하니스: 빌드된 화면을 실제 브라우저(headless Chrome)로 열어 종결까지 간다.
실행: cd frontend && npm run build 후 python harness/ui_flow.py [스크린샷 폴더]
확인: 흐름 완주와 소요 시간, 깨진 저장값 복구, 모바일 가로 넘침, 내보내기, 콘솔 오류, 호출 상한 소진 때 버튼 종결.
Chrome 경로는 CHROME 환경변수로 바꾼다(기본 /usr/bin/google-chrome)."""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from lib import ROOT, server

SHOTS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/reeper-shots")
SHOTS.mkdir(parents=True, exist_ok=True)
results: list[tuple[str, bool, str]] = []
MUSTS = ("해지 의사", "날짜", "금액", "입금 계좌", "문자 확인")
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")


def rec(name, ok, note=""):
    results.append((name, bool(ok), note))


def btn(page, name, exact=False):
    return page.get_by_role("button", name=name, exact=exact)


def start_intake(page):
    btn(page, "시작하기", exact=True).click()
    expect(page.get_by_role("heading", name="내 계약 입력")).to_be_visible()


def shows(locator, timeout=5000) -> bool:
    """보이면 참. 확인 결과를 예외 대신 rec로 남길 때 쓴다(실패해도 하니스가 멈추지 않는다)."""
    try:
        locator.first.wait_for(timeout=timeout)
        return True
    except Exception:
        return False


def record_amount(page, amount: str) -> None:
    """답장 시트에서 '금액을 말했어요' 줄을 펼쳐 금액을 적고 기록한다."""
    btn(page, "금액을 말했어요").click()
    page.get_by_label("업체 제시액(원)").fill(amount)
    btn(page, "이 금액으로 기록").click()


def open_paste(page) -> None:
    """자동 읽기를 못 쓰면 붙여넣기 칸이 접혀 있다. 접혀 있으면 편다."""
    if page.get_by_label("받은 답장").count() == 0:
        btn(page, "받은 문자 붙여넣기").click()
        page.get_by_label("받은 답장").wait_for()


def open_reply(page):
    """답장 기록은 바텀 시트 안에 있다. 닫혀 있으면 연다."""
    if page.get_by_role("dialog").count() == 0:
        page.get_by_role("button", name=re.compile(r"^업체 답장 기록$")).first.click()
        page.get_by_role("dialog").wait_for()


def close_sheet(page):
    """시트가 열려 있으면 Esc로 닫는다(열린 동안 뒤 화면은 누를 수 없다)."""
    if page.get_by_role("dialog").count():
        page.keyboard.press("Escape")
        page.get_by_role("dialog").wait_for(state="detached")


def new_page(browser, base, viewport, errors):
    ctx = browser.new_context(viewport=viewport, accept_downloads=True, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    page.clock.set_fixed_time(datetime(2026, 11, 16, 12, 0, 0))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(base + "/?demo", wait_until="networkidle")  # 시연 조작은 ?demo가 있을 때만 보인다
    start_intake(page)
    return ctx, page


def overflow(page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - window.innerWidth")


def full_flow(browser, base, tag, viewport):
    errors: list[str] = []
    ctx, page = new_page(browser, base, viewport, errors)
    t0 = time.time()
    # 날짜 칸 설명은 지우고 '쓴 만큼' 펼침 설명으로 옮겼다. 칸이 있는지만 본다
    rec(f"{tag}: 시작일과 마지막 이용일 칸",
        page.get_by_label("이용 시작일").count() == 1
        and page.get_by_label("마지막 이용일").count() == 1
        and page.get_by_role("radio", name="일수", exact=True).is_checked()
        and page.get_by_role("radio", name="개월 수", exact=True).count() == 0)
    page.screenshot(path=SHOTS / f"{tag}-1-intake.png", full_page=True)
    # 샘플 버튼: 가상 계약서로 해 보기 줄의 첫 버튼
    sample_buttons = page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button")
    sample_buttons.first.click()
    page.get_by_text("예상 환불액").first.wait_for()
    rec(f"{tag}: 예상 환불액에 계산 단위 표시", page.get_by_text("일수 기준으로 계산", exact=True).is_visible())
    rec(f"{tag}: 예상 환불액 표시", page.get_by_text("원").count() > 0)
    page.screenshot(path=SHOTS / f"{tag}-2-preview.png", full_page=True)
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    page.screenshot(path=SHOTS / f"{tag}-3-prepare.png", full_page=True)
    # 알리는 방법은 문자가 기본이고, 고른 쪽 문안과 기록 버튼만 보인다
    call_heading = page.get_by_role("heading", name="통화 대본", exact=True)  # 다른 카드의 같은 낱말과 헷갈리지 않게 제목으로 찾는다
    rec(f"{tag}: 기본은 문자 문안만", page.get_by_role("heading", name="보낼 문자", exact=True).count() == 1 and call_heading.count() == 0)
    link = page.get_by_role("link", name="문자 앱으로 열기").first
    href = link.get_attribute("href") if link.count() else None
    rec(f"{tag}: 문자 앱 링크가 sms: 주소", bool(href) and href.startswith("sms:") and "body=" in href, (href or "없음")[:40])
    page.get_by_role("radio", name="전화로").check()
    call_heading.wait_for()
    rec(f"{tag}: 전화로 고르면 통화 카드와 전화 기록 버튼", page.get_by_role("heading", name="보낼 문자", exact=True).count() == 0
        and btn(page, "통화 결과 기록").count() == 1 and btn(page, "문자로 보냈어요").count() == 0)
    # 긴 통화 카드를 내리지 않아도 기록 버튼이 화면 안에 있다(하단 고정 행동 바)
    page.evaluate("window.scrollTo(0, 0)")
    box = btn(page, "통화 결과 기록").bounding_box()
    rec(f"{tag}: 맨 위에서도 기록 버튼이 화면 안", box is not None and 0 <= box["y"] and box["y"] + box["height"] <= page.viewport_size["height"],
        f"y={round(box['y']) if box else '없음'} / {page.viewport_size['height']}")
    script = page.get_by_role("list", name="통화 순서")
    card = script.inner_text()
    musts = [m for m in MUSTS if m not in card]
    rec(f"{tag}: 통화 카드 꼭 말할 다섯 가지", not musts, "빠짐: " + ", ".join(musts) if musts else "")
    steps = script.get_by_role("listitem").all_text_contents()
    rec(f"{tag}: 인사와 해지 요청을 첫 순서에 함께 표시", len(steps) == 5
        and "안녕하세요" in steps[0] and "오늘 날짜로 해지하겠습니다" in steps[0]
        and "문자 확인" in steps[-1]
        and page.get_by_text("해지 접수일과 환불 처리 일정을 다시 확인하세요.", exact=False).is_visible()
        and page.get_by_text("통화한 사람 이름과 시각을 적어 두세요. 끊은 뒤 바로 확인 문자를 보내세요.", exact=False).is_visible())
    first_line = page.get_by_text("오늘 날짜로 해지하겠습니다", exact=False).bounding_box()
    rec(f"{tag}: 첫마디 다음 문장도 하단 버튼 위에 보임", first_line is not None and box is not None
        and first_line["y"] + first_line["height"] <= box["y"])
    page.screenshot(path=SHOTS / f"{tag}-3-call.png")
    call_heading.locator("../..").screenshot(path=SHOTS / f"{tag}-3-call-script.png",
        style=".app-bar, .dock-slot, .tab-bar, .action-dock { display: none !important; }")
    responses = btn(page, "상황별 대답 보기")
    objection = page.get_by_text("정상가로 계산해야 합니다")
    initially_hidden = not objection.is_visible()
    responses.click()
    rec(f"{tag}: 업체 반응별 답변을 필요할 때 펼침", initially_hidden and objection.is_visible()
        and page.get_by_text("실제 결제한 금액 기준으로 계산해 주세요").is_visible())
    page.screenshot(path=SHOTS / f"{tag}-3-call-answers.png", animations="disabled")
    close_sheet(page)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="복사", exact=True).last.click()
    copied = page.evaluate("navigator.clipboard.readText()")
    rec(f"{tag}: 복사가 원문 그대로(제목 줄 포함)", "[첫마디]" in copied and "\n" in copied and "[끊기 전에]" in copied, f"{len(copied)}자")
    page.keyboard.press("Tab")
    rec(f"{tag}: 키보드 포커스 이동", page.evaluate("document.activeElement && document.activeElement !== document.body"))
    rec(f"{tag}: 시연 패널에 날짜 버튼(ready)", btn(page, "하루 지남").count() == 1 and btn(page, "사장:").count() == 0)
    # 단계가 그대로인 기록도 눌렸다는 게 보여야 한다. 연결이 안 됐으면 문자 문안으로 바꿔 보여 준다
    btn(page, "통화 결과 기록").click()
    page.get_by_role("dialog").get_by_role("button", name="연결이 안 됐어요").click()
    flash = page.locator(".flash", has_text="연결되지 않음")
    flash.wait_for()
    rec(f"{tag}: 전화 연결 안 됨을 누르면 기록 알림", flash.count() == 1, flash.inner_text()[:40])
    rec(f"{tag}: 연결 안 되면 문자 문안으로 바뀜", page.get_by_role("radio", name="문자로").is_checked()
        and btn(page, "문자로 보냈어요").count() == 1)
    page.get_by_role("radio", name="문자로").check()
    btn(page, "문자로 보냈어요").click()
    # 다음 단계 화면이 그려진 뒤에 잰다(그리기 전 한순간의 위치를 읽지 않게)
    page.get_by_text("답장 기한").first.wait_for()
    rec(f"{tag}: 단계가 바뀌면 맨 위에서 시작", page.evaluate("window.scrollY") == 0)
    rec(f"{tag}: 답변 기한과 남은 날", page.get_by_text(re.compile(r"답장 기한 .*3일 남음")).count() >= 1,
        page.get_by_text(re.compile("답장 기한 ")).first.inner_text())
    rec(f"{tag}: 법정 기한 아님 문구", page.get_by_text("법정 기한 아님").count() >= 1)
    page.screenshot(path=SHOTS / f"{tag}-4-waiting.png", full_page=True)
    # 버튼 경로: 금액 제시(수용선 미만). 답장 기록은 아래 주 버튼으로 여는 시트 안에 있다
    rec(f"{tag}: 답장 기다림 주 버튼이 시트를 연다", btn(page, "업체 답장 기록").count() == 1)
    open_reply(page)
    rec(f"{tag}: 금액 칸은 고르기 전엔 접힘", page.get_by_label("업체 제시액(원)").count() == 0)
    record_amount(page, "100000")
    page.get_by_text(re.compile("업체 제시액 .*원은")).first.wait_for()
    # 하한선을 정하지 않았으니 정한 적 없는 '하한선'이 아니라 '예상 환불액'과 비교한다고 적는다
    rec(f"{tag}: 수용선 미만 경고", page.get_by_text(re.compile("업체 제시액 .*원은 예상 환불액 .*보다 적어요")).count() >= 1
        and page.get_by_text(re.compile("거절 기준|수용선")).count() == 0)
    rec(f"{tag}: negotiating에서 낡은 기한 줄 없음", page.get_by_text(re.compile("답장 기한 .*(남음|지났어요|오늘까지)")).count() == 0)
    page.screenshot(path=SHOTS / f"{tag}-5-lowoffer.png", full_page=True)
    btn(page, "이 문자를 보냈어요").click()
    btn(page, "하루 지남").wait_for()
    # 애매한 답장: 읽은 결과를 확정하지 않으면 단계가 바뀌지 않는다
    open_reply(page)
    open_paste(page)
    page.get_by_label("받은 답장").fill("환불해 드릴게요. 위약금 30% 빼고요")
    btn(page, "답장 읽기").click()
    page.get_by_text("이렇게 읽었어요. 맞나요?").wait_for()
    btn(page, "아니에요, 직접 고를게요").click()
    rec(f"{tag}: 읽기만으로는 합의가 되지 않음", btn(page, "입금을 확인했어요").count() == 0
        and page.get_by_text("이렇게 읽었어요. 맞나요?").count() == 0)
    page.get_by_label("받은 답장").fill("")
    close_sheet(page)
    # 시연 조작: 사장 답도 읽은 결과를 확정해야 기록된다(가짜 LLM 키워드 판단). 읽은 결과가 있으면 시트가 저절로 열린다
    btn(page, "사장: 네 알겠습니다 환불해 드릴게요").click()
    page.get_by_text("이렇게 읽었어요. 맞나요?").wait_for()
    rec(f"{tag}: 사장 답 읽은 결과 표시", page.get_by_text("환불해 준대요", exact=True).count() >= 1)
    rec(f"{tag}: 수용 확정 전 합의 금액 안내", page.get_by_text(re.compile("기록하면 .+원으로 합의하고")).count() == 1)
    btn(page, "맞아요, 기록할게요").click()
    btn(page, "입금을 확인했어요").wait_for()
    rec(f"{tag}: 입금 기한 표시", page.get_by_text(re.compile("입금 기한 ")).count() >= 1)
    page.screenshot(path=SHOTS / f"{tag}-6-agreed.png", full_page=True)
    # 위 막대는 내려도 붙어 있다
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    rec(f"{tag}: 위 막대 고정", page.evaluate("Math.round(document.querySelector('.app-bar').getBoundingClientRect().top)") == 0)
    # 내보내기는 '기록' 탭에 있고 접혀 있어 먼저 펼친다
    page.get_by_role("tab", name="기록").click()
    page.get_by_text("기록 저장", exact=True).first.click()
    with page.expect_download() as dl:
        btn(page, "글 파일로 저장").click()
    name = dl.value.suggested_filename
    path = dl.value.path()
    text = Path(path).read_text(encoding="utf-8")
    rec(f"{tag}: 요약 파일 저장", name.startswith("reeper-") and name.endswith(".txt") and "원" in text, name)
    with page.expect_download() as dj:
        btn(page, "백업 파일로 저장").click()
    rec(f"{tag}: 보관용 JSON 저장", dj.value.suggested_filename.endswith(".json"), dj.value.suggested_filename)
    rec(f"{tag}: 실제/모의 구분 카드", page.get_by_text("Reeper가 하는 일과 시연용").count() == 1)
    page.get_by_role("tab", name="진행").click()
    btn(page, "입금을 확인했어요").click()
    page.get_by_text("환불 완료", exact=True).wait_for()
    elapsed = time.time() - t0
    rec(f"{tag}: 종결까지 완주", True, f"{elapsed:.1f}초")
    rec(f"{tag}: 3분 이내", elapsed < 180, f"{elapsed:.1f}초")
    rec(f"{tag}: 가로 넘침 없음", overflow(page) <= 0, f"{overflow(page)}px")
    rec(f"{tag}: 시연 패널이 종결 뒤 숨음", btn(page, "하루 지남").count() == 0)
    page.screenshot(path=SHOTS / f"{tag}-7-closed.png", full_page=True)
    # 새로고침해도 이어진다
    page.reload(wait_until="networkidle")
    rec(f"{tag}: 새로고침 뒤 사건 유지", page.get_by_text("환불 완료", exact=True).count() == 1)
    rec(f"{tag}: 끝난 사건은 맨 위 안내 카드 없음", page.get_by_role("heading", name="환불금을 받았어요").count() == 0)
    rec(f"{tag}: 저장된 사건이면 대문을 건너뜀", btn(page, "시작하기", exact=True).count() == 0)
    btn(page, "새로 시작", exact=True).click()
    rec(f"{tag}: 새로 시작하면 입력 화면", shows(page.get_by_role("heading", name="내 계약 입력")))
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def demo_hidden(browser, base):
    """?demo 없이 열면 시연 조작이 보이지 않는다(배포 화면)."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    page = ctx.new_page()
    page.goto(base, wait_until="networkidle")
    rec("대문: 마스코트와 시작하기, 입력 화면은 아직 없음", shows(page.get_by_role("main").locator("img"))
        and btn(page, "시작하기", exact=True).count() == 1 and page.get_by_role("heading", name="내 계약 입력").count() == 0)
    start_intake(page)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    rec("배포 화면: 시연 조작 숨김", btn(page, "하루 지남").count() == 0 and page.get_by_text("시연용").count() == 0)
    ctx.close()


def limit_flow(browser, base):
    """호출 상한이 0인 서버(가짜 키, 외부 호출 없음). 자동 읽기가 실패해도 고정 문안과 버튼으로 종결한다."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    tag = "상한 소진"
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    page.get_by_role("radio", name="전화로").check()
    rec(f"{tag}: 고정 통화 카드", page.get_by_role("list", name="통화 순서")
        .get_by_text("인사하고 해지 의사 전하기").is_visible())
    page.get_by_role("radio", name="문자로").check()
    rec(f"{tag}: 쓸 수 없는 조언 칸은 숨김", page.get_by_text("내 상황에 맞는 조언").count() == 0)
    btn(page, "문자로 보냈어요").click()
    open_reply(page)
    btn(page, "환불해 준대요").wait_for()
    rec(f"{tag}: 자동 읽기 꺼지면 버튼 먼저, 붙여넣기는 접힘", btn(page, "환불해 준대요").count() == 1
        and page.get_by_label("받은 답장").count() == 0)
    open_paste(page)
    page.get_by_label("받은 답장").fill("네 알겠습니다 환불해 드릴게요")
    btn(page, "답장 읽기").click()
    page.get_by_text("낱말로 짐작했어요").first.wait_for()
    rec(f"{tag}: 읽기 실패 경고(키워드 대체)", True)
    # 키워드로 읽은 수용은 바로 확정하지 못하고, 버튼으로 직접 고른다
    rec(f"{tag}: 키워드 수용은 확정 버튼 없음", btn(page, "맞아요, 기록할게요").count() == 0
        and page.get_by_text("환불 여부와 금액은 원문을 보고").count() == 1)
    btn(page, "환불해 준대요").click()
    btn(page, "입금을 확인했어요").click()
    page.get_by_text("환불 완료", exact=True).wait_for()
    rec(f"{tag}: 버튼으로 종결", True)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def photo_fill(browser, base):
    """사진 읽기 결과(서버 응답을 가짜로 바꿈)가 직접 입력 칸에 들어간다. 계약서에 없는 값(null)은 확인 표시 없이 기본값."""
    errors: list[str] = []
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    real_health = {}

    def health(route):
        body = route.fetch().json()
        real_health.update(body)
        route.fulfill(json={**body, "upload": True})

    def f(value, check):
        return {"value": value, "confidence": 0.5 if check else 0.95, "quote": "", "check": check}

    fields = {"gym_name": f("가상필라테스", False), "total_paid": f(900000, False), "start_date": f("2026-11-01", False),
              "end_date": f("2027-04-30", False), "special_terms": f(None, True), "unit": f("count", False),
              "total_count": f(30, False), "addon_value": f(50000, True), "security_deposit": f(None, True)}
    page.route("**/api/health", health)
    page.route("**/api/contracts/extract", lambda r: r.fulfill(json={"fields": fields, "llm_fallback": False}))
    page.goto(base, wait_until="networkidle")
    start_intake(page)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    page.locator("input[type=file]").set_input_files({"name": "c.png", "mimeType": "image/png", "buffer": png})
    page.get_by_text("사진에서 읽어 채웠어요").wait_for()
    tag = "사진 채우기"
    rec(f"{tag}: 단위가 횟수", page.get_by_role("radio", name="횟수(PT·레슨)").is_checked())
    rec(f"{tag}: 총 횟수·부가상품", page.get_by_label("총 횟수").input_value() == "30"
        and page.get_by_label("사은품 금액(원, 선택)").input_value() == "50000")
    rec(f"{tag}: 보증금 없음은 빈칸", page.get_by_label("보증금(원, 선택)").input_value() == "")
    rec(f"{tag}: 비어 온 금액 칸 안내", page.get_by_text("보증금이 계약서에 적혀 있으면 직접 적어 주세요").count() == 1)
    # 화면 낭독용 알림 영역에도 같은 글이 남으므로 칸 아래 상태 표시만 센다
    warn = page.locator(".field-status", has_text="사진에서 읽었어요")
    rec(f"{tag}: 확인 표시는 check이고 값 있는 칸만", warn.count() == 1, f"{warn.count()}개")
    calc = btn(page, "확인했어요, 계산하기")
    rec(f"{tag}: 이미 쓴 횟수 없으면 계산 막힘", calc.is_disabled())
    page.get_by_label("이미 쓴 횟수").fill("5")
    page.get_by_label("사은품 금액(원, 선택)").fill("40000")
    rec(f"{tag}: 고친 칸은 확인 표시 사라짐", page.locator(".field-status", has_text="사진에서 읽었어요").count() == 0)
    btn(page, "계산하기").click()
    page.get_by_text("예상 환불액").first.wait_for()
    rec(f"{tag}: 회 단위로 계산", page.get_by_text(re.compile(r"\d+회 중 \d+회")).count() >= 1)
    btn(page, "계약 수정").click()
    fields.update(unit=f("month", False), total_count=f(6, True))
    page.locator("input[type=file]").set_input_files({"name": "month.png", "mimeType": "image/png", "buffer": png})
    page.get_by_text("개월 단위 회원권은 이용 시작일과 마지막 이용일을 확인해 주세요. 일수로 계산해요").wait_for()
    rec(f"{tag}: 개월 단위 사진은 일수로 검토",
        page.get_by_role("radio", name="일수", exact=True).is_checked()
        and page.get_by_label("총 개월 수").count() == 0 and page.get_by_label("총 횟수").count() == 0)
    btn(page, "계산하기").click()
    day_basis = page.get_by_text("일수 기준으로 계산", exact=True)
    day_basis.wait_for()
    rec(f"{tag}: 개월 단위 사진의 결과는 일수 기준", day_basis.is_visible())
    rec(f"{tag}: 실제 서버는 사진 읽기 꺼짐", real_health.get("upload") is False)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def not_sent_drafts(browser, base):
    """1372 상담 신청 내용은 업체에 보내는 글이 아니라 말투 선택과 문자 앱 버튼이 없다. 업체에 보내는 문자는 있다."""
    from lib import call
    contract = call(base, "/api/samples")[1][0]["contract"]
    _, res = call(base, "/api/cases", {"contract": contract, "today": "2026-11-16"})
    steps = [({"type": "notice_sent", "channel": "sms"}, "2026-11-16"), ({"type": "time_passed"}, "2026-11-20"),
             ({"type": "notice_sent", "channel": "sms"}, "2026-11-20"), ({"type": "time_passed"}, "2026-11-24"),
             ({"type": "escalation_sent"}, "2026-11-24"), ({"type": "time_passed"}, "2026-11-28")]
    for event, today in steps:
        _, res = call(base, "/api/cases/step", {"case": res["case"], "event": event, "today": today})
    tag = "보내지 않는 문안"
    rec(f"{tag}: 1372 단계 준비", res["action"]["type"] == "go_1372" and "go_1372" in res["drafts"], res["action"]["type"])
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    page = ctx.new_page()
    page.route("**/api/health", lambda r: r.fulfill(json={**r.fetch().json(), "llm": "OpenAILLM", "calls_left": 5}))
    page.goto(base, wait_until="networkidle")
    page.evaluate("(s) => localStorage.setItem('reeper.case', JSON.stringify(s))", {"version": 1, "step": res, "offset": 0})
    page.reload(wait_until="networkidle")
    card = page.locator("h3:has-text('1372에 말할 내용')").locator("xpath=ancestor::*[self::div][2]")
    card.first.wait_for()
    # "문안 말투"는 화면 낭독용 이름이라 글자로 찾지 않고 선택지로 찾는다
    rec(f"{tag}: 1372 카드에 말투 선택 없음", card.get_by_role("radio", name="정중하게").count() == 0)
    rec(f"{tag}: 1372 카드에 문자 앱 버튼 없음", card.get_by_role("link", name="문자 앱으로 열기").count() == 0
        and card.get_by_role("button", name="문자 앱으로 열기").count() == 0)
    rec(f"{tag}: 1372 카드 복사는 있음", card.get_by_role("button", name="복사", exact=True).count() == 1)
    # 1372 안내: 절차, 사용자가 거는 전화 링크, 챙길 것 체크(저장하지 않음). 말할 내용보다 위에 있다
    guide = page.get_by_role("heading", name="1372에 상담하기")
    rec(f"{tag}: 1372 안내 카드", guide.count() == 1
        and page.locator("a[href='tel:1372']").count() == 1
        and page.get_by_role("checkbox").count() == 4)
    rec(f"{tag}: 1372 안내가 말할 내용 위", guide.bounding_box()["y"] < card.first.bounding_box()["y"])
    ctx.close()
    # 대조: 업체에 보내는 첫 문자에는 말투 선택이 보인다
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    page = ctx.new_page()
    page.route("**/api/health", lambda r: r.fulfill(json={**r.fetch().json(), "llm": "OpenAILLM", "calls_left": 5}))
    page.goto(base, wait_until="networkidle")
    start_intake(page)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    rec(f"{tag}: 대조 - 업체에 보내는 문자는 말투 선택 있음", page.get_by_role("radio", name="정중하게").count() >= 1)
    ctx.close()


def pick_kind(page, name):
    """업체 사정 유형을 고른다. 이미 골랐으면 선택지가 한 줄로 접혀 있어 '바꾸기'로 연다."""
    radio = page.get_by_role("radio", name=name)
    change = page.get_by_role("button", name="어떤 일이었는지 바꾸기")
    radio.or_(change).first.wait_for()
    if radio.count() == 0:
        change.click()
    # 고르면 선택지가 바로 접혀 사라지므로 check()(고른 뒤 상태를 다시 확인함) 대신 click()
    radio.click()


def open_cases(page):
    """금액 아래에 접힌 비슷한 사례를 편다."""
    page.get_by_text(re.compile(r"^비슷한 사례 \d+건 참고하기$")).click()


def business_fault(browser, base):
    """업체 잘못 계산을 받지 못하면(계산 분기가 없는 서버, 오류) 금액·시작 버튼을 열지 않고 1372 안내와 말할 내용 정리를 보인다.
    서버 응답을 이 검사 안에서만 바꿔 흉내 낸다. 화면이 숫자를 만들지 않고 disputed_refund로 준비 여부를 가리는지 본다(#154 C 리뷰)."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    tag = "업체 잘못"
    asked: list[dict] = []

    # mode="old": 계산 분기가 없는 서버(위약금을 빼고 disputed_refund 없음)
    # mode="zero": 위약금이 우연히 0원(결제액 10원 미만)인데 계산 분기는 없는 서버
    def fake(mode: str):
        def handler(route):
            body = json.loads(route.request.post_data or "{}")
            data = route.fetch().json()
            if body.get("contract", {}).get("cancel_reason") == "business":
                asked.append(body["contract"])
                disputed = data.get("disputed_refund")
                consumer = disputed if disputed is not None else data["refund"]
                penalty = (data["refund"] - disputed) if disputed is not None else data["penalty"]
                data = ({**data, "refund": consumer, "penalty": penalty, "disputed_refund": None} if mode == "old"
                        else {**data, "refund": consumer + penalty, "penalty": 0, "disputed_refund": None})
            route.fulfill(json=data)
        return handler

    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").wait_for()
    rec(f"{tag}: 기본은 내 사정", page.get_by_role("radio", name=re.compile("내 사정")).is_checked())
    page.get_by_role("radio", name=re.compile("업체 잘못")).check()
    page.get_by_text("어떤 일이었는지 고르면 금액을 계산해 드려요", exact=False).wait_for()
    rec(f"{tag}: 유형 고르기 전에는 금액·시작 버튼 없음", page.get_by_role("heading", name=re.compile("예상 환불액")).count() == 0
        and btn(page, "이 금액으로 시작").count() == 0)
    page.route("**/api/refund-preview", fake("old"))
    pick_kind(page, "약속한 트레이너·강사가 바뀌거나 그만둠")
    page.get_by_text("1372 상담을 먼저 받아 보세요").wait_for()
    rec(f"{tag}: 계산 분기가 없으면 시작 버튼 없음", btn(page, "이 금액으로 시작").count() == 0)
    rec(f"{tag}: 계약 값으로 유형을 보냄", any(k.get("fault_kind") == "trainer_change" for k in asked))
    rec(f"{tag}: 1372 연락처", page.get_by_text("국번 없이 1372").count() == 1
        and page.locator("a[href='tel:1372']").count() == 1)
    rec(f"{tag}: 애매하면 문자 전에 1372 안내", page.get_by_text(re.compile("애매하면.*1372")).count() >= 1)
    page.get_by_label("무슨 일이 있었나요").fill("11월부터 샤워실 운영 중단, 공지만 붙음")
    summary = page.locator(".draft", has_text="[1372에 말할 내용]").inner_text()
    rec(f"{tag}: 1372에 말할 내용 정리", "가상피트니스" in summary and "600,000원" in summary
        and "샤워실 운영 중단" in summary, summary.replace(chr(10), " / ")[:80])
    rec(f"{tag}: 정리에 계산 금액 없음", "위약금" not in summary and "460,000" not in summary)
    page.unroute("**/api/refund-preview")
    page.route("**/api/refund-preview", fake("zero"))
    pick_kind(page, "그 밖의 업체 사정")
    page.get_by_text("1372 상담을 먼저 받아 보세요").wait_for()
    rec(f"{tag}: 위약금 0원이어도 다툴 때 금액이 없으면 시작 버튼 없음", btn(page, "이 금액으로 시작").count() == 0)
    # 계산 응답을 읽지 못해도(빈 본문) 1372 안내로 남는다(#156 C 하니스)
    page.unroute("**/api/refund-preview")
    page.route("**/api/refund-preview", lambda route: route.fulfill(status=200, content_type="application/json", body=""))
    with page.expect_response("**/api/refund-preview"):
        pick_kind(page, "휴업·폐업이나 시설 일부 폐쇄")
    page.get_by_text("1372 상담을 먼저 받아 보세요").wait_for()
    rec(f"{tag}: 계산을 못 받으면 1372 안내만", btn(page, "이 금액으로 시작").count() == 0)
    page.unroute("**/api/refund-preview")
    page.get_by_role("radio", name=re.compile("내 사정")).check()
    btn(page, "이 금액으로 시작").wait_for()
    rec(f"{tag}: 내 사정으로 돌리면 위약금을 뺀 금액", "−60,000원" in page.locator(".receipt").inner_text())
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def business_amount(browser, base):
    """유형을 고르면 실제 서버 계산으로 영수증이 열리고 업체 사정이 사건과 첫 통지 문안에 반영된다."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    tag = "업체 잘못 금액"
    with page.expect_response("**/api/refund-preview") as mine_preview:
        page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    mine = mine_preview.value.json()
    btn(page, "이 금액으로 시작").wait_for()
    page.get_by_role("radio", name=re.compile("업체 잘못")).check()
    with page.expect_response("**/api/refund-preview") as business_preview:
        pick_kind(page, "약속한 트레이너·강사가 바뀌거나 그만둠")
    preview = business_preview.value
    business = preview.json()
    contract = preview.request.post_data_json["contract"]
    rec(f"{tag}: 계약 값으로 유형을 보냄", contract.get("cancel_reason") == "business"
        and contract.get("fault_kind") == "trainer_change")
    heading = page.get_by_role("heading", name="예상 환불액(업체 잘못이 인정되면)")
    heading.wait_for()
    rec(f"{tag}: 실제 서버가 계산한 업체 사정 영수증", business["penalty"] == 0
        and business["disputed_refund"] == mine["refund"]
        and page.locator(".receipt").get_by_text("−0원", exact=True).count() == 1
        and page.locator(".receipt-total").get_by_text(f"{business['refund']:,}원", exact=True).count() == 1)
    btn(page, "위약금").first.click()
    rec(f"{tag}: 위약금 설명은 업체 잘못 기준(G4)", page.get_by_text("업체 사정으로 해지하면 위약금을 빼지 않고 계산했어요", exact=False).count() == 1)
    dispute = f"업체가 다투면 위약금 {mine['penalty']:,}원이 빠져 {business['disputed_refund']:,}원이 될 수 있어요"
    rec(f"{tag}: 화면의 다툴 때 금액은 서버 비교액", page.get_by_text(dispute, exact=True).count() == 1)
    # 사례는 금액 아래에 요약 한 줄로 접혀 있다(인정·불인정 수). 펴야 사례가 보인다
    rec(f"{tag}: 사례는 금액 아래 요약으로 접힘", page.get_by_text("3,275,216원", exact=False).count() == 0
        and page.get_by_text(re.compile(r"^(인정|불인정|판단 어려움|원문에 판단 없음) \d")).count() >= 1
        and page.get_by_text("비슷한 사례 3건 참고하기").bounding_box()["y"] > heading.bounding_box()["y"])
    open_cases(page)
    rec(f"{tag}: 비슷한 조정례 결과와 원문 링크", page.get_by_text("3,275,216원", exact=False).count() >= 1
        and page.get_by_role("link", name="1372 원문 보기 (새 창)").get_attribute("target") == "_blank")
    rec(f"{tag}: 인정되지 않은 사례도 함께 보임", page.get_by_text("업체 잘못으로 인정되지 않았어요", exact=False).count() >= 1
        and page.get_by_text("업체 책임에 대한 판단은 사례마다 달랐어요", exact=False).is_visible())

    pick_kind(page, "휴업·폐업이나 시설 일부 폐쇄")
    page.get_by_text("업체가 아예 문을 닫아 연락이 안 되면 문자 대신 1372에 상담하세요").wait_for()
    open_cases(page)
    rec(f"{tag}: 폐쇄 유형은 결정 금액에 10%가 더해진 사례", page.get_by_text("552,000원", exact=False).count() >= 1
        and page.get_by_role("link", name="소비자24 원문 보기 (새 창)").count() >= 1)
    rec(f"{tag}: 폐쇄도 시작 버튼", btn(page, "이 금액으로 시작").count() == 1)
    with page.expect_response("**/api/cases") as opened_response:
        btn(page, "이 금액으로 시작").click()
    opened = opened_response.value.json()
    draft = page.locator(".draft", has_text="휴업이나 시설 폐쇄로")
    draft.first.wait_for()
    rec(f"{tag}: 업체 사정으로 열리고 첫 통지에 개인 사정 문구 없음",
        opened["case"]["contract"]["cancel_reason"] == "business"
        and opened["case"]["contract"]["fault_kind"] == "closure"
        and "개인 사정으로" not in draft.first.inner_text())
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def business_without_cases(browser, base):
    """조정례(/api/mediation-cases)를 못 불러와도 유형 선택지는 화면 상수라 고를 수 있고 금액·시작 버튼으로 간다(#161 B 리뷰)."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    tag = "조정례 없이 업체 잘못"
    page.route("**/api/mediation-cases", lambda route: route.abort())
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").wait_for()
    page.get_by_role("radio", name=re.compile("업체 잘못")).check()
    pick_kind(page, "약속한 트레이너·강사가 바뀌거나 그만둠")
    page.get_by_role("heading", name="예상 환불액(업체 잘못이 인정되면)").wait_for()
    rec(f"{tag}: 유형을 골라 금액과 시작 버튼", btn(page, "이 금액으로 시작").count() == 1
        and page.get_by_text(re.compile(r"^비슷한 사례 \d+건 참고하기$")).count() == 0)
    # 요청을 일부러 끊었으니 그 실패만 콘솔 오류에서 뺀다
    rest = [e for e in errors if "mediation-cases" not in e and "ERR_FAILED" not in e]
    rec(f"{tag}: 콘솔 오류 없음", not rest, "; ".join(rest)[:200])
    ctx.close()


def business_negotiation(browser, base):
    """업체 사정 사건: 업체가 거절하면 반박 문자 아래에 같은 유형의 조정례를 접어 두고,
    반박 뒤에도 거절하면 내용증명 없이 1372 안내로 간다(engine.BUSINESS_MAX_COUNTERS)."""
    from lib import call
    contract = {**call(base, "/api/samples")[1][0]["contract"], "cancel_reason": "business", "fault_kind": "trainer_change"}
    _, res = call(base, "/api/cases", {"contract": contract, "today": "2026-11-16"})
    for event in ({"type": "notice_sent", "channel": "sms"},
                  {"type": "reply_received", "reply_type": "refuse", "text": "강사 변경은 계약 위반이 아닙니다"}):
        _, res = call(base, "/api/cases/step", {"case": res["case"], "event": event, "today": "2026-11-16"})
    tag = "업체 사정 협상"
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)

    def load(step):
        page.evaluate("(s) => localStorage.setItem('reeper.case', JSON.stringify(s))", {"version": 1, "step": step, "offset": 0})
        page.reload(wait_until="networkidle")

    load(res)
    page.get_by_text("비슷한 사례 3건 참고하기").wait_for()
    rec(f"{tag}: 거절 뒤 반박 문자와 비슷한 사례", res["action"]["type"] == "counter" and page.locator(".draft").count() >= 1)
    angry = page.locator('img[src*="angry"]')
    rec(f"{tag}: 업체가 거절하면 반박 문자 제목 옆에 화난 마스코트", angry.count() == 1)
    for event in ({"type": "counter_sent"}, {"type": "reply_received", "reply_type": "refuse", "text": "그래도 환불은 어렵습니다"}):
        # 화면의 오늘은 new_page가 2026-11-16으로 고정한다. 그보다 늦은 기록이면 화면이 409를 받는다
        _, res = call(base, "/api/cases/step", {"case": res["case"], "event": event, "today": "2026-11-16"})
    load(res)
    page.get_by_role("heading", name="1372에 상담하기").wait_for()
    rec(f"{tag}: 반박 뒤 거절이면 내용증명 없이 1372", res["action"]["type"] == "go_1372"
        and btn(page, "내용증명을 보냈어요").count() == 0 and btn(page, "1372에 접수했어요").count() == 1)
    rec(f"{tag}: 1372 단계에도 비슷한 사례", page.get_by_text("비슷한 사례 3건 참고하기").count() == 1)
    # 거절이 아닌 답(접수 안내)에도 같은 반박 문안이 나가지만, 화낼 일이 아니라 화난 마스코트는 두지 않는다(#170 리뷰)
    _, res = call(base, "/api/cases", {"contract": contract, "today": "2026-11-16"})
    for event in ({"type": "notice_sent", "channel": "sms"},
                  {"type": "reply_received", "reply_type": "unknown", "text": "환불 요청은 접수했습니다. 처리 중입니다."}):
        _, res = call(base, "/api/cases/step", {"case": res["case"], "event": event, "today": "2026-11-16"})
    load(res)
    page.locator(".draft").first.wait_for()
    rec(f"{tag}: 거절이 아닌 답에는 화난 마스코트 없음", res["action"]["type"] == "counter" and angry.count() == 0)
    # 거절도 제시도 아닌(unknown) 답이라도 업체가 귀책·위약금을 말하면, 한 번뿐인 반박은 위약금 반박이다.
    # "확인한 뒤 다시 연락드리겠습니다"로 나가면 안 된다(#166)
    _, res = call(base, "/api/cases", {"contract": contract, "today": "2026-11-16"})
    for event in ({"type": "notice_sent", "channel": "sms"},
                  {"type": "reply_received", "reply_type": "unknown", "text": "새 강사를 배정했으니 저희 귀책이 아니고, 위약금 부담은 어렵습니다"}):
        _, res = call(base, "/api/cases/step", {"case": res["case"], "event": event, "today": "2026-11-16"})
    load(res)
    page.locator(".draft").first.wait_for()
    rec(f"{tag}: 귀책·위약금을 말한 unknown 답에는 위약금 반박", res["action"]["type"] == "counter"
        and page.get_by_text("위약금을 공제하지 않고").filter(visible=True).count() >= 1
        and page.get_by_text("확인한 뒤 다시 연락드리겠습니다").count() == 0)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def business_accept_disputed(browser, base):
    """업체 사정 사건에서 업체가 위약금을 뺀 금액(disputed_refund) 이상을 내면, 하한선 경고는 그대로 두고
    받기 버튼을 함께 보인다. 그보다 적으면 받기 버튼이 없다. 반박 뒤 1372 단계에서도 받고 끝낼 수 있다."""
    from lib import call
    contract = {**call(base, "/api/samples")[1][0]["contract"], "cancel_reason": "business", "fault_kind": "trainer_change"}
    day = "2026-11-16"
    _, res = call(base, "/api/cases", {"contract": contract, "today": day})
    _, res = call(base, "/api/cases/step", {"case": res["case"], "event": {"type": "notice_sent", "channel": "sms"}, "today": day})
    noticed = res["case"]
    disputed = noticed["refund"]["disputed_refund"]
    tag = "업체 사정 위약금 뺀 금액"
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)

    def offer(case, amount):
        event = {"type": "reply_received", "reply_type": "low_offer", "amount": amount, "text": "새 강사를 배정했으니 위약금은 뺍니다"}
        return call(base, "/api/cases/step", {"case": case, "event": event, "today": day})[1]

    def load(step):
        page.evaluate("(s) => localStorage.setItem('reeper.case', JSON.stringify(s))", {"version": 1, "step": step, "offset": 0})
        page.reload(wait_until="networkidle")

    rec(f"{tag}: 시험 사건에 위약금이 있음", disputed is not None and 0 < disputed < noticed["refund"]["refund"])
    # 위약금 뺀 금액보다 적으면 경고만 있고 받기 버튼은 없다
    load(offer(noticed, disputed - 1000))
    btn(page, "이 문자를 보냈어요").wait_for()
    rec(f"{tag}: 그보다 적으면 받기 버튼 없음", btn(page, "으로 받을게요").count() == 0 and btn(page, "에 합의했어요").count() == 0)
    # 위약금 뺀 금액이면 경고와 받기 버튼이 함께 있다. 반박이 주 버튼이다
    res = offer(noticed, disputed)
    load(res)
    btn(page, "으로 받을게요").wait_for()
    rec(f"{tag}: 같은 금액이면 경고와 받기 버튼", res["action"]["warn"] and page.get_by_text("보다 적어요").count() >= 1
        and btn(page, "이 문자를 보냈어요").count() == 1)
    # 반박 한 번 뒤 같은 금액이면 1372 안내와 받기 버튼이 함께 있고, 누르면 합의로 넘어간다
    _, res = call(base, "/api/cases/step", {"case": res["case"], "event": {"type": "counter_sent"}, "today": day})
    res = offer(res["case"], disputed + 500)
    load(res)
    page.get_by_role("heading", name="1372에 상담하기").wait_for()
    rec(f"{tag}: 반박 뒤에도 1372와 받기 버튼", res["action"]["type"] == "go_1372" and res["action"]["warn"]
        and btn(page, "1372에 접수했어요").count() == 1 and btn(page, "으로 받을게요").count() == 1)
    btn(page, "으로 받을게요").click()
    page.wait_for_function("() => JSON.parse(localStorage.getItem('reeper.case')).step.case.stage === 'agreed'")
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('reeper.case')).step.case")
    rec(f"{tag}: 받으면 그 금액으로 합의", saved["stage"] == "agreed" and saved["agreed_amount"] == disputed + 500)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def industry_gate(browser, base):
    """기준을 확인하지 않은 업종이면 금액·시작 버튼 대신 1372 안내가 나오고, 확인된 업종으로 돌리면 금액이 다시 보인다."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    tag = "업종"
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").wait_for()
    rec(f"{tag}: 기본은 헬스장", page.get_by_role("radio", name=re.compile("헬스장")).is_checked())
    page.get_by_role("radio", name=re.compile("그 밖의 업종")).check()
    page.get_by_text("이 업종은 아직 계산하지 않아요").wait_for()
    rec(f"{tag}: 그 밖이면 금액·시작 버튼 없음", page.get_by_role("heading", name="예상 환불액").count() == 0
        and btn(page, "이 금액으로 시작").count() == 0)
    rec(f"{tag}: 그 밖이면 1372 안내", page.get_by_text("국번 없이 1372").count() == 1)
    page.screenshot(path=SHOTS / "업종.png", full_page=True)
    page.get_by_role("radio", name=re.compile("요가")).check()
    btn(page, "이 금액으로 시작").wait_for()
    rec(f"{tag}: 요가·필라테스는 금액 보임", page.get_by_role("heading", name="예상 환불액").count() == 1)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def zero_refund(browser, base):
    """계산한 환불액이 0원이면 시작 버튼 대신 안내가 나온다. 0원 환불을 요청하는 문자를 만들지 않는다(2026-11-22 시나리오 점검)."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)

    def zero(route):
        body = route.fetch().json()
        route.fulfill(json={**body, "refund": 0, "per_day_loss": 0})
    page.route("**/api/refund-preview", zero)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    shown = shows(page.get_by_role("heading", name="계산으로는 돌려받을 돈이 없어요"))
    rec("0원 환불: 안내가 나오고 시작 버튼은 없음", shown and btn(page, "이 금액으로 시작").count() == 0
        and btn(page, "계약 수정").count() == 1)
    rec("0원 환불: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def restart_from_amount(browser, base):
    """사건을 열기 전 금액 화면에서도 위 막대에 '새로 시작'이 있고, 누르면 빈 입력 화면으로 돌아간다(저장된 것이 없어 묻지 않는다)."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    rec("새로 시작: 입력 화면에는 없음", btn(page, "새로 시작", exact=True).count() == 0)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").wait_for()
    rec("새로 시작: 금액 화면부터 보임", btn(page, "새로 시작", exact=True).count() == 1)
    btn(page, "새로 시작", exact=True).click()
    back = shows(page.get_by_role("heading", name="내 계약 입력"))
    rec("새로 시작: 금액 화면에서 누르면 빈 입력 화면", back and btn(page, "이 금액으로 시작").count() == 0
        and btn(page, "새로 시작", exact=True).count() == 0 and page.get_by_text("지금 기록을 지울까요?").count() == 0)
    rec("새로 시작: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def good_offer(browser, base):
    """업체가 받고 싶은 금액 이상을 말하면, 그 금액을 받겠다는 새 문자가 접히지 않고 보인다(보낸 적 없는 문자다)."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").click()
    open_reply(page)
    record_amount(page, "460000")
    btn(page, "에 합의했어요").wait_for()
    rec("좋은 제시액: 수락 문자가 펼쳐져 있음", page.get_by_text("원으로 환불받겠습니다").filter(visible=True).count() == 1
        and page.get_by_text("보낸 문자 다시 보기").count() == 0)
    ctx.close()


def callback_draft(browser, base):
    """업체가 나중에 연락하겠다고 미루면 언제 연락할지 묻는 문자가 펼쳐져 나오고, 재요청을 보낸 뒤에는 다시 나오지 않는다."""
    errors: list[str] = []
    ctx, page = new_page(browser, base, {"width": 390, "height": 844}, errors)
    page.get_by_role("group", name="가상 계약서로 해 보기").get_by_role("button").first.click()
    btn(page, "이 금액으로 시작").click()
    btn(page, "문자로 보냈어요").click()
    open_reply(page)
    btn(page, "다시 연락 준대요").click()
    ask = page.get_by_text("날짜와 시간을 문자로 알려 주시겠어요")
    ask.first.wait_for()
    rec("미루는 답 뒤: 묻는 문자가 펼쳐져 있고 보낸 문자 다시 보기는 없음", ask.filter(visible=True).count() == 1
        and page.get_by_text("보낸 문자 다시 보기").count() == 0 and btn(page, "업체 답장 기록").filter(visible=True).count() == 1)
    btn(page, "4일 지남").click()
    btn(page, "다시 보냈어요").click()
    page.get_by_text("답장 기한").first.wait_for()
    rec("미루는 답 뒤: 재요청을 보낸 뒤에는 묻는 문자가 없음", ask.count() == 0)
    ctx.close()


def storage_recovery(browser, base):
    cases = {
        "깨진 JSON": "{bad",
        "알 수 없는 모양": '{"hello":1}',
        "필드 빠진 사건": '{"step":{"case":{"stage":"waiting","contract":{},"refund":{},"timeline":[]},'
                        '"action":{"type":"wait","reason":"x"},"drafts":{}},"offset":0}',
    }
    for label, raw in cases.items():
        errors: list[str] = []
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base, wait_until="networkidle")
        page.evaluate("(raw) => localStorage.setItem('reeper.case', raw)", raw)
        page.reload(wait_until="networkidle")
        # 망가진 저장값은 버리고 대문부터 다시 연다. 시작하기를 누르면 가상 계약서로 해 보기가 보인다
        ok_start = shows(btn(page, "시작하기", exact=True))
        if ok_start:
            btn(page, "시작하기", exact=True).click()
        ok_intro = shows(page.get_by_text("가상 계약서로 해 보기"))
        rec(f"저장값 복구: {label}", ok_start and ok_intro and not page.locator("[role=alert]").filter(has_text=re.compile(r"\S")).count(), "; ".join(errors)[:120])
        ctx.close()


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("frontend/dist가 없습니다. 먼저 npm run build 를 하세요.")
        return 2
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        with server() as base:
            full_flow(browser, base, "데스크톱", {"width": 1280, "height": 900})
            full_flow(browser, base, "모바일", {"width": 390, "height": 844})
            demo_hidden(browser, base)
            photo_fill(browser, base)
            not_sent_drafts(browser, base)
            business_fault(browser, base)
            business_amount(browser, base)
            business_without_cases(browser, base)
            business_negotiation(browser, base)
            business_accept_disputed(browser, base)
            industry_gate(browser, base)
            zero_refund(browser, base)
            restart_from_amount(browser, base)
            good_offer(browser, base)
            callback_draft(browser, base)
            storage_recovery(browser, base)
        with server({"OPENAI_API_KEY": "harness-no-call", "LLM_DAILY_LIMIT": "0"}) as base:
            limit_flow(browser, base)
        browser.close()
    width = max(len(r[0]) for r in results)
    for name, ok, note in results:
        print(f"{'통과' if ok else '실패'}  {name.ljust(width)}  {note}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과  스크린샷: {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

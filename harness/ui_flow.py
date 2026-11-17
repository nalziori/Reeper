"""화면 하니스: 빌드된 화면을 실제 브라우저(headless Chrome)로 열어 종결까지 간다.
실행: cd frontend && npm run build 후 python harness/ui_flow.py [스크린샷 폴더]
확인: 흐름 완주와 소요 시간, 깨진 저장값 복구, 모바일 가로 넘침, 내보내기, 콘솔 오류."""
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from lib import ROOT, server

SHOTS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/reeper-shots")
SHOTS.mkdir(parents=True, exist_ok=True)
results: list[tuple[str, bool, str]] = []


def rec(name, ok, note=""):
    results.append((name, bool(ok), note))


def btn(page, name, exact=False):
    return page.get_by_role("button", name=name, exact=exact)


def new_page(browser, base, viewport, errors):
    ctx = browser.new_context(viewport=viewport, accept_downloads=True, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    page.clock.set_fixed_time(datetime(2026, 11, 16, 12, 0, 0))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(base + "/?demo", wait_until="networkidle")  # 시연 조작은 ?demo가 있을 때만 보인다
    return ctx, page


def overflow(page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - window.innerWidth")


def full_flow(browser, base, tag, viewport):
    errors: list[str] = []
    ctx, page = new_page(browser, base, viewport, errors)
    t0 = time.time()
    page.screenshot(path=SHOTS / f"{tag}-1-intake.png", full_page=True)
    # 샘플 버튼: 샘플 계약서로 해 보기 카드 안의 첫 primary 버튼
    sample_buttons = page.locator("h2:has-text('샘플 계약서로 해 보기')").locator("xpath=ancestor::*[self::div][1]").get_by_role("button")
    sample_buttons.first.click()
    page.get_by_text("예상 환불액").first.wait_for()
    rec(f"{tag}: 예상 환불액 표시", page.get_by_text("원").count() > 0)
    page.screenshot(path=SHOTS / f"{tag}-2-preview.png", full_page=True)
    btn(page, "이 기준으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    page.screenshot(path=SHOTS / f"{tag}-3-prepare.png", full_page=True)
    rec(f"{tag}: 통화 준비 카드와 문자 문안", page.get_by_text("통화 준비 카드").count() > 0 and page.get_by_text("문자로 보낼 문안").count() > 0)
    link = page.get_by_role("link", name="문자 앱으로 열기").first
    href = link.get_attribute("href") if link.count() else None
    rec(f"{tag}: 문자 앱 링크가 sms: 주소", bool(href) and href.startswith("sms:") and "body=" in href, (href or "없음")[:40])
    rec(f"{tag}: 통화 카드 구역 제목 굵게", page.locator(".draft-section").count() >= 3, f"{page.locator('.draft-section').count()}개")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="복사", exact=True).last.click()
    copied = page.evaluate("navigator.clipboard.readText()")
    rec(f"{tag}: 복사가 원문 그대로(제목 줄 포함)", "[첫마디]" in copied and "\n" in copied and "[끊기 전에]" in copied, f"{len(copied)}자")
    page.keyboard.press("Tab")
    rec(f"{tag}: 키보드 포커스 이동", page.evaluate("document.activeElement && document.activeElement !== document.body"))
    rec(f"{tag}: 시연 패널에 날짜 버튼(ready)", btn(page, "하루 지남").count() == 1 and btn(page, "사장:").count() == 0)
    btn(page, "문자로 보냈어요").click()
    page.get_by_text("답변 기한").first.wait_for()
    rec(f"{tag}: 답변 기한과 남은 날", page.get_by_text(re.compile(r"답변 기한 .*3일 남음")).count() >= 1,
        page.get_by_text(re.compile("답변 기한 ")).first.inner_text())
    rec(f"{tag}: 법정 기한 아님 문구", page.get_by_text("법정 기한이 아니에요").count() >= 1)
    page.screenshot(path=SHOTS / f"{tag}-4-waiting.png", full_page=True)
    # 버튼 경로: 금액 제시(수용선 미만)
    page.get_by_label("제시한 금액(원)").fill("100000")
    btn(page, "금액을 제시했어요").click()
    page.get_by_text("최저 수용선").first.wait_for()
    rec(f"{tag}: 수용선 미만 경고", page.get_by_text(re.compile("최저 수용선.*보다 적습니다")).count() >= 1)
    rec(f"{tag}: negotiating에서 낡은 기한 줄 없음", page.get_by_text(re.compile("답변 기한 .*(남음|지났어요|오늘까지)")).count() == 0)
    page.screenshot(path=SHOTS / f"{tag}-5-lowoffer.png", full_page=True)
    btn(page, "반박 문안을 보냈어요").click()
    btn(page, "하루 지남").wait_for()
    # 시연 조작: 사장 답(텍스트 경로, 가짜 LLM 키워드 판단)
    btn(page, "사장: 네 알겠습니다 환불해 드릴게요").click()
    btn(page, "입금을 확인했어요").wait_for()
    rec(f"{tag}: 입금 기한 표시", page.get_by_text(re.compile("입금 기한 ")).count() >= 1)
    page.screenshot(path=SHOTS / f"{tag}-6-agreed.png", full_page=True)
    # 내보내기
    with page.expect_download() as dl:
        btn(page, "요약 파일 저장").click()
    name = dl.value.suggested_filename
    path = dl.value.path()
    text = Path(path).read_text(encoding="utf-8")
    rec(f"{tag}: 요약 파일 저장", name.startswith("reeper-") and name.endswith(".txt") and "원" in text, name)
    with page.expect_download() as dj:
        btn(page, "보관용 파일 저장").click()
    rec(f"{tag}: 보관용 JSON 저장", dj.value.suggested_filename.endswith(".json"), dj.value.suggested_filename)
    rec(f"{tag}: 실제/모의 구분 카드", page.get_by_text("실제로 되는 것과 시연용인 것").count() == 1)
    btn(page, "입금을 확인했어요").click()
    page.get_by_text("환불금을 받았습니다").wait_for()
    elapsed = time.time() - t0
    rec(f"{tag}: 종결까지 완주", True, f"{elapsed:.1f}초")
    rec(f"{tag}: 3분 이내", elapsed < 180, f"{elapsed:.1f}초")
    rec(f"{tag}: 가로 넘침 없음", overflow(page) <= 0, f"{overflow(page)}px")
    rec(f"{tag}: 시연 패널이 종결 뒤 숨음", btn(page, "하루 지남").count() == 0)
    page.screenshot(path=SHOTS / f"{tag}-7-closed.png", full_page=True)
    # 새로고침해도 이어진다
    page.reload(wait_until="networkidle")
    rec(f"{tag}: 새로고침 뒤 사건 유지", page.get_by_text("환불금을 받았습니다").count() == 1)
    rec(f"{tag}: 콘솔 오류 없음", not errors, "; ".join(errors)[:200])
    ctx.close()


def demo_hidden(browser, base):
    """?demo 없이 열면 시연 조작이 보이지 않는다(배포 화면)."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    page = ctx.new_page()
    page.goto(base, wait_until="networkidle")
    page.locator("h2:has-text('샘플 계약서로 해 보기')").locator("xpath=ancestor::*[self::div][1]").get_by_role("button").first.click()
    btn(page, "이 기준으로 시작").click()
    btn(page, "문자로 보냈어요").wait_for()
    rec("배포 화면: 시연 조작 숨김", btn(page, "하루 지남").count() == 0 and page.get_by_text("시연용").count() == 0)
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
        ok_intro = page.get_by_text("샘플 계약서로 해 보기").count() == 1
        rec(f"저장값 복구: {label}", ok_intro and not page.locator("[role=alert]").count(), "; ".join(errors)[:120])
        ctx.close()


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("frontend/dist가 없습니다. 먼저 npm run build 를 하세요.")
        return 2
    with server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        full_flow(browser, base, "데스크톱", {"width": 1280, "height": 900})
        full_flow(browser, base, "모바일", {"width": 390, "height": 844})
        demo_hidden(browser, base)
        storage_recovery(browser, base)
        browser.close()
    width = max(len(r[0]) for r in results)
    for name, ok, note in results:
        print(f"{'통과' if ok else '실패'}  {name.ljust(width)}  {note}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과  스크린샷: {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

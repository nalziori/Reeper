"""검증 하니스 공용: 키 없는 서버를 임의 포트에 띄우고 HTTP로 부른다. 외부 패키지 없이 표준 라이브러리만 쓴다."""
import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def server(extra_env: dict | None = None):
    """실제 LLM 키를 지운 서버. extra_env로 값을 더할 수 있다. 끝나면 종료한다."""
    port = free_port()
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"} | (extra_env or {})
    py = BACKEND / ".venv" / "bin" / "python"
    proc = subprocess.Popen([str(py if py.exists() else sys.executable), "-m", "uvicorn", "app.main:app",
                             "--port", str(port), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError("서버가 떴다 꺼졌습니다: " + proc.stderr.read().decode()[-500:])
                time.sleep(0.1)
        else:
            raise RuntimeError("서버가 시간 안에 뜨지 않았습니다")
        yield base
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)


def call(base: str, path: str, body=None, raw: bytes | None = None) -> tuple[int, dict | list | str]:
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    req = urllib.request.Request(base + path, data=data, method="GET" if data is None else "POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode(errors="replace")
        except ConnectionError:
            # 서버가 큰 본문(413)을 다 받기 전에 연결을 닫으면 Windows에서 본문 읽기가 끊긴다. 상태 코드만 돌려준다
            return e.code, ""
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, text

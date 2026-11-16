"""테스트는 실행 환경에 API 키가 있어도 가짜 LLM으로 시작한다."""
import os

os.environ.pop("OPENAI_API_KEY", None)

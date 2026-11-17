import { Container, getContainer } from '@cloudflare/containers'

interface Env {
  REEPER: DurableObjectNamespace<ReeperContainer>
  OPENAI_API_KEY?: string // wrangler secret put OPENAI_API_KEY. 없으면 가짜 LLM으로 뜬다
  LLM_DAILY_LIMIT: string
  OPENAI_MODEL: string
  TZ: string
}

// 화면과 /api를 함께 내보내는 FastAPI 컨테이너. 요청은 모두 한 인스턴스로 보낸다.
export class ReeperContainer extends Container<Env> {
  defaultPort = 8000
  // 잠들면 프로세스가 내려가 하루 호출 수가 0으로 돌아간다. 너무 짧게 잡지 않는다
  sleepAfter = '2h'

  constructor(ctx: DurableObjectState<Env>, env: Env) {
    super(ctx, env)
    const vars: Record<string, string> = { LLM_DAILY_LIMIT: env.LLM_DAILY_LIMIT, OPENAI_MODEL: env.OPENAI_MODEL, TZ: env.TZ }
    if (env.OPENAI_API_KEY) vars.OPENAI_API_KEY = env.OPENAI_API_KEY
    this.envVars = vars
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return getContainer(env.REEPER).fetch(request)
  },
}

// 서버 계약(docs/계약.md)의 화면 쪽 사본. backend/app/models.py와 같이 바꾼다.
export type Contract = {
  gym_name: string
  total_paid: number
  start_date: string
  end_date: string
  special_terms?: string
  unit?: 'day' | 'month' | 'count'
  total_count?: number | null
  used_count?: number | null
  addon_value?: number
  security_deposit?: number
}
export type Refund = {
  total_days: number
  used_days: number
  used_amount: number
  penalty: number
  refund: number
  per_day_loss: number
  addon: number
  unit_label: string
  security_deposit: number
  refs: string[]
  provisional: boolean
}
export type Case = {
  contract: Contract
  refund: Refund
  target: number
  floor: number
  stage: 'ready' | 'waiting' | 'negotiating' | 'escalated' | 'agreed' | 'closed' | 'handed_off'
  notified_on: string | null
  deadline_on: string | null
  attempts: number
  last_reply: ReplyType | null
  offered: number | null
  agreed_amount: number | null
  deposit_due_on: string | null
  timeline: { on: string; type: string; text: string }[]
  situation?: string
  strategy?: Strategy | null
}
// 상황 설명으로 세운 전략. 표시용이다. 근거의 정식 명칭은 GET /api/rules에서 붙인다.
export type Strategy = {
  summary: string
  grounds: { rule_id: string; why: string; verified: boolean }[]
  contract_points: { quote: string; how_to_handle: string }[]
  objections: { objection: string; response: string }[]
  cautions: string[]
  questions: string[]
}
export type ReplyType = 'accept' | 'low_offer' | 'refuse' | 'list_price' | 'visit' | 'unknown' | 'no_answer' | 'callback'
export type Action = { type: string; reason: string; warn: boolean }
export type CaseEvent = {
  type: 'notice_sent' | 'call_attempted' | 'reply_received' | 'counter_sent' | 'time_passed' |
    'agreement_recorded' | 'deposit_confirmed' | 'escalation_sent' | 'handoff_done'
  channel?: 'sms' | 'call'
  text?: string
  reply_type?: ReplyType | null
  amount?: number | null
}
// 붙여넣은 답장에서 짚은 주장. 표시용이다. rule_id가 null이면 "확인 필요"로 보여 준다.
export type Claim = { quote: string; claim: string; rule_id: string | null; advice: string }
export type Analysis = { claims: Claim[]; note: string }
export type Step = {
  case: Case
  action: Action
  drafts: Record<string, string>
  llm_fallback?: boolean
  analysis?: Analysis | null
}
// 문안 말투. 고정 양식이 기본이고, 다듬은 문안은 숫자·근거 검사를 통과해야 온다.
export type Tone = 'polite' | 'firm'
export type Polished = { text: string; polished: boolean }
export type Health = { ok: boolean; llm: string; upload: boolean; calls_left: number; tokens_today: number }
export type Sample = { id: string; label: string; contract: Contract }
export type Rules = Record<string, { title: string; summary: string; url: string; verified: boolean }>

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => null)
    if (typeof error?.detail === 'string') throw new Error(error.detail)
    throw new Error(`요청에 실패했습니다 (${res.status})`)
  }
  return res.json()
}

export const api = {
  health: () => call<Health>('/api/health'),
  samples: () => call<Sample[]>('/api/samples'),
  rules: () => call<Rules>('/api/rules'),
  preview: (contract: Contract, today: string) => call<Refund>('/api/refund-preview', { contract, today }),
  open: (contract: Contract, today: string, limits?: { target?: number; floor?: number }) =>
    call<Step>('/api/cases', { contract, today, ...limits }),
  strategy: (c: Case, situation: string, today: string) =>
    call<{ case: Case; llm_fallback?: boolean }>('/api/cases/strategy', { case: c, situation, today }),
  polish: (c: Case, kind: string, tone: Tone) => call<Polished>('/api/drafts/polish', { case: c, kind, tone }),
  step: (c: Case, event: CaseEvent, today: string) =>
    call<Step>('/api/cases/step', { case: c, event, today }),
}

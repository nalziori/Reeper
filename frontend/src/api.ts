// 서버 계약(docs/계약.md)의 화면 쪽 사본. backend/app/models.py와 같이 바꾼다.
export type Contract = {
  gym_name: string
  total_paid: number
  start_date: string
  end_date: string
  special_terms?: string
}
export type Refund = {
  total_days: number
  used_days: number
  used_amount: number
  penalty: number
  refund: number
  per_day_loss: number
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
  offered: number | null
  agreed_amount: number | null
  deposit_due_on: string | null
  timeline: { on: string; type: string; text: string }[]
}
export type Action = { type: string; reason: string; warn: boolean }
export type Step = { case: Case; action: Action; drafts: Record<string, string> }
export type Sample = { id: string; label: string; contract: Contract }
export type Rules = Record<string, { title: string; summary: string; url: string; verified: boolean }>

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (res.status === 409) {
    const error = await res.json().catch(() => null)
    if (typeof error?.detail === 'string') throw new Error(error.detail)
  }
  if (!res.ok) throw new Error(`요청에 실패했습니다 (${res.status})`)
  return res.json()
}

export const api = {
  samples: () => call<Sample[]>('/api/samples'),
  rules: () => call<Rules>('/api/rules'),
  open: (contract: Contract, today: string) => call<Step>('/api/cases', { contract, today }),
  step: (c: Case, event: Record<string, unknown>, today: string) =>
    call<Step>('/api/cases/step', { case: c, event, today }),
}

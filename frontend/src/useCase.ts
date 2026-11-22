import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Case, type CaseEvent, type Step } from './api'
import { STORAGE_KEY, isoDate } from './format'

// 사건은 서버가 아니라 이 브라우저에만 보관한다.
const KEY = STORAGE_KEY
const VERSION = 1
const REFRESH_ERROR = '다음 행동을 새로 불러오지 못했습니다.'

// refundFrom: 알리기 전에 날짜가 지나 예상 환불액이 줄었을 때, 처음 보았던 금액. 줄었다는 안내(Prepare)에만 쓴다
export type Saved = { step: Step; offset: number; note?: string; actionDate?: string; refundFrom?: number }
export type Send = (event: CaseEvent, patch?: Partial<Saved>, opts?: { analyze?: boolean }) => Promise<boolean>

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isStr = (v: unknown): v is string => typeof v === 'string'
const orNull = (v: unknown, test: (x: unknown) => boolean) => v === null || test(v)
const isStrArr = (v: unknown) => Array.isArray(v) && v.every(isStr)
const isObjArr = (v: unknown, keys: string[]) =>
  Array.isArray(v) && v.every((x) => isObj(x) && keys.every((k) => isStr(x[k])))
// 전략은 표시용이다. 모양이 틀리면 사건 전체를 버린다.
const isStrategy = (s: unknown): boolean => isObj(s) && isStr(s.summary)
  && Array.isArray(s.grounds) && s.grounds.every((g) => isObj(g) && isStr(g.rule_id) && isStr(g.why) && typeof g.verified === 'boolean')
  && isObjArr(s.contract_points, ['quote', 'how_to_handle']) && isObjArr(s.objections, ['objection', 'response'])
  && isStrArr(s.cautions) && isStrArr(s.questions)
const STAGES = ['ready', 'waiting', 'negotiating', 'escalated', 'agreed', 'closed', 'handed_off']

// 화면이 바로 읽는 필드는 모양을 하나씩 확인한다. 하나라도 틀리면 저장값을 쓰지 않는다.
const isCase = (c: unknown): boolean => {
  if (!isObj(c) || !isObj(c.contract) || !isObj(c.refund)) return false
  const { contract: k, refund: r } = c
  return STAGES.includes(c.stage as string)
    && isStr(k.gym_name) && isNum(k.total_paid) && isStr(k.start_date) && isStr(k.end_date)
    && ['refund', 'used_amount', 'penalty', 'per_day_loss', 'addon', 'security_deposit', 'total_days', 'used_days']
      .every((f) => isNum(r[f]))
    && isStr(r.unit_label) && Array.isArray(r.refs) && r.refs.every(isStr) && typeof r.provisional === 'boolean'
    && isNum(c.target) && isNum(c.floor)
    && orNull(c.notified_on, isStr) && orNull(c.deadline_on, isStr) && orNull(c.deposit_due_on, isStr)
    && orNull(c.offered, isNum) && orNull(c.agreed_amount, isNum)
    && Array.isArray(c.timeline)
    && c.timeline.every((t) => isObj(t) && isStr(t.on) && isStr(t.type) && isStr(t.text))
    && (c.situation === undefined || isStr(c.situation))
    && (c.strategy == null || isStrategy(c.strategy))
}

const isStep = (v: unknown): v is Step => {
  if (!isObj(v) || !isCase(v.case) || !isObj(v.action) || !isObj(v.drafts)) return false
  return isStr(v.action.type) && isStr(v.action.reason) && typeof v.action.warn === 'boolean'
    && Object.values(v.drafts).every(isStr)
    && (v.llm_fallback === undefined || typeof v.llm_fallback === 'boolean')
    && (v.analysis == null || (isObj(v.analysis) && Array.isArray(v.analysis.claims) && isStr(v.analysis.note)))
}

// 깨졌거나 모양이 틀린 값은 null로 처리하고 키를 지운다. 버전 없는 예전 형식도 읽는다.
const parse = (raw: string | null): Saved | null => {
  if (raw === null) return null
  const v: unknown = JSON.parse(raw)
  if (!isObj(v) || !isStep(v.step)) return null
  if (v.version !== undefined && v.version !== VERSION) return null
  if (typeof v.offset !== 'number' || !Number.isFinite(v.offset)) return null
  if (v.note !== undefined && typeof v.note !== 'string') return null
  if (v.actionDate !== undefined && typeof v.actionDate !== 'string') return null
  if (v.refundFrom !== undefined && (typeof v.refundFrom !== 'number' || !Number.isFinite(v.refundFrom))) return null
  return { step: v.step, offset: v.offset, note: v.note, actionDate: v.actionDate, refundFrom: v.refundFrom }
}

// 옛 규칙(개월로 셈)으로 열고 아직 통지하지 않은 월 단위 사건. 첫 통지 때 예상 환불액만 일할로 바뀌고
// 희망 금액·하한선은 옛 금액에 남으므로, 통지 전에 새 금액을 보여 주고 기준을 다시 정하게 한다(#137).
// 새 규칙은 unit_label "개월"을 만들지 않는다. 첫 통지 뒤에는 금액이 고정돼 서로 어긋나지 않는다.
export const isOldMonth = (c: Case): boolean => c.refund.unit_label === '개월' && c.notified_on === null

const load = (): Saved | null => {
  try {
    const saved = parse(localStorage.getItem(KEY))
    if (!saved) localStorage.removeItem(KEY)
    return saved
  } catch {
    try { localStorage.removeItem(KEY) } catch { /* 저장소를 쓸 수 없으면 그대로 둔다 */ }
    return null
  }
}

export function useCase() {
  const [saved, setSaved] = useState<Saved | null>(load)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const revision = useRef(0)
  const pending = useRef(0)

  const keep = useCallback((s: Saved | null) => {
    revision.current++
    setSaved(s)
    try {
      if (s) localStorage.setItem(KEY, JSON.stringify({ version: VERSION, ...s }))
      else localStorage.removeItem(KEY)
    } catch { /* 저장하지 못해도 화면은 계속 쓴다 */ }
  }, [])

  useEffect(() => {
    if (!saved || saved.step.case.stage === 'closed') return
    let active = true
    let refreshing = false
    const refresh = async () => {
      const today = isoDate(saved.offset)
      if (refreshing || pending.current || saved.actionDate === today) return
      refreshing = true
      const expected = revision.current
      try {
        // 알리기 전 사건은 서버가 오늘 기준 환불액으로 다시 계산해 돌려준다. 그 밖의 단계는 사건이 그대로다
        const { action, drafts, case: next } = await api.step(saved.step.case, { type: 'time_passed' }, today)
        if (active && expected === revision.current) {
          const before = saved.step.case.refund.refund
          const dropped = saved.step.case.stage === 'ready' && next.refund.refund < before
          keep({ ...saved, actionDate: today, refundFrom: dropped ? saved.refundFrom ?? before : saved.refundFrom,
            step: { ...saved.step, case: next, action, drafts } })
          setError((current) => current === REFRESH_ERROR ? '' : current)
        }
      } catch {
        if (active && expected === revision.current) {
          setError((current) => current || REFRESH_ERROR)
        }
      } finally {
        refreshing = false
      }
    }
    void refresh()
    window.addEventListener('focus', refresh)
    const timer = window.setInterval(refresh, 60_000)
    return () => {
      active = false
      window.removeEventListener('focus', refresh)
      window.clearInterval(timer)
    }
  }, [saved, keep])

  // actionDate는 다음 행동을 그날 기준으로 받았는지 표시한다. 전략 요청처럼 행동을 바꾸지 않는 호출은 undefined를 넘겨 그대로 둔다.
  const run = async (p: Promise<Step>, today: string | undefined, patch: Partial<Saved> = {}) => {
    const expected = ++revision.current
    pending.current++
    setBusy(true)
    try {
      setError('')
      const step = await p
      if (expected !== revision.current) return false
      keep({ offset: 0, ...saved, ...patch, actionDate: today ?? saved?.actionDate, step })
      return true
    } catch (e) {
      if (expected === revision.current) setError(String((e as Error).message))
      return false
    } finally {
      pending.current--
      if (!pending.current) setBusy(false)
    }
  }
  const send: Send = (event, patch = {}, opts = {}) => {
    if (pending.current) return Promise.resolve(false)
    const today = isoDate(patch.offset ?? saved!.offset)
    // 통화 직후 문자는 통화를 기록한 직후에만 쓴다. 날짜만 지날 때는 두고, 다른 기록이 생기면 지운다.
    const next = event.type === 'time_passed' || 'note' in patch ? patch : { ...patch, note: undefined }
    return run(api.step(saved!.step.case, event, today, opts.analyze), today, next)
  }

  // 상황 설명으로 전략을 받는다. 서버는 단계·금액·문안을 바꾸지 않으므로 사건만 바꿔 끼운다.
  // 받은 전략이 null인지(자동 전략을 쓸 수 없음) 화면이 알 수 있게 결과를 돌려준다.
  const plan = async (situation: string): Promise<'ok' | 'empty' | 'failed'> => {
    if (pending.current || !saved) return 'failed'
    const base = saved.step
    let empty = false
    const p = api.strategy(base.case, situation, isoDate(saved.offset)).then(({ case: c }) => {
      empty = !c.strategy
      return { ...base, case: c }
    })
    if (!await run(p, undefined)) return 'failed'
    return empty ? 'empty' : 'ok'
  }

  // 옛 월 단위 사건의 예상 환불액을 새 규칙으로 바꾼다. useNew면 희망 금액·하한선도 새 금액으로 맞춘다.
  // 기록·전략 등 나머지는 그대로 두고, 바뀐 금액으로 다음 행동과 문안을 다시 받는다.
  const rebase = async (useNew: boolean): Promise<boolean> => {
    if (pending.current || !saved) return false
    const base = saved.step.case
    const today = isoDate(saved.offset)
    const p = api.preview(base.contract, today).then((refund) => {
      const c = { ...base, refund, ...(useNew ? { target: refund.refund, floor: refund.refund } : {}) }
      return api.step(c, { type: 'time_passed' }, today)
    })
    return run(p, today)
  }

  return { saved, error, busy, keep, send, plan, rebase }
}

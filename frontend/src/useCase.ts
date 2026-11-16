import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type CaseEvent, type Step } from './api'
import { STORAGE_KEY, isoDate } from './format'

// 사건은 서버가 아니라 이 브라우저에만 보관한다.
const KEY = STORAGE_KEY
const VERSION = 1
const REFRESH_ERROR = '다음 행동을 새로 불러오지 못했습니다.'

export type Saved = { step: Step; offset: number; note?: string; actionDate?: string }
export type Send = (event: CaseEvent, patch?: Partial<Saved>) => Promise<boolean>

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isStr = (v: unknown): v is string => typeof v === 'string'
const orNull = (v: unknown, test: (x: unknown) => boolean) => v === null || test(v)
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
  return { step: v.step, offset: v.offset, note: v.note, actionDate: v.actionDate }
}

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
        const { action, drafts } = await api.step(saved.step.case, { type: 'time_passed' }, today)
        if (active && expected === revision.current) {
          keep({ ...saved, actionDate: today, step: { ...saved.step, action, drafts } })
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

  const run = async (p: Promise<Step>, today: string, patch: Partial<Saved> = {}) => {
    const expected = ++revision.current
    pending.current++
    setBusy(true)
    try {
      setError('')
      const step = await p
      if (expected !== revision.current) return false
      keep({ offset: 0, ...saved, ...patch, actionDate: today, step })
      return true
    } catch (e) {
      if (expected === revision.current) setError(String((e as Error).message))
      return false
    } finally {
      pending.current--
      if (!pending.current) setBusy(false)
    }
  }
  const send: Send = (event, patch = {}) => {
    if (pending.current) return Promise.resolve(false)
    const today = isoDate(patch.offset ?? saved!.offset)
    return run(api.step(saved!.step.case, event, today), today, patch)
  }

  return { saved, error, busy, keep, send }
}

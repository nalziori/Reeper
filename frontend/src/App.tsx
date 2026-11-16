import { Badge } from '@astryxdesign/core/Badge'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { TextInput } from '@astryxdesign/core/TextInput'
import { VStack } from '@astryxdesign/core/VStack'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type CaseEvent, type Contract, type Refund, type Rules, type Sample, type Step } from './api'

// 사건은 서버가 아니라 이 브라우저에만 보관한다.
const KEY = 'reeper.case'
const REFRESH_ERROR = '다음 행동을 새로 불러오지 못했습니다.'
type Saved = { step: Step; offset: number; note?: string; actionDate?: string }
const load = (): Saved | null => JSON.parse(localStorage.getItem(KEY) ?? 'null')

const won = (n: number) => `${n.toLocaleString('ko-KR')}원`
const isoDate = (offset: number) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const STAGE: Record<string, string> = {
  ready: '보낼 준비', waiting: '답 기다리는 중', negotiating: '대응 필요', escalated: '내용증명 단계',
  agreed: '입금 기다리는 중', closed: '환불 완료', handed_off: '1372 접수',
}
const DRAFT: Record<string, string> = {
  notice_sms: '문자로 보낼 문안', call_card: '전화로 말할 때: 통화 준비 카드', after_call_sms: '통화 직후 보낼 확인 문자',
  follow_up: '재요청 문안', counter_refuse: '다음에 보낼 문장', counter_list_price: '다음에 보낼 문장',
  counter_visit: '다음에 보낼 문장', counter_low_offer: '다음에 보낼 문장', counter_unknown: '다음에 보낼 문장', counter_penalty: '다음에 보낼 문장',
  accept_offer: '수락 문안', confirm_agreement: '합의 확인 문안', remind_deposit: '입금 요청 문안',
  certified_mail: '내용증명 초안', go_1372: '1372 상담 신청 내용',
}
// 시연용: 심사위원이 사장 역할로 던져 볼 답
const OWNER_SAYS = ['네 알겠습니다 환불해 드릴게요', '20만원만 드릴게요', '이벤트 상품은 환불 불가입니다',
  '정상가 기준으로 차감합니다', '방문하셔야 처리됩니다']

function Draft({ kind, text }: { kind: string; text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>{DRAFT[kind] ?? kind}</Heading>
        <pre className="draft">{text}</pre>
        <HStack gap={2} wrap="wrap">
          <Button label={copied ? '복사됨' : '복사'} onClick={() => {
            navigator.clipboard.writeText(text)
            setCopied(true)
          }} />
          {kind !== 'call_card' && <a href={`sms:?&body=${encodeURIComponent(text)}`}>문자 앱으로 열기</a>}
        </HStack>
      </VStack>
    </Card>
  )
}

function Start({ onConfirm, rules }: { onConfirm: (step: Step, today: string) => void; rules: Rules }) {
  const [samples, setSamples] = useState<Sample[]>([])
  const [c, setC] = useState<Contract>({ gym_name: '', total_paid: 0, start_date: '', end_date: '' })
  const [preview, setPreview] = useState<{ contract: Contract; refund: Refund; today: string } | null>(null)
  const [target, setTarget] = useState('')
  const [floor, setFloor] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setError('샘플 계약서를 불러오지 못했습니다. 직접 입력하거나 새로고침해 주세요.'))
  }, [])

  const runIntake = async (operation: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try {
      await operation()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const review = (contract: Contract) => runIntake(async () => {
    const today = isoDate(0)
    const refund = await api.preview(contract, today)
    setPreview({ contract, refund, today })
    setC(contract)
    setTarget('')
    setFloor('')
  })

  if (preview) {
    const { contract, refund } = preview
    const targetAmount = target === '' ? refund.refund : Number(target)
    const floorAmount = floor === '' ? refund.refund : Number(floor)
    const validAmount = (value: string) => value === '' || (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)))
    const targetValid = validAmount(target)
    const floorValid = validAmount(floor)
    const limitsError = !targetValid || !floorValid ? '금액은 0원 이상의 정수로 입력해 주세요.'
      : floorAmount > targetAmount ? '최저 수용선은 목표 금액 이하여야 합니다.' : ''
    const confirm = () => runIntake(async () => {
      const today = isoDate(0)
      if (today !== preview.today) {
        const recalculated = await api.preview(contract, today)
        setPreview({ contract, refund: recalculated, today })
        setError('날짜가 바뀌어 예상 환불액을 다시 계산했습니다. 금액을 확인해 주세요.')
        return
      }
      const step = await api.open(contract, today, {
        target: target === '' ? undefined : targetAmount,
        floor: floor === '' ? undefined : floorAmount,
      })
      onConfirm(step, today)
    })
    return (
      <VStack gap={4}>
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Card>
          <VStack gap={2}>
            <Heading level={2}>예상 환불액</Heading>
            <Text type="display-3">{won(refund.refund)}</Text>
            <Text>{contract.gym_name || '내 회원권'} · {contract.start_date} ~ {contract.end_date}</Text>
            <Text type="supporting">
              결제 {won(contract.total_paid)} · 이용분 {won(refund.used_amount)} · 위약금 {won(refund.penalty)}
            </Text>
            {refund.per_day_loss > 0 && <Text weight="semibold">하루 미루면 예상 환불액이 {won(refund.per_day_loss)} 줄어듭니다.</Text>}
            {(refund.addon > 0 || refund.security_deposit > 0) && (
              <Text type="supporting">부가 이용분 {won(refund.addon)} · 반환 보증금 {won(refund.security_deposit)}</Text>
            )}
            {contract.special_terms && <Text type="supporting">특약: {contract.special_terms}</Text>}
            {refund.refs.length > 0 && <Text type="supporting">근거: {refund.refs.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>}
            {refund.provisional && <Text type="supporting">일반적인 기준에 따른 예상 금액입니다. 실제 환불액은 달라질 수 있습니다.</Text>}
          </VStack>
        </Card>
        <Card>
          <VStack gap={3}>
            <Heading level={2}>협상 기준</Heading>
            <Text type="supporting">비워 둔 금액에는 예상 환불액 {won(refund.refund)}을 사용합니다.</Text>
            <TextInput label="목표 금액(원)" value={target} onChange={setTarget} inputMode="numeric"
              isDisabled={busy} status={!targetValid ? { type: 'error', message: limitsError } : undefined} />
            <TextInput label="최저 수용선(원)" value={floor} onChange={setFloor} inputMode="numeric"
              isDisabled={busy} status={!floorValid || (floorAmount > targetAmount) ? { type: 'error', message: limitsError } : undefined} />
          </VStack>
        </Card>
        <HStack gap={2} wrap="wrap">
          <Button label="계약 수정" isDisabled={busy} onClick={() => { setError(''); setPreview(null) }} />
          <Button variant="primary" label={busy ? '확인 중…' : '이 기준으로 시작'} isDisabled={busy || Boolean(limitsError)} onClick={confirm} />
        </HStack>
      </VStack>
    )
  }

  return (
    <VStack gap={4}>
      {error && <Banner status="error" title={error} collapsible={false} />}
      <Text as="p">헬스장·PT·필라테스 회원권 환불, 말 꺼내기부터 입금까지 챙겨 드립니다. 근거를 찾고, 그대로 보낼 문장을 만들고, 돈이 들어올 때까지 추적합니다.</Text>
      <Card>
        <VStack gap={3}>
          <Heading level={2}>샘플 계약서로 해 보기</Heading>
          {samples.map((s) => <Button key={s.id} variant="primary" label={s.label} isDisabled={busy} onClick={() => review(s.contract)} />)}
        </VStack>
      </Card>
      <Card>
        <VStack gap={3}>
          <Heading level={2}>내 계약 직접 입력</Heading>
          <TextInput label="업체 이름" value={c.gym_name} onChange={(v) => setC({ ...c, gym_name: v })} />
          <TextInput label="실제 결제한 금액(원)" value={c.total_paid ? String(c.total_paid) : ''}
            onChange={(v) => setC({ ...c, total_paid: Number(v.replace(/\D/g, '')) })} />
          <label>이용 시작일 <input type="date" value={c.start_date} onChange={(e) => setC({ ...c, start_date: e.target.value })} /></label>
          <label>이용 종료일 <input type="date" value={c.end_date} onChange={(e) => setC({ ...c, end_date: e.target.value })} /></label>
          <Button label={busy ? '계산 중…' : '환불액 계산'} isDisabled={busy || !c.total_paid || !c.start_date || !c.end_date} onClick={() => review(c)} />
        </VStack>
      </Card>
    </VStack>
  )
}

export default function App() {
  const [saved, setSaved] = useState<Saved | null>(load)
  const [rules, setRules] = useState<Rules>({})
  const [reply, setReply] = useState('')
  const [settlement, setSettlement] = useState('')
  const [error, setError] = useState('')
  const revision = useRef(0)
  const pending = useRef(0)
  useEffect(() => { api.rules().then(setRules) }, [])

  const keep = useCallback((s: Saved | null) => {
    revision.current++
    setSaved(s)
    if (s) localStorage.setItem(KEY, JSON.stringify(s))
    else localStorage.removeItem(KEY)
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
    }
  }
  const send = (event: CaseEvent, patch: Partial<Saved> = {}) => {
    const today = isoDate(patch.offset ?? saved!.offset)
    return run(api.step(saved!.step.case, event, today), today, patch)
  }

  const header = (
    <HStack hAlign="between" vAlign="center">
      <Heading level={1}>Reeper</Heading>
      {saved && <Button variant="ghost" label="새 사건 시작" onClick={() => { setSettlement(''); keep(null) }} />}
    </HStack>
  )
  if (!saved) {
    return (
      <VStack gap={4} padding={4} maxWidth={640}>
        {header}
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Start rules={rules} onConfirm={(step, today) => keep({ offset: 0, step, actionDate: today })} />
      </VStack>
    )
  }

  const { case: c, action, drafts } = saved.step
  const r = c.refund
  const settlementAmount = Number(settlement)
  return (
    <VStack gap={4} padding={4} maxWidth={640}>
      {header}
      {error && <Banner status="error" title={error} collapsible={false} />}

      <Card>
        <VStack gap={2}>
          <HStack hAlign="between" vAlign="center">
            <Heading level={2}>{c.contract.gym_name || '내 회원권'}</Heading>
            <Badge label={STAGE[c.stage]} variant={c.stage === 'closed' ? 'success' : 'info'} />
          </HStack>
          <Text type="display-3">{won(c.agreed_amount ?? r.refund)}</Text>
          <Text type="supporting">목표 {won(c.target)} · 최저 수용선 {won(c.floor)}</Text>
          <Text type="supporting">
            결제 {won(c.contract.total_paid)} − 이용분 {won(r.used_amount)} ({r.total_days}{r.unit_label} 중 {r.used_days}{r.unit_label}) − 위약금 {won(r.penalty)}
          </Text>
          {c.stage === 'ready' && r.per_day_loss > 0 && <Text weight="semibold">하루 미루면 약 {won(r.per_day_loss)}씩 줄어듭니다.</Text>}
          <Divider />
          <Text type="supporting">근거: {r.refs.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>
          {r.provisional && <Text type="supporting">일반적인 기준에 따른 예상 금액이며, 계산식은 원문 확인 전 임시입니다. 다툼이 있으면 1372 소비자상담센터에 문의하세요.</Text>}
        </VStack>
      </Card>

      <Banner status={action.warn ? 'warning' : c.stage === 'closed' ? 'success' : 'info'} collapsible={false}
        title={action.warn ? `제시액 ${won(c.offered ?? 0)}은 최저 수용선 ${won(c.floor)}보다 적습니다` : action.reason}
        description={action.warn ? action.reason : undefined} />

      {saved.note && <Draft kind="after_call_sms" text={saved.note} />}
      {Object.entries(drafts).filter(([k]) => k !== 'after_call_sms').map(([k, text]) => <Draft key={k} kind={k} text={text} />)}

      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
          {action.type === 'send_notice' && (
            <HStack gap={2} wrap="wrap">
              <Button variant="primary" label="문자로 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />
              <Button label="전화로 말했어요" onClick={() => send({ type: 'notice_sent', channel: 'call' }, { note: drafts.after_call_sms })} />
              <Button label="전화 연결이 안 됐어요" onClick={() => send({ type: 'call_attempted' })} />
            </HStack>
          )}
          {action.type === 'follow_up' && <Button variant="primary" label="재요청을 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />}
          {action.type === 'counter' && <Button label="반박 문안을 보냈어요" onClick={() => send({ type: 'counter_sent' })} />}
          {action.type === 'certified_mail' && <Button variant="primary" label="내용증명을 보냈어요" onClick={() => send({ type: 'escalation_sent' })} />}
          {action.type === 'go_1372' && c.stage !== 'handed_off' && <Button variant="primary" label="1372에 접수했어요" onClick={() => send({ type: 'handoff_done' })} />}
          {c.stage === 'negotiating' && c.offered != null && !action.warn && (
            <Button variant="primary" label={`${won(c.offered)}에 합의했어요`} onClick={() => send({ type: 'agreement_recorded', amount: c.offered })} />
          )}
          {c.stage === 'agreed' && <Button variant="primary" label="입금을 확인했어요" onClick={() => send({ type: 'deposit_confirmed' })} />}
          {c.stage === 'handed_off' && (
            <>
              <label>1372 접수 후 합의 금액(원) <input type="number" min="1" step="1" value={settlement}
                onChange={(e) => setSettlement(e.target.value)} /></label>
              <Button label="합의 금액 기록" isDisabled={!Number.isSafeInteger(settlementAmount) || settlementAmount <= 0}
                onClick={async () => {
                  if (await send({ type: 'agreement_recorded', amount: settlementAmount })) setSettlement('')
                }} />
            </>
          )}
          {['waiting', 'negotiating', 'escalated'].includes(c.stage) && (
            <>
              <TextArea label="업체 답장이나 통화 내용" description="받은 문자를 붙여넣거나, 통화에서 들은 말을 적어 주세요."
                value={reply} onChange={setReply} maxLength={500} />
              <Button label="답장 읽기" isDisabled={!reply.trim()} onClick={async () => {
                if (await send({ type: 'reply_received', text: reply })) {
                  setReply((current) => current === reply ? '' : current)
                }
              }} />
            </>
          )}
          {c.stage === 'closed' && <Text>환불금을 받았습니다. 수고하셨습니다.</Text>}
        </VStack>
      </Card>

      {!['ready', 'closed', 'handed_off'].includes(c.stage) && (
        <Card variant="muted">
          <VStack gap={3}>
            <Heading level={3}>시연용 조작</Heading>
            <Text type="supporting">실제 서비스에는 없는 기능입니다. 업체의 답과 날짜 경과를 가상으로 만듭니다.</Text>
            <HStack gap={2} wrap="wrap">
              {c.stage !== 'agreed' && OWNER_SAYS.map((t) => <Button key={t} size="sm" label={`사장: ${t}`} onClick={() => send({ type: 'reply_received', text: t })} />)}
              <Button size="sm" label="4일 지남" onClick={() => send({ type: 'time_passed' }, { offset: saved.offset + 4 })} />
            </HStack>
          </VStack>
        </Card>
      )}

      {c.timeline.length > 0 && (
        <Card>
          <VStack gap={2}>
            <Heading level={3}>지금까지</Heading>
            {c.timeline.filter((t) => t.text).map((t, i) => <Text key={i} as="p">{t.on.slice(5)} · {t.text}</Text>)}
          </VStack>
        </Card>
      )}
    </VStack>
  )
}

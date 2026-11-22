import { Banner, BottomSheet, Button, Card, DockProvider, HStack, Heading, Text, VStack } from './ui'
import { CheckCircleIcon, ClockIcon, FlagIcon, PlusIcon, ScaleIcon } from '@heroicons/react/24/outline'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { forgetAccount } from './account'
import { api, type Health, type ReadReply, type Rules, type Step } from './api'
import { DeadlineLine } from './components/DeadlineLine'
import { Mascot } from './components/Mascot'
import { DemoPanel } from './components/DemoPanel'
import { ExportMenu } from './components/ExportMenu'
import { JourneyProgress } from './components/JourneyProgress'
import { OfferCompare } from './components/OfferCompare'
import { PolishContext } from './components/PolishContext'
import { RealityNote } from './components/RealityNote'
import { StrategyCard } from './components/StrategyCard'
import { ReplyReading } from './components/ReplyReading'
import { Timeline } from './components/Timeline'
import { DEMO, JOURNEY, PAGE_WIDTH, STAGE, isoDate, journeyPhase, won } from './format'
import { JourneyReview } from './components/JourneyReview'
import { Deposit } from './steps/Deposit'
import { Evidence } from './steps/Evidence'
import { Intake } from './steps/Intake'
import { Prepare } from './steps/Prepare'
import { Respond } from './steps/Respond'
import { isOldMonth, useCase } from './useCase'
import { OldMonthNotice } from './components/OldMonthNotice'

type TabKey = 'now' | 'basis' | 'log'
const TABS = [
  { value: 'now', label: '진행', Icon: FlagIcon },
  { value: 'basis', label: '근거', Icon: ScaleIcon },
  { value: 'log', label: '기록', Icon: ClockIcon },
] as const

// 아래 탭. 고른 탭만 Tab 키로 들어가고, 좌우 화살표로 옮긴다
function TabBar({ value, onChange }: { value: TabKey; onChange: (v: TabKey) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const move = (e: KeyboardEvent, i: number) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const next = (i + step + TABS.length) % TABS.length
    onChange(TABS[next].value)
    refs.current[next]?.focus()
  }
  return (
    <div role="tablist" aria-label="화면">
      {TABS.map(({ value: v, label, Icon }, i) => (
        <button key={v} ref={(el) => { refs.current[i] = el }} type="button" role="tab" id={`tab-${v}`}
          aria-selected={value === v} aria-controls={`panel-${v}`} tabIndex={value === v ? 0 : -1}
          onClick={() => onChange(v)} onKeyDown={(e) => move(e, i)}>
          <Icon aria-hidden />{label}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const { saved, error, busy, keep, send, plan, rebase } = useCase()
  const [showWelcome, setShowWelcome] = useState(!saved)
  const intakeRef = useRef<HTMLElement>(null)
  const [rules, setRules] = useState<Rules>({})
  const [reply, setReply] = useState('')
  const [settlement, setSettlement] = useState('')
  // 아래 탭. 단계가 바뀌면 '진행'으로 돌아온다(고른 탭을 그때의 단계와 함께 둔다)
  const [tabAt, setTabAt] = useState<{ tab: TabKey; stage: Step['case']['stage'] } | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  // 붙여넣은 답장을 읽은 결과. 사용자가 확정하기 전에는 사건을 바꾸지 않는다.
  // 읽을 때의 사건(step)을 같이 둔다. 사건이 바뀌면(기록, 날짜 경과, 새 사건) 확정 전 결과는 보이지 않는다
  type Reading = { step: Step | undefined; result: (ReadReply & { text: string }) | null; note: string }
  const [reading, setReading] = useState<Reading & { busy: boolean }>({ step: undefined, result: null, note: '', busy: false })
  const readReply = async (text: string) => {
    const at = saved?.step
    setReading({ step: at, result: null, note: '', busy: true })
    try {
      setReading({ step: at, result: { text, ...(await api.readReply(text)) }, note: '', busy: false })
    } catch {
      setReading({ step: at, result: null, note: '답장을 읽지 못했어요. 아래 버튼으로 골라 주세요', busy: false })
    }
  }
  const current = reading.step === saved?.step
  const read = current ? reading.result : null
  const readNote = current ? reading.note : ''
  // 근거 이름을 못 불러와도 화면은 id로 계속 쓴다.
  useEffect(() => { api.rules().then(setRules).catch(() => setRules({})) }, [])
  // 상태를 못 불러와도 화면은 그대로 동작한다.
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])
  const autoReadOff = health !== null && (health.llm === 'FakeLLM' || health.calls_left <= 0)

  // 사건은 이 브라우저에만 있어서 지우면 되돌릴 수 없다. 끝나지 않은 사건은 한 번 더 묻는다
  const [confirmReset, setConfirmReset] = useState(false)
  // 위 진행 표시에서 누른 지난 단계(1~5). 읽기 전용 시트로 그 단계 내용을 보여 준다
  const [peek, setPeek] = useState<number | null>(null)
  const [dockEl, setDockEl] = useState<HTMLElement | null>(null)
  // 기록이 하나 늘면 무엇을 기록했는지 잠깐 보여 준다. 단계가 그대로인 기록(전화 연결 안 됨, 전화 안 받음)은
  // 화면이 바뀌지 않아 눌렸는지 알 수 없었다. 새 사건·새로고침·새로 시작에는 띄우지 않는다
  const logCount = saved?.step.case.timeline.length
  const lastLog = saved?.step.case.timeline.at(-1)?.text ?? ''
  const prevCount = useRef<number | undefined>(undefined)
  const [flash, setFlash] = useState<{ text: string; n: number } | null>(null)
  useEffect(() => {
    if (prevCount.current !== undefined && logCount !== undefined && logCount > prevCount.current && lastLog) {
      setFlash({ text: lastLog, n: logCount })
    }
    prevCount.current = logCount
  }, [logCount, lastLog])
  useEffect(() => {
    if (!flash) return
    const t = window.setTimeout(() => setFlash(null), 5000)
    return () => window.clearTimeout(t)
  }, [flash])
  const reset = () => { forgetAccount(); setConfirmReset(false); setSettlement(''); setTabAt(null); keep(null) }
  // 환불이 끝나면 계좌는 더 쓸 데가 없다. 같이 쓰는 PC에서 다음 사람이 보지 않게 브라우저에서 지운다
  const closed = saved?.step.case.stage === 'closed'
  useEffect(() => { if (closed) forgetAccount() }, [closed])
  const tab: TabKey = saved && tabAt?.stage === saved.step.case.stage ? tabAt.tab : 'now'
  // 단계가 바뀌거나 탭을 오가면 맨 위에서 시작한다. 앞 화면의 스크롤 위치에 남으면 새 단계 안내가 가려진다
  const view = saved ? `${journeyPhase(saved.step.case.stage)}:${tab}` : showWelcome ? 'welcome' : 'intake'
  useEffect(() => {
    window.scrollTo({ top: 0 })
    if (view === 'intake') intakeRef.current?.focus({ preventScroll: true })
  }, [view])

  if (view === 'welcome') {
    return (
      <VStack role="main" gap={7} padding={6} className="page items-center justify-center bg-brand-soft text-center">
        <Mascot pose="hello" />
        <VStack gap={2}>
          <Heading level={1} className="text-5xl font-bold tracking-tight">Reeper</Heading>
          <Text as="p">헬스장·PT·필라테스 환불, 입금까지 챙겨 드려요.</Text>
        </VStack>
        <Button variant="primary" size="lg" className="h-12 w-full max-w-64" label="시작하기" onClick={() => setShowWelcome(false)} />
      </VStack>
    )
  }

  // 위에 붙어 있는 막대: 이름, 새로 시작, 사건이 있으면 업체·받을 돈과 진행 단계. 내려도 어디까지 왔는지 보인다
  const sc = saved?.step.case
  const appBar = (
    <header className="app-bar">
      {/* 이름 줄만 대표색으로 칠한다. 진행 표시까지 칠하면 주황 동그라미가 배경에 묻힌다 */}
      <div className="app-bar-brand">
        <HStack hAlign="between" vAlign="center">
          <Heading level={1}>Reeper</Heading>
          {saved && <Button variant="ghost" size="sm" label="새로 시작" icon={<PlusIcon aria-hidden />} isDisabled={busy}
            onClick={() => saved.step.case.stage === 'closed' ? reset() : setConfirmReset(true)} />}
        </HStack>
      </div>
      {sc && (
        <div className="app-bar-body">
          <VStack gap={2}>
            <HStack hAlign="between" vAlign="center">
              {/* 방금 기록한 것은 잠깐 이 줄에 보인다. 아래쪽에 띄우면 문안·안내를 가렸다. 화면 읽기 프로그램에도 읽힌다 */}
              <div role="status" aria-live="polite" className="min-w-0 flex-1">
                {flash
                  ? <p key={flash.n} className="flash"><CheckCircleIcon aria-hidden /><span>기록했어요 · {flash.text}</span></p>
                  : <Text type="supporting">{sc.contract.gym_name || '내 회원권'} · {STAGE[sc.stage]}</Text>}
              </div>
              <Text weight="semibold">{won(sc.agreed_amount ?? sc.refund.refund)}</Text>
            </HStack>
            {/* 합의 뒤 입금이 안 돼 1372로 갔으면 입금 추적의 연장이다. 진행 표시가 뒤로 가지 않게 한다 */}
            {/* 끝난 사건은 다섯 단계가 모두 지난 것으로(6) 그려 마지막 단계도 체크로 보인다 */}
            <JourneyProgress current={sc.stage === 'closed' ? 6 : sc.stage === 'handed_off' && sc.agreed_amount != null ? 5 : journeyPhase(sc.stage)} onPick={setPeek} />
          </VStack>
        </div>
      )}
      {/* 서버에 묻는 동안 위 막대 아래로 줄이 흐른다. 어느 화면에 있어도 돌아가는 중인 것이 보인다 */}
      {(busy || reading.busy) && <div className="busy-bar" role="progressbar" aria-label="처리하고 있어요" />}
    </header>
  )
  // 위 막대는 페이지의 바로 아래 자식이어야 내려도 붙어 있다(짧은 묶음 안에 두면 그 묶음과 함께 올라간다)
  const header = (
    <>
      {appBar}
      {/* 화면 안 카드로 두면 위 막대 아래에 끼어 내려간 화면에서는 보이지 않았다. 시트로 띄워 누른 곳에서 바로 답하게 한다 */}
      <BottomSheet open={!!saved && confirmReset} onOpenChange={setConfirmReset} title="지금 기록을 지울까요?">
        <VStack gap={3}>
          <Text as="p">이 브라우저에만 있어서 되돌릴 수 없어요. 남기려면 아래 '기록' 탭에서 먼저 저장하세요</Text>
          {/* 오른손 엄지가 닿는 오른쪽 아래에 둔다. 주 버튼(계속하기)이 맨 오른쪽이다 */}
          <HStack gap={2} wrap="wrap" hAlign="end">
            <Button label="지우고 새로 시작" onClick={reset} />
            <Button label="계속하기" variant="primary" onClick={() => setConfirmReset(false)} />
          </HStack>
        </VStack>
      </BottomSheet>
      {saved && (
        <BottomSheet open={peek !== null} onOpenChange={(open) => { if (!open) setPeek(null) }}
          title={peek ? `${JOURNEY[peek - 1]} 다시 보기` : ''}>
          {peek && <JourneyReview c={saved.step.case} rules={rules} today={isoDate(saved.offset)} step={peek} />}
        </BottomSheet>
      )}
    </>
  )
  if (!saved) {
    return (
      <VStack gap={4} padding={4} maxWidth={PAGE_WIDTH} className="page">
        {header}
        {error && <Banner status="error" title={error} collapsible={false} />}
        <main ref={intakeRef} tabIndex={-1} aria-label="계약 입력">
          <Intake rules={rules} upload={health?.upload === true} onConfirm={(step, today) => keep({ offset: 0, step, actionDate: today })} />
        </main>
      </VStack>
    )
  }

  const { case: c, action } = saved.step
  const phase = journeyPhase(c.stage)
  // 1372에 넘긴 뒤에는 상담 결과(합의 금액)만 기록한다. 전략과 날짜 조작은 쓸 일이 없다.
  const handedOff = c.stage === 'handed_off'
  return (
    <VStack gap={4} padding={4} maxWidth={PAGE_WIDTH} className="page has-tabs">
      {header}
      {error && <Banner status="error" title={error} collapsible={false} />}
      {isOldMonth(c) && <OldMonthNotice c={c} today={isoDate(saved.offset)} busy={busy} onChoose={(useNew) => void rebase(useNew)} />}

      {tab === 'basis' && <div id="panel-basis" role="tabpanel" aria-labelledby="tab-basis"><Evidence c={c} rules={rules} /></div>}
      {tab === 'log' && (
        <div id="panel-log" role="tabpanel" aria-labelledby="tab-log">
          <VStack gap={4}>
            <Timeline c={c} today={isoDate(saved.offset)} />
            <ExportMenu c={c} rules={rules} />
            <RealityNote demo={DEMO} />
          </VStack>
        </div>
      )}

      {tab === 'now' && <div id="panel-now" role="tabpanel" aria-labelledby="tab-now">
      <DockProvider value={dockEl}>
      <PolishContext.Provider value={{ c, enabled: !autoReadOff }}>
      <fieldset disabled={busy} className="journey-interactions" aria-busy={busy}>
      {/* 지금 할 일 한 문장과 기한. 금액 제시 없이 다시 요청하는 반박('근거를 들어 다시 요청하세요', 애매한 답의
          '요청한 금액을 다시 밝혀 두세요')은 아래 문자 카드와 같은 말이고 기한도 없어서 보이지 않는다. 그 문장은 답장 분석에
          '이유'로만 들어간다. 이유나 기한이 있는 문장은 그대로 둔다(문장은 engine.py가 정한다) */}
      {!(phase === 3 && action.type === 'send_notice') && !(action.type === 'counter' && !action.warn && c.offered == null) && <Card className="mb-3">
        <HStack hAlign="between" vAlign="start" gap={2}>
          <VStack gap={3}>
            <Heading level={2}>{action.reason}</Heading>
            <DeadlineLine c={c} offset={saved.offset} />
          </VStack>
          {action.type === 'wait' && c.stage === 'agreed' && <Mascot pose="wait" small />}
        </HStack>
      </Card>}
      {/* 업체 답을 기다릴 때는 보낼 문안이 없어야 마스코트를 크게 보여 준다. */}
      {action.type === 'wait' && c.stage !== 'agreed' && Object.keys(saved.step.drafts).length === 0 && <Mascot pose="wait" />}
      {c.stage === 'closed' && <Mascot pose="done" />}
      {/* 한 화면에 할 일 하나: 지금 단계의 일을 위에서부터 쌓고, 참고용(조언·시연)은 맨 아래에 접어 둔다 */}
      <VStack gap={3}>
        {action.warn && <OfferCompare offered={c.offered ?? 0} floor={c.floor} refund={c.refund.refund} />}
        <ReplyReading step={saved.step} rules={rules} />
        {/* 옛 월 단위 사건은 금액을 확인하기 전까지 옛 금액 문안과 발송 버튼을 보이지 않는다. 서버는 기록만 막고 발송은 막지 못한다 */}
        {phase === 3 && !isOldMonth(c) && <Prepare saved={saved} send={send} />}
        {phase === 4 && <Respond saved={saved} send={send} reply={reply} setReply={setReply}
          settlement={settlement} setSettlement={setSettlement} autoReadOff={autoReadOff}
          read={read} readNote={readNote} reading={reading.busy} readReply={readReply}
          clearRead={() => setReading((r) => ({ ...r, result: null }))} />}
        {phase === 5 && <Deposit saved={saved} send={send} />}
        {/* 조언을 받을 수 없으면(키 없음·한도 초과) 쓸 수 없는 칸을 보이지 않는다. 이미 받은 조언은 그대로 보여 준다 */}
        {(phase === 3 || phase === 4) && !handedOff && (!autoReadOff || c.strategy) && <StrategyCard c={c} rules={rules} autoReadOff={autoReadOff} plan={plan} />}
        {DEMO && !handedOff && <DemoPanel stage={c.stage} offset={saved.offset} send={send}
          ownerSays={(t) => { setReply(t); void readReply(t) }} />}
      </VStack>
      </fieldset>
      </PolishContext.Provider>
      </DockProvider>
      </div>}
      {/* 주 버튼 자리. 탭 바로 위에 고정된다 */}
      {/* 저장 중에는 이 버튼들도 잠근다(카드 쪽 fieldset 밖으로 옮겨 그리므로 따로 잠근다) */}
      <div className="bottom-stack">
        <fieldset disabled={busy} className="journey-interactions" aria-busy={busy}>
          <div ref={setDockEl} className="dock-slot" />
        </fieldset>
      </div>

      {/* 아래 탭: 지금 할 일, 계산 근거, 지금까지 한 일·저장. 화면 아래에 늘 붙어 있다 */}
      <div className="tab-spacer" aria-hidden />
      <nav className="tab-bar" aria-label="화면 바꾸기">
        <TabBar value={tab} onChange={(v) => setTabAt({ tab: v, stage: c.stage })} />
      </nav>
    </VStack>
  )
}

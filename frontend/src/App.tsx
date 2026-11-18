import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Icon } from '@astryxdesign/core/Icon'
import { Tab, TabList } from '@astryxdesign/core/TabList'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import { useEffect, useState } from 'react'
import { api, type Health, type ReadReply, type Rules, type Step } from './api'
import { DeadlineLine } from './components/DeadlineLine'
import { DemoPanel } from './components/DemoPanel'
import { ExportMenu } from './components/ExportMenu'
import { JourneyProgress } from './components/JourneyProgress'
import { PolishContext } from './components/PolishContext'
import { RealityNote } from './components/RealityNote'
import { StrategyCard } from './components/StrategyCard'
import { ReplyReading } from './components/ReplyReading'
import { Timeline } from './components/Timeline'
import { DEMO, PAGE_WIDTH, STAGE, isoDate, journeyPhase, won } from './format'
import { Deposit } from './steps/Deposit'
import { Evidence } from './steps/Evidence'
import { Intake } from './steps/Intake'
import { Prepare } from './steps/Prepare'
import { Respond } from './steps/Respond'
import { useCase } from './useCase'

export default function App() {
  const { saved, error, busy, keep, send, plan } = useCase()
  const [rules, setRules] = useState<Rules>({})
  const [reply, setReply] = useState('')
  const [settlement, setSettlement] = useState('')
  // 아래 탭. 단계가 바뀌면 '진행'으로 돌아온다(고른 탭을 그때의 단계와 함께 둔다)
  type TabKey = 'now' | 'basis' | 'log'
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
  const reset = () => { setConfirmReset(false); setSettlement(''); setTabAt(null); keep(null) }
  const tab: TabKey = saved && tabAt?.stage === saved.step.case.stage ? tabAt.tab : 'now'
  // 단계가 바뀌거나 탭을 오가면 맨 위에서 시작한다. 앞 화면의 스크롤 위치에 남으면 새 단계 안내가 가려진다
  const view = saved ? `${journeyPhase(saved.step.case.stage)}:${tab}` : 'intake'
  useEffect(() => { window.scrollTo({ top: 0 }) }, [view])
  // 위에 붙어 있는 막대: 이름, 새로 시작, 사건이 있으면 업체·받을 돈과 진행 단계. 내려도 어디까지 왔는지 보인다
  const sc = saved?.step.case
  const appBar = (
    <header className="app-bar">
      <VStack gap={2}>
        <HStack hAlign="between" vAlign="center">
          <Heading level={1}>Reeper</Heading>
          {saved && <Button variant="ghost" label="새로 시작" isDisabled={busy}
            onClick={() => saved.step.case.stage === 'closed' ? reset() : setConfirmReset(true)} />}
        </HStack>
        {sc && (
          <>
            <HStack hAlign="between" vAlign="center">
              <Text type="supporting">{sc.contract.gym_name || '내 회원권'} · {STAGE[sc.stage]}</Text>
              <Text weight="semibold">{won(sc.agreed_amount ?? sc.refund.refund)}</Text>
            </HStack>
            {/* 합의 뒤 입금이 안 돼 1372로 갔으면 입금 추적의 연장이다. 진행 표시가 뒤로 가지 않게 한다 */}
            <JourneyProgress current={sc.stage === 'handed_off' && sc.agreed_amount != null ? 5 : journeyPhase(sc.stage)} />
          </>
        )}
      </VStack>
    </header>
  )
  // 위 막대는 페이지의 바로 아래 자식이어야 내려도 붙어 있다(짧은 묶음 안에 두면 그 묶음과 함께 올라간다)
  const header = (
    <>
      {appBar}
      {saved && confirmReset && (
        <Card>
          <VStack gap={3}>
            <Heading level={2}>지금 기록을 지울까요?</Heading>
            <Text as="p">이 브라우저에만 있어서 되돌릴 수 없어요. 남기려면 아래 '기록' 탭에서 먼저 저장하세요</Text>
            <HStack gap={2} wrap="wrap">
              <Button label="계속하기" variant="primary" onClick={() => setConfirmReset(false)} />
              <Button label="지우고 새로 시작" onClick={reset} />
            </HStack>
          </VStack>
        </Card>
      )}
    </>
  )
  if (!saved) {
    return (
      <VStack gap={4} padding={4} maxWidth={PAGE_WIDTH} className="page">
        {header}
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Intake rules={rules} upload={health?.upload === true} onConfirm={(step, today) => keep({ offset: 0, step, actionDate: today })} />
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

      {tab === 'basis' && <div id="panel-basis" role="tabpanel" aria-label="근거"><Evidence c={c} rules={rules} /></div>}
      {tab === 'log' && (
        <div id="panel-log" role="tabpanel" aria-label="기록">
          <VStack gap={4}>
            <Timeline c={c} today={isoDate(saved.offset)} />
            <ExportMenu c={c} rules={rules} />
            <RealityNote demo={DEMO} />
          </VStack>
        </div>
      )}

      {tab === 'now' && <div id="panel-now" role="tabpanel" aria-label="진행"><VStack gap={4}>
      {/* 지금 할 일 한 문장과 기한. 업체·받을 돈은 위에 붙은 막대에 늘 보인다 */}
      <Card>
        <VStack gap={2}>
          <Heading level={2}>{action.reason}</Heading>
          <DeadlineLine c={c} offset={saved.offset} />
        </VStack>
      </Card>
      {action.warn && (
        <Banner status="warning" collapsible={false} title={`업체가 말한 ${won(c.offered ?? 0)}은 거절 기준 ${won(c.floor)}보다 적어요`} />
      )}

      <PolishContext.Provider value={{ c, enabled: !autoReadOff }}>
      <fieldset disabled={busy} className="journey-interactions" aria-busy={busy}>
      <VStack gap={4}>
      <ReplyReading step={saved.step} rules={rules} />
      {phase === 3 &&<Prepare saved={saved} send={send} />}
      {phase === 4 && <Respond saved={saved} send={send} reply={reply} setReply={setReply}
        settlement={settlement} setSettlement={setSettlement} autoReadOff={autoReadOff}
        read={read} readNote={readNote} reading={reading.busy} readReply={readReply}
        clearRead={() => setReading((r) => ({ ...r, result: null }))} />}
      {phase === 5 && <Deposit saved={saved} send={send} />}
      {(phase === 3 || phase === 4) && !handedOff && <StrategyCard c={c} rules={rules} autoReadOff={autoReadOff} plan={plan} />}
      {DEMO && !handedOff && <DemoPanel stage={c.stage} offset={saved.offset} send={send}
        ownerSays={(t) => { setReply(t); void readReply(t) }} />}
      </VStack>
      </fieldset>
      </PolishContext.Provider>
      </VStack></div>}

      {/* 아래 탭: 지금 할 일, 계산 근거, 지금까지 한 일·저장. 화면 아래에 늘 붙어 있다 */}
      <div className="tab-spacer" aria-hidden />
      <nav className="tab-bar" aria-label="화면 바꾸기">
        <TabList role="tablist" layout="fill" size="lg" value={tab}
          onChange={(v) => setTabAt({ tab: v as TabKey, stage: c.stage })}>
          <Tab value="now" label="진행" panelId="panel-now" icon={<Icon icon="check" />} />
          <Tab value="basis" label="근거" panelId="panel-basis" icon={<Icon icon="info" />} />
          <Tab value="log" label="기록" panelId="panel-log" icon={<Icon icon="clock" />} />
        </TabList>
      </nav>
    </VStack>
  )
}

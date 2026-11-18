import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
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
import { DEMO, STAGE, isoDate, journeyPhase, won } from './format'
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
  const [evidenceStage, setEvidenceStage] = useState<Step['case']['stage'] | null>(null)
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
  const reset = () => { setConfirmReset(false); setSettlement(''); setEvidenceStage(null); keep(null) }
  // 단계가 바뀌거나 근거 보기를 오가면 맨 위에서 시작한다. 앞 화면의 스크롤 위치에 남으면 진행 표시와 새 단계 안내가 가려진다
  const view = saved ? `${journeyPhase(saved.step.case.stage)}:${evidenceStage === saved.step.case.stage}` : 'intake'
  useEffect(() => { window.scrollTo({ top: 0 }) }, [view])
  const header = (
    <VStack gap={3}>
      <HStack hAlign="between" vAlign="center">
        <Heading level={1}>Reeper</Heading>
        {saved && <Button variant="ghost" label="새 사건 시작" isDisabled={busy}
          onClick={() => saved.step.case.stage === 'closed' ? reset() : setConfirmReset(true)} />}
      </HStack>
      {saved && confirmReset && (
        <Card>
          <VStack gap={3}>
            <Heading level={2}>지금 사건을 지울까요?</Heading>
            <Text as="p">기록은 이 브라우저에만 있어서 지우면 되돌릴 수 없어요. 남겨 두려면 아래 '사건 파일 내보내기'에서 먼저 저장하세요.</Text>
            <HStack gap={2} wrap="wrap">
              <Button label="계속 진행" variant="primary" onClick={() => setConfirmReset(false)} />
              <Button label="지우고 새로 시작" onClick={reset} />
            </HStack>
          </VStack>
        </Card>
      )}
    </VStack>
  )
  if (!saved) {
    return (
      <VStack gap={4} padding={4} maxWidth={640} className="page">
        {header}
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Intake rules={rules} upload={health?.upload === true} onConfirm={(step, today) => keep({ offset: 0, step, actionDate: today })} />
      </VStack>
    )
  }

  const { case: c, action } = saved.step
  const showEvidence = evidenceStage === c.stage
  const phase = journeyPhase(c.stage)
  // 1372에 넘긴 뒤에는 상담 결과(합의 금액)만 기록한다. 전략과 날짜 조작은 쓸 일이 없다.
  const handedOff = c.stage === 'handed_off'
  return (
    <VStack gap={4} padding={4} maxWidth={640} className="page">
      {header}
      {error && <Banner status="error" title={error} collapsible={false} />}

      {/* 근거를 다시 볼 때도 진행 표시는 지금 단계에 둔다 */}
      {/* 합의 뒤 입금이 안 돼 1372로 갔으면 입금 추적의 연장이다. 진행 표시가 뒤로 가지 않게 한다 */}
      <JourneyProgress current={handedOff && c.agreed_amount != null ? 5 : phase} />
      <HStack gap={2} wrap="wrap">
        <Button label="계산 근거 보기" variant={showEvidence ? 'primary' : 'ghost'}
          isDisabled={busy} onClick={() => setEvidenceStage(c.stage)} />
        <Button label={phase === 3 ? '말할 준비' : phase === 5 ? '입금 추적' : handedOff ? '1372 상담' : '답변 대응'}
          variant={showEvidence ? 'ghost' : 'primary'} isDisabled={busy} onClick={() => setEvidenceStage(null)} />
      </HStack>

      {showEvidence && <Evidence c={c} rules={rules} />}

      {!showEvidence && <>
      <Card>
        <HStack hAlign="between" vAlign="center" wrap="wrap">
          <Text weight="semibold">{c.contract.gym_name || '내 회원권'} · {STAGE[c.stage]}</Text>
          <Text weight="semibold">{won(c.agreed_amount ?? c.refund.refund)}</Text>
        </HStack>
      </Card>
      <Banner status={action.warn ? 'warning' : c.stage === 'closed' ? 'success' : 'info'} collapsible={false}
        title={action.warn ? `제시액 ${won(c.offered ?? 0)}은 최저 수용선 ${won(c.floor)}보다 적습니다` : action.reason}
        description={action.warn ? action.reason : undefined} />

      <DeadlineLine c={c} offset={saved.offset} />

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

      <Timeline c={c} today={isoDate(saved.offset)} />
      <ExportMenu c={c} rules={rules} />
      <RealityNote demo={DEMO} />
      </>}
    </VStack>
  )
}

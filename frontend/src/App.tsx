import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import { useEffect, useState } from 'react'
import { api, type Health, type Rules, type Step } from './api'
import { DeadlineLine } from './components/DeadlineLine'
import { DemoPanel } from './components/DemoPanel'
import { ExportMenu } from './components/ExportMenu'
import { JourneyProgress } from './components/JourneyProgress'
import { PolishContext } from './components/PolishContext'
import { RealityNote } from './components/RealityNote'
import { ReplyReading } from './components/ReplyReading'
import { Timeline } from './components/Timeline'
import { STAGE, journeyPhase, won } from './format'
import { Deposit } from './steps/Deposit'
import { Evidence } from './steps/Evidence'
import { Intake } from './steps/Intake'
import { Prepare } from './steps/Prepare'
import { Respond } from './steps/Respond'
import { useCase } from './useCase'

export default function App() {
  const { saved, error, busy, keep, send } = useCase()
  const [rules, setRules] = useState<Rules>({})
  const [reply, setReply] = useState('')
  const [settlement, setSettlement] = useState('')
  const [evidenceStage, setEvidenceStage] = useState<Step['case']['stage'] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  // 근거 이름을 못 불러와도 화면은 id로 계속 쓴다.
  useEffect(() => { api.rules().then(setRules).catch(() => setRules({})) }, [])
  // 상태를 못 불러와도 화면은 그대로 동작한다.
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])
  const autoReadOff = health !== null && (health.llm === 'FakeLLM' || health.calls_left <= 0)

  const header = (
    <HStack hAlign="between" vAlign="center">
      <Heading level={1}>Reeper</Heading>
      {saved && <Button variant="ghost" label="새 사건 시작" onClick={() => { setSettlement(''); setEvidenceStage(null); keep(null) }} />}
    </HStack>
  )
  if (!saved) {
    return (
      <VStack gap={4} padding={4} maxWidth={640}>
        {header}
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Intake rules={rules} onConfirm={(step, today) => keep({ offset: 0, step, actionDate: today })} />
      </VStack>
    )
  }

  const { case: c, action } = saved.step
  const showEvidence = evidenceStage === c.stage
  const phase = journeyPhase(c.stage)
  return (
    <VStack gap={4} padding={4} maxWidth={640}>
      {header}
      {error && <Banner status="error" title={error} collapsible={false} />}

      <JourneyProgress current={showEvidence ? 2 : phase} />
      <HStack gap={2} wrap="wrap">
        <Button label="계산 근거 보기" variant={showEvidence ? 'primary' : 'ghost'}
          isDisabled={busy} onClick={() => setEvidenceStage(c.stage)} />
        <Button label={phase === 3 ? '말할 준비' : phase === 5 ? '입금 추적' : '답변 대응'}
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
        settlement={settlement} setSettlement={setSettlement} autoReadOff={autoReadOff} />}
      {phase === 5 && <Deposit saved={saved} send={send} />}
      <DemoPanel stage={c.stage} offset={saved.offset} send={send} />
      </VStack>
      </fieldset>
      </PolishContext.Provider>

      <Timeline c={c} />
      <ExportMenu c={c} rules={rules} />
      <RealityNote />
      </>}
    </VStack>
  )
}

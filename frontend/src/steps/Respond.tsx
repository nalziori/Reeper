import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { TextArea } from '@astryxdesign/core/TextArea'
import { VStack } from '@astryxdesign/core/VStack'
import type { Rules } from '../api'
import { AnalysisCard } from '../components/AnalysisCard'
import { DraftList } from '../components/Draft'
import { ReplyButtons } from '../components/ReplyButtons'
import { won } from '../format'
import type { Saved, Send } from '../useCase'

type Props = {
  saved: Saved
  send: Send
  reply: string
  setReply: (update: string | ((current: string) => string)) => void
  settlement: string
  setSettlement: (value: string) => void
  rules: Rules
  autoReadOff: boolean
}

// stage가 waiting, negotiating, escalated, handed_off일 때: 문안, 기록 버튼, 답장 입력
export function Respond({ saved, send, reply, setReply, settlement, setSettlement, rules, autoReadOff }: Props) {
  const { case: c, action, drafts } = saved.step
  const settlementAmount = Number(settlement)
  return (
    <>
      {c.stage === 'negotiating' && saved.step.llm_fallback && (
        <Banner status="warning" collapsible={false}
          title="붙여넣은 답장을 자동으로 읽지 못해 키워드로 판단했어요. 맞는지 확인하고 버튼으로 고쳐 주세요." />
      )}
      {c.stage === 'negotiating' && saved.step.analysis && <AnalysisCard analysis={saved.step.analysis} rules={rules} />}
      <DraftList drafts={drafts} note={saved.note} />
      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
          {action.type === 'follow_up' && <Button variant="primary" label="재요청을 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />}
          {action.type === 'counter' && <Button label="반박 문안을 보냈어요" onClick={() => send({ type: 'counter_sent' })} />}
          {action.type === 'certified_mail' && <Button variant="primary" label="내용증명을 보냈어요" onClick={() => send({ type: 'escalation_sent' })} />}
          {action.type === 'go_1372' && c.stage !== 'handed_off' && <Button variant="primary" label="1372에 접수했어요" onClick={() => send({ type: 'handoff_done' })} />}
          {c.stage === 'negotiating' && c.offered != null && !action.warn && (
            <Button variant="primary" label={`${won(c.offered)}에 합의했어요`} onClick={() => send({ type: 'agreement_recorded', amount: c.offered })} />
          )}
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
              {autoReadOff && (
                <>
                  <Banner status="info" collapsible={false} title="자동 읽기를 쓸 수 없어요. 아래 버튼으로 골라 주세요" />
                  <ReplyButtons send={send} />
                </>
              )}
              <TextArea label="업체 답장이나 통화 내용" description="받은 문자를 붙여넣거나, 통화에서 들은 말을 적어 주세요."
                value={reply} onChange={setReply} maxLength={500} />
              <Button label="답장 읽기" isDisabled={!reply.trim()} onClick={async () => {
                if (await send({ type: 'reply_received', text: reply })) {
                  setReply((current) => current === reply ? '' : current)
                }
              }} />
              {!autoReadOff && <ReplyButtons send={send} />}
            </>
          )}
        </VStack>
      </Card>
    </>
  )
}

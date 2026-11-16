import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { VStack } from '@astryxdesign/core/VStack'
import type { Step } from '../api'
import { DraftList } from '../components/Draft'
import type { Saved, Send } from '../useCase'

// stage가 ready일 때: 보낼 문안과 첫 통지 기록
export function Prepare({ saved, send }: { saved: Saved; send: Send }) {
  const { action, drafts }: Step = saved.step
  return (
    <>
      <DraftList drafts={drafts} note={saved.note} />
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
        </VStack>
      </Card>
    </>
  )
}

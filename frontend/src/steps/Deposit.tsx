import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import { DraftList } from '../components/Draft'
import type { Saved, Send } from '../useCase'

// stage가 agreed, closed일 때: 합의 문안과 입금 확인
export function Deposit({ saved, send }: { saved: Saved; send: Send }) {
  const { case: c, drafts } = saved.step
  return (
    <>
      <DraftList drafts={drafts} note={saved.note} />
      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
          {c.stage === 'agreed' && <Button variant="primary" label="입금을 확인했어요" onClick={() => send({ type: 'deposit_confirmed' })} />}
          {c.stage === 'closed' && <Text>환불금을 받았습니다. 수고하셨습니다.</Text>}
        </VStack>
      </Card>
    </>
  )
}

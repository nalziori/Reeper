import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { Case } from '../api'
import { OWNER_SAYS, isoDate } from '../format'
import type { Send } from '../useCase'

// ownerSays: 사장 답을 답장 칸에 넣고 읽는다. 실제 답장과 같이 사용자가 읽은 결과를 확정해야 기록된다
export function DemoPanel({ stage, offset, send, ownerSays }: { stage: Case['stage']; offset: number; send: Send; ownerSays: (text: string) => void }) {
  if (stage === 'closed') return null
  const ownerCanReply = stage === 'waiting' || stage === 'negotiating' || stage === 'escalated'
  return (
    <Card variant="muted">
      <VStack gap={3}>
        <Heading level={3}>시연용 조작</Heading>
        <Text type="supporting">실제 서비스엔 없어요. 업체 답장과 날짜를 흉내 내요</Text>
        {offset > 0 && <Text as="p">시연 날짜: {isoDate(offset)} (실제보다 {offset}일 뒤)</Text>}
        <HStack gap={2} wrap="wrap">
          {ownerCanReply && OWNER_SAYS.map((t) => <Button key={t} size="sm" label={`사장: ${t}`} onClick={() => ownerSays(t)} />)}
          <Button size="sm" label="하루 지남" onClick={() => send({ type: 'time_passed' }, { offset: offset + 1 })} />
          <Button size="sm" label="4일 지남" onClick={() => send({ type: 'time_passed' }, { offset: offset + 4 })} />
        </HStack>
      </VStack>
    </Card>
  )
}

import { Badge } from '@astryxdesign/core/Badge'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { Case } from '../api'
import { OWNER_SAYS, isoDate } from '../format'
import type { Send } from '../useCase'

export function DemoPanel({ stage, offset, send }: { stage: Case['stage']; offset: number; send: Send }) {
  if (stage === 'closed') return null
  const ownerCanReply = stage === 'waiting' || stage === 'negotiating' || stage === 'escalated'
  return (
    <Card variant="muted">
      <VStack gap={3}>
        <HStack gap={2} vAlign="center">
          <Heading level={3}>시연용 조작</Heading>
          <Badge label="시연용" />
        </HStack>
        <Text type="supporting">실제 서비스에는 없는 기능입니다. 업체의 답과 날짜 경과를 가상으로 만듭니다.</Text>
        {offset > 0 && <Text as="p">시연 날짜: {isoDate(offset)} (실제보다 {offset}일 뒤)</Text>}
        <HStack gap={2} wrap="wrap">
          {ownerCanReply && OWNER_SAYS.map((t) => <Button key={t} size="sm" label={`사장: ${t}`} onClick={() => send({ type: 'reply_received', text: t })} />)}
          <Button size="sm" label="하루 지남" onClick={() => send({ type: 'time_passed' }, { offset: offset + 1 })} />
          <Button size="sm" label="4일 지남" onClick={() => send({ type: 'time_passed' }, { offset: offset + 4 })} />
        </HStack>
      </VStack>
    </Card>
  )
}

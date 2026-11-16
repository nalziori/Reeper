import { Badge } from '@astryxdesign/core/Badge'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { Case } from '../api'
import { koDate } from '../format'

export function Timeline({ c }: { c: Case }) {
  const upcoming = c.stage === 'waiting' || c.stage === 'escalated'
    ? (c.deadline_on ? { label: '답변 기한(서비스가 정한 기준)', on: c.deadline_on } : null)
    : c.stage === 'agreed' && c.deposit_due_on ? { label: '입금 기한(서비스가 정한 기준)', on: c.deposit_due_on } : null
  const past = c.timeline.filter((t) => t.text)
  if (past.length === 0 && !upcoming) return null
  return (
    <Card>
      <VStack gap={2}>
        <Heading level={3}>지금까지</Heading>
        {past.map((t, i) => <Text key={i} as="p">{koDate(t.on)} · {t.text}</Text>)}
        {upcoming && (
          <HStack gap={2} vAlign="center">
            <Text type="supporting">{koDate(upcoming.on)} · {upcoming.label}</Text>
            <Badge label="예정" />
          </HStack>
        )}
      </VStack>
    </Card>
  )
}

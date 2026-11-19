import { Badge, Card, HStack, Heading, Text, VStack } from '../ui'
import type { Case } from '../api'
import { koDate } from '../format'

// today: 화면이 기준으로 삼는 오늘(시연 날짜 포함). 기한이 지나면 '예정' 대신 '지남'으로 보인다
export function Timeline({ c, today }: { c: Case; today: string }) {
  const upcoming = c.stage === 'waiting' || c.stage === 'escalated'
    ? (c.deadline_on ? { label: '답장 기한', on: c.deadline_on } : null)
    : c.stage === 'agreed' && c.deposit_due_on ? { label: '입금 기한', on: c.deposit_due_on } : null
  const past = c.timeline.filter((t) => t.text)
  if (past.length === 0 && !upcoming) return null
  const overdue = upcoming !== null && today > upcoming.on
  return (
    <Card>
      <VStack gap={2}>
        <Heading level={3}>지금까지</Heading>
        {past.map((t, i) => <Text key={i} as="p">{koDate(t.on)} · {t.text}</Text>)}
        {upcoming && (
          <HStack gap={2} vAlign="center">
            <Text type="supporting">{koDate(upcoming.on)} · {upcoming.label}</Text>
            <Badge label={overdue ? '지남' : '예정'} variant={overdue ? 'warning' : 'neutral'} />
          </HStack>
        )}
      </VStack>
    </Card>
  )
}

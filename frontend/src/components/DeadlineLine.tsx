import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { Case } from '../api'
import { daysLeft, isoDate, koDate } from '../format'

export function DeadlineLine({ c, offset }: { c: Case; offset: number }) {
  // negotiating에서는 업체가 이미 답했으므로 지난 답변 기한을 보여 주지 않는다.
  const waiting = c.stage === 'waiting' || c.stage === 'escalated'
  const date = waiting ? c.deadline_on : c.stage === 'agreed' ? c.deposit_due_on : null
  if (!date) return null
  const left = daysLeft(date, isoDate(offset))
  const rest = left > 0 ? `${left}일 남음` : left === 0 ? '오늘까지' : `기한이 ${-left}일 지났어요`
  return (
    <VStack gap={1}>
      <Text weight="semibold">{waiting ? '답장 기한' : '입금 기한'} {koDate(date)} · {rest}</Text>
      <Text type="supporting">Reeper가 정한 기한이에요(법정 기한 아님)</Text>
    </VStack>
  )
}

import { Text, VStack } from '../ui'
import type { Case } from '../api'
import { daysLeft, isoDate, koDate } from '../format'

export function DeadlineLine({ c, offset }: { c: Case; offset: number }) {
  // negotiating에서는 업체가 이미 답했으므로 지난 답변 기한을 보여 주지 않는다.
  const waiting = c.stage === 'waiting' || c.stage === 'escalated'
  const date = waiting ? c.deadline_on : c.stage === 'agreed' ? c.deposit_due_on : null
  if (!date) return null
  const left = daysLeft(date, isoDate(offset))
  const rest = left > 0 ? `${left}일 남음` : left === 0 ? '오늘까지' : `기한이 ${-left}일 지났어요`
  const [, m, d] = date.split('-').map(Number)
  // 왼쪽 달력 칸은 기한 날짜, 오른쪽은 남은 날. 지났으면 빨강으로 바꾼다
  return (
    <div className="flex items-start gap-3">
      <div aria-hidden className={`flex h-13 w-12 shrink-0 flex-col items-center justify-center rounded-xl ${left < 0 ? 'bg-warn-soft text-warn' : 'bg-brand-soft text-brand-text'}`}>
        <span className="text-[11px]">{m}월</span>
        <span className="text-[20px] leading-none font-semibold">{d}</span>
      </div>
      <VStack gap={1}>
        <Text weight="semibold">{waiting ? '답장 기한' : '입금 기한'} {koDate(date)} · {rest}</Text>
        <Text type="supporting">Reeper가 정한 기한이에요(법정 기한 아님)</Text>
      </VStack>
    </div>
  )
}

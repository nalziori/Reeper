import { Text, VStack } from '../ui'
import type { Case, Rules } from '../api'
import { won } from '../format'
import { Evidence } from '../steps/Evidence'
import { Timeline } from './Timeline'

// 위 진행 표시에서 지난 단계를 누르면 보이는 읽기 전용 내용. 단계를 되돌리거나 값을 고치지 않는다
// 알리기·답장·입금은 그 단계에 기록된 일만 타임라인에서 골라 보여 준다
const PHASE_EVENTS: Record<number, string[]> = {
  3: ['notice_sent', 'call_attempted'],
  4: ['reply_received', 'counter_sent', 'escalation_sent', 'handoff_done', 'agreement_recorded'],
  5: ['deposit_confirmed'],
}

export function JourneyReview({ c, rules, today, step }: { c: Case; rules: Rules; today: string; step: number }) {
  if (step === 1) {
    const k = c.contract
    const rows: [string, string][] = [
      ['업체', k.gym_name || '(이름 없음)'],
      ['낸 돈', won(k.total_paid)],
      ['이용 기간', `${k.start_date} ~ ${k.end_date}`],
      ...(k.unit === 'count' ? [['이용 횟수', `${k.total_count ?? 0}회 중 ${k.used_count ?? 0}회 사용`] as [string, string]] : []),
      ...(k.addon_value ? [['사은품', won(k.addon_value)] as [string, string]] : []),
      ...(k.security_deposit ? [['보증금', won(k.security_deposit)] as [string, string]] : []),
      ...(k.special_terms ? [['계약서 특약', k.special_terms] as [string, string]] : []),
    ]
    return (
      <dl className="receipt">
        {rows.map(([dt, dd]) => <div key={dt}><dt>{dt}</dt><dd className="review-dd">{dd}</dd></div>)}
      </dl>
    )
  }
  if (step === 2) return <Evidence c={c} rules={rules} />
  const types = PHASE_EVENTS[step] ?? []
  const picked = c.timeline.filter((t) => types.includes(t.type) && t.text)
  if (picked.length === 0) return <Text as="p" type="supporting">이 단계에 기록된 일이 없어요</Text>
  // 다가올 기한은 지금 단계에서 보여 주므로 여기서는 지난 기록만 그린다
  return (
    <VStack gap={2}>
      <Timeline c={{ ...c, stage: 'closed', timeline: picked }} today={today} bare />
    </VStack>
  )
}

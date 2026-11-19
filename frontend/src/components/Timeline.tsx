import { Badge, Card, Heading, Text, VStack } from '../ui'
import {
  BanknotesIcon, CalendarDaysIcon, DocumentTextIcon, EnvelopeIcon, HandThumbUpIcon, InboxArrowDownIcon, LifebuoyIcon,
  PaperAirplaneIcon, PhoneIcon, PhoneXMarkIcon,
} from '@heroicons/react/24/outline'
import type { ComponentType, SVGProps } from 'react'
import type { Case } from '../api'
import { koDate } from '../format'

type Icon = ComponentType<SVGProps<SVGSVGElement>>
// 기록 종류마다 아이콘 하나. 한 줄씩 아이콘·내용·날짜가 같은 칸에 줄을 맞춘다(은행 앱 내역처럼)
const ICON: Record<string, Icon> = {
  notice_sent: PaperAirplaneIcon, call_attempted: PhoneXMarkIcon, reply_received: InboxArrowDownIcon,
  counter_sent: PaperAirplaneIcon, agreement_recorded: HandThumbUpIcon, deposit_confirmed: BanknotesIcon,
  escalation_sent: EnvelopeIcon, handoff_done: LifebuoyIcon,
}
const iconOf = (t: { type: string; text: string }) =>
  t.type === 'notice_sent' && t.text.startsWith('전화') ? PhoneIcon : ICON[t.type] ?? DocumentTextIcon

// today: 화면이 기준으로 삼는 오늘(시연 날짜 포함). 기한이 지나면 '예정' 대신 '지남'으로 보인다
// bare: 카드 없이 목록만(완료 화면 안에 넣을 때)
export function Timeline({ c, today, bare = false, title = '지금까지' }: { c: Case; today: string; bare?: boolean; title?: string }) {
  const upcoming = c.stage === 'waiting' || c.stage === 'escalated'
    ? (c.deadline_on ? { label: '답장 기한', on: c.deadline_on } : null)
    : c.stage === 'agreed' && c.deposit_due_on ? { label: '입금 기한', on: c.deposit_due_on } : null
  const past = c.timeline.filter((t) => t.text)
  if (past.length === 0 && !upcoming) return null
  const overdue = upcoming !== null && today > upcoming.on
  const list = (
    <ol className="tl">
      {past.map((t, i) => {
        const I = iconOf(t)
        return (
          <li key={i} className="tl-item">
            <span className="tl-dot" aria-hidden><I /></span>
            <Text as="span" className="min-w-0">{t.text}</Text>
            <Text as="span" type="supporting" className="tl-date">{koDate(t.on)}</Text>
          </li>
        )
      })}
      {upcoming && (
        <li className="tl-item tl-upcoming">
          <span className="tl-dot" aria-hidden><CalendarDaysIcon /></span>
          <span className="flex min-w-0 items-center gap-2">
            <Text as="span" type="supporting">{upcoming.label}</Text>
            <Badge label={overdue ? '지남' : '예정'} variant={overdue ? 'warning' : 'neutral'} />
          </span>
          <Text as="span" type="supporting" className="tl-date">{koDate(upcoming.on)}</Text>
        </li>
      )}
    </ol>
  )
  if (bare) return list
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>{title}</Heading>
        {list}
      </VStack>
    </Card>
  )
}

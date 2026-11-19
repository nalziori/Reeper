import { Badge, Card, Divider, HStack, Heading, Text, VStack } from '../ui'
import type { Case, Rules } from '../api'
import { STAGE, won } from '../format'

export function Evidence({ c, rules }: { c: Case; rules: Rules }) {
  const r = c.refund
  return (
    <Card>
      <VStack gap={2}>
        <HStack hAlign="between" vAlign="center">
          <Heading level={2}>{c.contract.gym_name || '내 회원권'}</Heading>
          <Badge label={STAGE[c.stage]} variant={c.stage === 'closed' ? 'success' : 'info'} />
        </HStack>
        <Text type="display-3">{won(c.agreed_amount ?? r.refund)}</Text>
        <Text type="supporting">받고 싶은 금액 {won(c.target)} · 거절 기준 {won(c.floor)}</Text>
        <Text type="supporting">
          결제 {won(c.contract.total_paid)} − 이용분 {won(r.used_amount)} ({r.total_days}{r.unit_label} 중 {r.used_days}{r.unit_label}) − 위약금 {won(r.penalty)}
        </Text>
        {c.stage === 'ready' && r.per_day_loss > 0 && <Text weight="semibold">하루 늦으면 약 {won(r.per_day_loss)}씩 줄어요</Text>}
        <Divider />
        <Text type="supporting">근거: {r.refs.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>
        {r.provisional && <Text type="supporting">일반 기준으로 계산했어요. 통보한 날 포함 여부, 끝전, 개월 수 세는 법은 아직 확인 중이에요. 다툼이 있으면 1372에 문의하세요</Text>}
      </VStack>
    </Card>
  )
}

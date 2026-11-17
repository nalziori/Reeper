import { Badge } from '@astryxdesign/core/Badge'
import { Card } from '@astryxdesign/core/Card'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
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
        <Text type="supporting">목표 {won(c.target)} · 최저 수용선 {won(c.floor)}</Text>
        <Text type="supporting">
          결제 {won(c.contract.total_paid)} − 이용분 {won(r.used_amount)} ({r.total_days}{r.unit_label} 중 {r.used_days}{r.unit_label}) − 위약금 {won(r.penalty)}
        </Text>
        {c.stage === 'ready' && r.per_day_loss > 0 && <Text weight="semibold">하루 미루면 약 {won(r.per_day_loss)}씩 줄어듭니다.</Text>}
        <Divider />
        <Text type="supporting">근거: {r.refs.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>
        {r.provisional && <Text type="supporting">일반적인 기준에 따른 예상 금액입니다. 해지 통보가 닿은 날의 포함 여부, 원 단위 끝전, 월 단위 개월 수는 아직 확인 중입니다. 다툼이 있으면 1372 소비자상담센터에 문의하세요.</Text>}
      </VStack>
    </Card>
  )
}

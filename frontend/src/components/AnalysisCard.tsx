import { Badge } from '@astryxdesign/core/Badge'
import { Card } from '@astryxdesign/core/Card'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { Analysis, Rules } from '../api'

// 표시 전용이다. 이 값으로 단계·금액·문안을 계산하지 않는다.
export function AnalysisCard({ analysis, rules }: { analysis: Analysis; rules: Rules }) {
  if (!analysis.claims.length && !analysis.note) return null
  return (
    <VStack gap={2}>
      <Card>
        <VStack gap={3}>
          <Text type="supporting">참고용 분석입니다. 업체에 보낼 문장은 아래 고정 문안을 쓰세요.</Text>
          {analysis.claims.map((cl, i) => {
            const rule = cl.rule_id ? rules[cl.rule_id] : undefined
            return (
              <VStack key={i} gap={1}>
                <Text as="p">“{cl.quote}”</Text>
                <Text as="p" weight="semibold">{cl.claim}</Text>
                {rule ? <Text type="supporting">근거: {rule.title}</Text> : <Badge label="확인 필요" variant="warning" />}
                <Text as="p">답하는 법: {cl.advice}</Text>
              </VStack>
            )
          })}
        </VStack>
      </Card>
      {analysis.note && <Text as="p" type="supporting">{analysis.note}</Text>}
    </VStack>
  )
}

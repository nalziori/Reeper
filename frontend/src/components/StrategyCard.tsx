import { Badge } from '@astryxdesign/core/Badge'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { VStack } from '@astryxdesign/core/VStack'
import { useState, type ReactNode } from 'react'
import type { Case, Rules } from '../api'

const LIMIT = 1000 // docs/계약.md: 상황 설명은 1000자까지

type Props = {
  c: Case
  rules: Rules
  autoReadOff: boolean
  plan: (situation: string) => Promise<'ok' | 'empty' | 'failed'>
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <VStack gap={2}>
      <Heading level={4}>{title}</Heading>
      {children}
    </VStack>
  )
}

// 상황 설명으로 받은 대응 전략. 표시 전용이다. 이 값으로 금액·단계·문안을 정하지 않는다.
export function StrategyCard({ c, rules, autoReadOff, plan }: Props) {
  const [situation, setSituation] = useState(c.situation ?? '')
  const [empty, setEmpty] = useState(false)
  const s = c.strategy
  const text = situation.trim()
  const tooLong = [...situation].length > LIMIT

  return (
    <Card>
      <div className="strategy">
      <VStack gap={4}>
        <VStack gap={1}>
          <Heading level={3}>상황에 맞춘 대응 전략</Heading>
          <Text type="supporting">참고용 전략이에요. 업체에 보낼 문장은 위의 고정 문안을 쓰세요</Text>
        </VStack>

        <TextArea label="내 상황" maxLength={LIMIT}
          description="개인 사정, 업체가 한 말, 계약서 특약을 적어 주세요. 이 내용은 서버에 저장되지 않아요"
          value={situation} onChange={setSituation}
          isDisabled={autoReadOff} disabledMessage="지금은 자동 전략을 쓸 수 없어요" />
        <div>
          <Button label={s ? '전략 다시 받기' : '전략 받기'} isDisabled={autoReadOff || !text || tooLong}
            onClick={async () => setEmpty(await plan(text) === 'empty')} />
        </div>
        {autoReadOff && <Text type="supporting">자동 전략을 쓸 수 없어요. 고정 문안과 버튼으로 끝까지 진행할 수 있어요</Text>}
        {!autoReadOff && empty && !s && (
          <Text type="supporting">이번에는 전략을 만들지 못했어요. 고정 문안과 버튼으로 계속 진행하면 돼요</Text>
        )}

        {s && (
          <>
            <Divider />
            {s.summary && <Text as="p">{s.summary}</Text>}

            {s.grounds.length > 0 && (
              <Section title="쓸 근거">
                {s.grounds.map((g) => {
                  const rule = rules[g.rule_id]
                  return (
                    <VStack key={g.rule_id} gap={1}>
                      <Text as="p" weight="semibold">{rule?.title ?? '근거 표에서 찾지 못한 근거'}</Text>
                      {(!g.verified || !rule) && <div><Badge label="확인 필요" variant="warning" /></div>}
                      <Text as="p" type="supporting">{g.why}</Text>
                    </VStack>
                  )
                })}
              </Section>
            )}

            {s.contract_points.length > 0 && (
              <Section title="다툼이 될 특약">
                {s.contract_points.map((p, i) => (
                  <VStack key={i} gap={1}>
                    <blockquote className="contract-quote"><Text as="p">{p.quote}</Text></blockquote>
                    <Text as="p" type="supporting">{p.how_to_handle}</Text>
                  </VStack>
                ))}
              </Section>
            )}

            {s.objections.length > 0 && (
              <Section title="업체가 할 법한 말">
                {s.objections.map((o, i) => (
                  <VStack key={i} gap={1}>
                    <Text as="p" weight="semibold">{o.objection}</Text>
                    <Text as="p">답하는 법: {o.response}</Text>
                  </VStack>
                ))}
              </Section>
            )}

            {s.cautions.length > 0 && (
              <Section title="미리 알아 둘 것">
                {s.cautions.map((t, i) => <Text key={i} as="p">{t}</Text>)}
              </Section>
            )}

            {s.questions.length > 0 && (
              <Section title="확인해 볼 것">
                {s.questions.map((t, i) => <Text key={i} as="p">{t}</Text>)}
              </Section>
            )}
          </>
        )}
      </VStack>
      </div>
    </Card>
  )
}

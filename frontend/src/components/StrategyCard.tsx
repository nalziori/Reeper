import { Badge, Button, Divider, Heading, Text, TextArea, VStack } from '../ui'
import { useState, type ReactNode } from 'react'
import type { Case, Rules } from '../api'
import { Fold } from './Fold'

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
    // 지금 할 일이 아니라 참고용이라 접어 둔다. 받은 전략이 있으면 펼쳐 둔다
    <Fold title="내 상황에 맞는 조언" defaultOpen={Boolean(s)}
      summary={autoReadOff ? '지금은 쓸 수 없어요. 버튼만으로도 끝까지 갈 수 있어요'
        : '참고용이에요. 업체에는 위 문자를 그대로 보내세요'}>
      <div className="strategy">
      <VStack gap={4}>

        <TextArea label="내 상황" maxLength={LIMIT}
          description="내 사정, 업체가 한 말, 계약서 특약을 적어 주세요"
          value={situation} onChange={setSituation}
          isDisabled={autoReadOff} disabledMessage="지금은 조언을 받을 수 없어요" />
        <div>
          <Button label={s ? '조언 다시 받기' : '조언 받기'} isDisabled={autoReadOff || !text || tooLong}
            onClick={async () => setEmpty(await plan(text) === 'empty')} />
        </div>
        {!autoReadOff && empty && !s && (
          <Text type="supporting">이번에는 조언을 만들지 못했어요. 버튼으로 계속 진행하면 돼요</Text>
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
    </Fold>
  )
}

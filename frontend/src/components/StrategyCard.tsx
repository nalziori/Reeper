import { Badge } from '@astryxdesign/core/Badge'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { VStack } from '@astryxdesign/core/VStack'
import { useEffect, useRef, useState } from 'react'
import { api, type Rules } from '../api'
import { isoDate } from '../format'
import type { Saved } from '../useCase'

type Props = { saved: Saved; keep: (s: Saved) => void; rules: Rules; llmOff: boolean }

// 상황 설명으로 받은 전략. 표시 전용이다. 이 값으로 단계·금액·문안을 계산하지 않는다.
export function StrategyCard({ saved, keep, rules, llmOff }: Props) {
  const c = saved.step.case
  const [situation, setSituation] = useState(c.situation ?? '')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const latest = useRef(saved)
  useEffect(() => { latest.current = saved })
  const s = c.strategy
  if (llmOff && !s) return null // LLM이 없으면 전략도 없다. 고정 문안과 버튼으로 끝까지 간다

  const ask = async () => {
    setLoading(true)
    setNotice('')
    try {
      const res = await api.strategy(c, situation, isoDate(saved.offset))
      // 기다리는 사이 사건이 진행됐을 수 있다. 최신 사건에 상황과 전략만 얹는다.
      const now = latest.current
      keep({ ...now, step: { ...now.step, case: { ...now.step.case, situation: res.case.situation, strategy: res.case.strategy } } })
      if (res.llm_fallback) setNotice('전략을 만들지 못했어요. 아래 문안으로 그대로 진행하셔도 됩니다.')
      else if (!res.case.strategy) setNotice('지금 정보로는 보여 드릴 전략이 없어요. 아래 문안으로 진행해 주세요.')
    } catch (e) {
      setNotice((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>내 상황에 맞는 전략</Heading>
        <Text type="supporting">참고용 안내입니다. 업체에 보낼 문장은 아래 고정 문안을 쓰세요. 금액은 위 계산값 그대로입니다.</Text>
        {!llmOff && (
          <>
            <TextArea label="내 상황" description="왜 그만두려는지, 업체가 뭐라고 했는지 편하게 적어 주세요. 비워 둬도 됩니다."
              value={situation} onChange={setSituation} maxLength={1000} />
            <Button label={loading ? '전략을 만드는 중…' : s ? '전략 다시 받기' : '전략 받기'} isDisabled={loading} onClick={ask} />
          </>
        )}
        {notice && <Text as="p" role="alert">{notice}</Text>}
        {s && (
          <VStack gap={3}>
            {s.summary && <Text as="p" weight="semibold">{s.summary}</Text>}
            {s.cautions.length > 0 && (
              <VStack gap={1}>
                <Text weight="semibold">미리 알아 둘 점</Text>
                {s.cautions.map((x, i) => <Text as="p" key={i}>· {x}</Text>)}
              </VStack>
            )}
            {s.grounds.length > 0 && (
              <VStack gap={1}>
                <Text weight="semibold">쓸 수 있는 근거</Text>
                {s.grounds.map((g, i) => (
                  <VStack key={i} gap={1}>
                    <Text type="supporting">{rules[g.rule_id]?.title ?? g.rule_id}</Text>
                    {!g.verified && <Badge label="확인 전 근거" variant="warning" />}
                    <Text as="p">{g.why}</Text>
                  </VStack>
                ))}
              </VStack>
            )}
            {s.contract_points.length > 0 && (
              <VStack gap={1}>
                <Text weight="semibold">계약서에서 다툴 수 있는 곳</Text>
                {s.contract_points.map((p, i) => (
                  <VStack key={i} gap={1}>
                    <Text as="p">“{p.quote}”</Text>
                    <Text as="p">{p.how_to_handle}</Text>
                  </VStack>
                ))}
              </VStack>
            )}
            {s.objections.length > 0 && (
              <VStack gap={1}>
                <Text weight="semibold">업체가 이렇게 말하면</Text>
                {s.objections.map((o, i) => (
                  <VStack key={i} gap={1}>
                    <Text as="p">“{o.objection}”</Text>
                    <Text as="p">{o.response}</Text>
                  </VStack>
                ))}
              </VStack>
            )}
            {s.questions.length > 0 && (
              <VStack gap={1}>
                <Text weight="semibold">확인해 두면 좋은 것</Text>
                {s.questions.map((x, i) => <Text as="p" key={i}>· {x}</Text>)}
              </VStack>
            )}
          </VStack>
        )}
      </VStack>
    </Card>
  )
}

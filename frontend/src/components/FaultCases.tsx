import { useEffect, useState } from 'react'
import { api, type MediationCase, type MediationCases } from '../api'
import { won } from '../format'
import { Card, Heading, RadioList, RadioListItem, Text, VStack } from '../ui'

// 업체 잘못을 고르면 어떤 일이 있었는지 묻고, 1372 판례/조정례에서 비슷한 사례가 어떻게 끝났는지 보여 준다.
// 데이터는 data/mediation_cases.json이다. 사례의 금액은 그 사건의 금액이고, 사용자 계약으로 계산하지 않는다.
// 조정례는 근거 표(rules.json)가 아니라 참고 자료다. 불러오지 못하면 이 카드를 보이지 않는다.
const FAULT_NOTE = {
  not_stated: '원문은 업체 잘못이라고 따로 적지 않았어요',
  not_determined: '원문은 업체 잘못이라고 단정하기 어렵다고 했어요',
} as const

function CaseView({ c }: { c: MediationCase }) {
  return (
    <VStack gap={2}>
      <Text weight="semibold">{c.title}</Text>
      <Text as="p"><b>있었던 일</b> · {c.facts}</Text>
      <Text as="p"><b>어떻게 끝났나</b> · 조정결정으로 끝났어요. {c.result}</Text>
      <Text as="p">
        <b>돌려받은 돈</b> · {won(c.decided_refund)}. {c.penalty_deducted ? '위약금을 뺐어요' : '위약금은 빼지 않았어요'}
      </Text>
      <Text type="supporting">이용분 계산: {c.usage_method}</Text>
      <Text type="supporting">{FAULT_NOTE[c.business_fault as keyof typeof FAULT_NOTE] ?? ''}</Text>
      <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-[14px] underline">1372 원문 보기 (새 창)</a>
    </VStack>
  )
}

export function FaultCases() {
  const [data, setData] = useState<MediationCases | null>(null)
  const [kind, setKind] = useState('')
  useEffect(() => {
    let active = true
    api.mediationCases().then((d) => { if (active) setData(d) }, () => { /* 참고 자료라 못 불러오면 숨긴다 */ })
    return () => { active = false }
  }, [])
  if (!data) return null
  const chosen = kind ? data.kinds[kind] : undefined
  const cases = chosen ? data.cases.filter((c) => chosen.cases.includes(c.id)) : []
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={2}>비슷한 일은 어떻게 끝났을까요</Heading>
        <RadioList label="어떤 일이 있었나요" value={kind} onChange={setKind}
          description="1372 소비자상담센터의 조정례에서 비슷한 사례를 찾아 보여 드려요">
          {Object.entries(data.kinds).map(([id, k]) => <RadioListItem key={id} value={id} label={k.label} />)}
        </RadioList>
        {chosen && (cases.length ? (<>
          {cases.map((c) => <CaseView key={c.id} c={c} />)}
          <Text type="supporting">
            비슷한 사례일 뿐, 내 계약도 같은 결과가 나온다는 뜻은 아니에요. 금액은 그 사건의 금액이에요. 내 경우는 1372에 상담하세요
          </Text>
        </>) : (
          <Text as="p">이 유형은 아직 찾은 조정례가 없어요. 1372에 상담하면서 업체 공지나 문자를 보여 주세요</Text>
        ))}
      </VStack>
    </Card>
  )
}

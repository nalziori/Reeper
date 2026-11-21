import { useEffect, useState } from 'react'
import { api, type MediationCase, type MediationCases } from '../api'
import { won } from '../format'
import { Card, Heading, RadioList, RadioListItem, Text, VStack } from '../ui'

// 업체 잘못을 고르면 어떤 일이 있었는지 묻고, 비슷한 조정례(1372·소비자24)에서 어떻게 판단했는지 보여 준다.
// 원문은 결정 내용만 담고 실제 입금 여부는 담지 않으므로 '돌려받았다'고 쓰지 않는다.
// 업체 잘못으로 인정되지 않은 사례도 같이 보여 준다. 인정된 사례만 보이면 늘 위약금이 없는 것처럼 읽히기 때문이다.
// 데이터는 data/mediation_cases.json이다. 사례의 금액은 그 사건의 금액이고, 사용자 계약으로 계산하지 않는다.
// 조정례는 근거 표(rules.json)가 아니라 참고 자료다. 불러오지 못하면 이 카드를 보이지 않는다.
const FAULT_NOTE = {
  recognized: '업체 사정으로 해지됐다고 인정됐어요',
  consumer: '업체 잘못으로 인정되지 않았어요(소비자 사정으로 봤어요)',
  not_determined: '해지에 업체 책임이 있다고 단정하기 어렵다고 봤어요',
  not_stated: '원문은 업체 잘못이라고 따로 적지 않았어요',
} as const
const sourceName = (url: string) => url.includes('consumer.go.kr') ? '소비자24' : '1372'

function CaseView({ c }: { c: MediationCase }) {
  return (
    <VStack gap={2}>
      <Text weight="semibold">{c.title}</Text>
      <Text type="supporting">{FAULT_NOTE[c.business_fault as keyof typeof FAULT_NOTE] ?? ''}</Text>
      <Text as="p"><b>있었던 일</b> · {c.facts}</Text>
      <Text as="p"><b>판단</b> · {c.result}</Text>
      <Text as="p">
        <b>결정에 적힌 환급액</b> · {won(c.decided_refund)}. {c.money_note}
      </Text>
      <Text type="supporting">이용분 계산: {c.usage_method}</Text>
      <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-[14px] underline">{sourceName(c.url)} 원문 보기 (새 창)</a>
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
  const mixed = new Set(cases.map((c) => c.business_fault)).size > 1
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={2}>비슷한 일은 어떻게 판단했을까요</Heading>
        <RadioList label="어떤 일이 있었나요" value={kind} onChange={setKind}
          description="한국소비자원 조정례(1372·소비자24)에서 비슷한 사례를 찾아 보여 드려요">
          {Object.entries(data.kinds).map(([id, k]) => <RadioListItem key={id} value={id} label={k.label} />)}
        </RadioList>
        {chosen && (cases.length ? (<>
          {mixed && <Text as="p">비슷한 유형에서도 업체 책임에 대한 판단은 사례마다 달랐어요</Text>}
          {cases.map((c) => <CaseView key={c.id} c={c} />)}
          <Text type="supporting">
            비슷한 사례일 뿐, 내 계약도 같은 결과가 나온다는 뜻은 아니에요. 금액은 그 사건의 결정 금액이고, 실제로 입금됐는지는 원문에 없어요. 내 경우는 1372에 상담하세요
          </Text>
        </>) : (
          <Text as="p">이 유형은 아직 찾은 조정례가 없어요. 1372에 상담하면서 업체 공지나 문자를 보여 주세요</Text>
        ))}
      </VStack>
    </Card>
  )
}

import { useState } from 'react'
import type { MediationCase } from '../api'
import { useMediationCases } from '../useMediationCases'
import { won } from '../format'
import { Card, Collapsible, ExternalLink, HStack, RadioList, RadioListItem, Text, VStack } from '../ui'

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

// 사례가 여러 건이면 금액이 화면 아래로 밀린다. 제목·판단 결과·결정 환급액·원문 링크만 보이고 자세한 내용은 눌러서 본다
function CaseView({ c }: { c: MediationCase }) {
  return (
    <VStack gap={2}>
      <Text weight="semibold">{c.title}</Text>
      <Text type="supporting">{FAULT_NOTE[c.business_fault as keyof typeof FAULT_NOTE] ?? ''}</Text>
      <Text as="p"><b>결정에 적힌 환급액</b> · {won(c.decided_refund)}</Text>
      <Collapsible trigger={<Text type="supporting">있었던 일과 판단 보기</Text>}>
        <VStack gap={2}>
          <Text as="p"><b>있었던 일</b> · {c.facts}</Text>
          <Text as="p"><b>판단</b> · {c.result}</Text>
          <Text as="p">{c.money_note}</Text>
          <Text type="supporting">이용분 계산: {c.usage_method}</Text>
        </VStack>
      </Collapsible>
      <ExternalLink href={c.url} label={`${sourceName(c.url)} 원문 보기`} />
    </VStack>
  )
}

// 업체 사정 유형 고르기. 금액을 정하는 질문이라 접수 화면의 업종·해지 이유 카드 안에 둔다.
// 고른 뒤에는 한 줄로 접어 자리를 줄이고, '바꾸기'로 다시 연다. 유형은 계약 값(fault_kind)이 된다. '그 밖'(other)은 조정례가 없다
export function FaultKindPicker({ value, onChange, isDisabled }: { value: string; onChange: (kind: string) => void; isDisabled?: boolean }) {
  const data = useMediationCases()
  const [open, setOpen] = useState(false)
  if (!data) return null
  const label = value === 'other' ? '그 밖의 업체 사정' : data.kinds[value]?.label
  if (value && label && !open) {
    return (
      <HStack gap={2} hAlign="between" vAlign="center">
        <Text><Text as="span" type="supporting">어떤 일이었나요 · </Text>{label}</Text>
        <button type="button" className="link-btn" aria-label="어떤 일이었는지 바꾸기" disabled={isDisabled} onClick={() => setOpen(true)}>바꾸기</button>
      </HStack>
    )
  }
  return (
    <RadioList label="어떤 일이었나요" value={value} isDisabled={isDisabled} onChange={(k) => { onChange(k); setOpen(false) }}>
      {Object.entries(data.kinds).map(([id, k]) => <RadioListItem key={id} value={id} label={k.label} />)}
      <RadioListItem value="other" label="그 밖의 업체 사정" />
    </RadioList>
  )
}

// 그 유형의 조정례를 요약 한 줄(인정·불인정 수)과 함께 접어서 보인다. 펼쳐야 사례가 보인다.
// 접수 화면에서는 금액 영수증 아래, 답장 화면에서는 문안 아래에 둔다. 사례가 없는 유형이면 보이지 않는다
const RESULT_SHORT = { recognized: '인정', consumer: '불인정', not_determined: '판단 어려움', not_stated: '원문에 판단 없음' } as const
export function FaultCases({ kind, context }: { kind: string; context: 'intake' | 'reply' }) {
  const data = useMediationCases()
  if (!data) return null
  const chosen = kind && kind !== 'other' ? data.kinds[kind] : undefined
  const cases = chosen ? data.cases.filter((c) => chosen.cases.includes(c.id)) : []
  if (!cases.length) return null
  const mixed = new Set(cases.map((c) => c.business_fault)).size > 1
  const counts = Object.entries(RESULT_SHORT)
    .map(([key, name]) => [name, cases.filter((c) => c.business_fault === key).length] as const)
    .filter(([, n]) => n > 0).map(([name, n]) => `${name} ${n}`).join(' · ')
  return (
    <Card>
      <Collapsible trigger={<VStack gap={1}>
        <Text weight="semibold">비슷한 사례 {cases.length}건 참고하기</Text>
        <Text type="supporting">{counts}</Text>
      </VStack>}>
        <VStack gap={4}>
          {chosen?.note && <Text as="p">{chosen.note}</Text>}
          {mixed && <Text as="p">비슷한 유형에서도 업체 책임에 대한 판단은 사례마다 달랐어요</Text>}
          {cases.map((c) => <CaseView key={c.id} c={c} />)}
          <Text type="supporting">
            {context === 'reply'
              ? '답장을 고쳐 쓰거나 1372에 말할 때 참고하세요. 문자에 넣는 근거는 아니에요'
              : '비슷한 사례일 뿐, 내 계약도 같은 결과가 나온다는 뜻은 아니에요. 금액은 그 사건의 결정 금액이고, 실제로 입금됐는지는 원문에 없어요'}
          </Text>
        </VStack>
      </Collapsible>
    </Card>
  )
}

import { Collapsible } from '@astryxdesign/core/Collapsible'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { TextInput } from '@astryxdesign/core/TextInput'
import { VStack } from '@astryxdesign/core/VStack'
import { useState } from 'react'
import type { Contract } from '../api'
import { extrasProblem } from '../contractCheck'

type Unit = NonNullable<Contract['unit']>

// 숫자만 남긴다. 비우면 undefined
const digits = (v: string): number | undefined => {
  const d = v.replace(/\D/g, '')
  return d === '' ? undefined : Number(d)
}
const shown = (n: number | null | undefined) => (n == null || n === 0 ? '' : String(n))

// 직접 입력에서 기본 네 칸 밖의 계약 내용: 이용 단위, 특약, 부가상품, 보증금
type Status = { type: 'warning' | 'error'; message: string }
type Field = 'unit' | 'total_count' | 'special_terms' | 'addon_value' | 'security_deposit'

// statusOf: 사진에서 읽어 사람이 확인할 칸의 표시. 없으면 표시하지 않는다
export function ContractExtras({ c, onChange, isDisabled, statusOf = () => undefined }: {
  c: Contract; onChange: (next: Contract) => void; isDisabled: boolean; statusOf?: (field: Field) => Status | undefined
}) {
  const unit: Unit = c.unit ?? 'day'
  const setUnit = (v: string) => {
    const next = v as Unit
    onChange({ ...c, unit: next, total_count: next === 'day' ? undefined : c.total_count,
      used_count: next === 'count' ? c.used_count : undefined })
  }
  const problem = extrasProblem(c)
  const usedTooMany = unit === 'count' && c.used_count != null && c.total_count != null && c.used_count > c.total_count
  // 특약·부가상품·보증금은 계약서에 있을 때만 적는 칸이라 접어 둔다. 값이 있거나 사진에서 읽어 확인할 칸이면 펼쳐 둔다
  const [open, setOpen] = useState(false)
  const filled = Boolean(c.special_terms || c.addon_value || c.security_deposit
    || statusOf('special_terms') || statusOf('addon_value') || statusOf('security_deposit'))
  return (
    <>
      <RadioList label="이용 단위" value={unit} onChange={setUnit} isDisabled={isDisabled} orientation="horizontal"
        description="계약서에 횟수나 개월 수로 적혀 있으면 바꾸세요">
        <RadioListItem value="day" label="기간" />
        <RadioListItem value="month" label="개월 수" />
        <RadioListItem value="count" label="횟수(PT·레슨)" />
      </RadioList>
      {statusOf('unit') && <Text type="supporting">{statusOf('unit')!.message}</Text>}
      {unit !== 'day' && (
        <TextInput label={unit === 'month' ? '총 개월 수' : '총 횟수'} inputMode="numeric" isDisabled={isDisabled}
          value={shown(c.total_count)} onChange={(v) => onChange({ ...c, total_count: digits(v) || undefined })}
          status={statusOf('total_count')} />
      )}
      {unit === 'count' && (
        <TextInput label="이미 쓴 횟수" inputMode="numeric" isDisabled={isDisabled}
          value={c.used_count == null ? '' : String(c.used_count)} onChange={(v) => onChange({ ...c, used_count: digits(v) })}
          status={usedTooMany ? { type: 'error', message: problem } : undefined} />
      )}
      {problem && !usedTooMany && <Text type="supporting">{problem}</Text>}
      <Collapsible isOpen={open || filled} onOpenChange={setOpen}
        trigger={<VStack gap={1}><Text weight="semibold">특약·부가상품·보증금(선택)</Text><Text type="supporting">계약서에 적혀 있을 때만 적어요</Text></VStack>}>
      <VStack gap={3}>
      <TextArea label="특약사항(선택)" isDisabled={isDisabled} maxLength={1000}
        description="계약서의 특약이나 비고 칸을 그대로 옮겨 적어 주세요."
        value={c.special_terms ?? ''} onChange={(v) => onChange({ ...c, special_terms: v || undefined })} status={statusOf('special_terms')} />
      <TextInput label="부가상품 가액(원, 선택)" inputMode="numeric" isDisabled={isDisabled}
        description="운동복·사은품처럼 계약서에 금액이 적힌 것만 적습니다."
        value={shown(c.addon_value)} onChange={(v) => onChange({ ...c, addon_value: digits(v) })}
        status={statusOf('addon_value')} />
      <TextInput label="보증금(원, 선택)" inputMode="numeric" isDisabled={isDisabled}
        description="락커 보증금처럼 결제 금액과 따로 낸 돈입니다. 돌려받을 금액에 더합니다."
        value={shown(c.security_deposit)} onChange={(v) => onChange({ ...c, security_deposit: digits(v) })}
        status={statusOf('security_deposit')} />
      </VStack>
      </Collapsible>
    </>
  )
}

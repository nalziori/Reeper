import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { TextInput } from '@astryxdesign/core/TextInput'
import { VStack } from '@astryxdesign/core/VStack'
import { useState } from 'react'
import type { ReplyType } from '../api'
import type { Send } from '../useCase'

const CHOICES: { type: ReplyType; label: string }[] = [
  { type: 'accept', label: '환불해 준대요' },
  { type: 'refuse', label: '환불이 안 된대요' },
  { type: 'list_price', label: '정상가로 계산한대요' },
  { type: 'visit', label: '방문해야 한대요' },
  { type: 'no_answer', label: '전화를 안 받아요' },
  { type: 'callback', label: '다시 연락 준대요' },
  { type: 'unknown', label: '잘 모르겠어요' },
]

// 금액 칸: 숫자만, 0보다 큰 안전한 정수
const parseAmount = (v: string): number | null => {
  if (!/^\d+$/.test(v)) return null
  const n = Number(v)
  return Number.isSafeInteger(n) && n > 0 ? n : null
}

// LLM 없이도 답장을 기록하는 버튼 묶음. 서버에는 유형과 라벨만 보낸다.
export function ReplyButtons({ send }: { send: Send }) {
  const [amount, setAmount] = useState('')
  const parsed = parseAmount(amount)
  const invalid = amount !== '' && parsed === null
  return (
    <VStack gap={2}>
      <Heading level={4}>버튼으로 고르기</Heading>
      <HStack gap={2} wrap="wrap">
        {CHOICES.map(({ type, label }) => (
          <Button key={type} label={label} onClick={() => send({ type: 'reply_received', reply_type: type, text: label })} />
        ))}
      </HStack>
      <TextInput label="제시한 금액(원)" value={amount} onChange={setAmount} inputMode="numeric"
        status={invalid ? { type: 'error', message: '0보다 큰 정수만 적어 주세요.' } : undefined} />
      <HStack><Button label="금액을 제시했어요" isDisabled={parsed === null}
        onClick={async () => {
          if (parsed !== null && await send({ type: 'reply_received', reply_type: 'low_offer', amount: parsed, text: '금액을 제시했어요' })) setAmount('')
        }} /></HStack>
      {parsed === null && !invalid && <Text type="supporting">금액을 제시했다면 위 칸에 숫자만 적어 주세요.</Text>}
    </VStack>
  )
}

import { Button, ChoiceRow, HStack, Heading, TextInput, VStack, Waiting } from '../ui'
import {
  BuildingStorefrontIcon, CalculatorIcon, ClockIcon, HandThumbDownIcon, HandThumbUpIcon, PhoneXMarkIcon, QuestionMarkCircleIcon,
} from '@heroicons/react/24/outline'
import { useState, type ComponentType, type SVGProps } from 'react'
import type { ReplyType } from '../api'
import type { Send } from '../useCase'

const CHOICES: { type: ReplyType; label: string; Icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { type: 'accept', label: '환불해 준대요', Icon: HandThumbUpIcon },
  { type: 'refuse', label: '환불이 안 된대요', Icon: HandThumbDownIcon },
  { type: 'list_price', label: '정상가로 계산한대요', Icon: CalculatorIcon },
  { type: 'visit', label: '방문해야 한대요', Icon: BuildingStorefrontIcon },
  { type: 'no_answer', label: '전화를 안 받아요', Icon: PhoneXMarkIcon },
  { type: 'callback', label: '다시 연락 준대요', Icon: ClockIcon },
  { type: 'unknown', label: '잘 모르겠어요', Icon: QuestionMarkCircleIcon },
]

// 금액 칸: 숫자만, 0보다 큰 안전한 정수
const parseAmount = (v: string): number | null => {
  if (!/^\d+$/.test(v)) return null
  const n = Number(v)
  return Number.isSafeInteger(n) && n > 0 ? n : null
}

// LLM 없이도 답장을 기록하는 선택지. 서버에는 유형과, 붙여넣은 원문이 있으면 원문(없으면 라벨)을 보낸다.
// 한 줄 전체가 버튼인 목록이다(바텀 시트 안에서 손가락으로 한 번에 고른다)
export function ReplyButtons({ send, text = '', saving = false }: { send: Send; text?: string; saving?: boolean }) {
  const [amount, setAmount] = useState('')
  const parsed = parseAmount(amount)
  const invalid = amount !== '' && parsed === null
  return (
    <VStack gap={3}>
      <Heading level={4}>업체가 뭐라고 했나요?</Heading>
      {saving && <Waiting message="기록하고 있어요" />}
      <div className="choice-list" role="group" aria-label="업체 답">
        {CHOICES.map(({ type, label, Icon }) => (
          <ChoiceRow key={type} icon={<Icon />} label={label} disabled={saving}
            onClick={() => void send({ type: 'reply_received', reply_type: type, text: text.trim() || label })} />
        ))}
      </div>
      <div className="choice-amount">
        <TextInput label="업체가 말한 금액(원)" value={amount} onChange={setAmount} inputMode="numeric"
          description="금액을 말했으면 적고 아래 버튼을 눌러요"
          status={invalid ? { type: 'error', message: '0보다 큰 숫자만 적어 주세요' } : undefined} />
        <HStack><Button label="금액을 말했어요" isDisabled={parsed === null || saving}
          onClick={async () => {
            if (parsed !== null && await send({ type: 'reply_received', reply_type: 'low_offer', amount: parsed, text: text.trim() || '금액을 제시했어요' })) setAmount('')
          }} /></HStack>
      </div>
    </VStack>
  )
}

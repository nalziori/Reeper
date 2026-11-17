import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { VStack } from '@astryxdesign/core/VStack'
import { useState } from 'react'
import type { Contract } from '../api'
import { won } from '../format'

// 업체 잘못으로 해지할 때 1372 상담에서 말할 사실만 모은다. 계산 금액과 조문은 넣지 않는다(근거 표 밖이다).
// 값은 사용자가 입력한 계약 내용과 직접 적은 글뿐이고, 이 브라우저 밖으로 보내지 않는다.
function faultSummary(c: Contract, happened: string): string {
  return [
    '[1372에 말할 내용]',
    `- 업체: ${c.gym_name || '(업체 이름)'}`,
    `- 계약 기간: ${c.start_date} ~ ${c.end_date}`,
    `- 결제 금액: ${won(c.total_paid)}`,
    `- 있었던 일: ${happened.trim() || '(언제부터 무엇이 달라졌는지)'}`,
    '- 가지고 있는 자료: 계약서, (공지 사진·문자 등)',
  ].join('\n')
}

export function FaultSummary({ c }: { c: Contract }) {
  const [happened, setHappened] = useState('')
  const [copied, setCopied] = useState('')
  const text = faultSummary(c, happened)
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>1372에 말할 내용 정리</Heading>
        <TextArea label="무슨 일이 있었나요" maxLength={500} value={happened} onChange={(v) => { setHappened(v); setCopied('') }}
          description="언제부터 무엇이 달라졌는지, 업체가 뭐라고 했는지 적어 주세요. 이 내용은 서버로 보내지 않아요" />
        <div className="draft">{text}</div>
        <div>
          <Button label={copied === text ? '복사됨' : '복사'} onClick={async () => {
            try { await navigator.clipboard.writeText(text); setCopied(text) } catch { setCopied('') }
          }} />
        </div>
        <Text type="supporting">상담할 때 이 내용을 보며 말하거나, 상담 신청서에 옮겨 적으세요</Text>
      </VStack>
    </Card>
  )
}

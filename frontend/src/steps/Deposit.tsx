import { Badge, Button, Card, Divider, HStack, Heading, Text, TextInput, VStack } from '../ui'
import { useState } from 'react'
import { DraftList } from '../components/Draft'
import { Timeline } from '../components/Timeline'
import { isoDate, won } from '../format'
import type { Saved, Send } from '../useCase'

// stage가 agreed, closed일 때: 합의 문안, 입금 확인(금액), 기한이 한참 지나면 1372 접수
export function Deposit({ saved, send }: { saved: Saved; send: Send }) {
  const { case: c, action, drafts } = saved.step
  const deposited = c.deposited ?? 0
  const left = Math.max((c.agreed_amount ?? 0) - deposited, 0)
  // 비워 두면 남은 금액 전부가 들어온 것으로 본다
  const [amount, setAmount] = useState('')
  const typed = amount === '' ? left : Number(amount)
  const valid = Number.isSafeInteger(typed) && typed > 0
  return (
    <>
      {/* 끝난 사건: 받은 돈을 크게, 그 아래 지금까지 한 일. 할 일이 없으니 문안·기록 칸은 두지 않는다 */}
      {c.stage === 'closed' && (
        <Card>
          <VStack gap={4}>
            <VStack gap={2}>
              <Badge label="환불 완료" variant="success" />
              <Text type="display-3">{won(deposited)}</Text>
              <Text type="supporting">
                {deposited >= c.refund.refund ? '처음 계산한 돈을 모두 받았어요' : `합의한 돈을 모두 받았어요(처음 계산 ${won(c.refund.refund)})`}
              </Text>
            </VStack>
            <Divider />
            <Timeline c={c} today={isoDate(saved.offset)} bare />
            <Text type="supporting">남기려면 아래 '기록' 탭에서 저장하세요. 이 브라우저에만 있어요</Text>
          </VStack>
        </Card>
      )}
      {c.stage !== 'closed' && <DraftList drafts={drafts} note={saved.note} />}
      {c.stage === 'agreed' && (
      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
            <>
              {deposited > 0 && <Text>받은 돈 {won(deposited)} · 남은 돈 {won(left)}</Text>}
              <TextInput label="들어온 금액(원)" inputMode="numeric" value={amount} placeholder={left.toLocaleString('ko-KR')}
                description="비우면 남은 돈이 다 들어온 걸로 기록해요"
                onChange={(v) => setAmount(v.replace(/\D/g, ''))} />
              <HStack gap={2} wrap="wrap">
                <Button variant="primary" label="입금을 확인했어요" isDisabled={!valid}
                  onClick={async () => { if (await send({ type: 'deposit_confirmed', amount: typed })) setAmount('') }} />
                {action.type === 'go_1372' && <Button label="1372에 접수했어요" onClick={() => send({ type: 'handoff_done' })} />}
              </HStack>
            </>
        </VStack>
      </Card>
      )}
    </>
  )
}

import { Button, Card, HStack, Heading, Text, TextInput, VStack } from '../ui'
import { useState } from 'react'
import { DraftList } from '../components/Draft'
import { won } from '../format'
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
      <DraftList drafts={drafts} note={saved.note} />
      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
          {c.stage === 'agreed' && (
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
          )}
          {c.stage === 'closed' && <Text>수고 많으셨어요. 남기려면 아래 '기록 저장'을 쓰세요</Text>}
        </VStack>
      </Card>
    </>
  )
}

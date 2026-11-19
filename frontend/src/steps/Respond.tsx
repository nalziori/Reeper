import { Banner, Button, Card, Collapsible, Dock, HStack, Heading, Text, TextArea, TextInput, VStack } from '../ui'
import { useEffect, useRef, useState } from 'react'
import type { ReadReply } from '../api'
import { DraftList } from '../components/Draft'
import { ReplyButtons } from '../components/ReplyButtons'
import { REPLY_LABEL, won } from '../format'
import type { Saved, Send } from '../useCase'

type Props = {
  saved: Saved
  send: Send
  reply: string
  setReply: (update: string | ((current: string) => string)) => void
  settlement: string
  setSettlement: (value: string) => void
  autoReadOff: boolean
  read: (ReadReply & { text: string }) | null
  readNote: string
  reading: boolean
  readReply: (text: string) => Promise<void>
  clearRead: () => void
}

// 읽은 결과를 보여 주고 사용자가 확정해야 기록한다. 자동 판단이 곧바로 합의 같은 단계를 만들지 않게 한다.
// 수용·금액 제시는 잘못 읽으면 합의 금액과 수용선 경고가 틀어지므로 원문을 다 보여 주고, 수용은 확정하면 생기는 일을 적는다.
// 키워드 판단은 이 둘을 자주 잘못 읽어서(평가에서 틀린 건 대부분이 금액) 미리 고른 값을 확정하지 못하게 하고 버튼으로 고르게 한다
function ReadConfirm({ read, refund, onConfirm, onReject }:
  { read: ReadReply & { text: string }; refund: number; onConfirm: () => void; onReject: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.scrollIntoView({ block: 'nearest' }) }, [read])
  const risky = read.reply_type === 'accept' || read.reply_type === 'low_offer'
  const quote = !risky && read.text.length > 60 ? `${read.text.slice(0, 60)}…` : read.text
  const keywordOnly = read.llm_fallback && risky
  return (
    <div ref={ref}>
      <Card variant="muted">
        <VStack gap={2}>
          <Heading level={4}>이렇게 읽었어요. 맞나요?</Heading>
          <Text type="supporting">“{quote}”</Text>
          <Text weight="semibold">{REPLY_LABEL[read.reply_type]}{read.amount != null ? ` · ${won(read.amount)}` : ''}</Text>
          {read.reply_type === 'accept' && !keywordOnly && (
            <Text type="supporting">기록하면 {won(refund)}으로 합의하고 입금 기한을 잡아요</Text>
          )}
          {keywordOnly
            ? <Text type="supporting">자동으로 못 읽어 낱말로 짐작했어요. 환불 여부와 금액은 원문을 보고 아래 버튼으로 골라 주세요</Text>
            : read.llm_fallback && <Text type="supporting">자동으로 못 읽어 낱말로 짐작했어요. 틀리기 쉬우니 꼭 봐 주세요</Text>}
          <HStack gap={2} wrap="wrap">
            {!keywordOnly && <Button variant="primary" label="맞아요, 기록할게요" onClick={onConfirm} />}
            <Button label={keywordOnly ? '닫기' : '아니에요, 직접 고를게요'} onClick={onReject} />
          </HStack>
        </VStack>
      </Card>
    </div>
  )
}

// stage가 waiting, negotiating, escalated일 때: 문안, 기록 버튼, 답장 입력. handed_off일 때: 1372 상담 뒤 합의 금액 기록
export function Respond({ saved, send, reply, setReply, settlement, setSettlement, autoReadOff, read, readNote, reading, readReply, clearRead }: Props) {
  const { case: c, action, drafts } = saved.step
  // 답장을 기록하면 붙여넣은 칸과 읽은 결과를 비운다
  const sendReply: Send = async (event, patch, opts) => {
    const ok = await send(event, patch, opts)
    if (ok) { setReply(''); clearRead() }
    return ok
  }
  const settlementAmount = Number(settlement)
  // 한 화면에 할 일 하나. 보내거나 말할 글이 있으면(재요청, 반박, 수락, 내용증명, 1372 접수) 그 글과 '했어요' 버튼이 이 화면의 일이고,
  // 답장 기록은 접어 둔다. 보낼 것이 없으면 답장 기록이 이 화면의 일이고, 지난 문자를 접어 둔다
  const sendFirst = ['follow_up', 'counter', 'certified_mail', 'confirm_agreement'].includes(action.type) || (action.type === 'go_1372' && c.stage !== 'handed_off')
  const hasDock = sendFirst || (c.stage === 'negotiating' && c.offered != null && c.offered > 0 && !action.warn)
  const replyStage = ['waiting', 'negotiating', 'escalated'].includes(c.stage)
  const [openReply, setOpenReply] = useState(false)
  const [openSent, setOpenSent] = useState(false)
  const hasDrafts = Object.keys(drafts).length > 0 || Boolean(saved.note)
  // 업체가 나중에 연락하겠다고 미뤘을 때의 문자는 아직 보낸 적이 없다. '보낸 문자 다시 보기'에 접지 않고 펼쳐 둔다
  const askFirst = 'ask_callback_time' in drafts

  const replyForm = (
    <VStack gap={3}>
      {autoReadOff && (
        <>
          <Banner status="info" collapsible={false} title="지금은 버튼으로 골라 주세요" />
          <ReplyButtons send={sendReply} text={reply} />
        </>
      )}
      <TextArea label="받은 답장" description="문자를 붙여넣거나 통화로 들은 말을 적어요"
        value={reply} onChange={setReply} maxLength={500} />
      <HStack><Button label={reading ? '읽는 중…' : '답장 읽기'} isDisabled={!reply.trim() || reading}
        onClick={() => void readReply(reply)} /></HStack>
      {readNote && <Text type="supporting" role="status">{readNote}</Text>}
      {read && (
        <ReadConfirm read={read} refund={c.refund.refund}
          onConfirm={() => void sendReply({ type: 'reply_received', text: read.text, reply_type: read.reply_type,
            ...(read.amount != null ? { amount: read.amount } : {}) }, {}, { analyze: !read.llm_fallback })}
          onReject={clearRead} />
      )}
      {!autoReadOff && <ReplyButtons send={sendReply} text={reply} />}
    </VStack>
  )

  return (
    <>
      {(sendFirst || askFirst) && <DraftList drafts={drafts} note={saved.note} />}
      {/* 이 단계에서 한 일을 기록하는 버튼. 탭 바로 위에 붙어 있다 */}
      {hasDock && (
        <Dock label="한 일 기록">
          <HStack gap={2} wrap="wrap">
            {action.type === 'follow_up' && <Button variant="primary" label="다시 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />}
            {action.type === 'counter' && <Button variant="primary" label="이 문자를 보냈어요" onClick={() => send({ type: 'counter_sent' })} />}
            {action.type === 'certified_mail' && <Button variant="primary" label="내용증명을 보냈어요" onClick={() => send({ type: 'escalation_sent' })} />}
            {action.type === 'go_1372' && c.stage !== 'handed_off' && <Button variant="primary" label="1372에 접수했어요" onClick={() => send({ type: 'handoff_done' })} />}
            {/* 합의 금액은 0원보다 커야 한다(서버가 0원 이하는 409로 거절) */}
            {c.stage === 'negotiating' && c.offered != null && c.offered > 0 && !action.warn && (
              <Button variant="primary" label={`${won(c.offered)}에 합의했어요`} onClick={() => send({ type: 'agreement_recorded', amount: c.offered })} />
            )}
          </HStack>
        </Dock>
      )}

      {c.stage === 'handed_off' && (
        <Card>
          <VStack gap={3}>
            <Heading level={3}>기록하기</Heading>
            <Text as="p">1372 상담으로 금액이 정해지면 적어 주세요. 입금될 때까지 챙겨 드려요</Text>
            <TextInput label="정해진 금액(원)" inputMode="numeric" value={settlement}
              onChange={(v) => setSettlement(v.replace(/\D/g, ''))} />
            <HStack><Button label="금액 저장" isDisabled={!Number.isSafeInteger(settlementAmount) || settlementAmount <= 0}
              onClick={async () => {
                if (await send({ type: 'agreement_recorded', amount: settlementAmount })) setSettlement('')
              }} /></HStack>
          </VStack>
        </Card>
      )}

      {/* 답장 기록: 보낼 문자가 없으면 이 화면의 일이라 펼쳐 둔다 */}
      {replyStage && !hasDock && (
        <Card>
          <VStack gap={3}>
            <Heading level={3}>답장 기록</Heading>
            {replyForm}
          </VStack>
        </Card>
      )}
      {/* 보낼 문자가 먼저인 화면에서도 답장이 먼저 오면 바로 적을 수 있다. 읽던 답장이 있으면 펼쳐 둔다 */}
      {replyStage && hasDock && (
        <Card>
          <Collapsible isOpen={openReply || Boolean(read) || Boolean(readNote) || reply.trim() !== ''} onOpenChange={setOpenReply}
            trigger={<VStack gap={1}><Text weight="semibold">업체가 먼저 답했나요?</Text>
              <Text type="supporting">답장을 받았으면 여기서 기록해요</Text></VStack>}>
            <div className="fold-body">{replyForm}</div>
          </Collapsible>
        </Card>
      )}

      {/* 지난 문자. 다시 보낼 때 쓴다 */}
      {!sendFirst && !askFirst && hasDrafts && (
        <Card>
          <Collapsible isOpen={openSent} onOpenChange={setOpenSent}
            trigger={<VStack gap={1}><Text weight="semibold">보낸 문자 다시 보기</Text>
              <Text type="supporting">복사해서 다시 보낼 수 있어요</Text></VStack>}>
            <div className="fold-body"><VStack gap={3}><DraftList drafts={drafts} note={saved.note} /></VStack></div>
          </Collapsible>
        </Card>
      )}
    </>
  )
}

import { BottomSheet, Button, Card, Collapsible, Dock, HStack, Heading, Text, TextArea, TextInput, VStack, Waiting } from '../ui'
import { InboxArrowDownIcon } from '@heroicons/react/24/outline'
import { useEffect, useRef, useState } from 'react'
import type { ReadReply } from '../api'
import { DraftList } from '../components/Draft'
import { FaultCases } from '../components/FaultCases'
import { Guide1372 } from '../components/Guide1372'
import { ReplyButtons } from '../components/ReplyButtons'
import { REPLY_LABEL, won } from '../format'
import type { Saved, Send } from '../useCase'
import { Mascot } from '../components/Mascot'

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
function ReadConfirm({ read, refund, saving, onConfirm, onReject }:
  { read: ReadReply & { text: string }; refund: number; saving: boolean; onConfirm: () => void; onReject: () => void }) {
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
            {!keywordOnly && <Button variant="primary" label={saving ? '기록하는 중…' : '맞아요, 기록할게요'} isLoading={saving} onClick={onConfirm} />}
            <Button label={keywordOnly ? '닫기' : '아니에요, 직접 고를게요'} isDisabled={saving} onClick={onReject} />
          </HStack>
          {/* 확정하면 답장을 한 번 더 분석해서 몇 초가 걸린다 */}
          {saving && <Waiting message="기록하고, 업체 말에 어떻게 답할지 정리하고 있어요" lines={3} art={<Mascot pose="write" small />} />}
        </VStack>
      </Card>
    </div>
  )
}

// stage가 waiting, negotiating, escalated일 때: 문안, 기록 버튼, 답장 입력. handed_off일 때: 1372 상담 뒤 합의 금액 기록
export function Respond({ saved, send, reply, setReply, settlement, setSettlement, autoReadOff, read, readNote, reading, readReply, clearRead }: Props) {
  const { case: c, action, drafts } = saved.step
  const [saving, setSaving] = useState(false)  // 답장을 기록하는 중(읽은 결과 확정, 선택지, 금액)
  // 답장을 기록하면 붙여넣은 칸과 읽은 결과를 비운다
  const sendReply: Send = async (event, patch, opts) => {
    // 시트는 화면 밖(Portal)에 그려져 fieldset의 잠금이 닿지 않는다. 저장하는 동안 직접 잠그고 기다리는 표시를 보인다
    setSaving(true)
    try {
      const ok = await send(event, patch, opts)
      if (ok) { setReply(''); clearRead(); setSheet(false) }
      return ok
    } finally { setSaving(false) }
  }
  const settlementAmount = Number(settlement)
  // 한 화면에 할 일 하나. 보내거나 말할 글이 있으면(재요청, 반박, 수락, 내용증명, 1372 접수) 그 글과 '했어요' 버튼이 이 화면의 일이고,
  // 답장 기록은 접어 둔다. 보낼 것이 없으면 답장 기록이 이 화면의 일이고, 지난 문자를 접어 둔다
  const sendFirst = ['follow_up', 'counter', 'certified_mail', 'confirm_agreement'].includes(action.type) || (action.type === 'go_1372' && c.stage !== 'handed_off')
  // 업체 잘못 사건에서 업체가 위약금을 뺀 금액(rules.py의 disputed_refund) 이상을 내면, 하한선보다 적어 경고가 떠도
  // 받고 끝낼지는 사용자가 정한다. 경고는 그대로 두고 받기 버튼만 함께 둔다. 서버는 하한선과 관계없이 합의를 받는다
  const disputed = c.refund.disputed_refund
  const takeDisputed = action.warn && c.contract.cancel_reason === 'business' && disputed != null && c.offered != null && c.offered >= disputed
  const canAgree = c.stage === 'negotiating' && c.offered != null && c.offered > 0 && (!action.warn || takeDisputed)
  const hasDock = sendFirst || canAgree
  const replyStage = ['waiting', 'negotiating', 'escalated'].includes(c.stage)
  // 답장 기록은 아래에서 올라오는 시트에서 한다. 읽는 중이거나 읽은 결과가 있으면 열어 둔다(시연 버튼으로 넣은 답장도 바로 보인다)
  const [sheet, setSheet] = useState(false)
  const sheetOpen = replyStage && (sheet || reading || Boolean(read) || Boolean(readNote))
  const closeSheet = () => { setSheet(false); clearRead() }
  const [openSent, setOpenSent] = useState(false)
  const hasDrafts = Object.keys(drafts).length > 0 || Boolean(saved.note)
  // 업체가 나중에 연락하겠다고 미뤘을 때의 문자는 아직 보낸 적이 없다. '보낸 문자 다시 보기'에 접지 않고 펼쳐 둔다
  const askFirst = 'ask_callback_time' in drafts

  // 붙여넣기 칸. 자동 읽기를 못 쓰면 버튼이 먼저고 이 칸은 접어 둔다(붙여넣은 글은 고른 답과 함께 기록된다)
  const [pasteOpen, setPasteOpen] = useState(false)
  const paste = (
    <VStack gap={3}>
      <TextArea label="받은 답장" description="받은 문자를 붙여넣거나 통화로 들은 말을 적어요"
        value={reply} onChange={setReply} maxLength={500} />
      <HStack><Button label={reading ? '읽는 중…' : '답장 읽기'} isLoading={reading} isDisabled={!reply.trim()}
        onClick={() => void readReply(reply)} /></HStack>
      {reading && <Waiting message="답장을 읽고 있어요. 몇 초 걸려요" lines={2} art={<Mascot pose="read" small />} />}
      {readNote && <Text type="supporting" role="status">{readNote}</Text>}
      {read && (
        <ReadConfirm read={read} refund={c.refund.refund} saving={saving}
          onConfirm={() => void sendReply({ type: 'reply_received', text: read.text, reply_type: read.reply_type,
            ...(read.amount != null ? { amount: read.amount } : {}) }, {}, { analyze: !read.llm_fallback })}
          onReject={clearRead} />
      )}
    </VStack>
  )
  const replyForm = autoReadOff ? (
    <VStack gap={4}>
      <ReplyButtons send={sendReply} text={reply} saving={saving} />
      <Collapsible isOpen={pasteOpen || Boolean(reply) || Boolean(read) || Boolean(readNote)} onOpenChange={setPasteOpen}
        trigger={<VStack gap={1}><Text weight="semibold">받은 문자 붙여넣기(선택)</Text>
          <Text type="supporting">무슨 답인지 모르겠으면 붙여넣어 보세요</Text></VStack>}>
        <div className="fold-body">{paste}</div>
      </Collapsible>
    </VStack>
  ) : (
    <VStack gap={4}>
      {paste}
      <ReplyButtons send={sendReply} text={reply} saving={saving} />
    </VStack>
  )

  return (
    <>
      {/* 1372로 넘어갈 때는 절차·전화 버튼·챙길 것을 말할 내용 위에 둔다 */}
      {action.type === 'go_1372' && c.stage !== 'handed_off' && <Guide1372 />}
      {(sendFirst || askFirst) && <DraftList drafts={drafts} note={saved.note} />}
      {/* 업체 사정 사건에서 업체가 반박할 만한 답을 했거나 1372로 넘어갈 때, 같은 유형의 조정례를 문안 아래에 접어 둔다 */}
      {c.contract.cancel_reason === 'business' && c.contract.fault_kind && c.stage !== 'handed_off'
        && (action.type === 'counter' || action.type === 'go_1372') && <FaultCases kind={c.contract.fault_kind} context="reply" />}
      {/* 이 단계에서 한 일을 기록하는 버튼. 탭 바로 위에 붙어 있다 */}
      {hasDock && (
        <Dock label="한 일 기록">
          <HStack gap={2} wrap="wrap">
            {action.type === 'follow_up' && <Button variant="primary" label="다시 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />}
            {action.type === 'counter' && <Button variant="primary" label="이 문자를 보냈어요" onClick={() => send({ type: 'counter_sent' })} />}
            {action.type === 'certified_mail' && <Button variant="primary" label="내용증명을 보냈어요" onClick={() => send({ type: 'escalation_sent' })} />}
            {action.type === 'go_1372' && c.stage !== 'handed_off' && <Button variant="primary" label="1372에 접수했어요" onClick={() => send({ type: 'handoff_done' })} />}
            {/* 합의 금액은 0원보다 커야 한다(서버가 0원 이하는 409로 거절) */}
            {/* 경고가 떠 있을 때는 반박·1372 접수가 주 버튼이고, 받기는 보조 버튼으로 둔다 */}
            {canAgree && c.offered != null && (
              <Button variant={takeDisputed ? 'secondary' : 'primary'}
                label={takeDisputed ? `${won(c.offered)}으로 받을게요` : `${won(c.offered)}에 합의했어요`}
                onClick={() => send({ type: 'agreement_recorded', amount: c.offered })} />
            )}
          </HStack>
        </Dock>
      )}

      {c.stage === 'handed_off' && (
        <Card>
          <VStack gap={3}>
            <Heading level={3}>정해진 금액 적기</Heading>
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

      {/* 답장 기록: 보낼 문자가 없으면 이 화면의 일이라 탭 바로 위 주 버튼으로 시트를 연다 */}
      {replyStage && !hasDock && (
        <Dock label="답장 기록">
          <HStack gap={2} wrap="wrap">
            <Button variant="primary" label="업체 답장 기록" icon={<InboxArrowDownIcon aria-hidden />} onClick={() => setSheet(true)} />
          </HStack>
        </Dock>
      )}
      {/* 보낼 문자가 먼저인 화면에서도 답장이 먼저 오면 바로 적을 수 있다 */}
      {replyStage && hasDock && (
        <Card>
          <HStack hAlign="between" vAlign="center" gap={3} wrap="wrap">
            <VStack gap={1}>
              <Text weight="semibold">업체가 먼저 답했나요?</Text>
              <Text type="supporting">답장을 받았으면 기록해요</Text>
            </VStack>
            <Button label="업체 답장 기록" icon={<InboxArrowDownIcon aria-hidden />} onClick={() => setSheet(true)} />
          </HStack>
        </Card>
      )}
      <BottomSheet open={sheetOpen} onOpenChange={(o) => (o ? setSheet(true) : closeSheet())} title="업체 답장 기록">
        {replyForm}
      </BottomSheet>

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

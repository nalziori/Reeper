import { ChatBubbleBottomCenterTextIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline'
import { Button, Card, HStack, Heading, SegmentedControl, SegmentedControlItem, Text, VStack, Waiting } from '../ui'
import { useContext, useRef, useState } from 'react'
import { api, type Tone } from '../api'
import { DRAFT, won } from '../format'
import { PolishContext } from './PolishContext'

type Choice = 'base' | Tone

// 업체에 보내는 글이 아니다. 통화 메모와 1372 상담 신청에 옮겨 적을 내용이라 말투를 다듬지 않고(서버 agent.NOT_SENT와 같다) 문자 앱으로 열지 않는다
const NOT_SENT = new Set(['call_card', 'go_1372'])

// 문안은 줄바꿈 그대로 보여 주되, [첫마디] 같은 구역 제목 줄은 굵게 해서 훑어볼 수 있게 한다. 복사는 원문 그대로다.
// 업체에 보낼 문자는 말풍선으로 보이고, 받을 돈은 밑줄로 짚는다(계산과 같은 숫자라는 표시)
function DraftText({ text, bubble, amount }: { text: string; bubble: boolean; amount?: string }) {
  const lines = text.split('\n')
  const mark = (line: string) => !amount ? line : line.split(amount).flatMap((part, j) =>
    j === 0 ? [part] : [<mark key={j}>{amount}</mark>, part])
  return (
    <div className="draft" data-bubble={bubble || undefined}>
      {lines.map((line, i) => {
        const end = i < lines.length - 1 ? '\n' : ''
        return /^\[[^\]]+\]$/.test(line.trim())
          ? <strong key={i} className="draft-section">{line}{end}</strong>
          : <span key={i}>{mark(line)}{end}</span>
      })}
    </div>
  )
}

// 말투를 바꿔도 금액·조문은 그대로다. 서버가 검사를 못 넘긴 문안은 원래 양식으로 돌려준다.
function useTone(kind: string, base: string) {
  const { c, enabled } = useContext(PolishContext)
  const [choice, setChoice] = useState<Choice>('base')
  const [cache, setCache] = useState<Partial<Record<Tone, string>>>({})
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState('')
  const asked = useRef(0)
  const select = async (next: Choice) => {
    setChoice(next)
    setNote('')
    if (next === 'base' || cache[next] !== undefined || !c) return
    const ticket = ++asked.current
    setLoading(true)
    try {
      const res = await api.polish(c, kind, next)
      if (ticket !== asked.current) return
      if (res.polished) setCache((prev) => ({ ...prev, [next]: res.text }))
      else { setChoice('base'); setNote('이번에는 말투를 못 바꿨어요. 기본 문자를 쓰세요') }
    } catch {
      if (ticket === asked.current) { setChoice('base'); setNote('말투를 못 바꿨어요. 기본 문자를 쓰세요') }
    } finally {
      if (ticket === asked.current) setLoading(false)
    }
  }
  const text = choice === 'base' ? base : cache[choice] ?? base
  return { canPolish: enabled && !!c && !NOT_SENT.has(kind), choice, select, text, loading, note }
}

export function Draft({ kind, text: base }: { kind: string; text: string }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState('')
  const tone = useTone(kind, base)
  const text = tone.text
  const { c } = useContext(PolishContext)
  const sendable = !NOT_SENT.has(kind)
  const amount = c ? won(c.agreed_amount ?? c.refund.refund) : undefined
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>{DRAFT[kind] ?? kind}</Heading>
        {tone.canPolish && (
          <SegmentedControl label="말투" size="sm" value={tone.choice} isDisabled={tone.loading}
            onChange={(v) => { setCopied(false); void tone.select(v as Choice) }}>
            <SegmentedControlItem value="base" label="기본" />
            <SegmentedControlItem value="polite" label="정중하게" />
            <SegmentedControlItem value="firm" label="단호하게" />
          </SegmentedControl>
        )}
        <DraftText text={text} bubble={sendable} amount={sendable ? amount : undefined} />
        {tone.choice !== 'base' && <Text type="supporting">말투만 바꿨어요. 금액과 근거는 그대로예요</Text>}
        {tone.loading && <Waiting message="말투를 바꾸고 있어요. 금액과 근거는 그대로 둬요" />}
        {tone.note && <Text type="supporting" role="status">{tone.note}</Text>}
        <HStack gap={2} wrap="wrap" hAlign={sendable ? 'end' : 'start'}>
          <Button label={copied ? '복사됨' : '복사'} icon={<DocumentDuplicateIcon aria-hidden />} onClick={async () => {
            try {
              await navigator.clipboard.writeText(text)
              setCopied(true)
              setCopyError('')
            } catch {
              setCopyError('복사하지 못했어요. 글을 길게 눌러 복사해 주세요')
            }
          }} />
          {sendable && <Button label="문자 앱으로 열기" icon={<ChatBubbleBottomCenterTextIcon aria-hidden />} href={`sms:?&body=${encodeURIComponent(text)}`} />}
        </HStack>
        {copyError && <Text as="p" role="alert">{copyError}</Text>}
      </VStack>
    </Card>
  )
}

// 통화 직후 문자(note)를 맨 앞에, 나머지 문안을 서버가 준 순서대로 보여 준다.
export function DraftList({ drafts, note }: { drafts: Record<string, string>; note?: string }) {
  return (
    <>
      {note && <Draft key={note} kind="after_call_sms" text={note} />}
      {Object.entries(drafts).filter(([k]) => k !== 'after_call_sms').map(([k, text]) => <Draft key={`${k}:${text}`} kind={k} text={text} />)}
    </>
  )
}

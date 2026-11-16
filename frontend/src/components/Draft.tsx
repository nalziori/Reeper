import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import { useState } from 'react'
import { DRAFT } from '../format'

// 문안은 줄바꿈 그대로 보여 주되, [첫마디] 같은 구역 제목 줄은 굵게 해서 훑어볼 수 있게 한다. 복사는 원문 그대로다.
function DraftText({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className="draft">
      {lines.map((line, i) => {
        const end = i < lines.length - 1 ? '\n' : ''
        return /^\[[^\]]+\]$/.test(line.trim())
          ? <strong key={i} className="draft-section">{line}{end}</strong>
          : <span key={i}>{line}{end}</span>
      })}
    </div>
  )
}

export function Draft({ kind, text }: { kind: string; text: string }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState('')
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>{DRAFT[kind] ?? kind}</Heading>
        <DraftText text={text} />
        <HStack gap={2} wrap="wrap">
          <Button label={copied ? '복사됨' : '복사'} onClick={async () => {
            try {
              await navigator.clipboard.writeText(text)
              setCopied(true)
              setCopyError('')
            } catch {
              setCopyError('복사하지 못했습니다. 문안을 직접 선택해 복사해 주세요.')
            }
          }} />
          {kind !== 'call_card' && <Button label="문자 앱으로 열기" href={`sms:?&body=${encodeURIComponent(text)}`} />}
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
      {note && <Draft kind="after_call_sms" text={note} />}
      {Object.entries(drafts).filter(([k]) => k !== 'after_call_sms').map(([k, text]) => <Draft key={k} kind={k} text={text} />)}
    </>
  )
}

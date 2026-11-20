import { BottomSheet, Button, Card, Dock, HStack, Heading, SegmentedControl, SegmentedControlItem, Text, VStack } from '../ui'
import { useState } from 'react'
import type { Step } from '../api'
import { Draft, DraftList } from '../components/Draft'
import type { Saved, Send } from '../useCase'

type Channel = 'sms' | 'call'

// stage가 ready일 때: 보낼 문안과 첫 통지 기록.
// 문자 문안과 통화 카드를 한꺼번에 펼치면 화면이 세 배로 길어진다. 고른 방법의 문안과 기록 버튼만 보인다.
// 기본은 문자다. 전화를 어려워하는 사용자가 대상이다.
export function Prepare({ saved, send }: { saved: Saved; send: Send }) {
  const { action, drafts }: Step = saved.step
  const [channel, setChannel] = useState<Channel>('sms')
  const [sheet, setSheet] = useState<'answers' | 'outcome' | null>(null)
  const callMode = action.type === 'send_notice' && channel === 'call'
  const shown = Object.fromEntries(Object.entries(drafts).filter(([k]) => k !== 'call_card'))
  return (
    <>
      {/* 알리는 방법과 그 방법의 문안은 한 장에 둔다(고르고 바로 본다) */}
      <VStack gap={3} className={callMode ? 'call-preparation' : undefined}>
        {action.type === 'send_notice' && channel === 'sms' && (
          <Card><Heading level={2}>{action.reason}</Heading></Card>
        )}
        {action.type === 'send_notice' && (
          <Card>
            <VStack gap={3}>
              <Heading level={3}>어떻게 알릴까요?</Heading>
              <SegmentedControl label="알리는 방법" layout="fill" value={channel} onChange={(v) => setChannel(v as Channel)}>
                <SegmentedControlItem value="sms" label="문자로" />
                <SegmentedControlItem value="call" label="전화로" />
              </SegmentedControl>
              <Text type="supporting">
                {channel === 'sms' ? '복사하거나 문자 앱으로 열어 보내요' : '스피커폰을 켜고 아래 대본을 순서대로 읽어요'}
              </Text>
            </VStack>
          </Card>
        )}
        {callMode && drafts.call_card
          ? <Draft kind="call_card" text={drafts.call_card}
              callAnswers={{ open: sheet === 'answers', onOpenChange: (open) => setSheet(open ? 'answers' : null) }} />
          : <DraftList drafts={action.type === 'send_notice' ? shown : drafts} note={saved.note} />}
      </VStack>
      {/* 보냈거나 말했으면 바로 누를 수 있게 탭 바로 위에 붙여 둔다(문안 카드를 넘기지 않아도 된다) */}
      {action.type === 'send_notice' && (
        <Dock label="기록하기">
          <HStack gap={2} wrap="wrap">
            {channel === 'sms' ? (
              <Button variant="primary" label="문자로 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />
            ) : (<>
              <Button variant="primary" label="통화 결과 기록" onClick={() => setSheet('outcome')} />
              {drafts.call_card && <Button label="상황별 대답 보기" onClick={() => setSheet('answers')} />}
            </>)}
          </HStack>
        </Dock>
      )}
      <BottomSheet title="통화 결과 기록" open={sheet === 'outcome'}
        onOpenChange={(open) => setSheet(open ? 'outcome' : null)}>
        <VStack gap={2}>
          <Button variant="primary" label="해지 의사를 전했어요" onClick={() => {
            setSheet(null)
            void send({ type: 'notice_sent', channel: 'call' }, { note: drafts.after_call_sms })
          }} />
          <Button label="연결이 안 됐어요" onClick={async () => {
            setSheet(null)
            if (await send({ type: 'call_attempted' })) setChannel('sms')
          }} />
        </VStack>
      </BottomSheet>
    </>
  )
}

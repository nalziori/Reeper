import { Button, Card, Dock, HStack, Heading, SegmentedControl, SegmentedControlItem, Text, VStack } from '../ui'
import { useState } from 'react'
import type { Step } from '../api'
import { DraftList } from '../components/Draft'
import type { Saved, Send } from '../useCase'

type Channel = 'sms' | 'call'

// stage가 ready일 때: 보낼 문안과 첫 통지 기록.
// 문자 문안과 통화 카드를 한꺼번에 펼치면 화면이 세 배로 길어진다. 고른 방법의 문안과 기록 버튼만 보인다.
// 기본은 문자다. 전화를 어려워하는 사용자가 대상이다.
export function Prepare({ saved, send }: { saved: Saved; send: Send }) {
  const { action, drafts }: Step = saved.step
  const [channel, setChannel] = useState<Channel>('sms')
  const shown = Object.fromEntries(Object.entries(drafts).filter(([k]) => channel === 'call' ? k === 'call_card' : k !== 'call_card'))
  return (
    <>
      {/* 알리는 방법과 그 방법의 문안은 한 장에 둔다(고르고 바로 본다) */}
      <VStack gap={3}>
        {action.type === 'send_notice' && (
          <Card>
            <VStack gap={3}>
              <Heading level={3}>어떻게 알릴까요?</Heading>
              <SegmentedControl label="알리는 방법" layout="fill" value={channel} onChange={(v) => setChannel(v as Channel)}>
                <SegmentedControlItem value="sms" label="문자로" />
                <SegmentedControlItem value="call" label="전화로" />
              </SegmentedControl>
              <Text type="supporting">
                {channel === 'sms' ? '복사하거나 문자 앱으로 열어 보내요' : '대본을 보며 말해요. 끊은 뒤 보낼 문자도 만들어 드려요'}
              </Text>
            </VStack>
          </Card>
        )}
        <DraftList drafts={action.type === 'send_notice' ? shown : drafts} note={saved.note} />
      </VStack>
      {/* 보냈거나 말했으면 바로 누를 수 있게 탭 바로 위에 붙여 둔다(문안 카드를 넘기지 않아도 된다) */}
      {action.type === 'send_notice' && (
        <Dock label="기록하기">
          <HStack gap={2} wrap="wrap">
            {channel === 'sms' ? (
              <Button variant="primary" label="문자로 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />
            ) : (<>
              <Button variant="primary" label="전화로 말했어요" onClick={() => send({ type: 'notice_sent', channel: 'call' }, { note: drafts.after_call_sms })} />
              <Button label="전화 연결이 안 됐어요" onClick={() => send({ type: 'call_attempted' })} />
            </>)}
          </HStack>
        </Dock>
      )}
    </>
  )
}

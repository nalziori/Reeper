import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
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
      {action.type === 'send_notice' && (
        <Card>
          <VStack gap={3}>
            <Heading level={3}>어떻게 알릴까요?</Heading>
            <SegmentedControl label="알리는 방법" layout="fill" value={channel} onChange={(v) => setChannel(v as Channel)}>
              <SegmentedControlItem value="sms" label="문자로" />
              <SegmentedControlItem value="call" label="전화로" />
            </SegmentedControl>
            <Text type="supporting">
              {channel === 'sms' ? '아래 문안을 복사하거나 문자 앱으로 열어 보내세요' : '아래 카드를 보며 말하세요. 끊은 뒤 보낼 확인 문자도 만들어 드려요'}
            </Text>
          </VStack>
        </Card>
      )}
      <DraftList drafts={action.type === 'send_notice' ? shown : drafts} note={saved.note} />
      <Card>
        <VStack gap={3}>
          <Heading level={3}>기록하기</Heading>
          {action.type === 'send_notice' && (
            <HStack gap={2} wrap="wrap">
              {channel === 'sms' ? (
                <Button variant="primary" label="문자로 보냈어요" onClick={() => send({ type: 'notice_sent', channel: 'sms' })} />
              ) : (<>
                <Button variant="primary" label="전화로 말했어요" onClick={() => send({ type: 'notice_sent', channel: 'call' }, { note: drafts.after_call_sms })} />
                <Button label="전화 연결이 안 됐어요" onClick={() => send({ type: 'call_attempted' })} />
              </>)}
            </HStack>
          )}
        </VStack>
      </Card>
    </>
  )
}

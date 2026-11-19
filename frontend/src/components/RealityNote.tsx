import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'

export function RealityNote({ demo }: { demo: boolean }) {
  return (
    <Card variant="muted">
      <VStack gap={2}>
        <Heading level={3}>{demo ? 'Reeper가 하는 일과 시연용' : 'Reeper가 하는 일'}</Heading>
        <Text as="p"><b>하는 일</b> · 환불액 계산, 보낼 문자와 통화 대본, 기한 알림, 기록 저장</Text>
        {demo && <Text as="p"><b>시연용</b> · 사장 답 버튼, 날짜 넘기기</Text>}
        <Text as="p"><b>안 하는 일</b> · 문자 보내기, 전화 걸기. 보내고 말하는 건 직접 해요</Text>
        <Text type="supporting">계산 일부(통보한 날 포함 여부, 끝전, 개월 수)는 아직 확인 중이에요. 기록은 이 브라우저에만 저장하고 서버에는 남기지 않아요</Text>
      </VStack>
    </Card>
  )
}

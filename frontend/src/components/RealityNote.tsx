import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'

export function RealityNote({ demo }: { demo: boolean }) {
  return (
    <Card variant="muted">
      <VStack gap={2}>
        <Heading level={3}>{demo ? '이 화면에서 실제로 되는 것과 시연용인 것' : '이 화면이 하는 일과 하지 않는 일'}</Heading>
        <Text as="p"><b>실제로 되는 것</b> · 환불액 계산(계산식은 임시, 원문 확인 전), 보낼 문안과 통화 준비 카드 만들기, 기한 추적, 사건 파일 내보내기</Text>
        {demo && <Text as="p"><b>시연용</b> · 사장 답 버튼, 날짜 건너뛰기</Text>}
        <Text as="p"><b>하지 않는 일</b> · 문자 발송, 전화, 통화 듣기. 보내고 말하는 건 사용자가 해요.</Text>
        <Text type="supporting">데이터는 이 브라우저에만 저장돼요.</Text>
      </VStack>
    </Card>
  )
}

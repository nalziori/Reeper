import { PhoneIcon } from '@heroicons/react/24/outline'
import { useState } from 'react'
import { Button, Card, Checkbox, HStack, Heading, Text, VStack } from '../ui'

// 1372로 넘어갈 때의 안내: 절차, 전화 버튼, 챙길 것. 전화는 사용자가 건다(에이전트는 전화하지 않는다).
// 절차는 앱 안에서 확인되는 일(1372 번호·누리집, 상담 뒤 금액 기록)과 B가 소비자24·한국소비자원 안내에서 확인한 것(피해구제는 상담을 거쳐 신청, 첨부 3개)만 적는다. 1372·한국소비자원의 처리 절차나
// 기한은 근거 표 밖이라 적지 않는다. 문구는 B 초안과 C 확인을 받아 바꾼다.
// 체크 표시는 이 화면에서만 쓰고 저장하지 않는다(사건이나 계약 내용을 남기지 않는다).
const CHECKLIST = [
  '계약서(사진도 괜찮아요)',
  '결제 내역(카드 영수증, 이체 내역)',
  '업체와 주고받은 문자, 통화한 날짜',
  '업체 공지나 안내문 사진(업체 사정이 바뀌었다면)',
] as const

// tracked: 사건이 열려 있어 상담 뒤 금액을 기록할 수 있는 화면인지. 접수 화면(폐업 등 사건을 열지 않는 경우)은 거짓이다
export function Guide1372({ scriptLabel = '1372에 말할 내용', tracked = true }: { scriptLabel?: string; tracked?: boolean }) {
  const [done, setDone] = useState<Record<string, boolean>>({})
  return (
    <Card>
      <VStack gap={4}>
        <Heading level={2}>1372에 상담하기</Heading>
        <ol className="guide-steps">
          <li>국번 없이 1372로 전화하거나 www.1372.go.kr에서 상담을 신청해요</li>
          <li>아래 '{scriptLabel}'을 보며 상담원에게 말해요. 상담에서 피해구제를 안내받으면 아래 자료를 붙여 신청해요</li>
          {tracked && <li>상담으로 금액이 정해지면 Reeper에 적어 두세요. 입금될 때까지 챙겨 드려요</li>}
        </ol>
        {/* 오른손 엄지가 닿는 오른쪽에 둔다 */}
        <HStack hAlign="end">
          <Button label="1372에 전화하기" href="tel:1372" icon={<PhoneIcon aria-hidden />} />
        </HStack>
        <VStack gap={1}>
          <Text weight="semibold">챙길 것</Text>
          {CHECKLIST.map((item) => (
            <Checkbox key={item} label={item} checked={Boolean(done[item])} onChange={(v) => setDone({ ...done, [item]: v })} />
          ))}
          {/* 소비자24 신청 양식 안내(B 확인): 첨부는 3개, 합계 30MB까지이고 넘으면 압축 파일로 올리라고 한다 */}
          <Text type="supporting">첨부는 3개까지라, 여러 장이면 압축 파일 하나로 묶어 올려요</Text>
        </VStack>
      </VStack>
    </Card>
  )
}

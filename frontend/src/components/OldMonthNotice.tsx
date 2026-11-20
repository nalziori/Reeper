import { useEffect, useState } from 'react'
import { api, type Case } from '../api'
import { won } from '../format'
import { Button, Card, HStack, Heading, Text, VStack } from '../ui'

// 옛 규칙(개월로 셈)으로 열고 아직 통지하지 않은 월 단위 사건. 사건과 기록은 그대로 두고,
// 새 규칙(날짜로 일할)의 예상 환불액을 보여 준 뒤 희망 금액·하한선을 사용자가 정하게 한다(#137).
// 확인하기 전에는 서버가 첫 통지를 받지 않는다(engine.validate_transition).
export function OldMonthNotice({ c, today, busy, onChoose }: {
  c: Case; today: string; busy: boolean; onChoose: (useNew: boolean) => void
}) {
  const [next, setNext] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    api.preview(c.contract, today).then(
      (r) => { if (active) setNext(r.refund) },
      () => { if (active) setFailed(true) },
    )
    return () => { active = false }
  }, [c.contract, today])
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={2} className="text-[16px] font-semibold">환불 계산 방식이 바뀌었어요</Heading>
        <Text>
          월 단위 계약도 이제 개월이 아니라 날짜로 나눠 계산해요. 업체에 알리기 전에 금액을 다시 확인해 주세요.
          지금까지의 기록은 그대로 남아요.
        </Text>
        <Text type="supporting">
          예전 예상 환불액 {won(c.refund.refund)} → 새 예상 환불액 {next === null ? (failed ? '불러오지 못했어요' : '계산 중') : won(next)}
        </Text>
        <Text type="supporting">지금 기준: 희망 금액 {won(c.target)} · 하한선 {won(c.floor)}</Text>
        <HStack gap={2} wrap="wrap">
          <Button variant="primary" label="새 예상 환불액으로 맞추기" isDisabled={busy || next === null}
            onClick={() => onChoose(true)} />
          <Button label="지금 기준 유지" isDisabled={busy || next === null} onClick={() => onChoose(false)} />
        </HStack>
      </VStack>
    </Card>
  )
}

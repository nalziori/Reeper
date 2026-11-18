import { Card } from '@astryxdesign/core/Card'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import type { ReactNode } from 'react'

// 지금 할 일이 아닌 카드(전략, 내보내기 등)는 제목과 한 줄 설명만 보이고 눌러야 펼쳐진다.
// 제목은 버튼 안에 들어가므로 Heading이 아니라 굵은 글자로 둔다(버튼 안에 제목 요소를 넣지 않는다).
export function Fold({ title, summary, defaultOpen = false, children }: {
  title: string; summary?: string; defaultOpen?: boolean; children: ReactNode
}) {
  return (
    <Card>
      <Collapsible defaultIsOpen={defaultOpen} trigger={
        <VStack gap={1}>
          <Text weight="semibold">{title}</Text>
          {summary && <Text type="supporting">{summary}</Text>}
        </VStack>
      }>
        <div className="fold-body">{children}</div>
      </Collapsible>
    </Card>
  )
}

import { Button, Heading, Text, VStack } from '../ui'
import { Component, type ReactNode } from 'react'
import { PAGE_WIDTH, STORAGE_KEY } from '../format'

// 화면을 그리다 예외가 나도 흰 화면으로 두지 않는다. 저장된 사건이 원인일 수 있어 지우고 다시 시작할 수 있게 한다.
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  restart = () => {
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* 저장소를 쓸 수 없으면 새로고침만 한다 */ }
    window.location.reload()
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <VStack gap={3} padding={4} maxWidth={PAGE_WIDTH} role="alert" className="page">
        <Heading level={2}>화면을 불러오지 못했어요</Heading>
        <Text as="p">이 브라우저에 저장된 사건이 올바르지 않을 수 있어요. 저장된 사건을 지우고 처음부터 다시 시작할 수 있어요.</Text>
        <Button variant="primary" label="저장된 사건 지우고 다시 시작" onClick={this.restart} />
      </VStack>
    )
  }
}

// 단계의 주 버튼 줄. 진행 탭에서는 탭 바로 위에 고정된 자리로 옮겨 그린다. 그 자리가 없으면(계약 입력 화면) 제자리에 둔다
import { createContext, useContext, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

const DockTarget = createContext<HTMLElement | null>(null)
export const DockProvider = DockTarget.Provider

export function Dock({ label, children }: { label: string; children: ReactNode }) {
  const target = useContext(DockTarget)
  const bar = <div className="action-dock" role="group" aria-label={label}>{children}</div>
  return target ? createPortal(bar, target) : bar
}

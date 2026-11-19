// 아래에서 올라오는 선택 창(바텀 시트). Base UI Dialog라 열리면 초점이 안으로 들어가고, Esc·바깥 누르기로 닫힌다
import { Dialog } from '@base-ui/react/dialog'
import { XMarkIcon } from '@heroicons/react/24/outline'
import type { ReactNode } from 'react'

export function BottomSheet({ open, onOpenChange, title, children }: {
  open: boolean; onOpenChange: (open: boolean) => void; title: string; children: ReactNode
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => onOpenChange(o)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="sheet-backdrop" />
        <Dialog.Popup className="sheet">
          <div className="sheet-grip" aria-hidden />
          <div className="sheet-head">
            <Dialog.Title className="m-0 text-[19px] leading-snug font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="sheet-close" aria-label="닫기"><XMarkIcon aria-hidden /></Dialog.Close>
          </div>
          <div className="sheet-body">{children}</div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

// 시트 안의 한 줄 선택지. 줄 전체가 버튼이고 손가락으로 누르기 좋은 높이(56px)다
export function ChoiceRow({ icon, label, onClick, disabled }: {
  icon: ReactNode; label: string; onClick: () => void; disabled?: boolean
}) {
  return (
    <button type="button" className="choice-row" onClick={onClick} disabled={disabled}>
      <span className="choice-icon" aria-hidden>{icon}</span>
      <span className="min-w-0 flex-1 text-left">{label}</span>
    </button>
  )
}

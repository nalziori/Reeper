import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { won } from '../format'

// 업체 제시액이 거절 기준보다 적을 때: 두 금액을 막대로 나란히 둔다. 얼마나 모자란지가 한눈에 보인다
export function OfferCompare({ offered, floor }: { offered: number; floor: number }) {
  const max = Math.max(offered, floor, 1)
  const bar = (label: string, amount: number, color: string) => (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-[14px]">
        <span className="text-muted-foreground">{label}</span>
        <b className="font-semibold">{won(amount)}</b>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${(amount / max) * 100}%` }} />
      </div>
    </div>
  )
  return (
    <div role="status" className="flex flex-col gap-3 rounded-2xl bg-card p-5">
      <p className="m-0 flex items-start gap-2 text-[15px] font-semibold text-warn break-keep">
        <ExclamationTriangleIcon className="mt-0.5 size-[18px] shrink-0" aria-hidden />
        업체가 말한 {won(offered)}은 거절 기준 {won(floor)}보다 적어요
      </p>
      {bar('업체가 말한 돈', offered, 'bg-offer')}
      {bar('내 거절 기준', floor, 'bg-success')}
      <p className="m-0 text-[13px] text-muted-foreground break-keep">{won(floor - offered)} 모자라요. 받아들이기 전에 항목별 근거를 물어보세요</p>
    </div>
  )
}

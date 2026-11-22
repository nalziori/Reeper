import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { won } from '../format'

// 업체 제시액이 하한선보다 적을 때: 두 금액을 막대로 나란히 둔다. 얼마나 모자란지가 한눈에 보인다
// 하한선을 따로 정하지 않았으면 예상 환불액이 기준이다. 정한 적 없는 '하한선'으로 부르지 않는다
// takeable: 업체 잘못 사건에서 업체가 다툴 때의 환불액(위약금을 뺀 금액) 이상을 냈을 때 그 금액. 화면에 받기 버튼이 함께 있으므로
// 근거만 물어보라고 하지 않고, 받으면 위약금 없이 요청할 여지를 내려놓는다는 점을 알린다
export function OfferCompare({ offered, floor, refund, takeable }: { offered: number; floor: number; refund: number; takeable?: number }) {
  const floorName = floor === refund ? '예상 환불액' : '하한선'
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
        업체 제시액 {won(offered)}은 {floorName} {won(floor)}보다 적어요
      </p>
      {bar('업체 제시액', offered, 'bg-offer')}
      {bar(floorName, floor, 'bg-success')}
      <p className="m-0 text-[13px] text-muted-foreground break-keep">
        {takeable !== undefined
          ? `${won(floor - offered)} 모자라요. 위약금을 뺀 금액(${won(takeable)}) 이상이라 받고 끝낼 수도 있어요. 받으면 위약금 없이 요청할 여지는 내려놓게 돼요`
          : `${won(floor - offered)} 모자라요. 받아들이기 전에 항목별 근거를 물어보세요`}
      </p>
    </div>
  )
}

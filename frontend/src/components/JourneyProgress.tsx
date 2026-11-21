import { CheckIcon } from '@heroicons/react/24/outline'
import { JOURNEY } from '../format'

// 위 막대의 진행 단계. 지난 단계는 체크, 지금 단계는 주황 테두리, 남은 단계는 회색 점. 점 사이를 선으로 잇는다(배송 단계 표시처럼)
// onPick을 주면 지난 단계를 눌러 그 단계 내용을 다시 볼 수 있다. 단계를 되돌리지는 않는다(단계는 엔진만 바꾼다)
export function JourneyProgress({ current, onPick }: { current: number; onPick?: (step: number) => void }) {
  return (
    <ol className="journey-steps" aria-label="환불 진행 단계">
      {JOURNEY.map((label, index) => {
        const step = index + 1
        const state = step === current ? 'current' : step < current ? 'done' : 'next'
        return (
          <li key={label} data-state={state} aria-current={step === current ? 'step' : undefined}>
            {state === 'done' && onPick ? (
              <button type="button" className="journey-btn" aria-label={`${label} 다시 보기`} onClick={() => onPick(step)}>
                <span className="journey-dot" aria-hidden><CheckIcon /></span>
                <span className="journey-label">{label}</span>
              </button>
            ) : (<>
              <span className="journey-dot" aria-hidden>{state === 'done' ? <CheckIcon /> : step}</span>
              <span className="journey-label">{label}</span>
            </>)}
          </li>
        )
      })}
    </ol>
  )
}

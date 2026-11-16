import { JOURNEY } from '../format'

export function JourneyProgress({ current }: { current: number }) {
  return (
    <ol className="journey-steps" aria-label="환불 진행 단계">
      {JOURNEY.map((label, index) => {
        const step = index + 1
        return <li key={label} data-state={step === current ? 'current' : step < current ? 'done' : 'next'}
          aria-current={step === current ? 'step' : undefined}>{label}</li>
      })}
    </ol>
  )
}

import done from '../assets/mascot/done.webp'
import wait from '../assets/mascot/wait.webp'

// Reeper 마스코트(딱따구리). 할 말을 딱 정리해 준다는 뜻이다. 기다릴 때와 다 끝났을 때만 쓴다.
// 금액·근거·문자처럼 정확해야 하는 화면과 업체 잘못·1372 화면에는 두지 않는다. 꾸밈 그림이라 화면 읽기 프로그램은 건너뛴다.
// 그림은 디자인 시트에서 잘라 배경을 지운 것이다. 원본 개별 파일을 받으면 같은 이름으로 바꾼다.
const POSE = { wait, done } as const

export function Mascot({ pose }: { pose: keyof typeof POSE }) {
  return (
    <div className="mascot" aria-hidden>
      <img src={POSE[pose]} alt="" width={pose === 'wait' ? 80 : 105} height={120} />
    </div>
  )
}

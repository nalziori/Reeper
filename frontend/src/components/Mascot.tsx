import done from '../assets/mascot/done.webp'
import read from '../assets/mascot/read.webp'
import think from '../assets/mascot/think.webp'
import wait from '../assets/mascot/wait.webp'
import write from '../assets/mascot/write.webp'

// Reeper 마스코트(딱따구리). 할 말을 딱 정리해 준다는 뜻이다. 기다릴 때, 다 끝났을 때, AI 답이 길어질 때만 쓴다.
// 금액·근거·문자처럼 정확해야 하는 화면과 업체 잘못·1372 화면에는 두지 않는다. 꾸밈 그림이라 화면 읽기 프로그램은 건너뛴다.
// 그림은 디자인 시트에서 잘라 배경을 지운 것이다. 레티나에서 깨지지 않게 표시 크기의 2배 이상인 것만 쓴다
// (wait: 시트의 큰 손 흔드는 포즈 360px를 120px로, done: 약 200px를 100px로, 작은 그림 200px 안팎을 56px로).
// 원본 개별 파일을 받으면 같은 이름으로 바꾼다.
// read: 돋보기(사진·답장 읽기), think: 전구(조언), write: 노트북(말투·답장 정리)
const POSE = { wait, done, read, think, write } as const

export function Mascot({ pose, small = false }: { pose: keyof typeof POSE; small?: boolean }) {
  return (
    <div className={small ? 'mascot-sm' : 'mascot'} aria-hidden>
      <img src={POSE[pose]} alt="" className={pose === 'done' ? 'mascot-done' : undefined} />
    </div>
  )
}

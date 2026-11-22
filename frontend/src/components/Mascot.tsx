import done from '../assets/mascot/done.webp'
import read from '../assets/mascot/read.webp'
import think from '../assets/mascot/think.webp'
import wait from '../assets/mascot/wait.webp'
import write from '../assets/mascot/write.webp'
import angry from '../assets/mascot/angry.webp'
import helloGif from '../assets/mascot/hello.gif'
import waitGif from '../assets/mascot/wait.gif'
import readGif from '../assets/mascot/read.gif'
import writeGif from '../assets/mascot/write_background_removed.gif'
import angryGif from '../assets/mascot/angry.gif'
import doneGif from '../assets/mascot/done_celebration_transparent.gif'

// Reeper 마스코트(딱따구리). 꾸밈 그림이라 화면 읽기 프로그램은 건너뛴다.
// 두는 곳: 대문 인사(hello), 기다릴 때(wait), 다 끝났을 때(done), AI 답이 길어질 때(read·write·think),
// 업체가 실제로 거절한 뒤 '다음에 보낼 문자' 제목 옆(angry, 한 번만 재생).
// 두지 않는 곳: 금액·근거 카드와 문자 본문 안, 1372 안내. 문자 카드에는 제목 옆 angry만 허용한다(#170 B 리뷰로 규칙을 바꿈).
// 움직임 줄이기를 켜면 같은 포즈의 정지 그림을 보여 준다(angry.webp는 angry.gif의 마지막 프레임).
// 파일 이름은 영문으로 둔다. 공백·한글이 있으면 빌드 결과 주소를 따로 고쳐야 한다
const POSE = {
  hello: { still: wait, gif: helloGif },
  wait: { still: wait, gif: waitGif },
  read: { still: read, gif: readGif },
  write: { still: write, gif: writeGif },
  angry: { still: angry, gif: angryGif },
  done: { still: done, gif: doneGif },
  think: { still: think },
}

export function Mascot({ pose, small = false }: { pose: keyof typeof POSE; small?: boolean }) {
  const art = POSE[pose]
  return (
    <div className={small ? 'mascot-sm shrink-0' : 'mascot'} aria-hidden>
      <picture>
        {'gif' in art && <source media="(prefers-reduced-motion: no-preference)" srcSet={art.gif} />}
        <img src={art.still} alt="" className={pose === 'done' ? 'mascot-done' : undefined} />
      </picture>
    </div>
  )
}

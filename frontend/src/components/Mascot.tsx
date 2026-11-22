import done from '../assets/mascot/done.webp'
import read from '../assets/mascot/read.webp'
import think from '../assets/mascot/think.webp'
import wait from '../assets/mascot/wait.webp'
import write from '../assets/mascot/write.webp'
import helloGif from '../assets/mascot/귀여운 펭귄 마스코트 인사 웨이브이션.gif'
import waitGif from '../assets/mascot/기다리는 펭귄 시계 애니메이션.gif'
import readGif from '../assets/mascot/돋보기로 꼼꼼히 살피는 새 탐정.gif'
import writeGif from '../assets/mascot/write_background_removed.gif'
import angryGif from '../assets/mascot/화난 펭귄의 감정 변화 애니메이션.gif'
import doneGif from '../assets/mascot/done_celebration_transparent.gif'

// 움직임 줄이기를 켜면 기존 정지 그림을 보여 준다.
const POSE = {
  hello: { still: wait, gif: helloGif },
  wait: { still: wait, gif: waitGif },
  read: { still: read, gif: readGif },
  write: { still: write, gif: writeGif },
  angry: { still: think, gif: angryGif },
  done: { still: done, gif: doneGif },
  think: { still: think },
}

export function Mascot({ pose, small = false }: { pose: keyof typeof POSE; small?: boolean }) {
  const art = POSE[pose]
  return (
    <div className={small ? 'mascot-sm shrink-0' : 'mascot'} aria-hidden>
      <picture>
        {'gif' in art && <source media="(prefers-reduced-motion: no-preference)" srcSet={art.gif.replaceAll(' ', '%20')} />}
        <img src={art.still} alt="" className={pose === 'done' ? 'mascot-done' : undefined} />
      </picture>
    </div>
  )
}

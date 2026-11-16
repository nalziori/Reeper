import { createContext } from 'react'
import type { Case } from '../api'

// 문안 카드가 말투를 다듬을 때 쓰는 사건과 사용 가능 여부. 자동 읽기를 쓸 수 없으면 말투 선택을 숨긴다.
export const PolishContext = createContext<{ c: Case | null; enabled: boolean }>({ c: null, enabled: false })

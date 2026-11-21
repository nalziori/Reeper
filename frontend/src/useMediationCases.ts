import { useEffect, useState } from 'react'
import { api, type MediationCases } from './api'

// 조정례 데이터(data/mediation_cases.json). 유형 선택지와 사례 카드가 같이 쓴다. 못 불러오면 null로 남는다
export function useMediationCases() {
  const [data, setData] = useState<MediationCases | null>(null)
  useEffect(() => {
    let active = true
    api.mediationCases().then((d) => { if (active) setData(d) }, () => { /* 참고 자료라 못 불러오면 숨긴다 */ })
    return () => { active = false }
  }, [])
  return data
}

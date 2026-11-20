import type { Contract } from './api'

// 계산에 필요한 값이 다 있는지. 회 단위만 총 횟수와 이미 쓴 횟수가 필요하다(rules.calculate).
// 월 단위는 일 단위처럼 시작일과 종료일로 일할하므로 총 개월 수가 필요 없다(#137).
// 문제가 없으면 빈 문자열이다.
export function extrasProblem(c: Contract): string {
  const unit = c.unit ?? 'day'
  if (unit !== 'count') return ''
  if (!c.total_count) return '총 횟수를 적어 주세요.'
  if (c.used_count == null) return '이미 쓴 횟수를 적어 주세요. 안 썼으면 0입니다.'
  if (c.used_count > c.total_count) return '이미 쓴 횟수는 총 횟수보다 많을 수 없습니다.'
  return ''
}

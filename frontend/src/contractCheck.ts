import type { Contract } from './api'

// 횟수제 계약을 계산하려면 총 횟수와 이미 쓴 횟수가 필요하다.
// 문제가 없으면 빈 문자열이다.
export function extrasProblem(c: Contract): string {
  if (c.unit !== 'count') return ''
  if (!c.total_count) return '총 횟수를 적어 주세요.'
  if (c.used_count == null) return '이미 쓴 횟수를 적어 주세요. 안 썼으면 0입니다.'
  if (c.used_count > c.total_count) return '이미 쓴 횟수는 총 횟수보다 많을 수 없습니다.'
  return ''
}

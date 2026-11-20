import type { Contract } from './api'

export function withSuggestedMonthCount(c: Contract): Contract {
  if (c.unit !== 'month' || c.total_count !== undefined) return c

  const start = new Date(c.start_date + 'T00:00:00Z')
  const end = new Date(c.end_date + 'T00:00:00Z')
  if (!Number.isFinite(+start) || !Number.isFinite(+end) || end <= start
    || start.toISOString().slice(0, 10) !== c.start_date
    || end.toISOString().slice(0, 10) !== c.end_date) return c

  const inclusiveEnd = new Date(+end)
  inclusiveEnd.setUTCDate(inclusiveEnd.getUTCDate() + 1)
  // 계약서는 다음 월 기산일 또는 그 전날을 종료일로 적을 수 있다.
  for (const boundary of [inclusiveEnd, end]) {
    const months = (boundary.getUTCFullYear() - start.getUTCFullYear()) * 12
      + boundary.getUTCMonth() - start.getUTCMonth()
    const lastDay = new Date(+boundary)
    lastDay.setUTCMonth(lastDay.getUTCMonth() + 1, 0)
    if (months > 0 && boundary.getUTCDate() === Math.min(start.getUTCDate(), lastDay.getUTCDate())) {
      return { ...c, total_count: months }
    }
  }
  return c
}

// 계산에 필요한 값이 다 있는지. 월 단위는 총 개월 수, 회 단위는 총 횟수와 이미 쓴 횟수가 필요하다(rules.calculate).
// 문제가 없으면 빈 문자열이다.
export function extrasProblem(c: Contract): string {
  const unit = c.unit ?? 'day'
  if (unit === 'day') return ''
  if (!c.total_count) return unit === 'month' ? '총 개월 수를 적어 주세요.' : '총 횟수를 적어 주세요.'
  if (unit === 'count') {
    if (c.used_count == null) return '이미 쓴 횟수를 적어 주세요. 안 썼으면 0입니다.'
    if (c.used_count > c.total_count) return '이미 쓴 횟수는 총 횟수보다 많을 수 없습니다.'
  }
  return ''
}

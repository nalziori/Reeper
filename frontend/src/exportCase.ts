import type { Case, Rules } from './api'
import { STAGE, won } from './format'



export function buildSummary(c: Case, rules: Rules): string {
  const { contract, refund } = c
  const settled = c.agreed_amount != null
  const unit = refund.unit_label || '일'
  const lines: string[] = [
    'Reeper 사건 요약',
    '',
    `업체명: ${contract.gym_name || '(입력 안 함)'}`,
    `이용 기간: ${contract.start_date} ~ ${contract.end_date}`,
    `결제 금액: ${won(contract.total_paid)}`,
    `이용분: ${won(refund.used_amount)} (${refund.total_days}${unit} 중 ${refund.used_days}${unit})`,
    `위약금: ${won(refund.penalty)}`,
  ]
  if (refund.addon > 0) lines.push(`공제한 부가상품 가액: ${won(refund.addon)}`)
  if (refund.security_deposit > 0) lines.push(`환불액에 더한 보증금: ${won(refund.security_deposit)}`)
  lines.push(
    `${settled ? '합의 환불액' : '예상 환불액'}: ${won(settled ? (c.agreed_amount as number) : refund.refund)}`,
  )
  if (settled) lines.push(`처음 계산한 예상 환불액: ${won(refund.refund)}`)
  lines.push(`목표 금액: ${won(c.target)}`, `최저 수용선: ${won(c.floor)}`)
  const refs = refund.refs.map((id) => rules[id]?.title ?? id)
  lines.push(`계산 근거: ${refs.length ? refs.join(', ') : '(없음)'}`)
  lines.push(`현재 단계: ${STAGE[c.stage] ?? c.stage}`)
  if (c.notified_on) lines.push(`해지 의사 도달일: ${c.notified_on}`)
  if (c.deadline_on) lines.push(`답변 기한: ${c.deadline_on}`)
  if (c.deposit_due_on) lines.push(`입금 기한: ${c.deposit_due_on}`)
  if (refund.provisional) {
    lines.push('', '이 금액은 일반적인 기준에 따른 예상 금액이며 계산식은 원문 확인 전 임시입니다.')
  }
  lines.push('', '지금까지의 기록')
  if (c.timeline.length === 0) lines.push('- (아직 없음)')
  for (const r of c.timeline) lines.push(`- ${r.on} · ${r.text || r.type}`)
  lines.push('', '다툼이 있으면 1372 소비자상담센터에 문의하세요.')
  return lines.join('\n')
}

export function buildJson(c: Case): string {
  return JSON.stringify(c, null, 2)
}

export function fileName(c: Case, ext: 'txt' | 'json'): string {
  const d = new Date()
  const today = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
  const name = (c.contract.gym_name ?? '')
    .replace(/[\\/:*?"<>|\s.]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '')
  return `reeper-${name || 'case'}-${today}.${ext}`
}

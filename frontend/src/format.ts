// 사건을 보관하는 브라우저 저장소 키. 사건은 서버가 아니라 이 브라우저에만 있다.
export const STORAGE_KEY = 'reeper.case'
import type { Step } from './api'

export const won = (n: number) => `${n.toLocaleString('ko-KR')}원`
export const isoDate = (offset: number) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const utcDay = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / 86400000
}
// 기한 당일 0, 하루 전 1, 하루 뒤 -1
export const daysLeft = (dateIso: string, todayIso: string) => utcDay(dateIso) - utcDay(todayIso)
export const koDate = (iso: string) => `${Number(iso.slice(5, 7))}월 ${Number(iso.slice(8, 10))}일`

export const STAGE: Record<string, string> = {
  ready: '보낼 준비', waiting: '답 기다리는 중', negotiating: '대응 필요', escalated: '내용증명 단계',
  agreed: '입금 기다리는 중', closed: '환불 완료', handed_off: '1372 접수',
}
export const DRAFT: Record<string, string> = {
  notice_sms: '문자로 보낼 문안', call_card: '전화로 말할 때: 통화 준비 카드', after_call_sms: '통화 직후 보낼 확인 문자',
  follow_up: '재요청 문안', counter_refuse: '다음에 보낼 문장', counter_list_price: '다음에 보낼 문장',
  counter_visit: '다음에 보낼 문장', counter_low_offer: '다음에 보낼 문장', counter_unknown: '다음에 보낼 문장', counter_penalty: '다음에 보낼 문장',
  accept_offer: '수락 문안', confirm_agreement: '합의 확인 문안', remind_deposit: '입금 요청 문안',
  certified_mail: '내용증명 초안', go_1372: '1372 상담 신청 내용',
}
// 시연용: 심사위원이 사장 역할로 던져 볼 답
export const OWNER_SAYS = ['네 알겠습니다 환불해 드릴게요', '20만원만 드릴게요', '이벤트 상품은 환불 불가입니다',
  '정상가 기준으로 차감합니다', '방문하셔야 처리됩니다']

export const JOURNEY = ['계약 입력', '근거 확인', '말할 준비', '답변 대응', '입금 추적']
export const journeyPhase = (stage: Step['case']['stage']) =>
  stage === 'ready' ? 3 : stage === 'agreed' || stage === 'closed' ? 5 : 4

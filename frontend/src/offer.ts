import type { Action, Case } from './api'

// 하한선보다 적어 경고가 떠도 받고 끝낼 수 있는 제시: 업체 잘못 사건에서 업체가 다툴 때의 환불액(위약금을 뺀 금액) 이상을 냈을 때다.
// 서버의 agent._can_take와 같은 조건이다(0원 합의는 서버가 거절해서 0원보다 커야 한다). 한쪽을 바꾸면 다른 쪽도 바꾼다(#171, #175)
export const canTakeDisputed = (c: Case, action: Action): boolean => {
  const disputed = c.refund.disputed_refund
  return action.warn && c.contract.cancel_reason === 'business' && disputed != null
    && c.offered != null && c.offered > 0 && c.offered >= disputed
}

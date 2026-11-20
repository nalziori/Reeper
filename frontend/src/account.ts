// 환불받을 계좌. 서버에 보내지 않고(문안에는 화면에서 채운다) 이 브라우저에만 둔다.
// 같은 사건에서 문안이 바뀌어도 다시 적지 않게 남겨 두고, 새로 시작하면 지운다. 사건 내보내기에도 넣지 않는다

// 입금 계좌 자리. 양식(data/templates의 accept_offer, confirm_agreement)에 이 글자 그대로 들어 있다
export const ACCOUNT_SLOT = '(은행 / 계좌번호 / 예금주)'
const KEY = 'reeper-account'

export const loadAccount = () => { try { return localStorage.getItem(KEY) ?? '' } catch { return '' } }
export const saveAccount = (v: string) => {
  try { if (v.trim()) localStorage.setItem(KEY, v); else localStorage.removeItem(KEY) } catch { /* 이번 화면에서만 쓴다 */ }
}
export const forgetAccount = () => { try { localStorage.removeItem(KEY) } catch { /* 저장소를 못 쓰면 그대로 둔다 */ } }

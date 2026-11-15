"""가상 계약서 정답 세트 eval/contracts.jsonl을 만든다. rules.py를 부르지 않고 따로 계산한다.

실행: python eval/make_contracts.py eval/contracts.jsonl
used_count는 계약서에 없는 사용자 입력이라 contract가 아니라 usage에 둔다.
basis: kca_case(한국소비자원 조정 사례와 대조) / decision_table(docs/환불_규칙.md 팀 결정표)
       / unverified_month(월 단위 해석, 팀 미확인). 정확도 평가에서는 unverified_month를 뺀다.
"""
import json, sys
from datetime import date
# (id, 센터, 상품, 단위, 총수, 이용횟수, 결제, 정가, 시작, 종료, 해지일, 부가상품(이름,가액|None), 보증금, 특약, 메모)
C = [
("k01","가상짐 한빛점","3개월 회원권","day",None,None,600000,None,"2026-01-01","2026-03-31","2026-01-10",None,0,"","기본 예시(결정표)"),
("k02","가상짐 한빛점","3개월 회원권","day",None,None,600000,None,"2026-01-01","2026-03-31","2026-01-01",None,0,"","개시일 당일 해지 = 1일 이용"),
("k03","새봄피트니스","6개월 회원권","day",None,None,270000,None,"2026-02-01","2026-08-01","2026-02-21",None,0,"","조정 사례와 같은 182일 21일 구조"),
("k04","새봄피트니스","12개월 회원권","day",None,None,720000,990000,"2026-03-01","2027-02-28","2026-05-15",None,0,"이벤트 할인 상품은 환불이 불가합니다.","할인가가 기준, 환불 불가 특약 무시"),
("k05","바른몸헬스","1개월 회원권","day",None,None,90000,None,"2026-04-01","2026-04-30","2026-04-29",None,0,"","거의 다 씀: 공제가 결제를 넘어 0원"),
("k06","바른몸헬스","3개월 회원권","day",None,None,330000,None,"2026-06-01","2026-08-30","2026-05-20",None,0,"","개시 전 해지 = 이용 0일"),
("k07","바른몸헬스","3개월 회원권","day",None,None,330000,None,"2026-06-01","2026-08-30","2026-09-10",None,0,"","종료 후 = 전부 이용"),
("k08","온새필라테스","6개월 그룹 필라테스","day",None,None,480000,None,"2026-01-10","2026-07-09","2026-03-03",None,0,"","필라테스도 위약금 10%"),
("k09","가상짐 한빛점","3개월 회원권 + 운동복","day",None,None,650000,None,"2026-01-01","2026-03-31","2026-01-10",("운동복 1벌",50000),0,"","부가상품 가액 기재 → 공제"),
("k10","가상짐 한빛점","3개월 회원권 + 운동복","day",None,None,650000,None,"2026-01-01","2026-03-31","2026-01-10",("운동복 1벌",None),0,"운동복은 사은품으로 제공됩니다.","부가상품 가액 미기재 → 공제 안 함"),
("k11","새봄피트니스","6개월 회원권","day",None,None,400000,None,"2026-03-01","2026-08-27","2026-04-10",None,20000,"락커 보증금은 별도입니다.","보증금 전액 반환"),
("k12","새봄피트니스","1개월 회원권","day",None,None,100000,None,"2026-03-01","2026-03-30","2026-03-30",None,10000,"","다 써도 보증금은 반환"),
("k13","바른몸헬스","12개월 회원권","day",None,None,1000000,None,"2026-01-01","2026-12-31","2026-02-14",("요가매트",40000),30000,"","부가상품 + 보증금 동시"),
("k14","가상짐 한빛점","3개월 회원권","month",3,None,600000,None,"2026-01-01","2026-03-31","2026-01-31",None,0,"월 단위로 이용료를 정산합니다.","월 단위 1개월째 마지막 날"),
("k15","가상짐 한빛점","3개월 회원권","month",3,None,600000,None,"2026-01-01","2026-03-31","2026-02-01",None,0,"월 단위로 이용료를 정산합니다.","월 단위 2개월째 첫날(미확인 해석)"),
("k16","온새필라테스","6개월 필라테스","month",6,None,900000,None,"2026-01-31","2026-07-30","2026-02-28",None,0,"월 단위로 이용료를 정산합니다.","1/31 시작 월말 경계"),
("k17","온새필라테스","12개월 필라테스","month",12,None,1440000,None,"2026-05-15","2027-05-14","2026-09-14",None,0,"월 단위로 이용료를 정산합니다.","4개월째 마지막 날"),
("k18","힘찬PT","PT 20회","count",20,5,1200000,None,"2026-01-05","2026-04-30","2026-02-10",None,0,"","PT 회 단위"),
("k19","힘찬PT","PT 30회","count",30,0,1650000,2100000,"2026-02-01","2026-07-31","2026-02-03",None,0,"PT는 1회라도 진행하면 환불이 불가합니다.","PT 0회 이용, 할인가 기준"),
("k20","힘찬PT","PT 10회","count",10,10,700000,None,"2026-03-01","2026-05-31","2026-05-01",None,0,"","PT 전부 이용 → 0원"),
("k21","온새필라테스","1:1 필라테스 24회","count",24,7,1560000,None,"2026-04-01","2026-09-30","2026-05-20",("필라테스 양말 3켤레",15000),0,"","회 단위 + 부가상품"),
("k22","힘찬PT","PT 16회","count",16,3,960000,None,"2026-06-01","2026-09-30","2026-06-20",None,50000,"","회 단위 + 보증금"),
("k23","바른몸헬스","100일 회원권","day",None,None,150000,None,"2026-07-01","2026-10-08","2026-07-31",None,0,"","100일 상품(나눠 떨어짐)"),
("k24","새봄피트니스","2개월 회원권","day",None,None,130000,None,"2026-08-01","2026-09-30","2026-08-15",None,0,"양도는 가능하나 환불은 불가합니다.","양도만 가능 특약 무시"),
("k26","새봄피트니스","3개월 회원권","day",None,None,600000,None,"2026-09-01","2026-11-29","2026-09-20",None,50000,"","총 납부액에 보증금이 섞여 적힘 → total_paid는 보증금 제외"),
("k27","온새필라테스","3개월 필라테스","month",3,None,450000,None,"2028-01-31","2028-04-30","2028-02-29",None,0,"월 단위로 이용료를 정산합니다.","윤년 2월 29일 월말 경계"),
("k25","가상짐 한빛점","6개월 회원권","day",None,None,540000,None,"2026-10-01","2027-03-31","2026-12-31",None,0,"","해를 넘기는 기간"),
]
def d(s): return date.fromisoformat(s)
def months(a,b):
    m=(b.year-a.year)*12+(b.month-a.month); return m+1 if b.day>=a.day else m
out=[]
for (i,gym,prod,unit,tot,usedc,paid,listp,s,e,n,addon,dep,sp,memo) in C:
    S,E,N=d(s),d(e),d(n)
    if unit=="day": T=(E-S).days+1; U=(N-S).days+1
    elif unit=="month": T=tot; U=months(S,N)
    else: T=tot; U=usedc
    U=min(max(U,0),T)
    used=paid*U//T; pen=paid*10//100; av=addon[1] if addon and addon[1] else 0
    refund=max(paid-used-av-pen,0)+dep
    from datetime import timedelta
    N2=N+timedelta(days=1)
    U2=(N2-S).days+1 if unit=="day" else months(S,N2) if unit=="month" else usedc
    U2=min(max(U2,0),T); refund2=max(paid-paid*U2//T-av-pen,0)+dep
    lines=["회원권 이용 계약서","",f"센터명: {gym}",f"상품: {prod}",
           (f"총 납부액: {paid+dep:,}원 (회원권 {paid:,}원 + 보증금 {dep:,}원)" if i=="k26" else f"결제금액: {paid:,}원")+(f" (정상가 {listp:,}원)" if listp else ""),
           f"이용기간: {S:%Y.%m.%d} ~ {E:%Y.%m.%d}"]
    if unit=="count": lines.append(f"이용 횟수: 총 {tot}회")
    if addon: lines.append(f"부가상품: {addon[0]}"+(f" (가액 {addon[1]:,}원)" if addon[1] else ""))
    if dep and i!="k26": lines.append(f"보증금: {dep:,}원 (별도 납부)")
    lines.append(f"특약: {sp or '없음'}")
    contract={"gym_name":gym,"total_paid":paid,"start_date":s,"end_date":e,"special_terms":sp,"unit":unit}
    if tot: contract["total_count"]=tot
    if av: contract["addon_value"]=av
    if dep: contract["security_deposit"]=dep
    basis="unverified_month" if unit=="month" else "kca_case" if i=="k03" else "decision_table"
    out.append({"id":i,"basis":basis,"note":memo,"text":"\n".join(lines),"contract":contract,"notified_on":n,"usage":({"used_count":usedc} if unit=="count" else {}),
                "expected":{"used_days":U,"total_days":T,"used_amount":used,"penalty":pen,"refund":refund,"per_day_loss":refund-refund2}})
open(sys.argv[1],"w",encoding="utf-8",newline="").write("".join(json.dumps(o,ensure_ascii=False)+"\n" for o in out))
print(len(out))

import { ClockIcon } from '@heroicons/react/24/outline'
import { Banner, Button, Card, Collapsible, DateInput, HStack, Heading, SegmentedControl, SegmentedControlItem, Text, TextInput, VStack, Waiting } from '../ui'
import { type ComponentProps, useEffect, useState } from 'react'
import { api, type Contract, type ExtractField, type Refund, type Rules, type Sample, type Step } from '../api'
import { ContractExtras } from '../components/ContractExtras'
import { extrasProblem } from '../contractCheck'
import { FaultCases } from '../components/FaultCases'
import { FaultSummary } from '../components/FaultSummary'
import { JourneyProgress } from '../components/JourneyProgress'
import { isoDate, won } from '../format'
import { shrinkPhoto } from '../photo'

// DateInput은 YYYY-MM-DD 모양만 받는다. 빈 값이나 다른 모양이면 비워 둔다
type Iso = NonNullable<ComponentProps<typeof DateInput>['value']>
const asIso = (v: string) => (/^\d{4}-\d{2}-\d{2}$/.test(v) ? (v as Iso) : undefined)

// 직접 입력 기본 네 칸 밖에서 사진으로 읽는 칸
const EXTRAS = ['unit', 'total_count', 'special_terms', 'addon_value', 'security_deposit'] as const

const CHECK = { type: 'warning' as const, message: '사진에서 읽었어요. 계약서와 같은지 봐 주세요' }

// DateInput이 받아들이지 않은 날짜의 안내. 컴포넌트 기본 문구는 영어라 한국어로 바꿔 보여 준다
type EntryError = Parameters<NonNullable<ComponentProps<typeof DateInput>['onEntryErrorChange']>>[0]
const entryMessage = (e: EntryError, min?: string) => !e ? undefined : {
  type: 'error' as const,
  message: e.kind === 'outOfRange' && min ? `이용 시작일(${min})과 같거나 늦은 날짜를 적어 주세요`
    : e.kind === 'nonexistent' ? '없는 날짜예요. 다시 확인해 주세요'
    : '연도-월-일 모양으로 적어 주세요(예: 2026-11-18)',
}

// 고른 항목의 예시만 한 줄로 보여 준다. 선택지 이름은 짧게 두고 예시를 여기 둔다
const INDUSTRY_HINT = { fitness: '헬스장, 피트니스, PT', yoga: '요가, 필라테스', other: '수영, 골프, 댄스, 학원 등. 아직 계산하지 않아요' } as const
const REASON_HINT = {
  mine: '이사, 건강, 마음이 바뀜 등', business: '시설 운영 중단, 약속한 강사·프로그램 불이행 등',
} as const
// 1372에 물어볼 만한 흔한 상황. 업체 잘못인지 판단하지 않는다(통계 아님, 법적 판단 아님).
// 이전·시설 고장은 상담 사례에서 업체 잘못으로 본 경우가 있어(#142 B 리뷰) '내 사정'으로 안내하지 않는다
const UNSURE_CASES = [
  '담당 강사가 바뀌었는데 계약서에 강사 지정이 없어요',
  '시설 공사나 장비 고장으로 일부를 못 써요',
  '수업·프로그램 일부가 없어지거나 시간이 바뀌었어요',
  '지점이 옮겨져서 다니기 멀어졌어요',
] as const

function WhyBox({ ids, rules, children }: { ids: string[]; rules: Rules; children: React.ReactNode }) {
  return (
    <VStack gap={1}>
      {children}
      <Text type="supporting">근거: {ids.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>
    </VStack>
  )
}

type Props = { onConfirm: (step: Step, today: string) => void; rules: Rules; upload: boolean }

export function Intake({ onConfirm, rules, upload }: Props) {
  const [samples, setSamples] = useState<Sample[]>([])
  const [c, setC] = useState<Contract>({ gym_name: '', total_paid: 0, start_date: '', end_date: '' })
  const [preview, setPreview] = useState<{ contract: Contract; refund: Refund; today: string } | null>(null)
  const [target, setTarget] = useState('')
  const [floor, setFloor] = useState('')
  // 해지 이유. 위약금 공제는 업체 잘못이 없는 해지가 전제라(docs/환불_규칙.md) 업체 잘못이면 이 계산을 쓰지 않는다
  // 업종. 위약금 기준(총계약대금의 10%)이 고시에서 확인된 것은 헬스·피트니스업과 요가·필라테스업뿐이다(docs/환불_규칙.md)
  const [industry, setIndustry] = useState<'fitness' | 'yoga' | 'other'>('fitness')
  const [reason, setReason] = useState<'mine' | 'business'>('mine')
  const [busy, setBusy] = useState(false)
  const [why, setWhy] = useState<'used' | 'penalty' | 'deposit' | null>(null)
  const [error, setError] = useState('')
  const [photoNote, setPhotoNote] = useState('')
  // 사진에서 읽었지만 확신이 낮은 칸. 사용자가 그 칸을 고치면 확인한 것으로 본다.
  const [checks, setChecks] = useState<Set<ExtractField>>(new Set())
  const [startError, setStartError] = useState<EntryError>(null)
  const [endError, setEndError] = useState<EntryError>(null)
  const [limitsOpen, setLimitsOpen] = useState(false)
  // 계약 입력과 근거 확인을 오가면 맨 위에서 시작한다
  useEffect(() => { window.scrollTo({ top: 0 }) }, [preview === null])
  const edit = (field: ExtractField, next: Contract) => {
    setC(next)
    setChecks((prev) => { const s = new Set(prev); s.delete(field); return s })
  }
  const readPhoto = (file: File) => runIntake(async () => {
    setPhotoNote('')
    const { fields, llm_fallback } = await api.extract(await shrinkPhoto(file))
    const str = (f: ExtractField) => typeof fields[f]?.value === 'string' ? fields[f]!.value as string : ''
    const num = (f: ExtractField) => typeof fields[f]?.value === 'number' ? fields[f]!.value as number : undefined
    const read = fields.unit?.value
    const unit = read === 'count' ? 'count' : 'day'
    setC({
      gym_name: str('gym_name'),
      total_paid: num('total_paid') ?? 0,
      start_date: str('start_date'),
      end_date: str('end_date'),
      special_terms: str('special_terms') || undefined,
      unit,
      total_count: unit === 'day' ? undefined : num('total_count'),
      used_count: undefined, // 계약서에 없는 값이라 사람이 적는다
      addon_value: num('addon_value') ?? 0,
      security_deposit: num('security_deposit') ?? 0,
    })
    setChecks(new Set((Object.keys(fields) as ExtractField[]).filter((f) =>
      (f !== 'total_count' || unit === 'count') && fields[f]?.check && fields[f]?.value != null)))
    // 계약서에 없어서 비었는지 못 읽어서 비었는지 구별할 수 없다. 비어 온 금액 칸은 사용자가 계약서를 다시 보게 한다
    const missed = [num('addon_value') ? '' : '부가상품', num('security_deposit') ? '' : '보증금'].filter(Boolean)
    setPhotoNote(llm_fallback
      ? '사진을 읽지 못했어요. 아래 칸에 직접 입력해 주세요'
      : '사진에서 읽어 채웠어요. 비었거나 표시된 칸은 계약서와 맞춰 보세요'
        + (read === 'month' ? '. 개월 단위 회원권은 이용 시작일과 마지막 이용일을 확인해 주세요. 일수로 계산해요' : '')
        + (missed.length ? `. ${missed.join('이나 ')}이 계약서에 적혀 있으면 직접 적어 주세요` : ''))
  })
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setError('가상 계약서를 못 불러왔어요. 직접 적거나 새로고침해 주세요'))
  }, [])

  const runIntake = async (operation: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try {
      await operation()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const review = (contract: Contract) => runIntake(async () => {
    const today = isoDate(0)
    const refund = await api.preview(contract, today)
    setPreview({ contract, refund, today })
    setC(contract)
    setTarget('')
    setFloor('')
  })

  if (preview) {
    const { contract, refund } = preview
    const unitName = refund.unit_label === '일' ? '일수' : refund.unit_label === '회' ? '이용 횟수' : refund.unit_label
    const targetAmount = target === '' ? refund.refund : Number(target)
    const floorAmount = floor === '' ? refund.refund : Number(floor)
    const validAmount = (value: string) => value === '' || (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)))
    const targetValid = validAmount(target)
    const floorValid = validAmount(floor)
    const limitsError = !targetValid || !floorValid ? '0 이상 숫자만 적어 주세요'
      : floorAmount > targetAmount ? '하한선은 희망 금액보다 클 수 없어요' : ''
    const confirm = () => runIntake(async () => {
      const today = isoDate(0)
      if (today !== preview.today) {
        const recalculated = await api.preview(contract, today)
        setPreview({ contract, refund: recalculated, today })
        setError('날짜가 바뀌어 다시 계산했어요. 금액을 확인해 주세요')
        return
      }
      const step = await api.open(contract, today, {
        target: target === '' ? undefined : targetAmount,
        floor: floor === '' ? undefined : floorAmount,
      })
      onConfirm(step, today)
    })
    // 업종과 해지 이유는 한 카드에 가로 선택으로 둔다. 둘 다 금액을 보여 줄지를 정하는 질문이다
    const byCount = refund.unit_label === '회'
    const whyButton = (key: 'used' | 'penalty' | 'deposit', label: string) => (
      <button type="button" className="receipt-btn" aria-expanded={why === key} onClick={() => setWhy(why === key ? null : key)}>
        {label}<span aria-hidden="true">{why === key ? ' ▴' : ' ▾'}</span>
      </button>
    )
    const industryCard = (
      <VStack gap={2}>
        <Text weight="semibold">회원권 업종</Text>
        <SegmentedControl label="회원권 업종" layout="fill" size="sm" value={industry} isDisabled={busy}
          onChange={(v) => setIndustry(v as 'fitness' | 'yoga' | 'other')}>
          <SegmentedControlItem value="fitness" label="헬스장·PT" />
          <SegmentedControlItem value="yoga" label="요가·필라테스" />
          <SegmentedControlItem value="other" label="그 밖의 업종" />
        </SegmentedControl>
        <Text type="supporting">{INDUSTRY_HINT[industry]}</Text>
      </VStack>
    )
    const reasonPicker = (
      <VStack gap={2}>
        <Text weight="semibold">해지하려는 이유</Text>
        <SegmentedControl label="해지하려는 이유" layout="fill" size="sm" value={reason} isDisabled={busy}
          onChange={(v) => setReason(v as 'mine' | 'business')}>
          <SegmentedControlItem value="mine" label="내 사정" />
          <SegmentedControlItem value="business" label="업체 잘못" />
        </SegmentedControl>
        <Text type="supporting">{REASON_HINT[reason]}</Text>
      </VStack>
    )
    if (industry === 'other') {
      // 기준을 확인하지 않은 업종이라 계산 금액·문안을 보여 주지 않고 사건도 열지 않는다
      return (
        <VStack gap={4}>
          <JourneyProgress current={2} />
          <Card>{industryCard}</Card>
          <Card>
            <VStack gap={2}>
              <Heading level={2}>이 업종은 아직 계산하지 않아요</Heading>
              <Text as="p">위약금 기준을 확인한 건 헬스·PT와 요가·필라테스뿐이에요</Text>
              <Text as="p">1372 소비자상담센터(국번 없이 1372, www.1372.go.kr)에 상담하세요. 계약서와 결제 내역을 챙기면 좋아요</Text>
            </VStack>
          </Card>
          <HStack gap={2} wrap="wrap">
            <Button label="계약 수정" isDisabled={busy} onClick={() => { setError(''); setPreview(null) }} />
          </HStack>
        </VStack>
      )
    }
    return (
      <VStack gap={4}>
        <JourneyProgress current={2} />
        {error && <Banner status="error" title={error} collapsible={false} />}
        <Card>
          <VStack gap={4}>
            {industryCard}
            {reasonPicker}
          </VStack>
        </Card>
        {reason === 'business' ? (<>
          <Card>
            <VStack gap={2}>
              <Heading level={2}>1372 상담을 먼저 받아 보세요</Heading>
              <Text as="p">업체 잘못이면 위약금을 빼지 않을 수 있어서, 이 계산은 쓰지 않아요</Text>
              <Text as="p">1372 소비자상담센터(국번 없이 1372, www.1372.go.kr)에 상담하세요. 공지 사진이나 문자처럼 업체 잘못을 보여 줄 자료를 챙기면 좋아요</Text>
              <Text type="supporting">1372에 물어볼 만한 경우예요</Text>
              <ul className="list-disc pl-5 text-sm text-muted-foreground" aria-label="애매한 상황 예시">
                {UNSURE_CASES.map((t) => <li key={t}>{t}</li>)}
              </ul>
              <Text type="supporting">업체 잘못이면 Reeper는 여기까지 도와드려요. 업체 잘못인지 애매하면 업체에 문자를 보내기 전에 1372에 물어보세요</Text>
            </VStack>
          </Card>
          <FaultCases />
          <FaultSummary c={contract} />
        </>) : (<>
        {/* 받을 돈이 이 화면의 주인공이다: 큰 숫자 한 줄, 그 아래 영수증처럼 계산식을 줄 맞춰 적는다 */}
        <Card>
          <VStack gap={3}>
            <VStack gap={1}>
              <Heading level={2} className="text-[15px] font-medium text-muted-foreground">예상 환불액</Heading>
              <Text type="display-3">{won(refund.refund)}</Text>
              <Text type="supporting">{unitName} 기준으로 계산</Text>
              <Text type="supporting">{contract.gym_name || '내 회원권'} · {contract.start_date} ~ {contract.end_date}</Text>
            </VStack>
            {/* 빠지는 돈은 눌러서 이유와 근거를 본다. 계산 근거 목록은 따로 두지 않고 각 줄 아래에 붙인다 */}
            <dl className="receipt">
              <div><dt>낸 돈</dt><dd>{won(contract.total_paid)}</dd></div>
              <div><dt>{whyButton('used', `쓴 만큼 · ${refund.total_days}${refund.unit_label} 중 ${refund.used_days}${refund.unit_label}`)}</dt><dd>−{won(refund.used_amount)}</dd></div>
              {why === 'used' && <div className="receipt-why"><WhyBox ids={['G5']} rules={rules}>
                {/* 회 단위는 날짜가 아니라 사용자가 적은 이용 횟수로 계산한다(rules.py) */}
                {byCount ? (
                  <Text as="p" type="supporting">이미 받은 횟수만큼은 돌려받지 않아요. 총 횟수 중 받은 횟수로 나눠 계산해요</Text>
                ) : (<>
                  <Text as="p" type="supporting">이용한 날짜만큼은 돌려받지 않아요. 가지 않은 날도 알린 날까지는 이용한 것으로 봐요. 이용 시작 전에 알리면 이 줄은 0원이에요</Text>
                  <Text as="p" type="supporting">이용 시작일은 계약일이 아니라 계약서에 적힌 이용 시작일이에요. 시작일과 마지막 이용일은 둘 다 이용한 날로 세요</Text>
                </>)}
              </WhyBox></div>}
              <div><dt>{whyButton('penalty', '위약금')}</dt><dd>−{won(refund.penalty)}</dd></div>
              {/* 시작 전 해지인데 위약금이 빠지는 것이 가장 헷갈리는 지점이라, 누르지 않아도 한 줄로 먼저 알린다 */}
              {refund.used_days === 0 && why !== 'penalty' && <div className="receipt-note"><Text type="supporting">{byCount ? '아직 받은 횟수가 없어 쓴 돈은 없지만' : '아직 이용 전이라 쓴 돈은 없지만'}, 위약금은 빠져요. 위약금을 눌러 이유를 보세요</Text></div>}
              {why === 'penalty' &&<div className="receipt-why"><WhyBox ids={['G10']} rules={rules}>
                <Text as="p" type="supporting">내 사정으로 해지하면 총 계약대금의 10%를 위약금으로 뺄 수 있어요. 이용 시작 전이든 후든 같은 기준이라, 시작 전에 해지해도 빠져요</Text>
                <Text as="p" type="supporting">업체 잘못으로 해지하는 경우에는 이 위약금을 내지 않을 수 있어요. 그때는 위에서 '업체 잘못'을 골라 주세요</Text>
              </WhyBox></div>}
              {refund.addon > 0 && <div><dt>사은품</dt><dd>−{won(refund.addon)}</dd></div>}
              {refund.security_deposit > 0 && <div><dt>{whyButton('deposit', '돌려받을 보증금')}</dt><dd>+{won(refund.security_deposit)}</dd></div>}
              {why === 'deposit' && <div className="receipt-why"><WhyBox ids={['G5D']} rules={rules}>
                <Text as="p" type="supporting">보증금은 계약대금에 들어가지 않아서 위약금을 계산할 때 빠져요. 별도 약정이 없으면 전액 돌려받아요</Text>
              </WhyBox></div>}
              <div className="receipt-total"><dt>돌려받을 돈</dt><dd>{won(refund.refund)}</dd></div>
            </dl>
            {/* 업체가 적게 주겠다고 할 때 알려 줄 기준. 시작 버튼보다 위에 있어야 정하고 시작한다. 값을 적었거나 오류가 있으면 펼쳐 둔다 */}
            <Collapsible isOpen={limitsOpen || target !== '' || floor !== '' || Boolean(limitsError)} onOpenChange={setLimitsOpen}
              trigger={<VStack gap={1}>
                <Text weight="semibold">희망 금액 정하기(선택)</Text>
                <Text type="supporting">비우면 업체가 위 금액보다 적게 주겠다고 할 때 알려 드려요</Text>
              </VStack>}>
              <VStack gap={3}>
                <TextInput label="희망 금액(원)" value={target} onChange={setTarget} inputMode="numeric"
                  isDisabled={busy} status={!targetValid ? { type: 'error', message: limitsError } : undefined} />
                <TextInput label="하한선(원)" description="업체가 이보다 적게 주겠다고 하면 받지 않아요" value={floor} onChange={setFloor} inputMode="numeric"
                  isDisabled={busy} status={!floorValid || (floorAmount > targetAmount) ? { type: 'error', message: limitsError } : undefined} />
              </VStack>
            </Collapsible>
            {refund.per_day_loss > 0 && (
              <p className="m-0 flex w-fit items-center gap-1.5 rounded-lg bg-warn-soft px-2.5 py-1.5 text-[13px] font-medium text-warn">
                <ClockIcon className="size-4" aria-hidden />하루 늦으면 {won(refund.per_day_loss)} 줄어요
              </p>
            )}
            {/* 특약 원문만 두면 위 금액과 맞지 않아 보인다. 계산에 넣지 않았다는 것과 근거(R52 요약 그대로)를 함께 적는다 */}
            {contract.special_terms && (
              <VStack gap={1}>
                <Text type="supporting">계약서 특약: {contract.special_terms}</Text>
                <Text type="supporting">위 금액은 이 특약을 빼고 계산했어요. 소비자에게 불리한 특약은 효력이 없을 수 있지만, 이 특약이 그런지는 확인이 필요해요</Text>
              </VStack>
            )}
            {refund.provisional && <Text type="supporting">일반 기준으로 계산했어요. 실제와 다를 수 있어요</Text>}
          </VStack>
        </Card>
        </>)}
        {/* 근거를 다 읽지 않아도 시작할 수 있게 화면 아래에 붙여 둔다 */}
        <div className="action-dock">
          <HStack gap={2} wrap="wrap">
            <Button label="계약 수정" isDisabled={busy} onClick={() => { setError(''); setPreview(null) }} />
            {reason !== 'business' && <Button variant="primary" label={busy ? '확인 중…' : '이 금액으로 시작'} isDisabled={busy || Boolean(limitsError)} onClick={confirm} />}
          </HStack>
        </div>
      </VStack>
    )
  }

  const blank = [!c.total_paid && '낸 돈', !c.start_date && '시작일', !c.end_date && '마지막 이용일'].filter(Boolean)
  const missing = blank.length ? `${blank.join(', ')}을 적으면 계산할 수 있어요` : extrasProblem(c).replace(/\.$/, '')
  return (
    <VStack gap={4}>
      <JourneyProgress current={1} />
      {error && <Banner status="error" title={error} collapsible={false} />}
      <Text as="p">헬스장·필라테스 환불, 입금까지 챙겨 드려요</Text>
      <Card>
        <VStack gap={3}>
          {/* 가상 계약서는 시연용이라 제목 오른쪽 위에 작은 버튼으로 둔다. 누르면 바로 계산한다 */}
          <HStack gap={2} hAlign="between" wrap="wrap">
            <Heading level={2}>내 계약 입력</Heading>
            {samples.length > 0 && (
              <div role="group" aria-label="가상 계약서로 해 보기">
                <HStack gap={2} wrap="wrap">
                  {samples.map((s) => <Button key={s.id} size="sm" label={samples.length === 1 ? '가상 계약서로 해 보기' : s.label}
                    isDisabled={busy} onClick={() => review(s.contract)} />)}
                </HStack>
              </div>
            )}
          </HStack>
          {/* 사진은 같은 칸을 채우는 방법이라 따로 카드를 두지 않고 입력 카드 맨 위에 둔다 */}
          {upload && (
            <VStack gap={2}>
              {/* 사진 고르기는 네이티브 입력을 쓴다(2026-11-16, 꾸민 파일 입력이 Edge에서 멈춘 적이 있다) */}
              <label className="photo-input">
                <span>계약서 사진으로 채우기</span>
                <Text type="supporting">시연용 가상 계약서만 올려 주세요. 사진은 저장하지 않아요</Text>
                <input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
                  onChange={(e) => {
                    const input = e.target
                    const file = input.files?.[0]
                    // 칸을 읽기 전에 비우면 파일을 못 읽고 멈추는 브라우저가 있어, 다 읽은 뒤에 비운다(같은 사진 다시 고르기용)
                    if (file) void readPhoto(file).finally(() => { input.value = '' })
                  }} />
              </label>
              {busy && <Waiting message="사진을 읽고 있어요. 몇 초 걸려요" />}
              {photoNote && <Text as="p" type="supporting" role="status">{photoNote}</Text>}
              <Text type="supporting">사진이 없으면 아래에 직접 적어 주세요</Text>
            </VStack>
          )}
          <TextInput label="업체 이름" value={c.gym_name} onChange={(v) => edit('gym_name', { ...c, gym_name: v })}
            status={checks.has('gym_name') ? CHECK : undefined} />
          <TextInput label="실제로 낸 돈(원)" value={c.total_paid ? String(c.total_paid) : ''}
            onChange={(v) => edit('total_paid', { ...c, total_paid: Number(v.replace(/\D/g, '')) })}
            status={checks.has('total_paid') ? CHECK : undefined} />
          {/* 시작일과 종료일은 한 줄에 둔다. 아주 좁은 화면에서는 index.css가 두 줄로 내린다 */}
          <div className="date-pair">
            <DateInput label="이용 시작일" format="system_date" placeholder="연도-월-일" value={asIso(c.start_date)} width="100%"
              onChange={(v) => edit('start_date', { ...c, start_date: v ?? '' })} onEntryErrorChange={setStartError}
              status={entryMessage(startError) ?? (checks.has('start_date') ? CHECK : undefined)} />
            <DateInput label="마지막 이용일" format="system_date" placeholder="연도-월-일" value={asIso(c.end_date)} min={asIso(c.start_date)} width="100%"
              onChange={(v) => edit('end_date', { ...c, end_date: v ?? '' })} onEntryErrorChange={setEndError}
              status={entryMessage(endError, c.start_date) ?? (checks.has('end_date') ? CHECK : undefined)} />
          </div>
          <ContractExtras c={c} isDisabled={busy} statusOf={(f) => checks.has(f) ? CHECK : undefined}
            onChange={(next) => {
              setC(next)
              setChecks((prev) => { const s = new Set(prev); for (const f of EXTRAS) if (next[f] !== c[f]) s.delete(f); return s })
            }} />
          <Button label={busy ? '계산 중…' : checks.size ? '확인했어요, 계산하기' : '환불액 계산하기'}
            isDisabled={busy || Boolean(missing)} onClick={() => review(c)} />
          {/* 버튼이 꺼진 이유를 버튼 바로 아래에 적는다. 어느 칸이 비었는지 몰라 멈추지 않게 한다 */}
          {!busy && missing && <Text type="supporting" role="status">{missing}</Text>}
        </VStack>
      </Card>
    </VStack>
  )
}

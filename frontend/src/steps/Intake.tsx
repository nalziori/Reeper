import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Card } from '@astryxdesign/core/Card'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack } from '@astryxdesign/core/HStack'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { DateInput } from '@astryxdesign/core/DateInput'
import { Text } from '@astryxdesign/core/Text'
import { TextInput } from '@astryxdesign/core/TextInput'
import { VStack } from '@astryxdesign/core/VStack'
import { type ComponentProps, useEffect, useState } from 'react'
import { api, type Contract, type ExtractField, type Refund, type Rules, type Sample, type Step } from '../api'
import { ContractExtras } from '../components/ContractExtras'
import { extrasProblem } from '../contractCheck'
import { FaultSummary } from '../components/FaultSummary'
import { JourneyProgress } from '../components/JourneyProgress'
import { isoDate, won } from '../format'
import { shrinkPhoto } from '../photo'

// DateInput은 YYYY-MM-DD 모양만 받는다. 빈 값이나 다른 모양이면 비워 둔다
type Iso = NonNullable<ComponentProps<typeof DateInput>['value']>
const asIso = (v: string) => (/^\d{4}-\d{2}-\d{2}$/.test(v) ? (v as Iso) : undefined)

// 직접 입력 기본 네 칸 밖에서 사진으로 읽는 칸
const EXTRAS = ['unit', 'total_count', 'special_terms', 'addon_value', 'security_deposit'] as const

const CHECK = { type: 'warning' as const, message: '사진에서 읽은 값이에요. 계약서와 같은지 확인해 주세요' }

// DateInput이 받아들이지 않은 날짜의 안내. 컴포넌트 기본 문구는 영어라 한국어로 바꿔 보여 준다
type EntryError = Parameters<NonNullable<ComponentProps<typeof DateInput>['onEntryErrorChange']>>[0]
const entryMessage = (e: EntryError, min?: string) => !e ? undefined : {
  type: 'error' as const,
  message: e.kind === 'outOfRange' && min ? `이용 시작일(${min})과 같거나 늦은 날짜를 적어 주세요`
    : e.kind === 'nonexistent' ? '없는 날짜예요. 다시 확인해 주세요'
    : '연도-월-일 모양으로 적어 주세요(예: 2026-11-18)',
}

// 고른 항목의 예시만 한 줄로 보여 준다. 선택지 이름은 짧게 두고 예시를 여기 둔다
const INDUSTRY_HINT = { fitness: '헬스장, 피트니스, PT', yoga: '요가, 필라테스', other: '수영, 골프, 댄스, 학원 등' } as const
const REASON_HINT = {
  mine: '이사, 건강, 마음이 바뀜 등', business: '시설 운영 중단, 약속한 강사·프로그램 불이행 등',
  unsure: '강사가 바뀌었는데 계약서에 강사 지정이 없는 경우 등',
} as const

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
  const [reason, setReason] = useState<'mine' | 'business' | 'unsure'>('mine')
  const [busy, setBusy] = useState(false)
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
    // 계약서에 단위가 없으면 null이 온다. 그때는 기간(일) 단위로 둔다
    const unit = read === 'month' || read === 'count' ? read : 'day'
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
    setChecks(new Set((Object.keys(fields) as ExtractField[]).filter((f) => fields[f]?.check && fields[f]?.value != null)))
    // 계약서에 없어서 비었는지 못 읽어서 비었는지 구별할 수 없다. 비어 온 금액 칸은 사용자가 계약서를 다시 보게 한다
    const missed = [num('addon_value') ? '' : '부가상품', num('security_deposit') ? '' : '보증금'].filter(Boolean)
    setPhotoNote(llm_fallback
      ? '사진을 읽지 못했어요. 아래 칸에 직접 입력해 주세요'
      : '사진에서 읽은 값을 아래 칸에 채웠어요. 비어 있거나 확인 표시가 있는 칸은 계약서와 대조해 주세요'
        + (missed.length ? `. ${missed.join('이나 ')}이 계약서에 적혀 있으면 직접 적어 주세요` : ''))
  })
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setError('샘플 계약서를 불러오지 못했습니다. 직접 입력하거나 새로고침해 주세요.'))
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
    const targetAmount = target === '' ? refund.refund : Number(target)
    const floorAmount = floor === '' ? refund.refund : Number(floor)
    const validAmount = (value: string) => value === '' || (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)))
    const targetValid = validAmount(target)
    const floorValid = validAmount(floor)
    const limitsError = !targetValid || !floorValid ? '금액은 0원 이상의 정수로 입력해 주세요.'
      : floorAmount > targetAmount ? '최저 수용선은 목표 금액 이하여야 합니다.' : ''
    const confirm = () => runIntake(async () => {
      const today = isoDate(0)
      if (today !== preview.today) {
        const recalculated = await api.preview(contract, today)
        setPreview({ contract, refund: recalculated, today })
        setError('날짜가 바뀌어 예상 환불액을 다시 계산했습니다. 금액을 확인해 주세요.')
        return
      }
      const step = await api.open(contract, today, {
        target: target === '' ? undefined : targetAmount,
        floor: floor === '' ? undefined : floorAmount,
      })
      onConfirm(step, today)
    })
    // 업종과 해지 이유는 한 카드에 가로 선택으로 둔다. 둘 다 금액을 보여 줄지를 정하는 질문이다
    const industryCard = (
      <VStack gap={2}>
        <Text weight="semibold">회원권 업종</Text>
        <SegmentedControl label="회원권 업종" layout="fill" size="sm" value={industry} isDisabled={busy}
          onChange={(v) => setIndustry(v as 'fitness' | 'yoga' | 'other')}>
          <SegmentedControlItem value="fitness" label="헬스장·PT" />
          <SegmentedControlItem value="yoga" label="요가·필라테스" />
          <SegmentedControlItem value="other" label="그 밖의 업종" />
        </SegmentedControl>
        <Text type="supporting">{INDUSTRY_HINT[industry]}. 업종에 따라 위약금 기준이 달라요</Text>
      </VStack>
    )
    const reasonPicker = (
      <VStack gap={2}>
        <Text weight="semibold">해지하려는 이유</Text>
        <SegmentedControl label="해지하려는 이유" layout="fill" size="sm" value={reason} isDisabled={busy}
          onChange={(v) => setReason(v as 'mine' | 'business' | 'unsure')}>
          <SegmentedControlItem value="mine" label="내 사정" />
          <SegmentedControlItem value="business" label="업체 잘못" />
          <SegmentedControlItem value="unsure" label="잘 모르겠어요" />
        </SegmentedControl>
        <Text type="supporting">{REASON_HINT[reason]}. 이유에 따라 위약금을 빼는지가 달라져요</Text>
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
              <Heading level={2}>이 업종은 계산 기준을 확인하지 않았어요</Heading>
              <Text as="p">Reeper의 계산은 위약금 기준이 확인된 헬스·피트니스와 요가·필라테스 회원권에만 맞춰져 있어요. 다른 업종은 기준을 확인하지 않아서 이 계산 금액과 문안을 쓰지 않아요.</Text>
              <Text as="p">1372 소비자상담센터(국번 없이 1372, www.1372.go.kr)에 상담을 신청하세요. 계약서와 결제 내역을 함께 준비하면 좋아요.</Text>
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
              <Text as="p">이 앱의 계산은 내 사정으로 해지할 때 위약금을 빼는 방식이에요. 업체 잘못으로 해지하면 위약금을 빼지 않아야 할 수 있어서, 이 계산 금액과 문안을 쓰지 않아요.</Text>
              <Text as="p">1372 소비자상담센터(국번 없이 1372, www.1372.go.kr)에 상담을 신청하세요. 계약서와 업체 잘못을 보여 주는 자료(공지 사진, 문자 등)를 함께 준비하면 좋아요.</Text>
            </VStack>
          </Card>
          <FaultSummary c={contract} />
        </>) : (<>
        {reason === 'unsure' && (
          <Banner status="info" collapsible={false} title="업체 잘못인지 애매하면 문자를 보내기 전에 '상황에 맞춘 대응 전략'에 상황을 먼저 적어 보세요. 확인할 것과 모을 자료를 알려 줘요. 그래도 애매하면 1372에 문의하세요" />
        )}
        <Card>
          <VStack gap={2}>
            <Heading level={2}>예상 환불액</Heading>
            <Text type="display-3">{won(refund.refund)}</Text>
            <Text>{contract.gym_name || '내 회원권'} · {contract.start_date} ~ {contract.end_date}</Text>
            <Text type="supporting">
              결제 {won(contract.total_paid)} · 이용분 {won(refund.used_amount)} · 위약금 {won(refund.penalty)}
            </Text>
            {refund.per_day_loss > 0 && <Text weight="semibold">하루 미루면 예상 환불액이 {won(refund.per_day_loss)} 줄어듭니다.</Text>}
            {(refund.addon > 0 || refund.security_deposit > 0) && (
              <Text type="supporting">부가 이용분 {won(refund.addon)} · 반환 보증금 {won(refund.security_deposit)}</Text>
            )}
            {contract.special_terms && <Text type="supporting">특약: {contract.special_terms}</Text>}
            {/* 근거 조문 이름이 길어 세 줄을 넘는다. 개수만 보이고 눌러야 펼친다(전체 근거는 '계산 근거 보기'에도 있다) */}
            {refund.refs.length > 0 && (
              <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">계산 근거 {refund.refs.length}개</Text>}>
                <Text type="supporting">{refund.refs.map((id) => rules[id]?.title ?? id).join(' · ')}</Text>
              </Collapsible>
            )}
            {refund.provisional && <Text type="supporting">일반적인 기준에 따른 예상 금액입니다. 실제 환불액은 달라질 수 있습니다.</Text>}
          </VStack>
        </Card>
        {/* 비우면 예상 환불액을 쓰는 칸이라 대부분 건드리지 않는다. 값을 적었거나 오류가 있으면 펼쳐 둔다 */}
        <Card>
          <Collapsible isOpen={limitsOpen || target !== '' || floor !== '' || Boolean(limitsError)} onOpenChange={setLimitsOpen}
            trigger={<VStack gap={1}>
              <Text weight="semibold">협상 기준(선택)</Text>
              <Text type="supporting">비워 두면 예상 환불액을 목표로 써요</Text>
            </VStack>}>
            <VStack gap={3}>
              <TextInput label="목표 금액(원)" value={target} onChange={setTarget} inputMode="numeric"
                isDisabled={busy} status={!targetValid ? { type: 'error', message: limitsError } : undefined} />
              <TextInput label="최저 수용선(원)" value={floor} onChange={setFloor} inputMode="numeric"
                isDisabled={busy} status={!floorValid || (floorAmount > targetAmount) ? { type: 'error', message: limitsError } : undefined} />
            </VStack>
          </Collapsible>
        </Card>
        </>)}
        {/* 근거를 다 읽지 않아도 시작할 수 있게 화면 아래에 붙여 둔다 */}
        <div className="action-dock">
          <HStack gap={2} wrap="wrap">
            <Button label="계약 수정" isDisabled={busy} onClick={() => { setError(''); setPreview(null) }} />
            {reason !== 'business' && <Button variant="primary" label={busy ? '확인 중…' : '이 기준으로 시작'} isDisabled={busy || Boolean(limitsError)} onClick={confirm} />}
          </HStack>
        </div>
      </VStack>
    )
  }

  return (
    <VStack gap={4}>
      <JourneyProgress current={1} />
      {error && <Banner status="error" title={error} collapsible={false} />}
      <Text as="p">헬스장·PT·필라테스 회원권 환불, 말 꺼내기부터 입금까지 챙겨 드립니다. 근거를 찾고, 그대로 보낼 문장을 만들고, 돈이 들어올 때까지 추적합니다.</Text>
      <Card>
        <VStack gap={3}>
          <Heading level={2}>샘플 계약서로 해 보기</Heading>
          {samples.map((s) => <Button key={s.id} variant="primary" label={s.label} isDisabled={busy} onClick={() => review(s.contract)} />)}
        </VStack>
      </Card>
      <Card>
        <VStack gap={3}>
          <Heading level={2}>내 계약 입력</Heading>
          {/* 사진은 같은 칸을 채우는 방법이라 따로 카드를 두지 않고 입력 카드 맨 위에 둔다 */}
          {upload && (
            <VStack gap={2}>
              {/* Astryx FileInput은 사진을 고르면 화면이 멈춰(2026-11-16, Edge) 네이티브 입력을 쓴다 */}
              <label className="photo-input">
                <span>계약서 사진으로 채우기</span>
                <Text type="supporting">시연용 가상 계약서만 올려 주세요. 읽은 값을 아래 칸에 채우고, 사진은 저장하지 않아요</Text>
                <input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
                  onChange={(e) => {
                    const input = e.target
                    const file = input.files?.[0]
                    // 칸을 읽기 전에 비우면 파일을 못 읽고 멈추는 브라우저가 있어, 다 읽은 뒤에 비운다(같은 사진 다시 고르기용)
                    if (file) void readPhoto(file).finally(() => { input.value = '' })
                  }} />
              </label>
              {busy && <Text type="supporting" role="status">사진을 읽고 있어요</Text>}
              {photoNote && <Text as="p" type="supporting" role="status">{photoNote}</Text>}
              <Text type="supporting">사진이 없으면 아래에 직접 적어 주세요</Text>
            </VStack>
          )}
          <TextInput label="업체 이름" value={c.gym_name} onChange={(v) => edit('gym_name', { ...c, gym_name: v })}
            status={checks.has('gym_name') ? CHECK : undefined} />
          <TextInput label="실제 결제한 금액(원)" value={c.total_paid ? String(c.total_paid) : ''}
            onChange={(v) => edit('total_paid', { ...c, total_paid: Number(v.replace(/\D/g, '')) })}
            status={checks.has('total_paid') ? CHECK : undefined} />
          {/* 시작일과 종료일은 한 줄에 둔다. 아주 좁은 화면에서는 index.css가 두 줄로 내린다 */}
          <div className="date-pair">
            <DateInput label="이용 시작일" format="system_date" placeholder="연도-월-일" value={asIso(c.start_date)} width="100%"
              onChange={(v) => edit('start_date', { ...c, start_date: v ?? '' })} onEntryErrorChange={setStartError}
              status={entryMessage(startError) ?? (checks.has('start_date') ? CHECK : undefined)} />
            <DateInput label="이용 종료일" format="system_date" placeholder="연도-월-일" value={asIso(c.end_date)} min={asIso(c.start_date)} width="100%"
              onChange={(v) => edit('end_date', { ...c, end_date: v ?? '' })} onEntryErrorChange={setEndError}
              status={entryMessage(endError, c.start_date) ?? (checks.has('end_date') ? CHECK : undefined)} />
          </div>
          <ContractExtras c={c} isDisabled={busy} statusOf={(f) => checks.has(f) ? CHECK : undefined}
            onChange={(next) => {
              setC(next)
              setChecks((prev) => { const s = new Set(prev); for (const f of EXTRAS) if (next[f] !== c[f]) s.delete(f); return s })
            }} />
          <Button label={busy ? '계산 중…' : checks.size ? '확인했어요, 환불액 계산' : '환불액 계산'}
            isDisabled={busy || !c.total_paid || !c.start_date || !c.end_date || Boolean(extrasProblem(c))} onClick={() => review(c)} />
        </VStack>
      </Card>
    </VStack>
  )
}

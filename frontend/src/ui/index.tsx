// 화면 부품. shadcn(Base UI + Tailwind) 위에 앱이 쓰던 이름과 props를 그대로 둔다.
// 화면 파일은 이 파일만 가져다 쓰고, 모양은 index.css의 토큰(주황 브랜드, 회색 바탕, 흰 카드)에서 정한다.
import { Collapsible as BaseCollapsible } from '@base-ui/react/collapsible'
import {
  CheckCircleIcon, ChevronDownIcon, ExclamationTriangleIcon, InformationCircleIcon, XCircleIcon,
} from '@heroicons/react/24/outline'
import { cn } from 'cn'
import {
  createContext, useContext, useId, type ElementType, type ReactNode,
} from 'react'
import { Badge as UiBadge } from '../components/ui/badge'
import { Button as UiButton, buttonVariants } from '../components/ui/button'

const space = (n?: number) => (n === undefined ? undefined : `${n * 4}px`)

// ── 쌓기 ──────────────────────────────────────────────
type StackProps = {
  gap?: number; padding?: number; maxWidth?: number; className?: string; role?: string; children?: ReactNode
}
export function VStack({ gap = 0, padding, maxWidth, className, role, children }: StackProps) {
  return (
    <div role={role} className={cn('flex min-w-0 flex-col', className)}
      style={{ gap: space(gap), padding: space(padding), maxWidth }}>{children}</div>
  )
}

const H_ALIGN = { start: 'justify-start', center: 'justify-center', end: 'justify-end', between: 'justify-between' }
const V_ALIGN = { start: 'items-start', center: 'items-center', end: 'items-end', stretch: 'items-stretch' }
export function HStack({ gap = 0, hAlign = 'start', vAlign = 'center', wrap, className, children }: {
  gap?: number; hAlign?: keyof typeof H_ALIGN; vAlign?: keyof typeof V_ALIGN; wrap?: 'wrap' | 'nowrap'
  className?: string; children?: ReactNode
}) {
  return (
    <div className={cn('flex min-w-0', H_ALIGN[hAlign], V_ALIGN[vAlign], wrap === 'wrap' && 'flex-wrap', className)}
      style={{ gap: space(gap) }}>{children}</div>
  )
}

// ── 글자 ──────────────────────────────────────────────
const TEXT = {
  body: 'text-[15px] leading-relaxed',
  large: 'text-[17px] leading-relaxed',
  label: 'text-[13px] font-medium',
  supporting: 'text-[13px] leading-normal text-muted-foreground',
  code: 'font-mono text-[13px]',
  // 받을 돈처럼 화면의 주인공인 숫자
  'display-3': 'text-[34px] leading-tight font-semibold tracking-[-0.02em]',
}
const WEIGHT = { normal: 'font-normal', medium: 'font-medium', semibold: 'font-semibold', bold: 'font-semibold' }
export function Text({ type = 'body', weight, as: Tag = 'span', role, className, children }: {
  type?: keyof typeof TEXT; weight?: keyof typeof WEIGHT; as?: ElementType; role?: string
  className?: string; children?: ReactNode
}) {
  return <Tag role={role} className={cn('break-keep', TEXT[type], weight && WEIGHT[weight], className)}>{children}</Tag>
}

const HEADING = {
  1: 'text-[17px] font-semibold',
  2: 'text-[20px] leading-snug font-semibold',
  3: 'text-[17px] leading-snug font-semibold',
  4: 'text-[15px] font-semibold',
  5: 'text-[15px] font-semibold',
  6: 'text-[15px] font-semibold',
}
export function Heading({ level, className, children }: { level: 1 | 2 | 3 | 4 | 5 | 6; className?: string; children?: ReactNode }) {
  const Tag = `h${level}` as ElementType
  return <Tag className={cn('m-0 break-keep text-foreground', HEADING[level], className)}>{children}</Tag>
}

// ── 상자 ──────────────────────────────────────────────
export function Card({ variant = 'default', className, children }: {
  variant?: 'default' | 'muted'; className?: string; children?: ReactNode
}) {
  return <div className={cn('rounded-2xl p-5', variant === 'muted' ? 'bg-muted' : 'bg-card', className)}>{children}</div>
}

export function Divider() {
  return <hr className="m-0 border-0 border-t border-border" />
}

// ── 버튼 ──────────────────────────────────────────────
const VARIANT = { primary: 'default', secondary: 'secondary', ghost: 'ghost', destructive: 'destructive' } as const
type ButtonProps = {
  label: string; variant?: keyof typeof VARIANT; size?: 'sm' | 'md' | 'lg'; isDisabled?: boolean
  onClick?: () => void; href?: string; icon?: ReactNode; className?: string
  isLoading?: boolean  // 참이면 아이콘 자리에 도는 표시를 두고 누르지 못하게 한다
}
export function Button({ label, variant = 'secondary', size = 'md', isDisabled, isLoading, onClick, href, icon, className }: ButtonProps) {
  const look = { variant: VARIANT[variant], size: size === 'md' ? 'default' as const : size }
  if (href) {
    // 꺼진 링크는 href를 빼서 키보드로도 열리지 않게 한다(href 없는 a는 초점을 받지 않는다)
    return <a href={isDisabled ? undefined : href} aria-disabled={isDisabled || undefined}
      className={cn(buttonVariants(look), 'no-underline', isDisabled && 'pointer-events-none opacity-50', className)}>{icon}{label}</a>
  }
  return <UiButton type="button" {...look} disabled={isDisabled || isLoading} aria-busy={isLoading || undefined}
    onClick={onClick} className={className}>{isLoading ? <Spinner /> : icon}{label}</UiButton>
}

// ── 새 창 링크 ────────────────────────────────────────
// 원문 같은 바깥 페이지를 새 창으로 연다. 이름에 "(새 창)"을 붙여 화면 낭독기에도 알린다
export function ExternalLink({ href, label }: { href: string; label: string }) {
  return <a href={href} target="_blank" rel="noopener noreferrer" className="text-[14px] underline">{label} (새 창)</a>
}

// ── 기다리는 표시 ────────────────────────────────────
// 실제 모델을 부르면 몇 초가 걸린다. 멈춘 것처럼 보이지 않게 도는 표시와 자리 표시 줄을 보여 준다
export function Spinner() {
  return <span aria-hidden className="spinner" />
}

// 0.4초 안에 끝나는 요청에서는 보이지 않는다(index.css의 .waiting). lines는 곧 채워질 글의 자리 표시 줄 수다.
// art는 AI 답이 길어질 때(2초 넘게) 문구 오른쪽에 나타나는 그림이다(.waiting-art). 자리는 처음부터 잡아 둬 글이 밀리지 않는다
export function Waiting({ message, lines = 0, art }: { message: string; lines?: number; art?: ReactNode }) {
  return (
    <div role="status" className="waiting">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />{message}</div>
        {art && <div className="waiting-art">{art}</div>}
      </div>
      {lines > 0 && (
        <div aria-hidden className="mt-3 flex flex-col gap-2">
          {Array.from({ length: lines }, (_, i) => <span key={i} className="skeleton" style={{ width: `${[92, 100, 78, 96, 64][i % 5]}%` }} />)}
        </div>
      )}
    </div>
  )
}

// ── 알림 줄 ──────────────────────────────────────────
const BANNER = {
  info: { box: 'bg-muted text-foreground', Icon: InformationCircleIcon },
  warning: { box: 'bg-warn-soft text-warn', Icon: ExclamationTriangleIcon },
  error: { box: 'bg-warn-soft text-warn', Icon: XCircleIcon },
  success: { box: 'bg-success-soft text-success', Icon: CheckCircleIcon },
}
export function Banner({ status = 'info', title }: { status?: keyof typeof BANNER; title: ReactNode; collapsible?: boolean }) {
  const { box, Icon } = BANNER[status]
  return (
    <div role={status === 'error' ? 'alert' : 'status'} className={cn('flex items-start gap-2 rounded-xl px-4 py-3 text-[14px] leading-normal break-keep', box)}>
      <Icon className="mt-0.5 size-[18px] shrink-0" aria-hidden />
      <span>{title}</span>
    </div>
  )
}

const BADGE = { neutral: 'secondary', info: 'brand', success: 'success', warning: 'destructive', error: 'destructive' } as const
export function Badge({ label, variant = 'neutral' }: { label: ReactNode; variant?: keyof typeof BADGE }) {
  return <UiBadge variant={BADGE[variant]}>{label}</UiBadge>
}

// ── 입력 칸 ──────────────────────────────────────────
export type FieldStatus = { type: 'error' | 'warning' | 'success'; message: string }

function Field({ id, label, description, status, children }: {
  id: string; label: string; description?: ReactNode; status?: FieldStatus; children: ReactNode
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-foreground">{label}</label>
      {description && <span id={`${id}-desc`} className="text-[13px] text-muted-foreground break-keep">{description}</span>}
      {children}
      {status && (
        <span id={`${id}-status`} role={status.type === 'error' ? 'alert' : undefined} data-type={status.type}
          className={cn('field-status text-[13px] break-keep', status.type === 'success' ? 'text-success' : 'text-warn')}>{status.message}</span>
      )}
    </div>
  )
}

const INPUT = 'w-full min-w-0 rounded-xl border border-transparent bg-muted px-3.5 text-base text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-primary focus-visible:bg-card disabled:opacity-50 aria-invalid:border-warn'
const describedBy = (id: string, description?: unknown, status?: unknown) =>
  [description ? `${id}-desc` : '', status ? `${id}-status` : ''].filter(Boolean).join(' ') || undefined

export function TextInput({ label, value, onChange, inputMode, isDisabled, description, status, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; inputMode?: 'numeric' | 'text'
  isDisabled?: boolean; description?: ReactNode; status?: FieldStatus; placeholder?: string
}) {
  const id = useId()
  return (
    <Field id={id} label={label} description={description} status={status}>
      <input id={id} className={cn(INPUT, 'h-12')} value={value} inputMode={inputMode} placeholder={placeholder}
        disabled={isDisabled} aria-invalid={status?.type === 'error' || undefined}
        aria-describedby={describedBy(id, description, status)} onChange={(e) => onChange(e.target.value)} />
    </Field>
  )
}

export function TextArea({ label, value, onChange, maxLength, isDisabled, disabledMessage, description, status }: {
  label: string; value: string; onChange: (v: string) => void; maxLength?: number
  isDisabled?: boolean; disabledMessage?: string; description?: ReactNode; status?: FieldStatus
}) {
  const id = useId()
  return (
    <Field id={id} label={label} description={isDisabled && disabledMessage ? disabledMessage : description} status={status}>
      <textarea id={id} className={cn(INPUT, 'min-h-24 resize-y py-3 leading-relaxed')} value={value} maxLength={maxLength}
        disabled={isDisabled} aria-invalid={status?.type === 'error' || undefined}
        aria-describedby={describedBy(id, description || disabledMessage, status)} onChange={(e) => onChange(e.target.value)} />
      {maxLength && <span className="self-end text-xs text-muted-foreground">{value.length}/{maxLength}</span>}
    </Field>
  )
}

// 날짜는 브라우저 날짜 칸을 쓴다. 휴대폰에서는 달력이 열리고, 값은 늘 연-월-일이다
export type DateEntryError = { kind: 'outOfRange' | 'nonexistent' | 'format' } | null
export function DateInput({ label, description, value, onChange, min, status, onEntryErrorChange }: {
  label: string; value?: string; onChange: (v: string | undefined) => void; min?: string
  description?: string; status?: FieldStatus; onEntryErrorChange?: (e: DateEntryError) => void
  format?: string; placeholder?: string; width?: string
}) {
  const id = useId()
  return (
    <Field id={id} label={label} description={description} status={status}>
      <input id={id} type="date" className={cn(INPUT, 'h-12')} value={value ?? ''} min={min}
        aria-invalid={status?.type === 'error' || undefined} aria-describedby={describedBy(id, description, status)}
        onChange={(e) => {
          const v = e.target.value
          onEntryErrorChange?.(e.target.validity.badInput ? { kind: 'format' } : v && min && v < min ? { kind: 'outOfRange' } : null)
          onChange(v || undefined)
        }} />
    </Field>
  )
}

// ── 고르기 ────────────────────────────────────────────
// 둘 중 하나, 셋 중 하나를 고르는 칸. 라디오 버튼이라 키보드·화면 읽기 프로그램에서 그대로 고를 수 있다
type Choice = { name: string; value: string; onChange: (v: string) => void; disabled?: boolean }
const ChoiceContext = createContext<Choice | null>(null)

export function SegmentedControl({ label, value, onChange, isDisabled, size = 'md', layout, children }: {
  label: string; value: string; onChange: (v: string) => void; isDisabled?: boolean
  size?: 'sm' | 'md'; layout?: 'fill'; children: ReactNode
}) {
  const name = useId()
  return (
    <ChoiceContext.Provider value={{ name, value, onChange, disabled: isDisabled }}>
      <div role="radiogroup" aria-label={label} data-size={size}
        className={cn('segmented grid auto-cols-fr grid-flow-col gap-1 rounded-xl bg-muted p-1', layout !== 'fill' && 'w-fit')}>
        {children}
      </div>
    </ChoiceContext.Provider>
  )
}
export function SegmentedControlItem({ value, label }: { value: string; label: string }) {
  const ctx = useContext(ChoiceContext)!
  return (
    <label className="segmented-item">
      <input type="radio" className="segmented-input" name={ctx.name} value={value} checked={ctx.value === value}
        disabled={ctx.disabled} onChange={() => ctx.onChange(value)} />
      <span>{label}</span>
    </label>
  )
}

export function RadioList({ label, value, onChange, isDisabled, orientation, description, children }: {
  label: string; value: string; onChange: (v: string) => void; isDisabled?: boolean
  orientation?: 'horizontal' | 'vertical'; description?: ReactNode; children: ReactNode
}) {
  const name = useId()
  return (
    <ChoiceContext.Provider value={{ name, value, onChange, disabled: isDisabled }}>
      <fieldset className="m-0 flex min-w-0 flex-col gap-1.5 border-0 p-0">
        <legend className="mb-1.5 p-0 text-[13px] font-medium">{label}</legend>
        {description && <span className="text-[13px] text-muted-foreground break-keep">{description}</span>}
        <div className={cn('flex gap-2', orientation === 'horizontal' ? 'flex-row flex-wrap' : 'flex-col')}>{children}</div>
      </fieldset>
    </ChoiceContext.Provider>
  )
}
export function RadioListItem({ value, label }: { value: string; label: string }) {
  const ctx = useContext(ChoiceContext)!
  return (
    <label className="radio-item">
      <input type="radio" name={ctx.name} value={value} checked={ctx.value === value}
        disabled={ctx.disabled} onChange={() => ctx.onChange(value)} />
      <span>{label}</span>
    </label>
  )
}

// 체크 상자. 네이티브 입력이라 키보드·화면 읽기 프로그램이 그대로 쓴다. 색은 index.css 토큰(accent-color)으로만 정한다
export function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check-item">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

// ── 접기 ──────────────────────────────────────────────
export function Collapsible({ trigger, defaultIsOpen, isOpen, onOpenChange, children }: {
  trigger: ReactNode; defaultIsOpen?: boolean; isOpen?: boolean; onOpenChange?: (open: boolean) => void
  gap?: number; children: ReactNode
}) {
  return (
    <BaseCollapsible.Root defaultOpen={defaultIsOpen} open={isOpen} onOpenChange={(o) => onOpenChange?.(o)}>
      <BaseCollapsible.Trigger className="group flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 border-0 bg-transparent p-0 text-left text-foreground">
        <span className="min-w-0">{trigger}</span>
        <ChevronDownIcon className="size-5 shrink-0 text-muted-foreground transition-transform group-data-[panel-open]:rotate-180" aria-hidden />
      </BaseCollapsible.Trigger>
      <BaseCollapsible.Panel>{children}</BaseCollapsible.Panel>
    </BaseCollapsible.Root>
  )
}

export { Dock, DockProvider } from './dock'
export { BottomSheet, ChoiceRow } from './sheet'

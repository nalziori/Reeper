import { Banner } from '@astryxdesign/core/Banner'
import type { Rules, Step } from '../api'
import { AnalysisCard } from './AnalysisCard'

// 답장을 읽은 직후의 대체 경고와 참고용 분석. 읽은 결과가 waiting·agreed로 가도 보여야 한다.
export function ReplyReading({ step, rules }: { step: Step; rules: Rules }) {
  const canFix = ['waiting', 'negotiating', 'escalated'].includes(step.case.stage)
  return (
    <>
      {step.llm_fallback && (
        <Banner status="warning" collapsible={false}
          title={canFix
            ? '답장을 자동으로 못 읽어 낱말로 짐작했어요. 틀리면 버튼으로 고쳐 주세요'
            : '답장을 자동으로 못 읽어 낱말로 짐작했어요. 지금 단계가 맞는지 꼭 확인해 주세요'} />
      )}
      {step.analysis && <AnalysisCard analysis={step.analysis} rules={rules} />}
    </>
  )
}

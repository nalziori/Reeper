import { InternationalizationProvider } from '@astryxdesign/core/i18n'
import koKR from '@astryxdesign/core/locales/ko-KR.generated.js'
import { Theme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral/built'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* 날짜 오류, 달력 버튼 같은 컴포넌트 기본 문구를 한국어로 */}
    <InternationalizationProvider locale="ko-KR" messages={{ 'ko-KR': koKR }}>
      <Theme theme={neutralTheme}>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </Theme>
    </InternationalizationProvider>
  </StrictMode>,
)

import { Button } from '@astryxdesign/core/Button'
import { HStack } from '@astryxdesign/core/HStack'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/VStack'
import { useState } from 'react'
import type { Case, Rules } from '../api'
import { buildJson, buildSummary, fileName } from '../exportCase'
import { Fold } from './Fold'

function save(text: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function ExportMenu({ c, rules }: { c: Case; rules: Rules }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState('')
  return (
    <Fold title="사건 파일 내보내기" summary="요약이나 보관용 파일로 저장해요. 서버로 보내지 않아요">
      <VStack gap={3}>
        <HStack gap={2} wrap="wrap">
          <Button label={copied ? '복사됨' : '요약 복사'} onClick={async () => {
            try {
              await navigator.clipboard.writeText(buildSummary(c, rules))
              setCopied(true)
              setCopyError('')
            } catch {
              setCopied(false)
              setCopyError('복사하지 못했습니다. 요약 파일로 저장해 주세요.')
            }
          }} />
          <Button label="요약 파일 저장(.txt)" onClick={() =>
            save(buildSummary(c, rules), fileName(c, 'txt'), 'text/plain;charset=utf-8')} />
          <Button label="보관용 파일 저장(.json)" onClick={() =>
            save(buildJson(c), fileName(c, 'json'), 'application/json;charset=utf-8')} />
        </HStack>
        {copyError && <Text as="p" role="alert">{copyError}</Text>}
      </VStack>
    </Fold>
  )
}

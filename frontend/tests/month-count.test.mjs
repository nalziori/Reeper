import assert from 'node:assert/strict'
import { test } from 'node:test'
import { withSuggestedMonthCount } from '../src/contractCheck.ts'

const contract = { unit: 'month', start_date: '2026-11-05', end_date: '2027-02-04' }

test('fills whole months for inclusive and anniversary end dates', () => {
  assert.equal(withSuggestedMonthCount(contract).total_count, 3)
  assert.equal(withSuggestedMonthCount({ ...contract, end_date: '2027-02-05' }).total_count, 3)
  assert.equal(withSuggestedMonthCount({ ...contract, start_date: '2028-01-31', end_date: '2028-02-29' }).total_count, 1)
})

test('leaves partial, missing, invalid and reversed periods blank', () => {
  for (const end_date of ['2027-02-02', '', '2027-02-30', '2026-11-01']) {
    assert.equal(withSuggestedMonthCount({ ...contract, end_date }).total_count, undefined)
  }
})

test('preserves entered values, deliberate clears, and non-month units', () => {
  for (const total_count of [4, null]) {
    assert.equal(withSuggestedMonthCount({ ...contract, total_count }).total_count, total_count)
  }
  assert.equal(withSuggestedMonthCount({ ...contract, unit: 'count' }).total_count, undefined)
})

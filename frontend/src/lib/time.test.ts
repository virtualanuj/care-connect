import { describe, expect, it } from 'vitest'

import { addDays, formatDateTime, formatTime, todayIn } from './time'

describe('time helpers (clinic time zone, not the browser zone)', () => {
  it('formats an instant as 24-hour clock time in the given zone', () => {
    expect(formatTime('2026-03-02T03:30:00Z', 'Asia/Kolkata')).toBe('09:00')
    expect(formatTime('2026-03-02T03:30:00Z', 'UTC')).toBe('03:30')
    expect(formatTime('2026-03-02T15:05:00Z', 'America/New_York')).toBe('10:05')
  })

  it('formats a date and time with the weekday', () => {
    expect(formatDateTime('2026-03-02T03:30:00Z', 'Asia/Kolkata')).toBe('Mon 2 Mar 2026, 09:00')
  })

  it('returns today in the clinic zone, which can differ from UTC', () => {
    const lateEveningUtc = new Date('2026-03-01T20:00:00Z') // already Monday 01:30 in Kolkata
    expect(todayIn('UTC', lateEveningUtc)).toBe('2026-03-01')
    expect(todayIn('Asia/Kolkata', lateEveningUtc)).toBe('2026-03-02')
  })

  it('adds days to a calendar date string, across month ends', () => {
    expect(addDays('2026-03-02', 1)).toBe('2026-03-03')
    expect(addDays('2026-02-28', 1)).toBe('2026-03-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
  })
})

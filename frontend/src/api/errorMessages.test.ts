import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { ERROR_MESSAGES, messageForError } from './errorMessages'

describe('messageForError', () => {
  it('uses the friendly message for a known API error code', () => {
    const error = new ApiError('SLOT_ALREADY_BOOKED', 'raw server text', 409)

    expect(messageForError(error)).toBe(ERROR_MESSAGES.SLOT_ALREADY_BOOKED)
    expect(messageForError(error)).not.toContain('raw server text')
  })

  it('distinguishes doctor and patient double-booking', () => {
    expect(ERROR_MESSAGES.SLOT_ALREADY_BOOKED).not.toBe(ERROR_MESSAGES.PATIENT_ALREADY_BOOKED)
  })

  it('falls back to a generic message for non-API errors', () => {
    expect(messageForError(new Error('boom'))).toBe(ERROR_MESSAGES.INTERNAL_ERROR)
    expect(messageForError('weird')).toBe(ERROR_MESSAGES.INTERNAL_ERROR)
  })

  it('has a non-empty message for every code', () => {
    for (const message of Object.values(ERROR_MESSAGES)) {
      expect(message.trim().length).toBeGreaterThan(0)
    }
  })
})

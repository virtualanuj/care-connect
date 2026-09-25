import { describe, expect, it } from 'vitest'

import type { Slot } from '../booking/bookingApi'
import { chooseWalkInTier } from './walkInTier'

const slot = (doctorId: string, start: string, isEmergency = false): Slot => ({
  doctorId,
  specialtyId: 's1',
  startTime: start,
  endTime: start,
  isEmergency,
})

const D1 = 'd1'
const D2 = 'd2'

describe('walk-in fallback order', () => {
  it('offers the requested doctor first whenever they have regular slots', () => {
    const doctorSlots = [slot(D1, '2026-03-02T04:00:00Z')]
    const result = chooseWalkInTier({
      doctorId: D1,
      doctorSlots,
      specialtySlots: [...doctorSlots, slot(D2, '2026-03-02T03:00:00Z')],
      emergencySlots: [slot(D1, '2026-03-02T05:00:00Z', true)],
    })

    expect(result.tier).toBe('doctor')
    expect(result.slots).toEqual(doctorSlots)
  })

  it('falls back to other doctors of the specialty when the doctor has none', () => {
    const others = [slot(D2, '2026-03-02T03:00:00Z'), slot('d3', '2026-03-02T03:20:00Z')]
    const result = chooseWalkInTier({
      doctorId: D1,
      doctorSlots: [],
      specialtySlots: others,
      emergencySlots: [slot(D1, '2026-03-02T05:00:00Z', true)],
    })

    expect(result.tier).toBe('specialty')
    expect(result.slots).toEqual(others)
  })

  it('never lists the requested doctor inside the specialty tier', () => {
    const result = chooseWalkInTier({
      doctorId: D1,
      doctorSlots: [],
      specialtySlots: [slot(D1, '2026-03-02T03:00:00Z'), slot(D2, '2026-03-02T03:00:00Z')],
      emergencySlots: [],
    })

    expect(result.slots.map((s) => s.doctorId)).toEqual([D2])
  })

  it('uses held-back emergency capacity only when no regular slot exists anywhere', () => {
    const result = chooseWalkInTier({
      doctorId: D1,
      doctorSlots: [],
      specialtySlots: [],
      emergencySlots: [
        slot(D2, '2026-03-02T03:00:00Z', true),
        slot(D1, '2026-03-02T05:00:00Z', true),
        slot(D2, '2026-03-02T02:00:00Z', false), // a regular slot is not emergency capacity
      ],
    })

    expect(result.tier).toBe('emergency')
    expect(result.slots.map((s) => [s.doctorId, s.startTime])).toEqual([
      [D1, '2026-03-02T05:00:00Z'], // the requested doctor first
      [D2, '2026-03-02T03:00:00Z'],
    ])
  })

  it('reports none when nothing at all is available', () => {
    expect(
      chooseWalkInTier({ doctorId: D1, doctorSlots: [], specialtySlots: [], emergencySlots: [] }),
    ).toEqual({ tier: 'none', slots: [] })
  })
})

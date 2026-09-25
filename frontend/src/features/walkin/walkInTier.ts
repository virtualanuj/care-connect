import type { Slot } from '../booking/bookingApi'

export type Tier = 'doctor' | 'specialty' | 'emergency' | 'none'

export interface TierInput {
  doctorId: string
  /** Regular slots of the requested doctor. */
  doctorSlots: Slot[]
  /** Regular slots of every active doctor in the requested doctor's specialty. */
  specialtySlots: Slot[]
  /** Slots from a search that includes held-back emergency capacity. */
  emergencySlots: Slot[]
}

/**
 * The walk-in fallback order (docs/spec.md §4): the requested doctor, then other doctors in the
 * same specialty, then held-back emergency capacity (which still needs authorization).
 */
export function chooseWalkInTier(input: TierInput): { tier: Tier; slots: Slot[] } {
  if (input.doctorSlots.length > 0) return { tier: 'doctor', slots: input.doctorSlots }

  const others = input.specialtySlots.filter((s) => s.doctorId !== input.doctorId)
  if (others.length > 0) return { tier: 'specialty', slots: others }

  const emergency = input.emergencySlots
    .filter((s) => s.isEmergency)
    .sort((a, b) => {
      const mine = Number(b.doctorId === input.doctorId) - Number(a.doctorId === input.doctorId)
      return mine !== 0 ? mine : a.startTime.localeCompare(b.startTime)
    })
  if (emergency.length > 0) return { tier: 'emergency', slots: emergency }

  return { tier: 'none', slots: [] }
}

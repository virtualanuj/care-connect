import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useClinicSettings } from '../settings/settingsApi'
import type { Patient } from '../patients/patientsApi'
import ConfirmBooking from './ConfirmBooking'
import PatientPicker from './PatientPicker'
import SlotSearch from './SlotSearch'
import type { Slot, SlotQuery } from './bookingApi'

type Step =
  | { name: 'slots' }
  | { name: 'patient'; slot: Slot; doctorName: string }
  | { name: 'confirm'; slot: Slot; doctorName: string; patient: Patient }

export default function BookingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const settings = useClinicSettings()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const [applied, setApplied] = useState<SlotQuery | null>(null)
  const [step, setStep] = useState<Step>({ name: 'slots' })

  return (
    <section>
      <h1>Book appointment</h1>
      {step.name === 'slots' && (
        <SlotSearch
          applied={applied}
          timeZone={timeZone}
          onSearch={setApplied}
          onPick={(slot, doctorName) => setStep({ name: 'patient', slot, doctorName })}
        />
      )}
      {step.name === 'patient' && (
        <PatientPicker
          slot={step.slot}
          doctorName={step.doctorName}
          timeZone={timeZone}
          onBack={() => setStep({ name: 'slots' })}
          onContinue={(patient) =>
            setStep({ name: 'confirm', slot: step.slot, doctorName: step.doctorName, patient })
          }
        />
      )}
      {step.name === 'confirm' && (
        <ConfirmBooking
          slot={step.slot}
          doctorName={step.doctorName}
          patient={step.patient}
          timeZone={timeZone}
          onBack={() => setStep({ name: 'patient', slot: step.slot, doctorName: step.doctorName })}
          onRefresh={() => {
            void queryClient.invalidateQueries({ queryKey: ['slots'] })
            setStep({ name: 'slots' })
          }}
          onBooked={(appointment) => {
            void queryClient.invalidateQueries({ queryKey: ['slots'] })
            void queryClient.invalidateQueries({ queryKey: ['appointments'] })
            navigate(`/appointments/${appointment.id}`)
          }}
        />
      )}
    </section>
  )
}

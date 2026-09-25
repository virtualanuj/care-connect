import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import ConfirmBooking from '../booking/ConfirmBooking'
import PatientPicker from '../booking/PatientPicker'
import type { Slot } from '../booking/bookingApi'
import type { Patient } from '../patients/patientsApi'
import { useClinicSettings } from '../settings/settingsApi'
import WalkInSlots from './WalkInSlots'

type Step =
  | { name: 'patient' }
  | { name: 'slots'; patient: Patient }
  | { name: 'confirm'; patient: Patient; slot: Slot; doctorName: string }

export default function WalkInPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const settings = useClinicSettings()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const [step, setStep] = useState<Step>({ name: 'patient' })

  return (
    <section>
      <h1>Register walk-in</h1>
      {step.name === 'patient' && (
        <PatientPicker
          summary="Who is walking in?"
          onContinue={(patient) => setStep({ name: 'slots', patient })}
        />
      )}
      {step.name === 'slots' && (
        <WalkInSlots
          timeZone={timeZone}
          onBack={() => setStep({ name: 'patient' })}
          onPick={(slot, doctorName) =>
            setStep({ name: 'confirm', patient: step.patient, slot, doctorName })
          }
        />
      )}
      {step.name === 'confirm' && (
        <ConfirmBooking
          walkIn
          slot={step.slot}
          doctorName={step.doctorName}
          patient={step.patient}
          timeZone={timeZone}
          onBack={() => setStep({ name: 'slots', patient: step.patient })}
          onRefresh={() => {
            void queryClient.invalidateQueries({ queryKey: ['slots'] })
            setStep({ name: 'slots', patient: step.patient })
          }}
          onBooked={(appointment) => {
            void queryClient.invalidateQueries({ queryKey: ['queue'] })
            void queryClient.invalidateQueries({ queryKey: ['slots'] })
            navigate(`/appointments/${appointment.id}`)
          }}
        />
      )}
    </section>
  )
}

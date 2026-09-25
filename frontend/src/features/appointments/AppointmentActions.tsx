import { useState } from 'react'

import { useDoctors } from '../../api/referenceHooks'
import { useAuth } from '../../auth/useAuth'
import { useToast } from '../../components/Toast'
import { useClinicSettings } from '../settings/settingsApi'
import { useAppointmentAction, type Action } from './actionsApi'
import type { Appointment } from './appointmentsApi'
import { CancelDialog, ForceCancelDialog } from './CancelDialogs'
import FollowUpDialog from './FollowUpDialog'
import RescheduleDialog from './RescheduleDialog'

type Dialog = 'cancel' | 'force' | 'reschedule' | 'follow-up' | null

const LIFECYCLE: { action: Action; label: string; from: Appointment['status'][] }[] = [
  { action: 'check-in', label: 'Check in', from: ['booked'] },
  { action: 'start-consultation', label: 'Start consultation', from: ['checked_in'] },
  { action: 'complete', label: 'Complete', from: ['in_consultation'] },
  { action: 'no-show', label: 'No-show', from: ['booked', 'checked_in'] },
]

/** Status- and role-dependent actions. The server enforces every rule; this only hides. */
export default function AppointmentActions({ appointment }: { appointment: Appointment }) {
  const { user } = useAuth()
  const { showError } = useToast()
  const doctors = useDoctors()
  const settings = useClinicSettings()
  const act = useAppointmentAction(appointment.id)
  const [dialog, setDialog] = useState<Dialog>(null)

  const isFrontDesk = user?.role === 'front_desk_admin'
  const ownDoctor = doctors.data?.find((d) => d.userId === user?.id)
  const canAct = isFrontDesk || (ownDoctor !== undefined && ownDoctor.id === appointment.doctorId)
  if (!canAct) return null

  const status = appointment.status
  const cancellable = status === 'booked' || status === 'checked_in'
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'

  async function run(action: Action) {
    try {
      await act.mutateAsync({ action })
    } catch (error) {
      showError(error)
    }
  }

  return (
    <div className="actions">
      {LIFECYCLE.filter((a) => a.from.includes(status)).map((a) => (
        <button key={a.action} type="button" disabled={act.isPending} onClick={() => run(a.action)}>
          {a.label}
        </button>
      ))}
      {cancellable && (
        <button type="button" onClick={() => setDialog('cancel')}>
          Cancel
        </button>
      )}
      {status === 'booked' && (
        <button type="button" onClick={() => setDialog('reschedule')}>
          Reschedule
        </button>
      )}
      {cancellable && isFrontDesk && (
        <button type="button" onClick={() => setDialog('force')}>
          Force cancel
        </button>
      )}
      {status === 'completed' && (
        <button type="button" onClick={() => setDialog('follow-up')}>
          Book follow-up
        </button>
      )}

      {dialog === 'cancel' && (
        <CancelDialog
          appointmentId={appointment.id}
          cutoffHours={settings.data?.cancellationCutoffHours}
          canForce={isFrontDesk}
          onClose={() => setDialog(null)}
          onForce={() => setDialog('force')}
        />
      )}
      {dialog === 'force' && (
        <ForceCancelDialog appointmentId={appointment.id} onClose={() => setDialog(null)} />
      )}
      {dialog === 'reschedule' && (
        <RescheduleDialog
          appointment={appointment}
          timeZone={timeZone}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'follow-up' && (
        <FollowUpDialog
          appointment={appointment}
          timeZone={timeZone}
          maxDays={settings.data?.followUpMaxDays}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  )
}

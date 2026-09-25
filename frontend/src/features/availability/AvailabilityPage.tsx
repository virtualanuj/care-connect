import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../../auth/useAuth'
import { useToast } from '../../components/Toast'
import ExceptionDialog from './ExceptionDialog'
import RuleDialog from './RuleDialog'
import {
  DAYS,
  useDeleteException,
  useDeleteRule,
  useDoctor,
  useExceptions,
  useRules,
  type ExceptionItem,
  type Rule,
} from './availabilityApi'

const span = (rule: Rule) => `${rule.startTime}–${rule.endTime}`

function describe(exception: ExceptionItem): string {
  const times =
    exception.startTime && exception.endTime ? ` ${exception.startTime}–${exception.endTime}` : ''
  if (exception.type === 'extra_hours') return `Extra hours${times}`
  return times ? `Unavailable${times}` : 'Unavailable all day'
}

type Dialog =
  { kind: 'add-rule' } | { kind: 'edit-rule'; rule: Rule } | { kind: 'add-exception' } | null

export default function AvailabilityPage() {
  const { doctorId = '' } = useParams()
  const { user } = useAuth()
  const { showError } = useToast()
  const doctor = useDoctor(doctorId)
  const rules = useRules(doctorId)
  const exceptions = useExceptions(doctorId)
  const deleteRule = useDeleteRule(doctorId)
  const deleteException = useDeleteException(doctorId)
  const [dialog, setDialog] = useState<Dialog>(null)

  const canEdit = user?.role === 'front_desk_admin' || doctor.data?.userId === user?.id

  async function remove(action: () => Promise<unknown>) {
    try {
      await action()
    } catch (error) {
      showError(error)
    }
  }

  if (doctor.isPending) return <p role="status">Loading…</p>
  if (doctor.isError) return <p role="alert">Doctor not found.</p>

  return (
    <section>
      <p>
        <Link to="/doctors">← Doctors</Link>
      </p>
      <div className="page-header">
        <h1>Availability — {doctor.data.name}</h1>
        {canEdit && (
          <button type="button" onClick={() => setDialog({ kind: 'add-rule' })}>
            Add hours
          </button>
        )}
      </div>
      <p>Times are in the clinic time zone.</p>

      <table>
        <tbody>
          {DAYS.map((day) => {
            const windows = (rules.data ?? []).filter((r) => r.dayOfWeek === day.value)
            return (
              <tr key={day.value}>
                <th scope="row">{day.label}</th>
                <td>
                  {windows.length === 0 && <span>Not working</span>}
                  {windows.map((rule) => (
                    <span key={rule.id} className="window">
                      {span(rule)}
                      {canEdit && (
                        <>
                          <button
                            type="button"
                            aria-label={`Edit ${day.label} ${span(rule)}`}
                            onClick={() => setDialog({ kind: 'edit-rule', rule })}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            aria-label={`Remove ${day.label} ${span(rule)}`}
                            onClick={() => remove(() => deleteRule.mutateAsync(rule.id))}
                          >
                            Remove
                          </button>
                        </>
                      )}
                    </span>
                  ))}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="page-header">
        <h2>Exceptions</h2>
        {canEdit && (
          <button type="button" onClick={() => setDialog({ kind: 'add-exception' })}>
            Add exception
          </button>
        )}
      </div>
      {exceptions.data && exceptions.data.length === 0 && <p>No exceptions.</p>}
      {exceptions.data && exceptions.data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>What</th>
              {canEdit && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {exceptions.data.map((e) => (
              <tr key={e.id}>
                <td>{e.date}</td>
                <td>{describe(e)}</td>
                {canEdit && (
                  <td>
                    <button
                      type="button"
                      aria-label={`Remove exception ${e.date}`}
                      onClick={() => remove(() => deleteException.mutateAsync(e.id))}
                    >
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {dialog?.kind === 'add-rule' && (
        <RuleDialog doctorId={doctorId} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'edit-rule' && (
        <RuleDialog doctorId={doctorId} rule={dialog.rule} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'add-exception' && (
        <ExceptionDialog doctorId={doctorId} onClose={() => setDialog(null)} />
      )}
    </section>
  )
}

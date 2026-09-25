import { Link } from 'react-router-dom'

import { useToast } from '../../components/Toast'
import { formatTime } from '../../lib/time'
import { useAppointmentAction } from '../appointments/actionsApi'
import { LIFECYCLE } from '../appointments/lifecycle'
import type { QueueItem } from './queueApi'

export default function QueueRow({ item, timeZone }: { item: QueueItem; timeZone: string }) {
  const { showError } = useToast()
  const act = useAppointmentAction(item.id)
  const actions = LIFECYCLE.filter((a) => a.from.includes(item.status))

  return (
    <li className="queue-item">
      <div>
        <strong>{formatTime(item.startTime, timeZone)}</strong>{' '}
        <Link to={`/appointments/${item.id}`}>{item.patientName}</Link>
        <div>
          <small>{item.doctorName}</small>
          {item.source === 'walk_in' && <span className="badge">Walk-in</span>}
          {item.isEmergencySlot && <span className="badge badge-emergency">Emergency</span>}
        </div>
      </div>
      {actions.length > 0 && (
        <div className="row-actions">
          {actions.map((a) => (
            <button
              key={a.action}
              type="button"
              aria-label={`${a.label} ${item.patientName}`}
              disabled={act.isPending}
              onClick={async () => {
                try {
                  await act.mutateAsync({ action: a.action })
                } catch (error) {
                  showError(error)
                }
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </li>
  )
}

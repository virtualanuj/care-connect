import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../auth/useAuth'
import { useClinicSettings } from '../settings/settingsApi'
import QueueRow from './QueueRow'
import { useQueue, type DailyQueue, type QueueItem } from './queueApi'

const COLUMNS: { key: keyof Omit<DailyQueue, 'date'>; title: string }[] = [
  { key: 'booked', title: 'Booked' },
  { key: 'checkedIn', title: 'Checked in' },
  { key: 'inProgress', title: 'In consultation' },
  { key: 'completed', title: 'Completed' },
  { key: 'noShows', title: 'No-show' },
  { key: 'cancelled', title: 'Cancelled' },
]

export default function QueuePage() {
  const { user } = useAuth()
  const settings = useClinicSettings()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const [chosen, setChosen] = useState('')
  const queue = useQueue(chosen)

  return (
    <section>
      <div className="page-header">
        <h1>Today&apos;s queue</h1>
        {user?.role === 'front_desk_admin' && <Link to="/walk-in">Register walk-in</Link>}
      </div>
      <label>
        Date
        <input
          type="date"
          value={chosen || queue.data?.date || ''}
          onChange={(e) => setChosen(e.target.value)}
        />
      </label>

      {queue.isError && <p role="alert">Could not load the queue.</p>}
      {queue.isPending && <p role="status">Loading…</p>}
      {queue.data && (
        <div className="queue">
          {COLUMNS.map(({ key, title }) => {
            const items: QueueItem[] = queue.data[key]
            return (
              <section key={key} className="queue-column">
                <h2>{`${title} (${items.length})`}</h2>
                {items.length === 0 ? (
                  <p>Nobody here</p>
                ) : (
                  <ul>
                    {items.map((item) => (
                      <QueueRow key={item.id} item={item} timeZone={timeZone} />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
      )}
    </section>
  )
}

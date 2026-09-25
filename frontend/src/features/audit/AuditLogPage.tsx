import { useState } from 'react'

import { messageForError } from '../../api/errorMessages'
import { formatDateTime } from '../../lib/time'
import { useClinicSettings } from '../settings/settingsApi'
import {
  ACTION_LABELS,
  AUDIT_PAGE_SIZE,
  useAuditLog,
  useStaffNames,
  type AuditAction,
} from './auditApi'

export default function AuditLogPage() {
  const [action, setAction] = useState<AuditAction | ''>('')
  const [page, setPage] = useState(1)
  const log = useAuditLog(action, page)
  const names = useStaffNames()
  const settings = useClinicSettings()
  const timeZone = settings.data?.clinicTimezone ?? 'UTC'
  const totalPages = Math.max(1, Math.ceil((log.data?.total ?? 0) / AUDIT_PAGE_SIZE))

  return (
    <section>
      <h1>Audit log</h1>
      <label>
        Action
        <select
          value={action}
          onChange={(e) => {
            setAction(e.target.value as AuditAction | '')
            setPage(1)
          }}
        >
          <option value="">All actions</option>
          {(Object.keys(ACTION_LABELS) as AuditAction[]).map((a) => (
            <option key={a} value={a}>
              {ACTION_LABELS[a]}
            </option>
          ))}
        </select>
      </label>

      {log.isError && <p role="alert">{messageForError(log.error)}</p>}
      {log.isPending && <p role="status">Loading…</p>}
      {log.data && log.data.items.length === 0 && <p>No audit entries.</p>}
      {log.data && log.data.items.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>By</th>
                <th>Target</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {log.data.items.map((e) => (
                <tr key={e.id}>
                  <td>{formatDateTime(e.createdAt, timeZone)}</td>
                  <td>{ACTION_LABELS[e.action]}</td>
                  <td>{names.data?.get(e.actorId) ?? e.actorId.slice(0, 8)}</td>
                  <td>{`${e.targetType} ${e.targetId.slice(0, 8)}`}</td>
                  <td>{e.reason ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
    </section>
  )
}

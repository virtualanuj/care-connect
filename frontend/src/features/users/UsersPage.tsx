import { useState } from 'react'

import { useToast } from '../../components/Toast'
import { useAuth } from '../../auth/useAuth'
import ResetPasswordDialog from './ResetPasswordDialog'
import UserFormDialog from './UserFormDialog'
import { PAGE_SIZE, useUpdateUser, useUsers, type UserItem } from './usersApi'

type Dialog =
  { kind: 'create' } | { kind: 'edit'; user: UserItem } | { kind: 'reset'; user: UserItem } | null

const ROLE_LABELS: Record<UserItem['role'], string> = {
  doctor: 'doctor',
  front_desk_admin: 'front desk',
}

export default function UsersPage() {
  const { user: me } = useAuth()
  const { showError } = useToast()
  const [page, setPage] = useState(1)
  const [dialog, setDialog] = useState<Dialog>(null)
  const users = useUsers(page)
  const update = useUpdateUser()

  const totalPages = Math.max(1, Math.ceil((users.data?.total ?? 0) / PAGE_SIZE))

  async function toggleActive(target: UserItem) {
    try {
      await update.mutateAsync({ id: target.id, body: { active: !target.active } })
    } catch (error) {
      showError(error)
    }
  }

  return (
    <section>
      <div className="page-header">
        <h1>Users</h1>
        <button type="button" onClick={() => setDialog({ kind: 'create' })}>
          New user
        </button>
      </div>

      {users.isError && <p role="alert">Could not load users.</p>}
      {users.isPending && <p role="status">Loading…</p>}

      {users.data && (
        <>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>{ROLE_LABELS[u.role]}</td>
                  <td>{u.active ? 'Active' : 'Inactive'}</td>
                  <td className="row-actions">
                    <button type="button" onClick={() => setDialog({ kind: 'edit', user: u })}>
                      Edit
                    </button>
                    <button type="button" onClick={() => setDialog({ kind: 'reset', user: u })}>
                      Reset password
                    </button>
                    <button
                      type="button"
                      disabled={u.id === me?.id || update.isPending}
                      onClick={() => toggleActive(u)}
                    >
                      {u.active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

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
        </>
      )}

      {dialog?.kind === 'create' && <UserFormDialog onClose={() => setDialog(null)} />}
      {dialog?.kind === 'edit' && (
        <UserFormDialog user={dialog.user} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'reset' && (
        <ResetPasswordDialog user={dialog.user} onClose={() => setDialog(null)} />
      )}
    </section>
  )
}

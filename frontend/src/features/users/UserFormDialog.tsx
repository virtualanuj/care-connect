import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { useCreateUser, useUpdateUser, type UserItem } from './usersApi'

export const MIN_PASSWORD_LENGTH = 12
export const PASSWORD_TOO_SHORT = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`

type Role = UserItem['role']
const ROLES: { value: Role; label: string }[] = [
  { value: 'doctor', label: 'Doctor' },
  { value: 'front_desk_admin', label: 'Front desk' },
]

interface Props {
  /** Existing user to edit; omit to create a new one. */
  user?: UserItem
  onClose: () => void
}

export default function UserFormDialog({ user, onClose }: Props) {
  const editing = user !== undefined
  const [email, setEmail] = useState('')
  const [name, setName] = useState(user?.name ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'doctor')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateUser()
  const update = useUpdateUser()
  const pending = create.isPending || update.isPending

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      if (editing) {
        const changes: { name?: string; role?: Role } = {}
        if (name !== user.name) changes.name = name
        if (role !== user.role) changes.role = role
        if (Object.keys(changes).length > 0)
          await update.mutateAsync({ id: user.id, body: changes })
      } else {
        if (password.length < MIN_PASSWORD_LENGTH) {
          setError(PASSWORD_TOO_SHORT)
          return
        }
        await create.mutateAsync({ email, name, role, password })
      }
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title={editing ? 'Edit user' : 'New user'} onClose={onClose}>
      <form onSubmit={onSubmit}>
        {!editing && (
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
        )}
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        {!editing && (
          <label>
            Password
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={pending}>
            {editing ? 'Save' : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

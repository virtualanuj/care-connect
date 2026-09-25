import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import Modal from '../../components/Modal'
import { MIN_PASSWORD_LENGTH, PASSWORD_TOO_SHORT } from './UserFormDialog'
import { useResetPassword, type UserItem } from './usersApi'

export default function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: UserItem
  onClose: () => void
}) {
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const reset = useResetPassword()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(PASSWORD_TOO_SHORT)
      return
    }
    try {
      await reset.mutateAsync({ id: user.id, newPassword })
      onClose()
    } catch (caught) {
      setError(messageForError(caught))
    }
  }

  return (
    <Modal title="Reset password" onClose={onClose}>
      <p>
        Set a new password for <strong>{user.name}</strong>.
      </p>
      <form onSubmit={onSubmit}>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={reset.isPending}>
            Reset
          </button>
        </div>
      </form>
    </Modal>
  )
}

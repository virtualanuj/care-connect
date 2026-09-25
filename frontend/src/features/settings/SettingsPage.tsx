import { useState, type FormEvent } from 'react'

import { messageForError } from '../../api/errorMessages'
import { useAuth } from '../../auth/useAuth'
import { toForm, validate, type FormState } from './validation'
import {
  useClinicSettings,
  useSpecialties,
  useUpdateClinicSettings,
  type ClinicSettings,
  type ClinicSettingsUpdate,
  type SpecialtyItem,
} from './settingsApi'

function timeZones(current: string): string[] {
  const supported = Intl.supportedValuesOf('timeZone')
  return supported.includes(current) ? supported : [current, ...supported]
}

function SettingsForm({
  settings,
  specialties,
  canEdit,
}: {
  settings: ClinicSettings
  specialties: SpecialtyItem[]
  canEdit: boolean
}) {
  const [form, setForm] = useState(() => toForm(settings))
  const [errors, setErrors] = useState<ReturnType<typeof validate>>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const update = useUpdateClinicSettings()

  const set = (field: keyof FormState) => (value: string) => {
    setSaved(false)
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setServerError(null)
    setSaved(false)
    const found = validate(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    const original = toForm(settings)
    const changes: ClinicSettingsUpdate = {}
    if (form.cutoff !== original.cutoff) changes.cancellationCutoffHours = Number(form.cutoff)
    if (form.emergency !== original.emergency) {
      changes.emergencySlotsPerDoctorPerDay = Number(form.emergency)
    }
    if (form.followUp !== original.followUp) changes.followUpMaxDays = Number(form.followUp)
    if (form.timezone !== original.timezone) changes.clinicTimezone = form.timezone
    if (form.triageSpecialty !== original.triageSpecialty) {
      changes.defaultTriageSpecialtyId = form.triageSpecialty || null
    }
    if (Object.keys(changes).length === 0) return

    try {
      await update.mutateAsync(changes)
      setSaved(true)
    } catch (error) {
      setServerError(messageForError(error))
    }
  }

  return (
    <form onSubmit={onSubmit} className="settings-form">
      {!canEdit && <p>Only front-desk staff can change these settings.</p>}
      <label>
        Cancellation cutoff (hours)
        <input
          type="number"
          step="0.25"
          value={form.cutoff}
          disabled={!canEdit}
          onChange={(e) => set('cutoff')(e.target.value)}
        />
      </label>
      {errors.cutoff && <p role="alert">{errors.cutoff}</p>}
      <label>
        Emergency slots per doctor per day
        <input
          type="number"
          value={form.emergency}
          disabled={!canEdit}
          onChange={(e) => set('emergency')(e.target.value)}
        />
      </label>
      {errors.emergency && <p role="alert">{errors.emergency}</p>}
      <label>
        Follow-up window (days)
        <input
          type="number"
          value={form.followUp}
          disabled={!canEdit}
          onChange={(e) => set('followUp')(e.target.value)}
        />
      </label>
      {errors.followUp && <p role="alert">{errors.followUp}</p>}
      <label>
        Clinic time zone
        <select
          value={form.timezone}
          disabled={!canEdit}
          onChange={(e) => set('timezone')(e.target.value)}
        >
          {timeZones(settings.clinicTimezone).map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </label>
      <label>
        Default triage specialty
        <select
          value={form.triageSpecialty}
          disabled={!canEdit}
          onChange={(e) => set('triageSpecialty')(e.target.value)}
        >
          <option value="">None</option>
          {specialties.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      {serverError && <p role="alert">{serverError}</p>}
      {saved && <p role="status">Settings saved</p>}
      {canEdit && (
        <button type="submit" disabled={update.isPending}>
          Save settings
        </button>
      )}
    </form>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const settings = useClinicSettings()
  const specialties = useSpecialties()

  return (
    <section>
      <h1>Clinic settings</h1>
      {(settings.isPending || specialties.isPending) && <p role="status">Loading…</p>}
      {(settings.isError || specialties.isError) && <p role="alert">Could not load settings.</p>}
      {settings.data && specialties.data && (
        <SettingsForm
          settings={settings.data}
          specialties={specialties.data}
          canEdit={user?.role === 'front_desk_admin'}
        />
      )}
    </section>
  )
}

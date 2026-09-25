import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  useDoctors,
  useSpecialties,
  type DoctorItem,
  type SpecialtyItem,
} from '../../api/referenceHooks'
import { useAuth } from '../../auth/useAuth'
import { useToast } from '../../components/Toast'
import DoctorFormDialog from './DoctorFormDialog'
import SpecialtyDialog from './SpecialtyDialog'
import { useUpdateDoctor } from './doctorsApi'

type Dialog =
  | { kind: 'new-doctor' }
  | { kind: 'edit-doctor'; doctor: DoctorItem }
  | { kind: 'new-specialty' }
  | { kind: 'edit-specialty'; specialty: SpecialtyItem }
  | null

export default function DoctorsPage() {
  const { user } = useAuth()
  const { showError } = useToast()
  const doctors = useDoctors()
  const specialties = useSpecialties()
  const update = useUpdateDoctor()
  const [dialog, setDialog] = useState<Dialog>(null)
  const isFrontDesk = user?.role === 'front_desk_admin'

  const specialtyName = (id: string) => specialties.data?.find((s) => s.id === id)?.name ?? '—'

  async function toggleActive(doctor: DoctorItem) {
    try {
      await update.mutateAsync({ id: doctor.id, body: { active: !doctor.active } })
    } catch (error) {
      showError(error)
    }
  }

  return (
    <section>
      <div className="page-header">
        <h1>Doctors</h1>
        {isFrontDesk && (
          <button type="button" onClick={() => setDialog({ kind: 'new-doctor' })}>
            New doctor
          </button>
        )}
      </div>

      {(doctors.isPending || specialties.isPending) && <p role="status">Loading…</p>}
      {(doctors.isError || specialties.isError) && <p role="alert">Could not load doctors.</p>}

      {doctors.data && specialties.data && (
        <>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Specialty</th>
                <th>Slot length</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {doctors.data.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{specialtyName(d.specialtyId)}</td>
                  <td>{d.slotLengthMinutes} min</td>
                  <td>{d.active ? 'Active' : 'Inactive'}</td>
                  <td className="row-actions">
                    <Link to={`/doctors/${d.id}/availability`}>Availability</Link>
                    {(isFrontDesk || d.userId === user?.id) && (
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: 'edit-doctor', doctor: d })}
                      >
                        Edit
                      </button>
                    )}
                    {isFrontDesk && (
                      <button
                        type="button"
                        disabled={update.isPending}
                        onClick={() => toggleActive(d)}
                      >
                        {d.active ? 'Deactivate' : 'Activate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="page-header">
            <h2>Specialties</h2>
            {isFrontDesk && (
              <button type="button" onClick={() => setDialog({ kind: 'new-specialty' })}>
                New specialty
              </button>
            )}
          </div>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Default slot length</th>
                {isFrontDesk && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {specialties.data.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.defaultSlotLengthMinutes} min</td>
                  {isFrontDesk && (
                    <td>
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: 'edit-specialty', specialty: s })}
                      >
                        Edit specialty
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {(dialog?.kind === 'new-doctor' || dialog?.kind === 'edit-doctor') &&
        doctors.data &&
        specialties.data && (
          <DoctorFormDialog
            doctor={dialog.kind === 'edit-doctor' ? dialog.doctor : undefined}
            doctors={doctors.data}
            specialties={specialties.data}
            onClose={() => setDialog(null)}
          />
        )}
      {dialog?.kind === 'new-specialty' && <SpecialtyDialog onClose={() => setDialog(null)} />}
      {dialog?.kind === 'edit-specialty' && (
        <SpecialtyDialog specialty={dialog.specialty} onClose={() => setDialog(null)} />
      )}
    </section>
  )
}

import { execFileSync } from 'node:child_process'

import { E2E } from '../playwright.config'

const RESET_SQL = [
  'from sqlalchemy import text',
  'from app.db.session import get_engine',
  'with get_engine().begin() as connection:',
  '    connection.execute(text(',
  "        'TRUNCATE audit_log, visit_notes, pre_visit_summaries, medical_history_entries, availability_exceptions, availability, '",
  "        'doctors, patients, specialties, users CASCADE'",
  '    ))',
  '    # CASCADE also emptied clinic_settings (it references specialties): restore the default row.',
  '    connection.execute(text(',
  '        "INSERT INTO clinic_settings (id, cancellation_cutoff_hours, "',
  '        "emergency_slots_per_doctor_per_day, follow_up_max_days, clinic_timezone) "',
  '        "VALUES (1, 2, 1, 30, \'Asia/Kolkata\')"',
  '    ))',
].join('\n')

/** Reset the application tables and seed the front-desk admin before the run. */
export default function globalSetup() {
  const databaseUrl = process.env.DATABASE_URL ?? 'localhost'
  if (!/@(localhost|127\.0\.0\.1)[:/]/.test(databaseUrl) && databaseUrl !== 'localhost') {
    throw new Error('Refusing to reset a database that is not on localhost')
  }

  const cwd = '../backend'
  const env = {
    ...process.env,
    SEED_ADMIN_EMAIL: E2E.adminEmail,
    SEED_ADMIN_PASSWORD: E2E.adminPassword,
  }
  execFileSync('uv', ['run', 'python', '-c', RESET_SQL], { cwd, env, stdio: 'inherit' })
  execFileSync('uv', ['run', 'python', '-m', 'app.db.seed'], { cwd, env, stdio: 'inherit' })
}

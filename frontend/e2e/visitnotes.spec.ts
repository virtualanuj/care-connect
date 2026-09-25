import { expect, test, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

// The dev doctor seeded by `python -m app.db.seed` (development only).
const DOCTOR = { email: 'doctor@clinic.test', password: 'dev doctor passphrase' }

/** The next date, at least two days ahead, falling on the given weekday (0 = Sunday). */
function upcoming(weekday: number): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 2)
  while (d.getUTCDay() !== weekday) d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
}

async function bookNineOClock(page: Page, date: string) {
  await page.goto('/book')
  await page.getByLabel('Date').fill(date)
  await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await page.getByRole('button', { name: '09:00' }).click()
  await page.getByLabel('Patient phone').fill('98765 43210')
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: /Kiran Rao/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
}

test('notes are drafted by AI, but only the doctor finalizes, and that locks the note', async ({
  page,
  browser,
}) => {
  await signIn(page, E2E.adminEmail, E2E.adminPassword)
  await bookNineOClock(page, upcoming(4)) // a Thursday
  const detail = page.url()

  // Pre-visit summary: nothing is generated until asked, and it carries the AI disclaimer.
  const summary = page.getByRole('region', { name: 'Pre-visit summary' })
  await expect(summary.getByText('No pre-visit summary yet.')).toBeVisible()
  await summary.getByRole('button', { name: 'Generate summary' }).click()
  await expect(summary.getByText(/\[dev previsit\]/)).toBeVisible()
  await expect(summary.getByText(/AI-generated/i)).toBeVisible()
  await expect(summary.getByRole('button', { name: 'Refresh summary' })).toBeVisible()

  // Notes only once the consultation has started.
  await expect(page.getByText(/once the consultation has started/i)).toBeVisible()
  await page.getByRole('button', { name: 'Check in' }).click()
  await page.getByRole('button', { name: 'Start consultation' }).click()
  await expect(page.getByText('In consultation', { exact: true })).toBeVisible()

  // Front-desk may write notes (autosaved on blur) and request an AI draft, but not finalize.
  await page.getByLabel('Visit notes').fill('Cough for a week. Chest clear.')
  await page.getByLabel('Visit notes').blur()
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Generate AI draft' }).click()
  const draft = page.getByRole('region', { name: 'AI draft' })
  await expect(draft.getByText(/\[dev draft\] Cough for a week/)).toBeVisible()
  await expect(draft.getByText(/AI-generated/i)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Finalize summary' })).toHaveCount(0)
  await expect(page.getByText(/only the appointment's doctor can finalize/i)).toBeVisible()

  // The appointment's doctor writes the final summary; the note is then locked.
  const doctorContext = await browser.newContext({ baseURL: E2E.baseURL })
  try {
    const doctorPage = await doctorContext.newPage()
    await signIn(doctorPage, DOCTOR.email, DOCTOR.password)
    await doctorPage.goto(detail)
    await expect(doctorPage.getByLabel('Visit notes')).toHaveValue('Cough for a week. Chest clear.')
    await doctorPage.getByRole('button', { name: 'Finalize summary' }).click()
    await expect(doctorPage.getByRole('alert')).toContainText(/final summary/i)
    await doctorPage.getByRole('button', { name: 'Use draft as final summary' }).click()
    await doctorPage.getByLabel('Final summary').fill('Viral cough. Rest and fluids.')
    await doctorPage.getByRole('button', { name: 'Finalize summary' }).click()

    await expect(doctorPage.getByText(/^Finalized/)).toBeVisible()
    await expect(doctorPage.getByText('Viral cough. Rest and fluids.')).toBeVisible()
    await expect(doctorPage.getByLabel('Visit notes')).not.toBeEditable()
    await expect(doctorPage.getByRole('button', { name: 'Finalize summary' })).toHaveCount(0)
  } finally {
    await doctorContext.close()
  }

  // Front-desk now sees the note as locked too.
  await page.reload()
  await expect(page.getByText(/^Finalized/)).toBeVisible()
  await expect(page.getByLabel('Visit notes')).not.toBeEditable()
})

import { expect, test, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

/** The next date, at least two days ahead, falling on the given weekday (0 = Sunday). */
function upcoming(weekday: number, extraDays = 0): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 2)
  while (d.getUTCDay() !== weekday) d.setUTCDate(d.getUTCDate() + 1)
  d.setUTCDate(d.getUTCDate() + extraDays)
  return d.toISOString().slice(0, 10)
}

async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
}

/** Book the 09:00 slot of the dev doctor on `date` for a patient found by phone. */
async function book(page: Page, date: string, phone: string, patient: string) {
  await page.goto('/book')
  await page.getByLabel('Date').fill(date)
  await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await page.getByRole('button', { name: '09:00' }).click()
  await page.getByLabel('Patient phone').fill(phone)
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: new RegExp(patient) }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
}

async function setCutoffHours(page: Page, hours: string) {
  await page.getByRole('link', { name: 'Settings' }).click()
  await page.getByLabel('Cancellation cutoff (hours)').fill(hours)
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Settings saved')).toBeVisible()
}

test('an appointment goes from booked to completed and a follow-up is booked from it', async ({
  page,
}) => {
  await signIn(page)
  await book(page, upcoming(2), '98765 43210', 'Kiran Rao') // a Tuesday

  await page.getByRole('button', { name: 'Check in' }).click()
  await expect(page.getByText('Checked in', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Start consultation' }).click()
  await expect(page.getByText('In consultation', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Complete' }).click()
  await expect(page.getByText('Completed', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Book follow-up' }).click()
  const dialog = page.getByRole('dialog', { name: 'Book follow-up' })
  await dialog.getByLabel('Date').fill(upcoming(2, 7))
  await dialog.getByRole('button', { name: 'Find slots' }).click()
  await dialog.getByRole('button', { name: '09:00' }).click()

  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  await expect(page.getByText('Booked', { exact: true })).toBeVisible()
  await page.goto('/appointments')
  await expect(page.getByRole('row', { name: /Kiran Rao.*Completed/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Kiran Rao.*Booked/ })).toBeVisible()
})

test('cancelling inside the cutoff is blocked and front-desk force-cancels with a reason', async ({
  page,
  request,
}) => {
  await signIn(page)
  await book(page, upcoming(3), '98765 43210', 'Asha Rao') // a Wednesday
  const detail = page.url()
  await setCutoffHours(page, '9000') // every upcoming appointment is now "inside the window"

  try {
    await page.goto(detail)
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    const cancel = page.getByRole('dialog', { name: 'Cancel appointment' })
    await cancel.getByRole('button', { name: 'Cancel appointment' }).click()
    await expect(cancel.getByRole('alert')).toContainText('too close to its start time')

    await cancel.getByRole('button', { name: 'Force cancel instead' }).click()
    const force = page.getByRole('dialog', { name: 'Force cancel appointment' })
    await force.getByRole('button', { name: 'Force cancel' }).click()
    await expect(force.getByRole('alert')).toContainText('reason is required')
    await force.getByLabel('Reason').fill('Patient hospitalised')
    await force.getByRole('button', { name: 'Force cancel' }).click()

    await expect(page.getByText('Cancelled', { exact: true })).toBeVisible()
    const login = await request.post('http://localhost:8100/api/v1/auth/login', {
      data: { email: E2E.adminEmail, password: E2E.adminPassword },
    })
    const { accessToken } = await login.json()
    const audit = await request.get('http://localhost:8100/api/v1/audit-log?action=force_cancel', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const entries = (await audit.json()).items as { reason: string }[]
    expect(entries.map((e) => e.reason)).toContain('Patient hospitalised')
  } finally {
    await setCutoffHours(page, '2')
  }
})

test('rescheduling moves the booking and the old one shows as cancelled', async ({ page }) => {
  await signIn(page)
  const thursday = upcoming(4)
  await book(page, thursday, '91234 56789', 'Meera Iyer')

  await page.getByRole('button', { name: 'Reschedule' }).click()
  const dialog = page.getByRole('dialog', { name: 'Reschedule appointment' })
  await dialog.getByLabel('Date').fill(thursday)
  await dialog.getByRole('button', { name: 'Find slots' }).click()
  await expect(dialog.getByRole('button', { name: '09:00' })).toHaveCount(0) // held by this booking
  await dialog.getByRole('button', { name: '09:20' }).click()

  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  await expect(page.getByText(/, 09:20$/)).toBeVisible()
  await page.goto('/appointments')
  await expect(page.getByRole('row', { name: /^Thu.*09:20.*Meera Iyer.*Booked/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /^Thu.*09:00.*Meera Iyer.*Cancelled/ })).toBeVisible()
})

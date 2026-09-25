import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

/**
 * The whole product in one pass, the way a clinic would use it: register a patient, triage, book
 * (regular and emergency), check in, consult, write and finalize notes, follow up, walk the queue,
 * force-cancel, and find it all in the audit log.
 */

const API = 'http://localhost:8100/api/v1'
const DOCTOR = { email: 'doctor@clinic.test', password: 'dev doctor passphrase' }

function upcoming(weekday: number, extraDays = 0): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 2)
  while (d.getUTCDay() !== weekday) d.setUTCDate(d.getUTCDate() + 1)
  d.setUTCDate(d.getUTCDate() + extraDays)
  return d.toISOString().slice(0, 10)
}

async function signIn(page: Page, email = E2E.adminEmail, password = E2E.adminPassword) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
}

async function adminApi(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, {
    data: { email: E2E.adminEmail, password: E2E.adminPassword },
  })
  const headers = { Authorization: `Bearer ${(await login.json()).accessToken}` }
  return {
    async get(path: string) {
      return (await request.get(`${API}${path}`, { headers })).json()
    },
    async post(path: string, data: unknown) {
      const response = await request.post(`${API}${path}`, { headers, data })
      expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy()
      return response.json()
    },
  }
}

async function findPatient(page: Page, phone: string, name: string) {
  await page.getByLabel('Patient phone').fill(phone)
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: new RegExp(name) }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
}

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
}

// Recorded on every run (uploaded as a CI artifact) so the whole demo can be watched afterwards.
test.use({ video: 'on', trace: 'on' })

test('registration to finalized visit, follow-up, emergency, queue, force-cancel and audit', async ({
  page,
  browser,
  request,
}) => {
  test.setTimeout(180_000)
  const api = await adminApi(request)
  const phone = `95${Math.floor(10000000 + Math.random() * 89999999)}`
  const name = 'Journey Patient'
  const visitDay = upcoming(1, 28) // a Monday four weeks out
  const followUpDay = upcoming(1, 35)
  const emergencyDay = upcoming(3, 35) // a Wednesday

  // 1. Register the patient.
  await signIn(page)
  await page.getByRole('link', { name: 'Patients' }).click()
  await page.getByRole('button', { name: 'Register new patient' }).click()
  const register = page.getByRole('dialog', { name: 'Register patient' })
  await register.getByLabel('Name').fill(name)
  await register.getByLabel('Phone').fill(phone)
  await register.getByRole('button', { name: 'Register' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()

  // 2. Book a regular slot, running (advisory) triage on the way.
  await page.goto('/book')
  await page.getByLabel('Date').fill(visitDay)
  await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await page.getByRole('button', { name: '09:00' }).click()
  await findPatient(page, phone, name)
  await page.getByLabel('Symptoms for triage').fill('mild cough for a week')
  await page.getByRole('button', { name: 'Run triage' }).click()
  const card = page.getByRole('region', { name: 'Triage result', exact: true })
  await expect(card.locator('.urgency')).not.toHaveText('emergency')
  await expect(card.getByText(/not a diagnosis/i)).toBeVisible()
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  const visitUrl = page.url()

  // 3. Check in, consult, write notes, ask the AI for a draft.
  await page.getByRole('button', { name: 'Check in' }).click()
  await page.getByRole('button', { name: 'Start consultation' }).click()
  await expect(page.getByText('In consultation', { exact: true })).toBeVisible()
  await page.getByLabel('Visit notes').fill('Dry cough for a week. Chest clear. Advised fluids.')
  await page.getByLabel('Visit notes').blur()
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Generate AI draft' }).click()
  await expect(page.getByRole('region', { name: 'AI draft' })).toBeVisible()

  // 4. The doctor finalizes; the note locks. The screen with the editor is accessible.
  const doctorContext = await browser.newContext({ baseURL: E2E.baseURL })
  try {
    const doctorPage = await doctorContext.newPage()
    await signIn(doctorPage, DOCTOR.email, DOCTOR.password)
    await doctorPage.goto(visitUrl)
    await doctorPage.getByRole('button', { name: 'Use draft as final summary' }).click()
    expect(await seriousViolations(doctorPage)).toEqual([])
    await doctorPage.getByRole('button', { name: 'Finalize summary' }).click()
    await expect(doctorPage.getByText(/^Finalized/)).toBeVisible()
  } finally {
    await doctorContext.close()
  }

  // 5. Complete the visit and book a follow-up from it.
  await page.reload()
  await expect(page.getByLabel('Visit notes')).not.toBeEditable()
  await page.getByRole('button', { name: 'Complete' }).click()
  await expect(page.getByText('Completed', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Book follow-up' }).click()
  const followUp = page.getByRole('dialog', { name: 'Book follow-up' })
  await followUp.getByLabel('Date').fill(followUpDay)
  await followUp.getByRole('button', { name: 'Find slots' }).click()
  await followUp.getByRole('button', { name: '09:00' }).click()
  await expect(page.getByText('Booked', { exact: true })).toBeVisible()
  const followUpUrl = page.url()
  expect(followUpUrl).not.toBe(visitUrl)

  // 6. An emergency: the regular slots are gone, so triage authorizes the held-back one.
  const dev = (await api.get('/doctors')).find((d: { name: string }) => d.name === 'Dr. Dev Doctor')
  const slots = (await api.get(`/slots?doctorId=${dev.id}&date=${emergencyDay}`)) as {
    startTime: string
  }[]
  for (const [index, slot] of slots.entries()) {
    const filler = await api.post('/patients', {
      name: `Journey Filler ${index}`,
      phone: `94${String(index).padStart(8, '0')}`,
    })
    await api.post('/appointments', {
      doctorId: dev.id,
      patientId: filler.id,
      startTime: slot.startTime,
    })
  }
  await page.goto('/walk-in')
  await findPatient(page, phone, name)
  await page.getByLabel('Date').fill(emergencyDay)
  await page
    .getByRole('combobox', { name: 'Requested doctor' })
    .selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await page.getByRole('button', { name: /emergency/ }).click()
  await page.getByLabel('Symptoms for triage').fill('crushing chest pain')
  await page.getByRole('button', { name: 'Run triage' }).click()
  await expect(
    page.getByRole('region', { name: 'Triage result', exact: true }).locator('.urgency'),
  ).toHaveText('emergency')
  await page.getByLabel('Authorization').selectOption('triage')
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByText('Yes', { exact: true })).toBeVisible() // emergency slot

  // 7. Walk that patient through the queue on the day.
  await page.goto('/queue')
  await page.getByLabel('Date').fill(emergencyDay)
  const column = (title: RegExp) => page.getByRole('heading', { name: title }).locator('..')
  // The day also holds the filler bookings, so look for this patient's own action buttons.
  await page.getByRole('button', { name: `Check in ${name}` }).click()
  await page.getByRole('button', { name: `Start consultation ${name}` }).click()
  await page.getByRole('button', { name: `Complete ${name}` }).click()
  await expect(column(/^Completed \(\d+\)/)).toContainText(name)

  // 8. Force-cancel the follow-up inside the cutoff, with a reason.
  const setCutoff = async (hours: string) => {
    await page.getByRole('link', { name: 'Settings' }).click()
    await page.getByLabel('Cancellation cutoff (hours)').fill(hours)
    await page.getByRole('button', { name: 'Save settings' }).click()
    await expect(page.getByText('Settings saved')).toBeVisible()
  }
  await setCutoff('9000')
  try {
    await page.goto(followUpUrl)
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    const cancel = page.getByRole('dialog', { name: 'Cancel appointment' })
    await cancel.getByRole('button', { name: 'Cancel appointment' }).click()
    await expect(cancel.getByRole('alert')).toContainText('too close to its start time')
    await cancel.getByRole('button', { name: 'Force cancel instead' }).click()
    const force = page.getByRole('dialog', { name: 'Force cancel appointment' })
    await force.getByLabel('Reason').fill('Patient travelling')
    await force.getByRole('button', { name: 'Force cancel' }).click()
    await expect(page.getByText('Cancelled', { exact: true })).toBeVisible()
  } finally {
    await setCutoff('2')
  }

  // 9. Everything sensitive is in the audit log.
  await page.getByRole('link', { name: 'Audit log' }).click()
  await page.getByLabel('Action').selectOption({ label: 'Force cancel' })
  await expect(page.getByRole('row', { name: /Force cancel.*Patient travelling/ })).toBeVisible()
  await page.getByLabel('Action').selectOption({ label: 'Emergency authorization' })
  await expect(page.getByRole('row', { name: /Emergency authorization/ }).first()).toBeVisible()
  expect(await seriousViolations(page)).toEqual([])
})

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

const API = 'http://localhost:8100/api/v1'

function upcoming(weekday: number, extraDays = 0): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 2)
  while (d.getUTCDay() !== weekday) d.setUTCDate(d.getUTCDate() + 1)
  d.setUTCDate(d.getUTCDate() + extraDays)
  return d.toISOString().slice(0, 10)
}

async function api(request: APIRequestContext) {
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

/** Book every regular slot of the dev doctor on `date`, leaving only the held-back one. */
async function fillRegularSlots(
  client: Awaited<ReturnType<typeof api>>,
  date: string,
  tag: string,
) {
  const dev = (await client.get('/doctors')).find(
    (d: { name: string }) => d.name === 'Dr. Dev Doctor',
  )
  const slots = (await client.get(`/slots?doctorId=${dev.id}&date=${date}`)) as {
    startTime: string
  }[]
  for (const [index, slot] of slots.entries()) {
    const patient = await client.post('/patients', {
      name: `Filler ${tag} ${index}`,
      phone: `9${tag}${String(index).padStart(7, '0')}`, // 10 digits, a valid Indian mobile
    })
    await client.post('/appointments', {
      doctorId: dev.id,
      patientId: patient.id,
      startTime: slot.startTime,
    })
  }
  return slots.length
}

async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Queue' })).toBeVisible()
}

/** Walk-in for Kiran on `date`: only the emergency-held slot is left, so go straight to it. */
async function walkInToEmergencyConfirm(page: Page, date: string) {
  await page.goto('/walk-in')
  await page.getByLabel('Patient phone').fill('98765 43210')
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: /Kiran Rao/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel('Date').fill(date)
  await page
    .getByRole('combobox', { name: 'Requested doctor' })
    .selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await expect(page.getByText(/No regular slots are available/)).toBeVisible()
  await page.getByRole('button', { name: /emergency/ }).click()
  await expect(page.getByText(/held for emergencies/i)).toBeVisible()
}

test('a red flag is returned even when the AI is down, and authorizes the emergency slot', async ({
  page,
  request,
}) => {
  const client = await api(request)
  const date = upcoming(4, 14) // a Thursday two weeks out
  expect(await fillRegularSlots(client, date, '11')).toBeGreaterThan(0)
  await signIn(page)
  await walkInToEmergencyConfirm(page, date)

  await page.getByLabel('Symptoms for triage').fill('crushing chest pain simulate-ai-outage')
  await page.getByRole('button', { name: 'Run triage' }).click()

  const card = page.getByRole('region', { name: 'Triage result', exact: true })
  await expect(card.locator('.urgency')).toHaveText('emergency')
  await expect(card.getByText('Safety rule')).toBeVisible() // decided by the deterministic check
  await expect(card.getByText(/not a diagnosis/i)).toBeVisible() // the disclaimer always comes along

  await page.getByLabel('Authorization').selectOption('triage')
  await expect(page.getByLabel('Reason for using emergency capacity')).toHaveCount(0)
  await page.getByRole('button', { name: 'Confirm booking' }).click()

  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  await expect(page.getByText('Yes', { exact: true })).toBeVisible() // emergency slot
  const audit = await client.get('/audit-log?action=emergency_authorization')
  expect(audit.items.length).toBeGreaterThan(0)
})

test('overriding an emergency result to routine removes triage authorization', async ({
  page,
  request,
}) => {
  const client = await api(request)
  const date = upcoming(4, 21)
  await fillRegularSlots(client, date, '22')
  await signIn(page)
  await walkInToEmergencyConfirm(page, date)

  await page.getByLabel('Symptoms for triage').fill('chest pain')
  await page.getByRole('button', { name: 'Run triage' }).click()
  await expect(
    page.getByRole('region', { name: 'Triage result', exact: true }).locator('.urgency'),
  ).toHaveText('emergency')
  const authorization = page.getByLabel('Authorization')
  await expect(authorization.getByRole('option')).toHaveCount(2)

  await page.getByRole('button', { name: 'Override' }).click()
  const dialog = page.getByRole('dialog', { name: 'Override triage result' })
  await dialog.getByLabel('Urgency').selectOption('routine')
  await dialog.getByRole('button', { name: 'Save override' }).click()
  await expect(dialog.getByRole('alert')).toContainText('reason is required')
  await dialog.getByLabel('Reason').fill('Anxiety attack, ECG normal')
  await dialog.getByRole('button', { name: 'Save override' }).click()

  const card = page.getByRole('region', { name: 'Triage result', exact: true })
  await expect(card.getByText('AI suggestion: emergency')).toBeVisible()
  await expect(card.getByText('Staff override: routine')).toBeVisible()
  await expect(card.getByText(/not a diagnosis/i)).toBeVisible()
  await expect(authorization.getByRole('option')).toHaveCount(1) // judgment only now
  const audit = await client.get('/audit-log?action=triage_override')
  expect(audit.items.map((e: { reason: string }) => e.reason).join(' ')).toContain('Anxiety attack')
})

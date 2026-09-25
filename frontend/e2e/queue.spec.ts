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

async function adminToken(request: APIRequestContext): Promise<string> {
  const login = await request.post(`${API}/auth/login`, {
    data: { email: E2E.adminEmail, password: E2E.adminPassword },
  })
  return (await login.json()).accessToken
}

function client(request: APIRequestContext, token: string) {
  const headers = { Authorization: `Bearer ${token}` }
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

async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Queue' })).toBeVisible()
}

/** A second doctor in the dev doctor's specialty working Friday 09:00-09:40 (2 slots; the last is held). */
async function addSecondDoctor(request: APIRequestContext) {
  const api = client(request, await adminToken(request))
  const doctors = await api.get('/doctors')
  const dev = doctors.find((d: { name: string }) => d.name === 'Dr. Dev Doctor')
  const stamp = Date.now()
  const user = await api.post('/users', {
    email: `eve.${stamp}@clinic.test`,
    name: 'Eve E2E',
    role: 'doctor',
    password: 'eve e2e passphrase',
  })
  const eve = await api.post('/doctors', {
    userId: user.id,
    name: 'Dr. E2E Eve',
    specialtyId: dev.specialtyId,
  })
  await api.post(`/doctors/${eve.id}/availability`, {
    dayOfWeek: 'friday',
    startTime: '09:00',
    endTime: '09:40',
  })
  return { api, dev, eve }
}

async function choosePatient(page: Page, phone: string, name: string) {
  await page.getByLabel('Patient phone').fill(phone)
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: new RegExp(name) }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
}

async function findWalkInSlots(page: Page, date: string) {
  await page.getByLabel('Date').fill(date)
  await page
    .getByRole('combobox', { name: 'Requested doctor' })
    .selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
}

test('a walk-in falls back to another doctor, then to emergency capacity with a reason', async ({
  page,
  request,
}) => {
  const { api, dev, eve } = await addSecondDoctor(request)
  const friday = upcoming(5)
  const nextFriday = upcoming(5, 7)
  for (const date of [friday, nextFriday]) {
    await api.post(`/doctors/${dev.id}/availability-exceptions`, { date, type: 'unavailable' })
  }
  await signIn(page)

  // 1. The requested doctor is off: another doctor in the specialty is offered.
  await page.goto('/walk-in')
  await choosePatient(page, '98765 43210', 'Asha Rao')
  await findWalkInSlots(page, friday)
  await expect(page.getByText(/Dr\. Dev Doctor has no open slots on this day/)).toBeVisible()
  await page.getByRole('button', { name: '09:00' }).click()
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  await expect(page.getByText('Walk-in', { exact: true })).toBeVisible()

  // 2. Eve's only regular slot is taken too: only held-back emergency capacity is left.
  const meera = (await api.get('/patients?phone=91234%2056789')).items[0]
  await api.post('/appointments', {
    doctorId: eve.id,
    patientId: meera.id,
    startTime: await slotStart(api, eve.id, nextFriday, false),
  })
  await page.goto('/walk-in')
  await choosePatient(page, '98765 43210', 'Kiran Rao')
  await findWalkInSlots(page, nextFriday)
  await expect(page.getByText(/No regular slots are available/)).toBeVisible()
  await page.getByRole('button', { name: /09:20/ }).click()
  await expect(page.getByText(/held for emergencies/i)).toBeVisible()

  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('alert')).toContainText('reason is required')
  await page.getByLabel('Reason for using emergency capacity').fill('Chest pain, walked in')
  await page.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('heading', { name: 'Appointment', exact: true })).toBeVisible()
  await expect(page.getByText('Yes', { exact: true })).toBeVisible() // emergency slot

  // The dashboard flags both, and the authorization is in the audit log.
  await page.goto('/queue')
  await page.getByLabel('Date').fill(nextFriday)
  const kiran = page.getByRole('listitem').filter({ hasText: 'Kiran Rao' })
  await expect(kiran.getByText('Walk-in')).toBeVisible()
  await expect(kiran.getByText('Emergency')).toBeVisible()
  const audit = await api.get('/audit-log?action=emergency_authorization')
  expect(audit.items.map((e: { reason: string }) => e.reason)).toContain('Chest pain, walked in')
})

async function slotStart(
  api: ReturnType<typeof client>,
  doctorId: string,
  date: string,
  emergency: boolean,
): Promise<string> {
  const query = `/slots?doctorId=${doctorId}&date=${date}${emergency ? '&includeEmergency=true' : ''}`
  const slots = (await api.get(query)) as { startTime: string; isEmergency: boolean }[]
  return slots.filter((s) => s.isEmergency === emergency)[0].startTime
}

test('the dashboard moves a patient through the queue', async ({ page, request }) => {
  const api = client(request, await adminToken(request))
  const dev = (await api.get('/doctors')).find((d: { name: string }) => d.name === 'Dr. Dev Doctor')
  const tuesday = upcoming(2, 14)
  const patients = (await api.get('/patients?phone=98765%2043210')).items as {
    id: string
    name: string
  }[]
  const asha = patients.find((p) => p.name === 'Asha Rao')!
  const slots = (await api.get(`/slots?doctorId=${dev.id}&date=${tuesday}`)) as {
    startTime: string
  }[]
  await api.post('/appointments', {
    doctorId: dev.id,
    patientId: asha.id,
    startTime: slots[0].startTime,
  })

  await signIn(page)
  await page.goto('/queue')
  await page.getByLabel('Date').fill(tuesday)
  const column = (title: RegExp) => page.getByRole('heading', { name: title }).locator('..')
  await expect(column(/^Booked \(1\)/)).toContainText('Asha Rao')

  await page.getByRole('button', { name: 'Check in Asha Rao' }).click()
  await expect(column(/^Checked in \(1\)/)).toContainText('Asha Rao')
  await expect(column(/^Booked \(0\)/)).toBeVisible()
  await page.getByRole('button', { name: 'Start consultation Asha Rao' }).click()
  await expect(column(/^In consultation \(1\)/)).toContainText('Asha Rao')
  await page.getByRole('button', { name: 'Complete Asha Rao' }).click()
  await expect(column(/^Completed \(1\)/)).toContainText('Asha Rao')
})

import { expect, test, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

const DOCTOR_PASSWORD = 'doctor passphrase 1'

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
}

test('admin creates a doctor who logs in with restricted navigation', async ({ page }) => {
  const doctorEmail = `doctor.${Date.now()}@clinic.test`

  await signIn(page, E2E.adminEmail, E2E.adminPassword)
  await expect(page.getByRole('link', { name: 'Users' })).toBeVisible()

  await page.getByRole('link', { name: 'Users' }).click()
  await page.getByRole('button', { name: 'New user' }).click()
  const dialog = page.getByRole('dialog', { name: 'New user' })
  await dialog.getByLabel('Email').fill(doctorEmail)
  await dialog.getByLabel('Name').fill('Dana Doctor')
  await dialog.getByLabel('Role').selectOption('doctor')
  await dialog.getByLabel('Password').fill(DOCTOR_PASSWORD)
  await dialog.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByRole('cell', { name: doctorEmail })).toBeVisible()
  await signOut(page)

  await signIn(page, doctorEmail, DOCTOR_PASSWORD)
  await expect(page.getByText('Dana Doctor')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Users' })).toHaveCount(0)

  await page.goto('/users')
  await expect(page.getByRole('heading', { name: 'Not permitted' })).toBeVisible()
})

test('deactivating a doctor ends their live session and is audited', async ({
  browser,
  request,
}) => {
  const doctorEmail = `live.${Date.now()}@clinic.test`
  const admin = await browser.newPage()
  await signIn(admin, E2E.adminEmail, E2E.adminPassword)
  await admin.getByRole('link', { name: 'Users' }).click()
  await admin.getByRole('button', { name: 'New user' }).click()
  const dialog = admin.getByRole('dialog', { name: 'New user' })
  await dialog.getByLabel('Email').fill(doctorEmail)
  await dialog.getByLabel('Name').fill('Live Doctor')
  await dialog.getByLabel('Password').fill(DOCTOR_PASSWORD)
  await dialog.getByRole('button', { name: 'Create' }).click()
  await expect(admin.getByRole('cell', { name: doctorEmail })).toBeVisible()

  const doctor = await browser.newPage()
  await signIn(doctor, doctorEmail, DOCTOR_PASSWORD)
  await expect(doctor.getByText('Live Doctor')).toBeVisible()

  const row = admin.getByRole('row', { name: new RegExp(doctorEmail) })
  await row.getByRole('button', { name: 'Deactivate' }).click()
  await expect(row.getByText('Inactive')).toBeVisible()

  await doctor.reload()
  await expect(doctor.getByRole('heading', { name: 'Sign in' })).toBeVisible()

  const login = await request.post('http://localhost:8100/api/v1/auth/login', {
    data: { email: E2E.adminEmail, password: E2E.adminPassword },
  })
  const { accessToken } = await login.json()
  const audit = await request.get('http://localhost:8100/api/v1/audit-log', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  const actions = (await audit.json()).items.map((entry: { action: string }) => entry.action)
  expect(actions).toContain('user_created')
  expect(actions).toContain('user_updated')
})

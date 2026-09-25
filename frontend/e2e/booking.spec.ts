import { expect, test, type Browser, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

/** A Monday at least two days ahead: the dev doctor works Mon-Fri 09:00-12:00. */
function upcomingMonday(): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 2)
  while (d.getUTCDay() !== 1) d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

async function newAdminPage(browser: Browser): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
  return page
}

async function pickSlot(page: Page, date: string) {
  await page.goto('/book')
  await page.getByLabel('Date').fill(date)
  await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await page.getByRole('button', { name: '09:00' }).click()
  await expect(page.getByRole('heading', { name: 'Choose patient' })).toBeVisible()
}

async function choosePatient(page: Page, name: string, phone: string) {
  await page.getByLabel('Patient phone').fill(phone)
  await page.getByRole('button', { name: 'Find patient' }).click()
  await page.getByRole('radio', { name: new RegExp(name) }).check()
  await page.getByRole('button', { name: 'Continue' }).click()
}

test('front-desk books a slot for one of two patients sharing a phone', async ({ browser }) => {
  const date = upcomingMonday()
  const page = await newAdminPage(browser)
  await pickSlot(page, date)

  await page.getByLabel('Patient phone').fill('98765 43210')
  await page.getByRole('button', { name: 'Find patient' }).click()
  await expect(page.getByRole('radio', { name: /Asha Rao/ })).toBeVisible()
  await expect(page.getByRole('radio', { name: /Kiran Rao/ })).toBeVisible() // both listed
  await page.getByRole('radio', { name: /Asha Rao/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()

  await page.getByLabel('Reported symptoms (optional)').fill('cough')
  await page.getByRole('button', { name: 'Confirm booking' }).click()

  await expect(page.getByRole('heading', { name: 'Appointment' })).toBeVisible()
  await expect(page.getByText('cough')).toBeVisible()
  await expect(page.getByText('Booked', { exact: true })).toBeVisible()

  // The booked slot is gone from the search; the next one is still open.
  await page.goto('/book')
  await page.getByLabel('Date').fill(date)
  await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
  await page.getByRole('button', { name: 'Find slots' }).click()
  await expect(page.getByRole('button', { name: '09:20' })).toBeVisible()
  await expect(page.getByRole('button', { name: '09:00' })).toHaveCount(0)

  await page.goto('/appointments')
  await expect(page.getByRole('row', { name: /Asha Rao.*Dr\. Dev Doctor/ })).toBeVisible()
})

test('a second front-desk user racing for the same slot gets the conflict message', async ({
  browser,
}) => {
  const date = upcomingMonday()
  const first = await newAdminPage(browser)
  const second = await newAdminPage(browser)
  // Both look at the day's slots before either books; use the 09:20 slot for this test.
  for (const page of [first, second]) {
    await page.goto('/book')
    await page.getByLabel('Date').fill(date)
    await page.getByRole('combobox', { name: 'Doctor' }).selectOption({ label: 'Dr. Dev Doctor' })
    await page.getByRole('button', { name: 'Find slots' }).click()
    await page.getByRole('button', { name: '09:20' }).click()
    await expect(page.getByRole('heading', { name: 'Choose patient' })).toBeVisible()
  }

  await choosePatient(first, 'Meera Iyer', '91234 56789')
  await first.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(first.getByRole('heading', { name: 'Appointment' })).toBeVisible()

  await second.getByLabel('Patient phone').fill('98765 43210')
  await second.getByRole('button', { name: 'Find patient' }).click()
  await second.getByRole('radio', { name: /Kiran Rao/ }).check()
  await second.getByRole('button', { name: 'Continue' }).click()
  await second.getByRole('button', { name: 'Confirm booking' }).click()

  await expect(second.getByRole('alert')).toContainText('no longer available')
  await second.getByRole('button', { name: 'Refresh slots' }).click()
  await expect(second.getByRole('button', { name: '09:20' })).toHaveCount(0)
  await expect(second.getByRole('button', { name: '09:40' })).toBeVisible()
})

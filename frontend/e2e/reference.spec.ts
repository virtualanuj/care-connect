import { expect, test, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

async function signInAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Patients' })).toBeVisible()
}

async function register(page: Page, name: string, phone: string) {
  await page.getByRole('button', { name: 'Register new patient' }).click()
  const dialog = page.getByRole('dialog', { name: 'Register patient' })
  await dialog.getByLabel('Name').fill(name)
  await dialog.getByLabel('Phone').fill(phone)
  await dialog.getByRole('button', { name: 'Register' }).click()
  return dialog
}

test('two family members share a phone number; the search shows both and duplicates are rejected', async ({
  page,
}) => {
  const phone = `98${Math.floor(10000000 + Math.random() * 89999999)}`
  await signInAsAdmin(page)
  await page.getByRole('link', { name: 'Patients' }).click()

  await register(page, 'Nisha Verma', phone)
  await expect(page.getByRole('heading', { name: 'Nisha Verma' })).toBeVisible()

  await page.getByRole('link', { name: '← Patients' }).click()
  await register(page, 'Tara Verma', phone)
  await expect(page.getByRole('heading', { name: 'Tara Verma' })).toBeVisible()

  await page.getByRole('link', { name: '← Patients' }).click()
  await page.getByLabel('Phone').fill(phone)
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.getByText('2 patients found')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Nisha Verma' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Tara Verma' })).toBeVisible()

  const dialog = await register(page, '  nisha   VERMA ', phone)
  await expect(dialog.getByRole('alert')).toContainText('already registered')
})

test('a history correction is added as an amendment and the original stays visible', async ({
  page,
}) => {
  const phone = `97${Math.floor(10000000 + Math.random() * 89999999)}`
  await signInAsAdmin(page)
  await page.getByRole('link', { name: 'Patients' }).click()
  await register(page, 'Ishaan Menon', phone)
  await expect(page.getByRole('heading', { name: 'Ishaan Menon' })).toBeVisible()

  await page.getByLabel('New history entry').fill('Allergic to penicillin')
  await page.getByRole('button', { name: 'Add entry' }).click()
  const first = page.getByRole('listitem', { name: 'History entry 1' })
  await expect(first).toContainText('Allergic to penicillin')

  await first.getByRole('button', { name: 'Amend' }).click()
  const dialog = page.getByRole('dialog', { name: 'Amend history entry' })
  await dialog.getByLabel('Correction').fill('Allergic to amoxicillin, not penicillin')
  await dialog.getByRole('button', { name: 'Add amendment' }).click()

  await expect(page.getByRole('listitem', { name: 'History entry 1' })).toContainText(
    'Allergic to penicillin',
  )
  const second = page.getByRole('listitem', { name: 'History entry 2' })
  await expect(second).toContainText('Amendment')
  await expect(second).toContainText('Amends: Allergic to penicillin')
})

test('front-desk adds availability for a doctor and overlapping hours are rejected', async ({
  page,
}) => {
  await signInAsAdmin(page)
  await page.getByRole('link', { name: 'Doctors' }).click()
  const row = page.getByRole('row', { name: /Dr\. Dev Doctor/ })
  await row.getByRole('link', { name: 'Availability' }).click()
  await expect(page.getByRole('heading', { name: 'Availability — Dr. Dev Doctor' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Monday/ })).toContainText('09:00–12:00')

  await page.getByRole('button', { name: 'Add hours' }).click()
  let dialog = page.getByRole('dialog', { name: 'Add working hours' })
  await dialog.getByLabel('Day').selectOption('saturday')
  await dialog.getByLabel('Start').fill('10:00')
  await dialog.getByLabel('End').fill('13:00')
  await dialog.getByRole('button', { name: 'Add' }).click()
  await expect(page.getByRole('row', { name: /Saturday/ })).toContainText('10:00–13:00')

  await page.getByRole('button', { name: 'Add hours' }).click()
  dialog = page.getByRole('dialog', { name: 'Add working hours' })
  await dialog.getByLabel('Day').selectOption('saturday')
  await dialog.getByLabel('Start').fill('12:00')
  await dialog.getByLabel('End').fill('14:00')
  await dialog.getByRole('button', { name: 'Add' }).click()
  await expect(dialog.getByRole('alert')).toContainText('overlaps another rule')
})

test('changed clinic settings persist across a reload', async ({ page }) => {
  await signInAsAdmin(page)
  await page.getByRole('link', { name: 'Settings' }).click()
  const followUp = page.getByLabel('Follow-up window (days)')
  await followUp.fill('14')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Settings saved')).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Follow-up window (days)')).toHaveValue('14')
})

import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

import { E2E } from '../playwright.config'

async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(E2E.adminEmail)
  await page.getByLabel('Password').fill(E2E.adminPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
}

/** Screens reachable from the navigation, each with a heading that shows it has rendered. */
const SCREENS = [
  { path: '/', heading: 'Welcome' },
  { path: '/queue', heading: /queue/i },
  { path: '/book', heading: /Book/ },
  { path: '/walk-in', heading: /walk-in/i },
  { path: '/appointments', heading: 'Appointments' },
  { path: '/patients', heading: 'Patients' },
  { path: '/doctors', heading: 'Doctors' },
  { path: '/settings', heading: 'Clinic settings' },
  { path: '/users', heading: 'Users' },
  { path: '/audit', heading: 'Audit log' },
]

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
}

test('the sign-in page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()

  expect(await seriousViolations(page)).toEqual([])
})

test('every main screen has no serious accessibility violations and fits a tablet', async ({
  page,
}) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await signIn(page)
  const problems: string[] = []

  for (const screen of SCREENS) {
    await page.goto(screen.path)
    await expect(page.getByRole('heading', { name: screen.heading }).first()).toBeVisible()
    await page.waitForLoadState('networkidle')
    for (const violation of await seriousViolations(page)) {
      problems.push(`${screen.path}: ${violation}`)
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    if (overflow > 0) problems.push(`${screen.path}: page scrolls sideways by ${overflow}px`)
  }

  expect(problems).toEqual([])
})

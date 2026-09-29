import { expect, test } from '@playwright/test'

test('persists English UI preference across reloads', async ({ page }) => {
  await page.route('**/api/stats/dashboard', route => route.fulfill({ json: { today_answered: 40, daily_goal: 160, today_exams: 1, today_accuracy: .8, today_seconds: 3600, total_answered: 400, overall_accuracy: .75, mle_mastery: .7, sde_mastery: .6, review_due: 12 } }))
  await page.route('**/api/exams/active', route => route.fulfill({ json: null }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '今天，完成一套真训练。' })).toBeVisible()
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Make today count under pressure.' })).toBeVisible()
})

test('exam autosaves a monotonic revision and reveals no answer before submit', async ({ page }) => {
  let savedRevision = 0
  await page.route('**/api/exams/exam-e2e', route => route.fulfill({ json: { id: 'exam-e2e', locale: 'zh-CN', duration_seconds: 3600, deadline_at: '2099-01-01T00:00:00Z', questions: [{ id: 'q1', position: 1, prompt: '哈希表查询复杂度？', type: 'single_choice', difficulty: 'L1', options: [{ id: 'A', text: 'O(1)' }, { id: 'B', text: 'O(n)' }] }] } }))
  await page.route('**/api/exams/exam-e2e/answers/1', async route => { savedRevision = (await route.request().postDataJSON()).client_revision; await route.fulfill({ json: { saved: true, client_revision: savedRevision } }) })
  await page.goto('/exam/exam-e2e')
  await expect(page.getByText('哈希表查询复杂度？')).toBeVisible()
  await expect(page.getByText(/正确答案|完整解析/)).toHaveCount(0)
  await page.getByRole('button', { name: /A O\(1\)/ }).click()
  await expect.poll(() => savedRevision).toBe(1)
  await expect(page.getByText('已保存')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: /A O\(1\)/ })).toHaveClass(/selected/)
})

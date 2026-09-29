import { expect, test } from '@playwright/test'

const backendUrl = process.env.VITE_API_URL || 'http://127.0.0.1:8000'

test('real backend supports build, autosave, restore, submit, and debrief', async ({ page }) => {
  await page.goto('/exams/new')
  await expect(page.getByRole('heading', { name: '标准套卷配置' })).toBeVisible()
  await page.getByRole('button', { name: /开始标准卷/ }).click()
  await expect(page).toHaveURL(/\/exam\/[a-f0-9]+$/)

  await expect(page.locator('.question-grid button')).toHaveCount(40)
  await expect(page.getByText(/正确答案|完整解析/)).toHaveCount(0)

  const firstOption = page.locator('.options button').first()
  await firstOption.click()
  await expect(page.getByText('已保存')).toBeVisible()
  await page.getByRole('button', { name: '标记' }).click()
  await expect(page.getByRole('button', { name: '取消标记' })).toBeVisible()

  await page.reload()
  await expect(page.locator('.options button.selected')).toHaveCount(1)
  await expect(page.getByRole('button', { name: '取消标记' })).toBeVisible()
  await expect(page.getByText(/正确答案|完整解析/)).toHaveCount(0)

  await page.getByRole('button', { name: '提前交卷' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '确认交卷' }).click()
  await expect(page).toHaveURL(/\/result\/[a-f0-9]+$/)
  await expect(page.getByRole('heading', { name: '结果与逐题解析' })).toBeVisible()
  await expect(page.getByText('完整解析').first()).toBeVisible()
})

test('real backend serves bilingual navigation and a rapid-drill question', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible()
  await page.goto('/drill')
  await expect(page.getByRole('heading', { name: 'High-throughput rapid drill' })).toBeVisible()
  await page.getByRole('button', { name: /Start drill/ }).click()
  await expect(page.locator('.drill-card h1')).toBeVisible()
  const choice = page.locator('.options button').first()
  if (await choice.count()) {
    await choice.click()
  } else {
    await page.locator('.rapid-input').fill('0')
  }
  await page.getByRole('button', { name: 'Submit answer' }).click()
  await expect(page.locator('.feedback')).toBeVisible()
  await expect(page.locator('.feedback p')).not.toBeEmpty()
})

test('immediate submit flushes the selected answer to the real backend', async ({ page }) => {
  await page.goto('/exams/new')
  await page.getByRole('button', { name: /开始标准卷/ }).click()
  await expect(page).toHaveURL(/\/exam\/[a-f0-9]+$/)
  const examId = page.url().split('/').at(-1)!
  const firstOption = page.locator('.options button').first()
  const optionId = (await firstOption.locator('span').textContent())!.trim()
  await firstOption.click()
  await page.getByRole('button', { name: '提前交卷' }).click()
  await page.getByRole('button', { name: '确认交卷' }).click()
  await expect(page).toHaveURL(new RegExp(`/result/${examId}$`))

  const response = await page.request.get(`${backendUrl}/api/exams/${examId}/result`)
  expect(response.ok()).toBeTruthy()
  const result = await response.json()
  expect(result.questions[0].user_answer).toBe(optionId)
})

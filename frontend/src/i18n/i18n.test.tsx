import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { LocaleProvider, LocaleToggle, useI18n } from './i18n'

function Probe() {
  const { t } = useI18n()
  return <><span>{t('nav.dashboard')}</span><LocaleToggle /></>
}

describe('locale preference', () => {
  it('switches to English and persists the choice', async () => {
    render(<LocaleProvider><Probe /></LocaleProvider>)
    expect(screen.getByText('控制台')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /English/i }))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(localStorage.getItem('exam:locale')).toBe('en-US')
  })
})

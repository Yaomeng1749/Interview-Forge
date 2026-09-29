import { BookOpenCheck, Boxes, Gauge, GraduationCap, LibraryBig, Settings2, Swords } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { LocaleToggle, useI18n } from '../i18n/i18n'

export function AppShell() {
  const { t } = useI18n()
  const nav = [
    ['/', t('nav.dashboard'), Gauge], ['/exams/new', t('nav.exam'), Swords], ['/drill', t('nav.drill'), Boxes],
    ['/learning-map', t('nav.map'), GraduationCap], ['/questions', t('nav.questions'), LibraryBig],
    ['/review', t('nav.review'), BookOpenCheck], ['/settings', t('nav.settings'), Settings2],
  ] as const
  return <div className="app-frame">
    <header className="topbar">
      <NavLink to="/" className="brand"><span className="brand-mark">IF</span><span><strong>{t('app.name')}</strong><small>{t('app.kicker')}</small></span></NavLink>
      <div className="topbar-right"><span className="local-indicator"><i />LOCAL / 127.0.0.1</span><LocaleToggle /></div>
    </header>
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="rail-label">OPERATIONS</div>
      <nav>{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'}><Icon size={17}/><span>{label}</span></NavLink>)}</nav>
      <div className="rail-foot"><span>40Q</span><span>60M</span><span>100P</span></div>
    </aside>
    <main className="main"><Outlet /></main>
  </div>
}

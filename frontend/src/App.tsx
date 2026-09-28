import { useEffect, useState } from 'react'
import { getAuth, logout } from './api'
import LoginView from './components/LoginView'
import ReadView from './components/ReadView'
import FormsView from './editor/FormsView'

type View = 'read' | 'forms'
type Theme = 'light' | 'dark'

const viewFromHash = (): View => (location.hash.startsWith('#forms') ? 'forms' : 'read')

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem('theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* depolama kapalı olabilir */ }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const ScanIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
    <circle cx="8.5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" className="solid" /><circle cx="15.5" cy="12" r="1.6" />
  </svg>
)

const TemplateIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <rect x="4" y="3.5" width="16" height="17" rx="1.5" />
    <path d="M8 8h8M8 12h3" /><rect x="13" y="11" width="4" height="6" rx=".6" className="solid" />
  </svg>
)

const ThemeIcon = ({ theme }: { theme: Theme }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {theme === 'dark'
      ? <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></>
      : <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />}
  </svg>
)

export default function App() {
  const [view, setView] = useState<View>(viewFromHash)
  const [theme, setTheme] = useState<Theme>(initialTheme)
  // null: sorgulanıyor; false: giriş gerekli; true: açık
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)
  const [authRequired, setAuthRequired] = useState(false)

  useEffect(() => {
    getAuth()
      .then((a) => { setAuthRequired(a.required); setIsAuthenticated(a.authenticated) })
      .catch(() => setIsAuthenticated(true))
  }, [])

  useEffect(() => {
    // herhangi bir istek 401 dönerse (oturum düştü) giriş ekranına dön
    const original = window.fetch
    window.fetch = async (...args) => {
      const res = await original(...args)
      if (res.status === 401 && !String(args[0]).includes('/api/auth/')) setIsAuthenticated(false)
      return res
    }
    return () => { window.fetch = original }
  }, [])

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', theme) } catch { /* yoksay */ }
  }, [theme])

  if (isAuthenticated === null) return null
  if (!isAuthenticated) return <LoginView onLogin={() => setIsAuthenticated(true)} />

  return (
    <div className="shell">
      <aside className="rail">
        <div className="timingStrip" aria-hidden="true" />
        <a className="brand" href="#read" title="Optik Form Okuyucu">
          <span className="brandMark"><i /><i className="on" /><i /></span>
          <span className="brandName">Optik<b>Okuyucu</b></span>
        </a>
        <nav className="railNav">
          <a className={view === 'read' ? 'active' : ''} href="#read"><ScanIcon /><span>Okuma</span></a>
          <a className={view === 'forms' ? 'active' : ''} href="#forms"><TemplateIcon /><span>Form Tanımları</span></a>
        </nav>
        {authRequired && (
          <button className="themeToggle logoutButton" onClick={() => logout().then(() => setIsAuthenticated(false))} title="Oturumu kapat">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 4H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M15 8l4 4-4 4M19 12H9" /></svg>
            <span>Çıkış</span>
          </button>
        )}
        <button className="themeToggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}>
          <ThemeIcon theme={theme} /><span>{theme === 'dark' ? 'Açık tema' : 'Koyu tema'}</span>
        </button>
      </aside>
      <main className="app">
        <ReadView isActive={view === 'read'} />
        {view === 'forms' && <FormsView />}
      </main>
    </div>
  )
}

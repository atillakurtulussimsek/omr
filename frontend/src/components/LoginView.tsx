import { useState } from 'react'
import { login } from '../api'

interface LoginViewProps {
  onLogin: () => void
}

export default function LoginView({ onLogin }: LoginViewProps) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isBusy, setIsBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setIsBusy(true)
    setError('')
    try {
      await login(password)
      onLogin()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <div className="loginWrap">
      <form className="card loginCard" onSubmit={submit}>
        <span className="bubbleRow" aria-hidden="true"><i>A</i><i>B</i><i className="on">C</i><i>D</i><i>E</i></span>
        <h2>Giriş</h2>
        <p className="muted">Bu uygulama öğrenci verisi işler; devam etmek için yönetici şifresi gerekir.</p>
        <input
          type="password" autoFocus placeholder="Yönetici şifresi" value={password}
          onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
        />
        {error && <p className="errorText">{error}</p>}
        <button className="primary" type="submit" disabled={!password || isBusy}>{isBusy ? 'Kontrol ediliyor…' : 'Giriş yap'}</button>
      </form>
    </div>
  )
}

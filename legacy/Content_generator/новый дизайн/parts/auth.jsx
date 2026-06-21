/* global React, Icon, Header, HeroDeco */
// Auth screens: login, register, forgot password.

const AuthShell = ({ children }) => (
  <div style={{ display: 'flex', height: '100%', background: 'var(--bg)' }}>
    <div style={{
      flex: '0 0 360px',
      background: 'linear-gradient(155deg, #0d2018 0%, #102f22 38%, #18996a 100%)',
      color: '#fff',
      padding: 36, position: 'relative', overflow: 'hidden',
    }}>
      {/* layered green glows */}
      <div style={{ position: 'absolute', top: -120, left: -80, width: 360, height: 360, borderRadius: '50%', background: 'radial-gradient(circle, rgba(46,209,138,0.55), transparent 65%)', filter: 'blur(10px)' }}/>
      <div style={{ position: 'absolute', bottom: -100, right: -60, width: 320, height: 320, borderRadius: '50%', background: 'radial-gradient(circle, rgba(46,209,138,0.35), transparent 70%)', filter: 'blur(6px)' }}/>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'radial-gradient(rgba(46,209,138,0.18) 1px, transparent 1px)',
        backgroundSize: '14px 14px', opacity: .6,
      }}/>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 56 }}>
        <div className="hdr-mark" style={{ background: '#0d2018', color: '#2ed18a' }}>21</div>
        <div style={{ lineHeight: 1.2 }}>
          <b style={{ display: 'block', fontWeight: 600 }}>Генератор</b>
          <span style={{ fontSize: 11.5, opacity: .6 }}>учебных проектов</span>
        </div>
      </div>
      <div style={{ position: 'relative', zIndex: 1 }}>
        <div className="badge" style={{ background: 'rgba(255,255,255,.1)', color: '#fff', borderColor: 'transparent', marginBottom: 18 }}>
          <span className="badge-dot" /> Генератор контента
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 600, lineHeight: 1.15, margin: '0 0 14px', letterSpacing: '-0.02em' }}>
          Создавайте,<br/>проверяйте<br/>и переводите README<br/>в единой среде.
        </h1>
        <p style={{ fontSize: 13.5, opacity: .65, lineHeight: 1.55, maxWidth: 280, margin: 0 }}>
          Полный методологический пайплайн для авторов учебных проектов: от паспорта программы до готового документа со всеми критериями качества.
        </p>
      </div>
      <div style={{ position: 'absolute', bottom: 32, left: 36, right: 36, fontSize: 12, opacity: .4, display: 'flex', justifyContent: 'space-between' }}>
        <span>v 2.4 · build 318</span>
        <span>RU · EN · KG · UZ · TG</span>
      </div>
      {/* decorative grid bottom right */}
      <svg width="180" height="180" viewBox="0 0 180 180" fill="none"
        style={{ position: 'absolute', right: -40, bottom: -40, opacity: .12 }}>
        <rect x="0"  y="0"  width="40" height="40" rx="8" fill="#fff"/>
        <rect x="50" y="50" width="40" height="40" rx="8" fill="#fff"/>
        <rect x="100" y="0" width="40" height="40" rx="8" fill="#fff"/>
        <rect x="0"  y="100" width="40" height="40" rx="8" fill="#fff"/>
        <rect x="100" y="100" width="40" height="40" rx="8" fill="#fff"/>
      </svg>
    </div>
    <div style={{ flex: 1, display: 'grid', placeItems: 'center', padding: 40 }}>
      <div style={{ width: '100%', maxWidth: 380 }}>{children}</div>
    </div>
  </div>
);

const Login = () => (
  <div className="app" style={{ width: '100%', height: '100%' }}>
    <AuthShell>
      <h2 style={{ margin: '0 0 6px', fontSize: 24, fontWeight: 600 }}>С возвращением</h2>
      <p style={{ margin: '0 0 28px', color: 'var(--muted)', fontSize: 14 }}>Войдите в свой аккаунт, чтобы продолжить работу</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="field">
          <label className="lbl">Email</label>
          <input className="input" defaultValue="m.kravtsova@school21.ru" />
        </div>
        <div className="field">
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <label className="lbl">Пароль</label>
            <a className="text-link" style={{ fontSize: 12 }}>Забыли пароль?</a>
          </div>
          <div className="input-icon">
            <input className="input focused" type="text" defaultValue="••••••••••••" />
            <button className="ico-btn"><Icon.Eye /></button>
          </div>
        </div>
        <label className="check">
          <span className="box" style={{ background:'var(--ink)', borderColor:'var(--ink)' }}>
            <span style={{ width: 9, height: 6, border: '1.6px solid #fff', borderTop: 0, borderRight: 0, transform: 'rotate(-45deg) translate(1px,-1px)', display: 'block' }}/>
          </span>
          <span className="text">Запомнить меня на этом устройстве</span>
        </label>
        <button className="btn btn-primary btn-lg btn-block">Войти <Icon.Arrow /></button>
        <button className="btn btn-secondary btn-block" style={{ display: 'flex' }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M14.5 8.18c0-.51-.05-1-.13-1.45H8v2.74h3.66c-.16.84-.64 1.55-1.36 2.03v1.69h2.2c1.29-1.18 2-2.93 2-5.01z" fill="#4285F4"/>
            <path d="M8 15c1.84 0 3.39-.6 4.51-1.65l-2.2-1.69c-.61.41-1.39.65-2.31.65-1.78 0-3.28-1.19-3.82-2.8H1.91v1.74C3.03 13.51 5.34 15 8 15z" fill="#34A853"/>
            <path d="M4.18 9.51c-.14-.41-.22-.85-.22-1.31s.08-.9.22-1.31V5.15H1.91A6.97 6.97 0 001 8.2c0 1.13.27 2.19.91 3.05l2.27-1.74z" fill="#FBBC05"/>
            <path d="M8 4.09c1 0 1.9.34 2.61 1.02l1.94-1.94C11.39 2.04 9.84 1.4 8 1.4c-2.66 0-4.97 1.49-6.09 3.75L4.18 6.89c.54-1.61 2.04-2.8 3.82-2.8z" fill="#EA4335"/>
          </svg>
          Войти через Sber ID
        </button>
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginTop: 6 }}>
          Нет аккаунта? <a className="text-link">Создать аккаунт</a>
        </div>
      </div>
    </AuthShell>
  </div>
);

const LoginError = () => (
  <div className="app" style={{ width: '100%', height: '100%' }}>
    <AuthShell>
      <h2 style={{ margin: '0 0 6px', fontSize: 24, fontWeight: 600 }}>С возвращением</h2>
      <p style={{ margin: '0 0 24px', color: 'var(--muted)', fontSize: 14 }}>Войдите в свой аккаунт, чтобы продолжить работу</p>
      <div style={{ background: 'var(--danger-bg)', border: '1px solid #ebcec7', borderRadius: 'var(--radius-sm)', padding: '11px 13px', marginBottom: 16, display: 'flex', gap: 10, color: 'var(--danger)', fontSize: 13 }}>
        <Icon.Warn s={16} />
        <div>
          <b style={{ fontWeight: 600 }}>Не удалось войти.</b> Проверьте email и пароль или восстановите доступ.
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="field">
          <label className="lbl">Email</label>
          <input className="input" defaultValue="m.kravtsova@school21.ru" />
        </div>
        <div className="field">
          <label className="lbl">Пароль</label>
          <div className="input-icon">
            <input className="input error" type="text" defaultValue="••••••" />
            <button className="ico-btn"><Icon.Eye /></button>
          </div>
          <div className="err"><Icon.Warn s={12}/> Неверный email или пароль</div>
        </div>
        <button className="btn btn-primary btn-lg btn-block" disabled>
          <span className="spinner" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,.3)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', marginRight: 6 }}/>
          Входим…
        </button>
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginTop: 4 }}>
          Нет аккаунта? <a className="text-link">Создать аккаунт</a>
        </div>
      </div>
    </AuthShell>
  </div>
);

const Register = () => (
  <div className="app" style={{ width: '100%', height: '100%' }}>
    <AuthShell>
      <h2 style={{ margin: '0 0 6px', fontSize: 24, fontWeight: 600 }}>Создать аккаунт</h2>
      <p style={{ margin: '0 0 24px', color: 'var(--muted)', fontSize: 14 }}>Начните работу с генерацией, проверкой и переводом README</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="field">
          <label className="lbl">Email <span className="req">*</span></label>
          <input className="input" placeholder="ivan@school21.ru" />
        </div>
        <div className="field">
          <label className="lbl">Имя пользователя <span className="req">*</span></label>
          <input className="input" placeholder="Иван Петров" />
        </div>
        <div className="field">
          <label className="lbl">Пароль <span className="req">*</span></label>
          <div className="input-icon">
            <input className="input" type="password" placeholder="Минимум 8 символов" defaultValue="••••••••••" />
            <button className="ico-btn"><Icon.Eye /></button>
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            <div style={{ flex: 1, height: 3, borderRadius: 99, background: 'var(--success)' }}/>
            <div style={{ flex: 1, height: 3, borderRadius: 99, background: 'var(--success)' }}/>
            <div style={{ flex: 1, height: 3, borderRadius: 99, background: 'var(--success)' }}/>
            <div style={{ flex: 1, height: 3, borderRadius: 99, background: 'var(--surface-muted)' }}/>
          </div>
          <div className="help">Хороший пароль · минимум 8 символов</div>
        </div>
        <label className="check on" style={{ marginTop: 4 }}>
          <span className="box"/>
          <span className="text">Я принимаю условия использования сервиса и политику обработки данных</span>
        </label>
        <button className="btn btn-primary btn-lg btn-block">Зарегистрироваться <Icon.Arrow /></button>
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginTop: 4 }}>
          Уже есть аккаунт? <a className="text-link">Войти</a>
        </div>
      </div>
    </AuthShell>
  </div>
);

const Forgot = () => (
  <div className="app" style={{ width: '100%', height: '100%' }}>
    <AuthShell>
      <a className="text-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, marginBottom: 18, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> Вернуться к входу
      </a>
      <h2 style={{ margin: '0 0 6px', fontSize: 24, fontWeight: 600 }}>Восстановление пароля</h2>
      <p style={{ margin: '0 0 24px', color: 'var(--muted)', fontSize: 14 }}>Введите email, и мы отправим ссылку для восстановления пароля</p>

      <div style={{ background: 'var(--success-bg)', border: '1px solid #cee3d7', borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 16, display: 'flex', gap: 10, color: 'var(--success)', fontSize: 13 }}>
        <Icon.Check2 s={16} />
        <div>
          <b style={{ fontWeight: 600 }}>Письмо отправлено.</b> Проверьте почту <b>m.kravtsova@school21.ru</b> — ссылка действительна 30 минут.
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="field">
          <label className="lbl">Email</label>
          <input className="input" defaultValue="m.kravtsova@school21.ru" />
        </div>
        <button className="btn btn-primary btn-lg btn-block">Отправить ссылку повторно</button>
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginTop: 4 }}>
          Вспомнили пароль? <a className="text-link">Войти</a>
        </div>
      </div>
    </AuthShell>
  </div>
);

Object.assign(window, { Login, LoginError, Register, Forgot });

/* global React */
// Shared UI atoms and screen helpers used across all artboards.

const Icon = {
  Sparkle: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>
    </svg>
  ),
  Check: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3.5 3.5L13 4.5"/>
    </svg>
  ),
  X: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M4 4l8 8M12 4l-8 8"/>
    </svg>
  ),
  Eye: ({ s = 16 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z"/><circle cx="10" cy="10" r="2.5"/>
    </svg>
  ),
  Doc: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 2h7l3 3v13H5z"/><path d="M12 2v3h3M7 9h6M7 12h6M7 15h4"/>
    </svg>
  ),
  Up: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 14V4M5 9l5-5 5 5M3 16h14"/>
    </svg>
  ),
  Globe: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="10" cy="10" r="7.5"/><path d="M2.5 10h15M10 2.5c2.5 2.5 2.5 12.5 0 15M10 2.5c-2.5 2.5-2.5 12.5 0 15"/>
    </svg>
  ),
  Check2: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 11l4 4 10-10"/>
    </svg>
  ),
  Wand: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3l3 3M12 5l3 3-9 9-3-3zM3 3l1 2 2 1-2 1-1 2-1-2-2-1 2-1zM16 12l.6 1.4 1.4.6-1.4.6L16 16l-.6-1.4-1.4-.6 1.4-.6z"/>
    </svg>
  ),
  Arrow: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8h10M9 4l4 4-4 4"/>
    </svg>
  ),
  ArrLeft: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 8H3M7 4L3 8l4 4"/>
    </svg>
  ),
  Chevron: ({ s = 12, dir = 'down' }) => (
    <svg width={s} height={s} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
      style={{ transform: dir === 'up' ? 'rotate(180deg)' : dir === 'right' ? 'rotate(-90deg)' : 'none' }}>
      <path d="M3 4.5l3 3 3-3"/>
    </svg>
  ),
  Plus: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M8 3v10M3 8h10"/>
    </svg>
  ),
  Stop: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="currentColor"><rect x="4" y="4" width="8" height="8" rx="1.5"/></svg>
  ),
  Download: ({ s = 16 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 3v10M5 9l5 5 5-5M3 17h14"/>
    </svg>
  ),
  Info: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="8" cy="8" r="6.5"/><path d="M8 7v4M8 5v.5" strokeLinecap="round"/>
    </svg>
  ),
  Warn: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2L1.5 14h13z"/><path d="M8 6.5v4M8 12v.5"/>
    </svg>
  ),
  Video: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="5" width="11" height="10" rx="1.5"/><path d="M13 9l5-3v8l-5-3z"/>
    </svg>
  ),
  Settings: ({ s = 16 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="10" cy="10" r="2.5"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M4.3 15.7l1.4-1.4M14.3 5.7l1.4-1.4" strokeLinecap="round"/>
    </svg>
  ),
  Logo: ({ s = 28 }) => (
    <div className="hdr-mark" style={{ width: s, height: s, fontSize: s * 0.42 }}>21</div>
  ),
  Send: ({ s = 16 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2L7 9M14 2l-5 12-2-5-5-2z"/>
    </svg>
  ),
  Chat: ({ s = 18 }) => (
    <svg width={s} height={s} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 5a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H8l-4 3v-3H5a2 2 0 01-2-2z"/>
      <path d="M7 8h6M7 11h4"/>
    </svg>
  ),
  Stop2: ({ s = 14 }) => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="3" width="10" height="10" rx="2"/></svg>
  ),
};

// Modular "21" mark — 7×7 pixel grid with stair geometry
const GenMark = ({ size = 36 }) => {
  // build a chunky 21 in 7 rows × 7 cols
  const grid = [
    "1100100",
    "0010100",
    "1110100",
    "1000100",
    "1110100",
    "0000000",
    "0000000",
  ];
  const cells = [];
  grid.forEach((row, r) => {
    [...row].forEach((c, i) => cells.push(c === '1'));
  });
  return (
    <div className="gen-mark" style={{ width: size }}>
      {cells.map((on, i) => <i key={i} className={on ? 'on' : ''}/>)}
    </div>
  );
};

// Header used on every "in-app" screen
const Header = ({ active }) => (
  <div className="hdr">
    <div className="hdr-brand">
      <div className="hdr-mark">21</div>
      <div className="hdr-title">
        <b>Генератор</b>
        <span>учебных проектов · v 2.4</span>
      </div>
    </div>
    <nav className="hdr-nav">
      <a className={active === 'home' ? 'active' : ''}>Главная</a>
      <a className={active === 'gen' ? 'active' : ''}>Генерация</a>
      <a className={active === 'check' ? 'active' : ''}>Проверка</a>
      <a className={active === 'tr' ? 'active' : ''}>Перевод</a>
      <a className={active === 'docs' ? 'active' : ''}>Документация</a>
    </nav>
    <div className="hdr-spacer" />
    <div className="hdr-right">
      <div className="hdr-lang">
        <span className="on">RU</span><span>EN</span>
      </div>
      <div className="hdr-user">
        <div className="av">МК</div>
        <span>М. Кравцова</span>
      </div>
    </div>
  </div>
);

// Diamond / dot stair logo background
const HeroDeco = () => (
  <svg width="160" height="160" viewBox="0 0 160 160" fill="none" style={{ position: 'absolute', top: 30, right: 30, opacity: .9 }}>
    <rect x="0"   y="0"   width="36" height="36" rx="8" fill="#0f1419"/>
    <rect x="44"  y="0"   width="36" height="36" rx="8" fill="#0f1419" opacity=".15"/>
    <rect x="0"   y="44"  width="36" height="36" rx="8" fill="#0f1419" opacity=".15"/>
    <rect x="44"  y="44"  width="36" height="36" rx="8" fill="#0f1419" opacity=".4"/>
    <rect x="88"  y="44"  width="36" height="36" rx="8" fill="#0f1419"/>
    <rect x="44"  y="88"  width="36" height="36" rx="8" fill="#0f1419"/>
    <rect x="88"  y="88"  width="36" height="36" rx="8" fill="#0f1419" opacity=".15"/>
    <rect x="124" y="88"  width="36" height="36" rx="8" fill="#0f1419" opacity=".4"/>
    <rect x="88"  y="124" width="36" height="36" rx="8" fill="#0f1419" opacity=".4"/>
  </svg>
);

// Methodologist chat assistant — fixed bottom-right of any working screen
const MethodChat = () => (
  <div className="chat-panel">
    <div className="chat-head">
      <div className="av">M</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Методолог-ассистент</div>
        <div style={{ fontSize: 11, opacity: .7 }}>контрольная точка · этап 5/10</div>
      </div>
      <span className="chat-stage-pill"><span className="badge-dot" style={{ background: 'var(--accent)' }}/>Практика</span>
      <button style={{ background: 'transparent', border: 0, color: 'rgba(255,255,255,.6)', cursor: 'pointer', fontSize: 18, padding: 0, marginLeft: 6 }}>×</button>
    </div>
    <div className="chat-msgs">
      <div className="chat-msg bot">
        <div className="av-sm">M</div>
        <div className="chat-bubble">
          Готов план практики из 5 задач + бонус. Хотите внести правки до перехода к генерации теории?
          <div style={{ marginTop: 8, padding: 8, background: 'var(--surface-muted)', borderRadius: 8, fontSize: 12, color: 'var(--ink-2)' }}>
            <b style={{ fontWeight: 600 }}>Задача 3:</b> «Расчёт удержания по неделе регистрации»<br/>
            <span style={{ color: 'var(--muted)' }}>сложность · средняя · ≈45 мин</span>
          </div>
        </div>
      </div>
      <div className="chat-msg me">
        <div className="av-sm">МК</div>
        <div className="chat-bubble">Сделай задачу 3 проще — это первый блок. И добавь шаг с визуализацией.</div>
      </div>
      <div className="chat-msg bot">
        <div className="av-sm">M</div>
        <div className="chat-bubble">
          Понял. Упрощу формулировку и добавлю шаг 4 «Heatmap retention в seaborn».<br/>
          <button className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}>Применить и продолжить</button>
        </div>
      </div>
    </div>
    <div className="chat-quick">
      <span className="q">+ примеры</span>
      <span className="q">упростить</span>
      <span className="q">добавить шаг</span>
      <span className="q">по непройденным критериям</span>
    </div>
    <div className="chat-input">
      <textarea rows="1" placeholder="Комментарий методолога…" defaultValue=""/>
      <button title="Отправить"><Icon.Send s={16}/></button>
    </div>
  </div>
);

Object.assign(window, { Icon, Header, HeroDeco, GenMark, MethodChat });

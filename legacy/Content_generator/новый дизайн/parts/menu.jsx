/* global React, Icon, Header, HeroDeco */
// Main menu — mode selector

const ModeCard = ({ num, title, desc, items, cta, accent, illust }) => (
  <div className="card" style={{ display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
    <div style={{
      height: 140, background: accent, position: 'relative', overflow: 'hidden',
      borderBottom: '1px solid var(--border)',
      backgroundImage: 'radial-gradient(rgba(15,20,25,0.06) 1px, transparent 1px)',
      backgroundSize: '14px 14px',
    }}>
      <div style={{ position: 'absolute', top: 16, left: 18, fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
        Режим / 0{num}
      </div>
      {illust}
    </div>
    <div style={{ padding: '20px 22px 22px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
      <div>
        <h3 style={{ margin: 0, fontSize: 19, fontWeight: 600, letterSpacing: '-0.02em' }}>{title}</h3>
        <p style={{ margin: '6px 0 0', color: 'var(--muted)', fontSize: 13.5, lineHeight: 1.5 }}>{desc}</p>
      </div>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
        {items.map((t, i) => (
          <li key={i} style={{ display: 'flex', gap: 9, fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.45 }}>
            <span style={{ color: 'var(--ink)', flexShrink: 0, marginTop: 2 }}><Icon.Check s={13}/></span>
            {t}
          </li>
        ))}
      </ul>
      <button className="btn btn-primary btn-block" style={{ marginTop: 4 }}>{cta} <Icon.Arrow /></button>
    </div>
  </div>
);

const MainMenu = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="home" />
    <div className="scroll-y" style={{ flex: 1, padding: '40px 56px 60px', position: 'relative', overflow: 'auto' }}>
      <div style={{ position: 'relative', maxWidth: 1280, margin: '0 auto' }}>
        <HeroDeco />
        <div className="badge" style={{ marginBottom: 16 }}>
          <span className="badge-dot"/> Главная · v 2.4
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.05, maxWidth: 720 }}>
          Генератор учебных проектов
        </h1>
        <p style={{ margin: '14px 0 0', fontSize: 16, color: 'var(--muted)', maxWidth: 560, lineHeight: 1.55 }}>
          Выберите режим работы. Все три инструмента работают с одной методологической базой и общими словарями.
        </p>

        <div style={{ display: 'flex', gap: 14, marginTop: 28, fontSize: 12.5, color: 'var(--muted)', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }}/> Сервис доступен
          </span>
          <span style={{ opacity: .4 }}>·</span>
          <span>Последний запуск: <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>сегодня, 11:42</b></span>
          <span style={{ opacity: .4 }}>·</span>
          <span>Активных задач: <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>2</b></span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginTop: 36 }}>
          <ModeCard
            num={1}
            title="Генерация README"
            desc="Полный пайплайн: от паспорта программы до итогового документа с теорией, практикой и критериями."
            items={[
              'Анализ учебного плана и ЗУНов',
              'План практики, задачи и критерии',
              'Диаграммы, формулы, отчёты',
            ]}
            cta="Перейти к генератору"
            accent="var(--surface-2)"
            illust={
              <svg width="200" height="140" viewBox="0 0 200 140" style={{ position: 'absolute', right: -10, bottom: -10 }} fill="none">
                <rect x="20" y="20" width="60" height="80" rx="6" fill="#fff" stroke="#0f1419" strokeWidth="1.2"/>
                <rect x="30" y="32" width="40" height="3" rx="1.5" fill="#0f1419"/>
                <rect x="30" y="42" width="32" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="48" width="36" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="54" width="28" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="64" width="40" height="3" rx="1.5" fill="#0f1419"/>
                <rect x="30" y="74" width="34" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="80" width="38" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="86" width="22" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="100" y="40" width="60" height="80" rx="6" fill="#0f1419"/>
                <rect x="110" y="52" width="40" height="3" rx="1.5" fill="#fff"/>
                <rect x="110" y="62" width="32" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="110" y="68" width="36" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="110" y="74" width="28" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="110" y="86" width="22" height="22" rx="4" fill="#fff" opacity=".15"/>
                <path d="M115 97l5 5 9-9" stroke="#fff" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M82 60h16M90 56v8" stroke="#0f1419" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            }
          />
          <ModeCard
            num={2}
            title="Проверка README"
            desc="Загрузите готовый README.md и получите разбор по 39 критериям с понятными комментариями."
            items={[
              'Все 39 критериев качества',
              'Что улучшить и почему — текстом',
              'Метрики и структура документа',
            ]}
            cta="Перейти к проверке"
            accent="var(--surface-2)"
            illust={
              <svg width="200" height="140" viewBox="0 0 200 140" style={{ position: 'absolute', right: -10, bottom: -10 }} fill="none">
                <rect x="40" y="22" width="120" height="100" rx="6" fill="#fff" stroke="#0f1419" strokeWidth="1.2"/>
                <rect x="50" y="34" width="40" height="3" rx="1.5" fill="#0f1419"/>
                <circle cx="142" cy="36" r="14" fill="#0f1419"/>
                <text x="142" y="40" fontSize="9" fontWeight="700" fontFamily="Inter" fill="#fff" textAnchor="middle">87%</text>
                <rect x="50" y="58" width="100" height="6" rx="2" fill="#eef0ec"/>
                <rect x="50" y="58" width="84" height="6" rx="2" fill="#0f1419"/>
                <rect x="50" y="74" width="100" height="3" rx="1" fill="#0f1419" opacity=".25"/>
                <rect x="50" y="82" width="76" height="3" rx="1" fill="#0f1419" opacity=".25"/>
                <rect x="50" y="92" width="42" height="14" rx="3" fill="#eaf4ee"/>
                <text x="71" y="102" fontSize="8" fontWeight="600" fontFamily="Inter" fill="#2f7a4d" textAnchor="middle">35 ✓</text>
                <rect x="98" y="92" width="42" height="14" rx="3" fill="#f7ebe7"/>
                <text x="119" y="102" fontSize="8" fontWeight="600" fontFamily="Inter" fill="#b54a3b" textAnchor="middle">4 ✕</text>
              </svg>
            }
          />
          <ModeCard
            num={3}
            title="Перевод документов и видео"
            desc="Переведите README или Markdown с сохранением структуры. Также — видео и субтитры."
            items={[
              'Markdown, формулы и таблицы целые',
              'Поддержка Mermaid-диаграмм',
              'Субтитры VTT/SRT и видео-перевод',
            ]}
            cta="Перейти к переводу"
            accent="var(--surface-2)"
            illust={
              <svg width="200" height="140" viewBox="0 0 200 140" style={{ position: 'absolute', right: -10, bottom: -10 }} fill="none">
                <rect x="20" y="30" width="76" height="80" rx="6" fill="#fff" stroke="#0f1419" strokeWidth="1.2"/>
                <text x="58" y="52" fontSize="11" fontWeight="600" fontFamily="Inter" fill="#0f1419" textAnchor="middle">RU</text>
                <rect x="30" y="62" width="56" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="68" width="48" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="74" width="52" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <rect x="30" y="80" width="40" height="2" rx="1" fill="#0f1419" opacity=".3"/>
                <path d="M100 70h12M108 66l4 4-4 4" stroke="#0f1419" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                <rect x="116" y="30" width="76" height="80" rx="6" fill="#0f1419"/>
                <text x="154" y="52" fontSize="11" fontWeight="600" fontFamily="Inter" fill="#fff" textAnchor="middle">EN</text>
                <rect x="126" y="62" width="56" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="126" y="68" width="48" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="126" y="74" width="52" height="2" rx="1" fill="#fff" opacity=".5"/>
                <rect x="126" y="80" width="40" height="2" rx="1" fill="#fff" opacity=".5"/>
              </svg>
            }
          />
        </div>

        {/* Recent runs */}
        <div style={{ marginTop: 44 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Недавние запуски</h3>
            <a className="text-link" style={{ fontSize: 13 }}>Все запуски →</a>
          </div>
          <div className="card">
            {[
              { name: 'S21-DA-04 · Когортный анализ для Sales Funnel', stage: 'Готово', when: 'сегодня, 11:42', score: '36/39', tag: 'Генерация', status: 'success' },
              { name: 'S21-ML-12 · Классификация изображений (basic)', stage: 'Перевод', when: 'сегодня, 09:14', score: '—', tag: 'Перегенерация', status: 'info' },
              { name: 'README — Network Security Lab', stage: 'Проверка', when: 'вчера, 18:03', score: '24/39', tag: 'Проверка', status: 'warn' },
              { name: 'methodology-handbook.md → EN', stage: 'Готово', when: 'вчера, 14:51', score: '—', tag: 'Перевод', status: 'success' },
            ].map((r, i, arr) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '1fr 120px 100px 110px 90px',
                gap: 16, alignItems: 'center', padding: '14px 20px',
                borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--surface-muted)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                    <Icon.Doc s={16} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>{r.when}</div>
                  </div>
                </div>
                <span className="badge" style={{ background: 'var(--surface-muted)', borderColor: 'transparent' }}>{r.tag}</span>
                <span className={`badge ${r.status}`}>
                  <span className="badge-dot"/>{r.stage}
                </span>
                <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>{r.score}</span>
                <button className="btn btn-secondary btn-sm">Открыть</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, { MainMenu });

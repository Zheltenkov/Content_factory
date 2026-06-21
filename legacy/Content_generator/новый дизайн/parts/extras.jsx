/* global React, Icon, Header */
// Checker, translator, modal, design system

const Checker = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="check"/>
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <a className="text-link" style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> Главное меню
      </a>
      <span style={{ color: 'var(--border-strong)' }}>/</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>Проверка README</span>
      <div style={{ flex: 1 }}/>
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '480px 1fr', flex: 1, minHeight: 0 }}>
      <div className="scroll-y" style={{ overflowY: 'auto', borderRight: '1px solid var(--border)', background: 'var(--surface)', padding: '24px 28px' }}>
        <h2 style={{ margin: '0 0 4px', fontSize: 22, fontWeight: 600 }}>Проверка собственного README</h2>
        <p style={{ margin: '0 0 22px', color: 'var(--muted)', fontSize: 13.5 }}>Загрузите README.md и получите разбор по 39 критериям.</p>

        <div className="upload uploaded" style={{ padding: 16, alignItems: 'flex-start', flexDirection: 'row', textAlign: 'left', gap: 12 }}>
          <div className="ic"><Icon.Doc s={18}/></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>network-security-lab.md</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>62 КБ · 4 218 слов · загружен</div>
          </div>
          <button className="btn-ghost btn-sm" style={{ background: 'transparent', border: 0, color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>×</button>
        </div>

        <div style={{ marginTop: 18, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1, fontSize: 13.5, fontWeight: 500 }}>Образовательные результаты</div>
            <span className="badge" style={{ fontSize: 10 }}>опционально</span>
            <Icon.Chevron dir="up"/>
          </div>
          <div style={{ padding: '0 16px 16px' }}>
            <textarea className="textarea" rows="4" placeholder="Один результат в строке"
              defaultValue={"Понимать модели атак на сетевую инфраструктуру\nУметь анализировать pcap-логи в Wireshark\nЗнать принципы конфигурации firewall и IDS"}/>
          </div>
        </div>

        <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1, fontSize: 13.5, fontWeight: 500 }}>Учебный план для улучшения</div>
            <span className="badge" style={{ fontSize: 10 }}>опционально</span>
            <Icon.Chevron dir="down"/>
          </div>
        </div>

        <div style={{ marginTop: 24, display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost">Очистить результат</button>
          <div style={{ flex: 1 }}/>
          <button className="btn btn-primary btn-lg"><Icon.Check2 s={16}/> Проверить README</button>
        </div>
      </div>

      {/* Right: results */}
      <div className="scroll-y" style={{ overflowY: 'auto', padding: '24px 28px 56px', background: 'var(--bg)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 16 }}>
          <div className="card card-pad" style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 18 }}>
            <div style={{ flexShrink: 0 }}>
              <ScoreRing pct={68}/>
            </div>
            <div style={{ flex: 1 }}>
              <div className="badge warn" style={{ marginBottom: 6 }}><Icon.Warn s={11}/> Ниже порога 70 %</div>
              <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Оценка README: 68 %</h3>
              <p style={{ margin: '4px 0 12px', fontSize: 13, color: 'var(--muted)' }}>Пройдено <b style={{ color: 'var(--ink-2)', fontWeight: 600 }}>26 из 39</b> критериев. Рекомендуется улучшить документ — система может извлечь данные и автоматически сгенерировать улучшенную версию.</p>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary"><Icon.Wand s={15}/> Улучшить README</button>
                <button className="btn btn-secondary">Только отчёт</button>
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="tabs">
            {[['Критерии', '39'], ['Статистика текста', null], ['Исходный README', null], ['Улучшенный README', 'beta']].map(([t, b], i) => (
              <div key={t} className={`tab ${i === 0 ? 'on' : ''}`}>
                {t} {b && <span style={{ marginLeft: 6, fontSize: 11, padding: '1px 6px', borderRadius: 99, background: 'var(--surface-muted)', color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>{b}</span>}
              </div>
            ))}
          </div>

          <div style={{ padding: 18 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
              <span className="chip">Все<span className="count">39</span></span>
              <span className="chip on">Не пройдено<span className="count">8</span></span>
              <span className="chip">Предупреждения<span className="count">5</span></span>
              <span className="chip">Пройдено<span className="count">26</span></span>
              <div style={{ flex: 1 }}/>
              <span className="chip">Раздел: Структура</span>
              <span className="chip">Приоритет: Высокий</span>
            </div>

            {[
              { id: 'R-18', t: 'Шаги в задачах атомарны и нумерованы', sec: 'Требования', prio: 'Высокий', s: 'fail', rec: 'Разбейте шаг 3 в задаче 2 на два — текущая формулировка содержит две операции.' },
              { id: 'S-04', t: 'Веса критериев суммируются в 100 %', sec: 'Структура', prio: 'Высокий', s: 'fail', rec: 'Сейчас сумма весов 92 %. Перераспределите 8 % между критериями «Качество кода» и «Документирование».' },
              { id: 'T-06', t: 'Единое обращение к читателю', sec: 'Тон', prio: 'Средний', s: 'fail', rec: 'В разделе «Бонус» обращение «вы» — приведите к «ты» как в остальном документе.' },
              { id: 'T-08', t: 'Англицизмы пояснены при первом упоминании', sec: 'Тон', prio: 'Средний', s: 'warn', rec: '«Funnel», «retention», «churn» стоит дать пояснение в скобках.' },
              { id: 'D-12', t: 'Diff-like структура для решений отсутствует', sec: 'Содержание', prio: 'Низкий', s: 'warn', rec: 'Для задач с правками кода используйте формат «было / стало».' },
            ].map((it, i, arr) => (
              <div key={it.id} style={{
                display: 'grid', gridTemplateColumns: '36px 80px 1fr 110px 120px',
                gap: 14, padding: '14px 4px',
                borderBottom: i < arr.length-1 ? '1px solid var(--border)' : 'none',
                alignItems: 'flex-start',
              }}>
                <div style={{ width: 28, height: 28, borderRadius: 7, display: 'grid', placeItems: 'center', background: it.s === 'fail' ? 'var(--danger-bg)' : 'var(--warn-bg)', color: it.s === 'fail' ? 'var(--danger)' : 'var(--warn)' }}>
                  {it.s === 'fail' ? <Icon.X s={12}/> : <Icon.Warn s={12}/>}
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)', paddingTop: 6 }}>{it.id}</div>
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 500 }}>{it.t}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 4, lineHeight: 1.55 }}>{it.rec}</div>
                </div>
                <span className="badge" style={{ background: 'var(--surface-muted)', borderColor: 'transparent', alignSelf: 'flex-start' }}>{it.sec}</span>
                <span className={`badge ${it.prio === 'Высокий' ? 'danger' : it.prio === 'Средний' ? 'warn' : ''}`} style={{ alignSelf: 'flex-start' }}>{it.prio}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

const ScoreRing = ({ pct = 92, size = 96 }) => {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--surface-muted)" strokeWidth="6"/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={pct >= 70 ? 'var(--ink)' : 'var(--warn)'} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - pct/100)} transform={`rotate(-90 ${size/2} ${size/2})`}/>
      <text x={size/2} y={size/2 + 2} textAnchor="middle" dominantBaseline="middle" fontFamily="Inter" fontWeight="600" fontSize="20" fill="var(--ink)" letterSpacing="-0.02em">{pct}%</text>
      <text x={size/2} y={size/2 + 20} textAnchor="middle" fontFamily="Inter" fontSize="9" fill="var(--muted)" textTransform="uppercase" letterSpacing="0.08em" fontWeight="600">качество</text>
    </svg>
  );
};

// ─── Translator
const Translator = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="tr"/>
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <a className="text-link" style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> Главное меню
      </a>
      <span style={{ color: 'var(--border-strong)' }}>/</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>Перевод</span>
      <div style={{ flex: 1 }}/>
      {/* Mode switcher */}
      <div style={{ display: 'flex', padding: 3, background: 'var(--surface-muted)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontWeight: 500 }}>
        <button style={{ padding: '6px 14px', background: 'var(--surface)', border: 0, borderRadius: 6, boxShadow: 'var(--shadow-1)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Icon.Doc s={14}/> Документ
        </button>
        <button style={{ padding: '6px 14px', background: 'transparent', border: 0, color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Icon.Video s={14}/> Видео
        </button>
      </div>
    </div>

    <div className="scroll-y" style={{ flex: 1, overflowY: 'auto', padding: '24px 28px 60px', background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        {/* Settings strip */}
        <div className="card card-pad" style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr auto', gap: 16, alignItems: 'flex-end', marginBottom: 16 }}>
          <div className="field">
            <label className="lbl">Источник</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
              <Icon.Doc s={14}/>
              <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>methodology-handbook.md</span>
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>RU · 4 218 слов</span>
              <button style={{ background: 'transparent', border: 0, color: 'var(--muted)', cursor: 'pointer' }}><Icon.X s={12}/></button>
            </div>
          </div>
          <div className="field">
            <label className="lbl">Режим</label>
            <select className="select" defaultValue="literal">
              <option value="literal">Дословный</option>
              <option>Комбинация версий</option>
            </select>
          </div>
          <div className="field">
            <label className="lbl">Целевой язык</label>
            <select className="select" defaultValue="en">
              <option value="ru">RU · Русский</option>
              <option value="en">EN · Английский</option>
              <option>KG · Киргизский</option>
              <option>UZ · Узбекский</option>
              <option>TG · Таджикский</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm">Очистить</button>
            <button className="btn btn-primary"><Icon.Globe s={15}/> Перевести</button>
          </div>
        </div>

        {/* Split view */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
            {/* Original */}
            <div style={{ borderRight: '1px solid var(--border)' }}>
              <div style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border)' }}>
                <span className="badge" style={{ background: 'var(--surface-muted)', borderColor: 'transparent' }}>RU · Оригинал</span>
                <div style={{ flex: 1 }}/>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>4 218 слов · 25 КБ</span>
              </div>
              <div style={{ padding: '24px 28px', fontSize: 13.5, lineHeight: 1.65, color: 'var(--ink-2)', maxHeight: 540, overflow: 'auto' }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}># Методология учебных проектов</h2>
                <p>Этот документ описывает, как мы строим учебные проекты Школы 21 — от формулирования цели до критериев приёмки. Он адресован методистам и преподавателям.</p>
                <h3 style={{ fontSize: 15, marginTop: 18 }}>## ЗУНы и образовательные результаты</h3>
                <p>ЗУНы — знания, умения и навыки — это атомарная единица учебного результата. Каждой задаче проекта должна соответствовать минимум одна ЗУНа из учебного плана.</p>
                <ul style={{ paddingLeft: 18 }}>
                  <li>Знания формулируются как «знать что»</li>
                  <li>Умения — как «уметь делать»</li>
                  <li>Навыки — как «делать в условиях»</li>
                </ul>
                <h3 style={{ fontSize: 15, marginTop: 16 }}>## Структура задачи</h3>
                <p>Каждая задача состоит из контекста, входа, шагов и ожидаемого результата.</p>
              </div>
            </div>
            {/* Translated */}
            <div>
              <div style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border)' }}>
                <span className="badge success"><Icon.Check s={11}/> EN · Перевод</span>
                <div style={{ flex: 1 }}/>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>4 102 слов</span>
                <button className="btn btn-secondary btn-sm"><Icon.Download s={12}/> Скачать</button>
              </div>
              <div style={{ padding: '24px 28px', fontSize: 13.5, lineHeight: 1.65, color: 'var(--ink-2)', maxHeight: 540, overflow: 'auto' }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}># Methodology of educational projects</h2>
                <p>This document describes how we build School 21 educational projects — from goal-setting to acceptance criteria. It is addressed to methodologists and teachers.</p>
                <h3 style={{ fontSize: 15, marginTop: 18 }}>## Knowledge, skills and abilities</h3>
                <p>KSA — knowledge, skills and abilities — is the atomic unit of an educational outcome. Each project task must correspond to at least one KSA from the curriculum.</p>
                <ul style={{ paddingLeft: 18 }}>
                  <li>Knowledge is phrased as “to know what”</li>
                  <li>Skills — as “to be able to do”</li>
                  <li>Abilities — as “to do under conditions”</li>
                </ul>
                <h3 style={{ fontSize: 15, marginTop: 16 }}>## Task structure</h3>
                <p>Each task consists of context, input, steps and expected outcome.</p>
              </div>
            </div>
          </div>
          <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, background: 'var(--surface-2)' }}>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>Сохранены: <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>Markdown</b> · <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>таблицы</b> · <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>формулы</b> · <b style={{ color: 'var(--ink-2)', fontWeight: 500 }}>Mermaid</b></span>
            <div style={{ flex: 1 }}/>
            <button className="btn btn-ghost btn-sm">Сравнить</button>
            <button className="btn btn-secondary btn-sm">Копировать</button>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ─── Translator video mode
const TranslatorVideo = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="tr"/>
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <span style={{ fontSize: 13, fontWeight: 500 }}>Перевод · Видео</span>
      <div style={{ flex: 1 }}/>
      <div style={{ display: 'flex', padding: 3, background: 'var(--surface-muted)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontWeight: 500 }}>
        <button style={{ padding: '6px 14px', background: 'transparent', border: 0, color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Icon.Doc s={14}/> Документ
        </button>
        <button style={{ padding: '6px 14px', background: 'var(--surface)', border: 0, borderRadius: 6, boxShadow: 'var(--shadow-1)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Icon.Video s={14}/> Видео
        </button>
      </div>
    </div>
    <div className="scroll-y" style={{ flex: 1, overflowY: 'auto', padding: '32px 28px 60px', background: 'var(--bg)' }}>
      <div style={{ maxWidth: 880, margin: '0 auto', display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 20 }}>
        <div>
          <div className="upload uploaded" style={{ padding: 20, alignItems: 'flex-start', flexDirection: 'column', textAlign: 'left', gap: 0 }}>
            <div style={{ width: '100%', aspectRatio: '16 / 9', background: 'var(--ink)', borderRadius: 'var(--radius-sm)', position: 'relative', overflow: 'hidden', marginBottom: 14 }}>
              <div className="pattern-dots" style={{ position: 'absolute', inset: 0, opacity: .12 }}/>
              <div style={{ position: 'absolute', top: 12, left: 14, color: 'rgba(255,255,255,.7)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>methodology-intro.mp4</div>
              <div style={{ position: 'absolute', bottom: 14, left: 14, right: 14, color: '#fff', fontSize: 14, lineHeight: 1.45, background: 'rgba(15,20,25,.6)', padding: '6px 10px', borderRadius: 4, backdropFilter: 'blur(2px)' }}>
                ЗУНы — атомарная единица учебного результата.
              </div>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: 56, height: 56, borderRadius: '50%', background: 'rgba(255,255,255,.16)', backdropFilter: 'blur(4px)', display: 'grid', placeItems: 'center' }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="#fff"><path d="M5 3l13 7-13 7z"/></svg>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 500, width: '100%' }}>
              <span style={{ flex: 1 }}>methodology-intro.mp4</span>
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>54 МБ · 04:21</span>
            </div>
            <div style={{ marginTop: 12, width: '100%' }}>
              <div className="pbar"><div className="pbar-fill" style={{ width: '72%' }}/></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                <span>Распознавание речи</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>72 %</span>
              </div>
            </div>
          </div>
          <div className="help" style={{ marginTop: 8 }}>MP4, WebM, MOV, AVI, MKV. До 100 МБ.</div>
        </div>

        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Параметры перевода</h3>
          <div className="field">
            <label className="lbl">Что получить</label>
            {[
              ['Видео с субтитрами', true],
              ['Файлы субтитров (VTT, SRT, ASS)', true],
              ['Только транскрипт (.txt)', false],
            ].map(([t, on]) => (
              <label key={t} className={`check ${on ? 'on' : ''}`} style={{ marginTop: 6 }}>
                <span className="box"/>
                <span className="text">{t}</span>
              </label>
            ))}
          </div>
          <div className="field">
            <label className="lbl">Целевой язык</label>
            <select className="select" defaultValue="en">
              <option value="ru">RU · Русский</option>
              <option value="en">EN · Английский</option>
              <option>KG · Киргизский</option>
              <option>UZ · Узбекский</option>
            </select>
          </div>
          <div className="field">
            <label className="lbl">Сохранить голос диктора <span className="opt">экспериментально</span></label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface-2)' }}>
              <div className="toggle"/>
              <span style={{ fontSize: 13, color: 'var(--muted)' }}>Клонировать тембр оригинала (TTS)</span>
            </div>
          </div>
          <button className="btn btn-primary btn-lg" style={{ marginTop: 'auto' }}><Icon.Globe s={15}/> Перевести видео</button>
        </div>
      </div>
    </div>
  </div>
);

// ─── Modal: improve README data
const ImproveModal = () => (
  <div className="app" style={{ width: '100%', height: '100%', position: 'relative', background: 'rgba(15,20,25,0.45)', backdropFilter: 'blur(2px)' }}>
    <div style={{
      position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
      width: 720, maxHeight: '90%', display: 'flex', flexDirection: 'column',
      background: 'var(--surface)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-3)', overflow: 'hidden',
    }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <div style={{ width: 36, height: 36, borderRadius: 9, background: 'var(--ink)', color: '#fff', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
          <Icon.Wand s={18}/>
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>Улучшение README</h3>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>Мы извлекли данные из README. Проверьте их перед генерацией улучшенной версии.</p>
        </div>
        <button style={{ background: 'transparent', border: 0, fontSize: 22, color: 'var(--muted)', cursor: 'pointer', lineHeight: 1, padding: 4 }}>×</button>
      </div>

      {/* Step indicator */}
      <div style={{ padding: '14px 24px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8, fontSize: 12, alignItems: 'center', background: 'var(--surface-2)' }}>
        {[['1', 'Основное', 'on'], ['2', 'Параметры проекта', ''], ['3', 'ЗУНы и навыки', ''], ['4', 'Бонус и репозиторий', '']].map(([n, t, s]) => (
          <React.Fragment key={n}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ width: 22, height: 22, borderRadius: 6, background: s === 'on' ? 'var(--ink)' : 'var(--surface-muted)', color: s === 'on' ? '#fff' : 'var(--muted)', fontWeight: 600, display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)' }}>{n}</span>
              <span style={{ fontWeight: s === 'on' ? 600 : 500, color: s === 'on' ? 'var(--ink)' : 'var(--muted)' }}>{t}</span>
            </div>
            {n !== '4' && <div style={{ flex: 1, height: 1, background: 'var(--border)' }}/>}
          </React.Fragment>
        ))}
      </div>

      <div className="scroll-y" style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
        <div style={{ background: 'var(--info-bg)', border: '1px solid #cdd9e7', borderRadius: 'var(--radius-sm)', padding: '10px 12px', display: 'flex', gap: 9, fontSize: 12.5, color: 'var(--info)', marginBottom: 16 }}>
          <Icon.Info s={14}/>
          <div>Данные извлечены автоматически. Поля, отмеченные <b>★</b>, не удалось распознать — заполните вручную.</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="field" style={{ gridColumn: 'span 2' }}>
            <label className="lbl">Название проекта <span className="req">*</span></label>
            <input className="input" defaultValue="Network Security Lab"/>
          </div>
          <div className="field" style={{ gridColumn: 'span 2' }}>
            <label className="lbl">Описание проекта <span className="req">*</span></label>
            <textarea className="textarea" rows="2" defaultValue="Студент собирает безопасную конфигурацию сети, моделирует атаки и анализирует логи."/>
          </div>
          <div className="field">
            <label className="lbl">Язык <span className="req">*</span></label>
            <select className="select"><option>RU · Русский</option></select>
          </div>
          <div className="field">
            <label className="lbl">Тематический блок <span className="req">*</span></label>
            <select className="select"><option>Сетевая безопасность</option></select>
            <a className="text-link" style={{ fontSize: 12, marginTop: 4 }}>+ добавить новый блок</a>
          </div>
          <div className="field">
            <label className="lbl">Уровень аудитории <span className="req">*</span></label>
            <select className="select"><option>Intermediate</option></select>
          </div>
          <div className="field">
            <label className="lbl">Тип проекта <span className="req">*</span></label>
            <select className="select"><option>Групповой · 3 чел.</option></select>
          </div>
          <div className="field" style={{ gridColumn: 'span 2' }}>
            <label className="lbl">Образовательные результаты <span style={{ color: 'var(--warn)', fontWeight: 700 }}>★</span></label>
            <textarea className="textarea" rows="3" placeholder="Не удалось извлечь автоматически — заполните вручную"/>
            <div className="help">По одному результату в строке</div>
          </div>
        </div>
      </div>

      <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center', background: 'var(--surface-2)' }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>Шаг 1 из 4</span>
        <div style={{ flex: 1 }}/>
        <button className="btn btn-ghost">Отмена</button>
        <button className="btn btn-primary">Далее <Icon.Arrow s={13}/></button>
      </div>
    </div>
  </div>
);

// ─── Design system board
const DesignSystem = () => (
  <div className="app" style={{ width: '100%', height: '100%', overflow: 'auto', background: 'var(--bg)' }}>
    <div style={{ padding: '32px 36px 56px', maxWidth: 1240, margin: '0 auto' }}>
      <div className="badge" style={{ marginBottom: 12 }}><span className="badge-dot"/> Design system · v 1.0</div>
      <h1 style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em' }}>Дизайн-система «Генератор»</h1>
      <p style={{ margin: '10px 0 28px', color: 'var(--muted)', fontSize: 14, maxWidth: 600 }}>Светлая, нейтральная, без брендовой привязки. Один акцентный цвет, мягкие скругления 8–12 px, пропорциональная типографика.</p>

      {/* Colors */}
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Цвета</h3>
      <div className="card card-pad" style={{ marginBottom: 24 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
          {[
            ['Page', '#f7f7f5', 'var(--bg)'],
            ['Surface', '#ffffff', 'var(--surface)'],
            ['Muted', '#f3f3f0', 'var(--surface-muted)'],
            ['Border', '#e6e5e0', 'var(--border)'],
            ['Ink', '#0f1419', 'var(--ink)'],
            ['Muted text', '#6b6f78', 'var(--muted)'],
          ].map(([n, hex, v]) => (
            <div key={n}>
              <div style={{ height: 56, borderRadius: 8, background: v, border: '1px solid var(--border)' }}/>
              <div style={{ marginTop: 6, fontSize: 12, fontWeight: 500 }}>{n}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{hex}</div>
            </div>
          ))}
          {[
            ['Success', '#2f7a4d', 'var(--success)'],
            ['Warn', '#a76a14', 'var(--warn)'],
            ['Danger', '#b54a3b', 'var(--danger)'],
            ['Info', '#2a5d8f', 'var(--info)'],
          ].map(([n, hex, v]) => (
            <div key={n}>
              <div style={{ height: 56, borderRadius: 8, background: v }}/>
              <div style={{ marginTop: 6, fontSize: 12, fontWeight: 500 }}>{n}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{hex}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Type */}
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Типографика — Inter</h3>
      <div className="card card-pad" style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {[
          ['H1 · 44 / 600 / -0.03em', 44, 600, 'Сложное — простым'],
          ['H2 · 28 / 600 / -0.02em', 28, 600, 'Заголовок раздела'],
          ['H3 · 18 / 600', 18, 600, 'Подзаголовок карточки'],
          ['Body · 14 / 400', 14, 400, 'Основной текст интерфейса. Цвет — ink-2 для длинных абзацев.'],
          ['Caption · 12 / 500 / muted', 12, 500, 'Хелперы, метаданные, сноски'],
          ['Mono · 12.5 / 500 (JetBrains Mono)', 12.5, 500, 'task_3.title · 03:42 · S21-DA-04', true],
        ].map(([n, sz, w, sample, mono]) => (
          <div key={n} style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20, alignItems: 'baseline', borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
            <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{n}</span>
            <span style={{ fontSize: sz, fontWeight: w, fontFamily: mono ? 'var(--font-mono)' : 'inherit', letterSpacing: sz >= 28 ? '-0.02em' : 'normal' }}>{sample}</span>
          </div>
        ))}
      </div>

      {/* Components */}
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Компоненты</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card card-pad">
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 10 }}>Buttons</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <button className="btn btn-primary">Primary</button>
            <button className="btn btn-secondary">Secondary</button>
            <button className="btn btn-ghost">Ghost</button>
            <button className="btn btn-danger">Danger</button>
            <button className="btn btn-primary" disabled>Disabled</button>
            <button className="btn btn-primary btn-sm">Small</button>
            <button className="btn btn-primary btn-lg">Large CTA</button>
          </div>
        </div>
        <div className="card card-pad">
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 10 }}>Badges & chips</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <span className="badge"><span className="badge-dot"/>Default</span>
            <span className="badge success"><Icon.Check s={11}/>Success</span>
            <span className="badge warn"><Icon.Warn s={11}/>Warn</span>
            <span className="badge danger"><Icon.X s={11}/>Danger</span>
            <span className="badge info"><Icon.Info s={11}/>Info</span>
            <span className="chip">Все<span className="count">39</span></span>
            <span className="chip on">Не пройдено<span className="count">3</span></span>
          </div>
        </div>
        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Inputs</div>
          <input className="input" placeholder="Default"/>
          <input className="input focused" defaultValue="Focused"/>
          <input className="input error" defaultValue="Error"/>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <label className="check on"><span className="box"/><span className="text">Selected</span></label>
            <label className="check"><span className="box"/><span className="text">Default</span></label>
            <div className="toggle on"/>
            <div className="toggle"/>
          </div>
        </div>
        <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Status states</div>
          <div style={{ background: 'var(--success-bg)', color: 'var(--success)', padding: '10px 12px', borderRadius: 8, fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Icon.Check2 s={14}/> README сохранён в архив · 11:42
          </div>
          <div style={{ background: 'var(--warn-bg)', color: 'var(--warn)', padding: '10px 12px', borderRadius: 8, fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Icon.Warn s={14}/> Веса критериев не суммируются в 100 %
          </div>
          <div style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '10px 12px', borderRadius: 8, fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Icon.X s={14}/> Не удалось загрузить файл — превышен лимит
          </div>
          <div style={{ background: 'var(--info-bg)', color: 'var(--info)', padding: '10px 12px', borderRadius: 8, fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Icon.Info s={14}/> Антиплагиат запущен в фоне — займёт ~2 мин
          </div>
        </div>
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginTop: 28, marginBottom: 12 }}>Радиусы и тени</h3>
      <div className="card card-pad" style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {[
          ['xs · 6', 6, 'var(--shadow-1)'],
          ['sm · 8', 8, 'var(--shadow-1)'],
          ['md · 10', 10, 'var(--shadow-2)'],
          ['lg · 14', 14, 'var(--shadow-2)'],
          ['xl · 20', 20, 'var(--shadow-3)'],
        ].map(([n, r, sh]) => (
          <div key={n} style={{ width: 130, height: 80, background: 'var(--surface)', borderRadius: r, boxShadow: sh, border: '1px solid var(--border)', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 500, color: 'var(--muted)' }}>{n}px</div>
        ))}
      </div>
    </div>
  </div>
);

Object.assign(window, { Checker, Translator, TranslatorVideo, ImproveModal, DesignSystem });

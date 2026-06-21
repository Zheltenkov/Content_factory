/* global React, Icon, Header */
// Generation progress + results screens

const Progress = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="gen" />
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <a className="text-link" style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> Главное меню
      </a>
      <span style={{ color: 'var(--border-strong)' }}>/</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>Генерация README</span>
      <span className="badge info"><span className="badge-dot"/>Выполняется</span>
      <div style={{ flex: 1 }}/>
      <button className="btn btn-danger btn-sm"><Icon.Stop s={11}/> Аварийная остановка</button>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '560px 1fr', flex: 1, minHeight: 0 }}>
      {/* LEFT — collapsed input summary */}
      <div className="scroll-y" style={{ overflowY: 'auto', borderRight: '1px solid var(--border)', background: 'var(--surface)', padding: '24px 28px' }}>
        <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 600 }}>Параметры запуска</h2>
        <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--muted)' }}>Зафиксированы на момент запуска · 11:38:42</p>
        <div className="card" style={{ padding: 0 }}>
          {[
            ['Учебный план', 'data-analytics-2025-passport.csv'],
            ['Направление', 'Бизнес-аналитика'],
            ['Тематический блок', 'Аналитические продукты'],
            ['Проект из УП', 'S21-DA-04'],
            ['Название', 'Когортный анализ для Sales Funnel'],
            ['Тип', 'Индивидуальный · Beginner+'],
            ['Язык', 'RU · Русский'],
            ['Кол-во задач', '5 + бонус'],
            ['Методология', 'Включена'],
          ].map(([k, v], i, arr) => (
            <div key={k} style={{ display: 'flex', padding: '11px 16px', borderBottom: i < arr.length-1 ? '1px solid var(--border)' : 'none', fontSize: 13 }}>
              <span style={{ flex: '0 0 180px', color: 'var(--muted)' }}>{k}</span>
              <span style={{ flex: 1, fontWeight: 500 }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 18, padding: 14, background: 'var(--warn-bg)', border: '1px solid #ead7b6', borderRadius: 'var(--radius-md)', color: 'var(--warn)', fontSize: 12.5, display: 'flex', gap: 10 }}>
          <Icon.Warn s={14}/>
          <div>
            <b style={{ fontWeight: 600 }}>Не закрывайте страницу.</b><br/>
            Генерация может занять до 15 минут. Прогресс сохраняется на сервере — если связь оборвётся, вы сможете вернуться к запуску.
          </div>
        </div>
      </div>

      {/* RIGHT — progress timeline */}
      <div className="scroll-y" style={{ overflowY: 'auto', padding: '32px 56px' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
            <div style={{
              width: 64, height: 64, borderRadius: 16, background: 'var(--ink)', color: '#fff',
              display: 'grid', placeItems: 'center', position: 'relative',
            }}>
              <svg width="64" height="64" viewBox="0 0 64 64" style={{ position: 'absolute', inset: 0 }}>
                <circle cx="32" cy="32" r="28" fill="none" stroke="rgba(255,255,255,.18)" strokeWidth="3"/>
                <circle cx="32" cy="32" r="28" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round"
                  strokeDasharray="176" strokeDashoffset="79" transform="rotate(-90 32 32)"/>
              </svg>
              <span style={{ fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>55%</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Этап 5 из 10</div>
              <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2, letterSpacing: '-0.02em' }}>Генерация практики</div>
              <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>Создаём задачи №3 и №4 · CriticAgent параллельно проверяет №1, №2</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Время</div>
              <div style={{ fontSize: 24, fontFamily: 'var(--font-mono)', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>03:42</div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>осталось ~ 6 мин</div>
            </div>
          </div>

          <div className="card card-pad">
            <div className="timeline">
              {[
                { n: '01', t: 'Анализ контекста', s: 'done', time: '0:18' },
                { n: '02', t: 'Планирование практики', s: 'done', time: '0:42' },
                { n: '03', t: 'Каркас README', s: 'done', time: '1:05' },
                { n: '04', t: 'Генерация теории', s: 'done', time: '2:21', sub: 'разделы: 3 · формул: 4 · диаграмм: 1' },
                { n: '05', t: 'Генерация практики', s: 'now', time: '3:42 / ~5:30', sub: 'задача 3 из 5 · CriticAgent активен' },
                { n: '06', t: 'Проверка качества', s: 'pending' },
                { n: '07', t: 'Антиплагиат', s: 'pending' },
                { n: '08', t: 'Оценка по критериям', s: 'pending' },
                { n: '09', t: 'Перевод', s: 'pending', sub: 'пропускается — целевой язык RU' },
                { n: '10', t: 'Сборка результата', s: 'pending' },
              ].map((r) => (
                <div key={r.n} className={`tl-row ${r.s}`}>
                  <div className="tl-dot">{r.s === 'done' ? <Icon.Check s={12}/> : r.n}</div>
                  <div>
                    <div className="tl-text">{r.t}</div>
                    {r.sub && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{r.sub}</div>}
                  </div>
                  <div className="tl-time">{r.time || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Methodologist gate */}
          <div style={{ marginTop: 16, border: '1px solid #b6e6cd', background: 'var(--accent-soft)', borderRadius: 'var(--radius-md)', padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent-dark-bg)', color: 'var(--accent)', display: 'grid', placeItems: 'center', flexShrink: 0 }}><Icon.Chat s={14}/></div>
            <div style={{ flex: 1, fontSize: 12.5, color: 'var(--ink-2)' }}>
              <b style={{ fontWeight: 600 }}>Контрольная точка методолога.</b> Практика готова — оставьте комментарий ассистенту, чтобы внести правки до генерации теории.
            </div>
            <button className="btn btn-primary btn-sm">Открыть чат</button>
          </div>

          {/* Live log peek */}
          <div style={{ marginTop: 16, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)' }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5, color: 'var(--muted)' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }}/>
              <span style={{ fontWeight: 500, color: 'var(--ink-2)' }}>Лог пайплайна</span>
              <div style={{ flex: 1 }}/>
              <a className="text-link" style={{ fontSize: 12 }}>скрыть</a>
            </div>
            <div style={{ padding: 14, fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.7, background: 'var(--surface-2)' }}>
              <div><span style={{ color: 'var(--ink-2)' }}>[03:38]</span> task_3.solution: validating against rubric R-12, R-18 …</div>
              <div><span style={{ color: 'var(--ink-2)' }}>[03:39]</span> CriticAgent: task_2 → score 0.86, suggestion: «уточнить шаг 4»</div>
              <div><span style={{ color: 'var(--ink-2)' }}>[03:41]</span> theory.section_3: ✓ committed (412 tokens)</div>
              <div style={{ color: 'var(--ink)' }}>[03:42] task_3.title: «Расчёт удержания по неделе регистрации» ▍</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <MethodChat/>
  </div>
);

// ─── Results screen
const ScoreRing = ({ pct = 92, size = 112 }) => {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--surface-muted)" strokeWidth="6"/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--ink)" strokeWidth="6" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - pct/100)} transform={`rotate(-90 ${size/2} ${size/2})`}/>
      <text x={size/2} y={size/2 + 2} textAnchor="middle" dominantBaseline="middle" fontFamily="Inter" fontWeight="600" fontSize="22" fill="var(--ink)" letterSpacing="-0.02em">{pct}%</text>
      <text x={size/2} y={size/2 + 22} textAnchor="middle" fontFamily="Inter" fontSize="9" fill="var(--muted)" textTransform="uppercase" letterSpacing="0.08em" fontWeight="600">качество</text>
    </svg>
  );
};

const Results = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="gen"/>
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <a className="text-link" style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> К параметрам
      </a>
      <span style={{ color: 'var(--border-strong)' }}>/</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>S21-DA-04 · Когортный анализ</span>
      <span className="badge success"><Icon.Check s={11}/> Готово · 09:41</span>
      <div style={{ flex: 1 }}/>
      <button className="btn btn-secondary btn-sm">Перегенерация</button>
      <button className="btn btn-primary btn-sm"><Icon.Download s={13}/> Скачать архив</button>
    </div>

    <div className="scroll-y" style={{ flex: 1, overflowY: 'auto', padding: '24px 28px 56px', background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        {/* Top summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 1fr 1fr', gap: 14, marginBottom: 18 }}>
          <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <ScoreRing pct={92}/>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)' }}>Оценка README</div>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 2 }}>36 / 39</div>
              <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 4 }}>Превышен порог 70 % · готов к публикации</div>
            </div>
          </div>
          {[
            { t: 'Слов', v: '4 218', s: 'Читаемость · Хорошая' },
            { t: 'Задач', v: '5 + 1', s: 'Сложность · Beginner+' },
            { t: 'Антиплагиат', v: '98 %', s: 'Уникальность по корпусу' },
          ].map((m) => (
            <div key={m.t} className="card card-pad">
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)' }}>{m.t}</div>
              <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 6, fontFamily: 'var(--font-mono)' }}>{m.v}</div>
              <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 6 }}>{m.s}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="tabs">
            {['Итоговый README', 'Практика', 'Данные', 'Метрики', 'Отчёт', 'Перегенерация'].map((t, i) => (
              <div key={t} className={`tab ${i === 0 ? 'on' : ''}`}>{t}</div>
            ))}
            <div style={{ flex: 1 }}/>
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 8px', gap: 6 }}>
              <button className="btn btn-ghost btn-sm">Сравнить</button>
              <button className="btn btn-secondary btn-sm">Markdown</button>
              <button className="btn btn-secondary btn-sm">Превью</button>
            </div>
          </div>

          {/* Markdown preview */}
          <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', minHeight: 480 }}>
            {/* TOC */}
            <div style={{ borderRight: '1px solid var(--border)', padding: '20px 16px', background: 'var(--surface-2)', fontSize: 12.5 }}>
              <div style={{ fontWeight: 600, fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>Содержание</div>
              {[
                ['Описание проекта', true],
                ['Учебная цель и ЗУНы', false],
                ['Теоретическая часть', false],
                ['Практика', false],
                ['Задача 1. SQL-агрегации', false],
                ['Задача 2. Когорты в pandas', false],
                ['Задача 3. Удержание по нед.', false],
                ['Задача 4. Визуализация', false],
                ['Задача 5. Презентация', false],
                ['Бонус. Дашборд в Metabase', false],
                ['Критерии оценки', false],
                ['Чек-лист сдачи', false],
              ].map(([t, on], i) => (
                <div key={i} style={{
                  padding: '5px 8px', borderRadius: 5, cursor: 'pointer',
                  background: on ? 'var(--surface)' : 'transparent',
                  color: on ? 'var(--ink)' : 'var(--muted)',
                  fontWeight: on ? 500 : 400,
                  borderLeft: on ? '2px solid var(--ink)' : '2px solid transparent',
                  marginLeft: -2,
                }}>{t}</div>
              ))}
            </div>
            {/* Markdown body */}
            <div style={{ padding: '28px 36px', fontSize: 14, lineHeight: 1.65, color: 'var(--ink-2)', overflow: 'hidden' }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 8, fontFamily: 'var(--font-mono)' }}># S21-DA-04</div>
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>Когортный анализ для Sales&nbsp;Funnel</h1>
              <p style={{ marginTop: 14 }}>В этом проекте ты разберёшься, как сегментировать пользователей по моменту входа в продукт и оценивать их удержание во времени. Ты получишь готовую методику, которой пользуются продакты и аналитики в реальных продуктах.</p>
              <h2 style={{ marginTop: 28, fontSize: 18, fontWeight: 600 }}>Учебная цель и ЗУНы</h2>
              <ul style={{ paddingLeft: 20, margin: '8px 0' }}>
                <li>Знать определение когорты и retention-таблицы</li>
                <li>Уметь строить когорты по событиям и временным окнам</li>
                <li>Уметь интерпретировать падения retention и формулировать гипотезы</li>
              </ul>
              <h2 style={{ marginTop: 24, fontSize: 18, fontWeight: 600 }}>Формула retention</h2>
              <div style={{
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)', padding: '14px 18px', textAlign: 'center',
                fontFamily: '"Times New Roman", serif', fontSize: 17, fontStyle: 'italic',
              }}>
                R<sub>n</sub> = | U<sub>0</sub> ∩ U<sub>n</sub> | / | U<sub>0</sub> | × 100 %
              </div>
              <p style={{ marginTop: 14 }}>где U<sub>0</sub> — пользователи когорты в неделю регистрации, U<sub>n</sub> — те же пользователи, активные в неделю <code style={{ background: 'var(--surface-muted)', padding: '1px 5px', borderRadius: 4, fontSize: 12.5, fontFamily: 'var(--font-mono)' }}>n</code>.</p>
              <h2 style={{ marginTop: 24, fontSize: 18, fontWeight: 600 }}>Пример SQL-запроса</h2>
              <pre style={{
                background: 'var(--ink)', color: '#dde2eb', padding: 16, borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.6, overflow: 'auto', margin: '8px 0 0',
              }}>
{`SELECT
  date_trunc('week', signup_at)  AS cohort,
  date_trunc('week', event_at)   AS event_week,
  count(DISTINCT user_id)        AS users
FROM events
GROUP BY 1, 2
ORDER BY 1, 2;`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ─── Metrics tab variant
const Metrics = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="gen"/>
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <span style={{ fontSize: 13, fontWeight: 500 }}>S21-DA-04 · Метрики качества</span>
      <span className="badge success"><Icon.Check s={11}/>36 из 39</span>
      <div style={{ flex: 1 }}/>
      <button className="btn btn-secondary btn-sm">Заполнить из непройденных</button>
      <button className="btn btn-primary btn-sm">Перегенерировать</button>
    </div>
    <div className="scroll-y" style={{ flex: 1, overflowY: 'auto', padding: '24px 28px 60px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
          <span className="chip on">Все<span className="count">39</span></span>
          <span className="chip">Пройдены<span className="count">36</span></span>
          <span className="chip">Не пройдены<span className="count">3</span></span>
          <span className="chip">Предупреждения<span className="count">5</span></span>
          <div style={{ flex: 1 }}/>
          <select className="select" style={{ width: 200 }}>
            <option>Группировка: по разделам</option>
          </select>
        </div>

        {[
          {
            sec: 'Структура', items: [
              { id: 'S-01', t: 'Заголовок и метаданные присутствуют', s: 'ok', c: 'Заголовок, проект, направление, тип — все на месте.' },
              { id: 'S-02', t: 'Содержание автогенерируется по h2', s: 'ok' },
              { id: 'S-03', t: 'Раздел «Цель» соответствует ЗУНам', s: 'ok' },
              { id: 'S-04', t: 'Раздел «Критерии» — таблица с весами', s: 'warn', c: 'Веса критериев не суммируются ровно в 100 %.' },
            ]
          },
          {
            sec: 'Требования', items: [
              { id: 'R-12', t: 'Каждая задача имеет вход / выход', s: 'ok' },
              { id: 'R-18', t: 'Шаги задачи нумерованы и атомарны', s: 'fail', c: 'В задаче 3 шаги 4 и 5 объединены — нужно разделить.' },
              { id: 'R-22', t: 'Указаны все обязательные инструменты', s: 'ok' },
            ]
          },
          {
            sec: 'Сторителлинг и тон', items: [
              { id: 'T-04', t: 'Единый сторителлинг через все задачи', s: 'ok' },
              { id: 'T-06', t: 'Обращение «ты» — последовательное', s: 'fail', c: 'В разделе «Бонус» — переход на «вы».' },
              { id: 'T-08', t: 'Нет англицизмов без объяснения', s: 'warn', c: '«Funnel», «retention» — стоит дать пояснение в скобках.' },
            ]
          },
        ].map((g) => (
          <div key={g.sec} className="card" style={{ marginBottom: 14, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <h4 style={{ margin: 0, fontSize: 13.5, fontWeight: 600 }}>{g.sec}</h4>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{g.items.length} критериев</span>
            </div>
            {g.items.map((it, i, arr) => {
              const ico = it.s === 'ok' ? <span style={{ color: 'var(--success)' }}><Icon.Check s={14}/></span>
                : it.s === 'warn' ? <span style={{ color: 'var(--warn)' }}><Icon.Warn s={14}/></span>
                : <span style={{ color: 'var(--danger)' }}><Icon.X s={14}/></span>;
              return (
                <div key={it.id} style={{ display: 'grid', gridTemplateColumns: '24px 80px 1fr auto', gap: 14, padding: '12px 18px', borderBottom: i < arr.length-1 ? '1px solid var(--border)' : 'none', alignItems: 'flex-start' }}>
                  <div style={{ paddingTop: 1 }}>{ico}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)', paddingTop: 2 }}>{it.id}</div>
                  <div>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>{it.t}</div>
                    {it.c && <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 3, lineHeight: 1.5 }}>{it.c}</div>}
                  </div>
                  <span className={`badge ${it.s === 'ok' ? 'success' : it.s === 'warn' ? 'warn' : 'danger'}`}>
                    {it.s === 'ok' ? 'Пройден' : it.s === 'warn' ? 'Предупр.' : 'Не пройден'}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  </div>
);

Object.assign(window, { Progress, Results, Metrics });

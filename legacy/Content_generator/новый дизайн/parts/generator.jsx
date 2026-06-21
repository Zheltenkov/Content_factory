/* global React, Icon, Header */
// Generator screen — left form, right empty state / results

const SectionHead = ({ num, title, hint }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
    <div className="sec-num">{num}</div>
    <div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{title}</div>
      {hint && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>{hint}</div>}
    </div>
  </div>
);

const Generator = () => (
  <div className="app" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Header active="gen" />
    {/* Sub-bar */}
    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <a className="text-link" style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <Icon.ArrLeft s={12}/> Главное меню
      </a>
      <span style={{ color: 'var(--border-strong)' }}>/</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>Генерация README</span>
      <span className="badge" style={{ background: 'var(--surface-muted)', borderColor: 'transparent' }}>Черновик · S21-DA-04</span>
      <div style={{ flex: 1 }}/>
      <span style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon.Check2 s={12}/> Автосохранено · 12 сек назад
      </span>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '560px 1fr', flex: 1, minHeight: 0 }}>
      {/* LEFT — form */}
      <div className="scroll-y" style={{ overflowY: 'auto', borderRight: '1px solid var(--border)', background: 'var(--surface)' }}>
        <div style={{ padding: '24px 28px 120px' }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em' }}>Входные параметры</h2>
          <p style={{ margin: '0 0 24px', fontSize: 13.5, color: 'var(--muted)' }}>Заполните поля или загрузите CSV с паспортом учебной программы.</p>

          {/* A. Учебный план */}
          <SectionHead num="01" title="Учебный план" hint="CSV с паспортом программы" />
          <div className="upload uploaded" style={{ padding: 16, alignItems: 'flex-start', flexDirection: 'row', textAlign: 'left', gap: 12 }}>
            <div className="ic"><Icon.Doc s={18}/></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>data-analytics-2025-passport.csv</span>
                <button className="btn-ghost btn-sm" style={{ background: 'transparent', border: 0, padding: 0, color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>удалить</button>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>184 КБ · 6 направлений · 84 проекта</div>
            </div>
          </div>

          {/* B. Methodology */}
          <div style={{ marginTop: 18, padding: 14, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface-2)', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div className="toggle on" style={{ marginTop: 2 }}/>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500 }}>Методологический режим</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>Останавливать генерацию на контрольных точках для подтверждения методологом</div>
            </div>
          </div>

          {/* C. Direction + tematic block */}
          <div style={{ marginTop: 28 }}>
            <SectionHead num="02" title="Контекст программы" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="field">
                <label className="lbl">Направление <span className="req">*</span></label>
                <select className="select" defaultValue="da">
                  <option value="da">Бизнес-аналитика</option>
                </select>
              </div>
              <div className="field">
                <label className="lbl">Тематический блок <span className="req">*</span></label>
                <select className="select"><option>Аналитические продукты</option></select>
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Проект из УП <span className="req">*</span></label>
                <select className="select"><option>S21-DA-04 · Когортный анализ для Sales Funnel</option></select>
                <div className="help">Подтянутся ЗУНы, образовательные результаты и инструменты по проекту</div>
              </div>
            </div>
          </div>

          {/* E. Параметры проекта */}
          <div style={{ marginTop: 28 }}>
            <SectionHead num="03" title="Параметры проекта" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="field">
                <label className="lbl">Язык <span className="req">*</span></label>
                <select className="select" defaultValue="ru">
                  <option value="ru">RU · Русский</option>
                  <option value="en">EN · Английский</option>
                  <option value="kg">KG · Киргизский</option>
                  <option value="uz">UZ · Узбекский</option>
                </select>
              </div>
              <div className="field">
                <label className="lbl">Тип проекта <span className="req">*</span></label>
                <div style={{ display: 'flex', gap: 0, padding: 3, background: 'var(--surface-muted)', borderRadius: 'var(--radius-sm)' }}>
                  <button style={{ flex: 1, padding: '7px 10px', fontSize: 13, fontWeight: 500, background: 'var(--surface)', border: 0, borderRadius: 6, boxShadow: 'var(--shadow-1)' }}>Индивидуальный</button>
                  <button style={{ flex: 1, padding: '7px 10px', fontSize: 13, fontWeight: 500, background: 'transparent', border: 0, color: 'var(--muted)' }}>Групповой</button>
                </div>
              </div>
              <div className="field">
                <label className="lbl">Уровень аудитории</label>
                <select className="select"><option>Beginner+ (после первого блока)</option></select>
              </div>
              <div className="field">
                <label className="lbl">Кол-во задач</label>
                <input className="input" defaultValue="5" />
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Название проекта <span className="req">*</span></label>
                <input className="input" defaultValue="Когортный анализ для Sales Funnel" />
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Обязательные инструменты</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '6px 8px', minHeight: 38, border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                  {['Python 3.11', 'pandas', 'numpy', 'matplotlib', 'Jupyter', 'PostgreSQL'].map((t) => (
                    <span key={t} className="chip" style={{ padding: '3px 8px', fontSize: 12 }}>{t}<Icon.X s={10}/></span>
                  ))}
                  <span style={{ fontSize: 12, color: 'var(--muted-2)', alignSelf: 'center', padding: '0 4px' }}>+ добавить</span>
                </div>
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Сторителлинг <span className="opt">не обязательно</span></label>
                <textarea className="textarea" placeholder="Краткая история-обёртка для проекта" defaultValue="Команда продукта Sales Funnel внутри финтех-сервиса заметила падение конверсии на 4-м шаге. Студент должен помочь продактам разобраться, какие сегменты пользователей теряются, и предложить гипотезы по их удержанию."/>
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Краткое описание проекта <span className="req">*</span></label>
                <textarea className="textarea error" defaultValue="Построить когортный анализ"/>
                <div className="err"><Icon.Warn s={12}/> Описание слишком короткое. Минимум 80 символов — нужно для качественной генерации теории.</div>
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="lbl">Образовательные результаты <span className="opt">подтянуты из УП — можно править</span></label>
                <textarea className="textarea" rows="3" defaultValue={"Уметь формировать когорты по событиям и временным окнам\nУметь визуализировать удержание и retention-таблицы\nЗнать ограничения когортного анализа и типичные ошибки"}/>
              </div>
            </div>
          </div>

          {/* F. Repo settings — accordion */}
          <div style={{ marginTop: 24, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
            <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <Icon.Settings s={15}/>
              <div style={{ flex: 1, fontSize: 13.5, fontWeight: 500 }}>Настройки репозитория</div>
              <span className="badge" style={{ fontSize: 10 }}>опционально</span>
              <Icon.Chevron dir="up"/>
            </div>
            <div style={{ padding: '0 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="field">
                <label className="lbl">Базовый URL</label>
                <input className="input" defaultValue="https://github.com/school21-curriculum/da-cohort"/>
              </div>
              <div className="field">
                <label className="lbl">Шаблон пути</label>
                <input className="input" defaultValue="ex{num:02d}/" style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5 }}/>
                <div className="help">Используйте <code style={{ background: 'var(--surface-muted)', padding: '1px 5px', borderRadius: 4, fontSize: 11.5 }}>{`{num:02d}`}</code> для номера задачи</div>
              </div>
            </div>
          </div>

          {/* G. Bonus */}
          <div style={{ marginTop: 14, padding: 16, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
            <label className="check on">
              <span className="box"/>
              <span className="text">Генерировать бонусное задание<small>Доп. задача повышенной сложности после основной практики</small></span>
            </label>
            <textarea className="textarea" style={{ marginTop: 10 }} placeholder="Дополнение к бонусному заданию (опционально)" defaultValue="Сделать дашборд в Metabase с фильтрами по сегментам и каналам привлечения."/>
          </div>
        </div>

        {/* Sticky footer */}
        <div style={{
          position: 'sticky', bottom: 0, background: 'var(--surface)',
          borderTop: '1px solid var(--border)', padding: '14px 28px',
          display: 'flex', gap: 8, alignItems: 'center',
          boxShadow: '0 -8px 16px -8px rgba(15,20,25,0.05)',
        }}>
          <button className="btn btn-ghost btn-sm">Очистить форму</button>
          <div style={{ flex: 1 }}/>
          <button className="btn btn-secondary">Сохранить шаблон</button>
          <button className="btn btn-primary btn-lg" style={{ paddingLeft: 18, paddingRight: 18 }}>
            <Icon.Sparkle s={16}/> Сгенерировать
          </button>
        </div>
      </div>

      {/* RIGHT — empty state */}
      <div className="pattern-grid" style={{ overflowY: 'auto', position: 'relative' }}>
        <div style={{ padding: 56, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ maxWidth: 480, textAlign: 'center' }}>
            <div style={{ width: 80, height: 80, borderRadius: 20, margin: '0 auto 22px', background: 'var(--surface)', border: '1px solid var(--border)', display: 'grid', placeItems: 'center', boxShadow: 'var(--shadow-2)', position: 'relative' }}>
              <Icon.Sparkle s={32}/>
              <div style={{ position: 'absolute', top: -6, right: -6, width: 22, height: 22, borderRadius: 7, background: 'var(--ink)' }}/>
              <div style={{ position: 'absolute', bottom: -6, left: -6, width: 14, height: 14, borderRadius: 4, background: 'var(--ink)', opacity: .3 }}/>
            </div>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, letterSpacing: '-0.02em' }}>Результаты появятся здесь</h3>
            <p style={{ margin: '8px 0 24px', color: 'var(--muted)', fontSize: 14, lineHeight: 1.55 }}>
              Заполните входные параметры слева и запустите генерацию. Полный пайплайн занимает 8–15 минут.
            </p>
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '4px', textAlign: 'left' }}>
              {[
                { t: 'README.md', s: 'теория, практика, критерии оценки' },
                { t: 'План практики', s: 'задачи, формулы, чек-листы, сложность' },
                { t: 'Метрики качества', s: '39 критериев, антиплагиат, читаемость' },
                { t: 'Архив для скачивания', s: 'результаты в .zip с отчётами' },
              ].map((x, i, arr) => (
                <div key={i} style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: i < arr.length-1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--surface-muted)', display: 'grid', placeItems: 'center' }}>
                    <Icon.Check s={14}/>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{x.t}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>{x.s}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, { Generator });

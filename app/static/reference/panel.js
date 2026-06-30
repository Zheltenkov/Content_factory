const state = {
  competencies: [],
  groups: [],
  profiles: [],
  skills: [],
  reviews: [],
  candidateCompetencies: [],
  candidateOptions: [],
  artifactTemplates: [],
  archive: { groups: [], skills: [], indicators: [], counts: { groups: 0, skills: 0, indicators: 0 } },
  intakeJobs: [],
  currentIntakeJob: null,
  current: null,
  currentProfile: null,
  selectedSkill: null,
  mode: initialModeFromLocation(),
};

const el = {
  searchInput: document.getElementById("searchInput"),
  searchButton: document.getElementById("searchButton"),
  reviewStatusFilter: document.getElementById("reviewStatusFilter"),
  reviewSeverityFilter: document.getElementById("reviewSeverityFilter"),
  reviewEntityFilter: document.getElementById("reviewEntityFilter"),
  reviewReasonFilter: document.getElementById("reviewReasonFilter"),
  includeServiceProfiles: document.getElementById("includeServiceProfiles"),
  summaryCards: document.getElementById("summaryCards"),
  competencyList: document.getElementById("competencyList"),
  groupList: document.getElementById("groupList"),
  profileList: document.getElementById("profileList"),
  skillList: document.getElementById("skillList"),
  reviewList: document.getElementById("reviewList"),
  candidateList: document.getElementById("candidateList"),
  templateList: document.getElementById("templateList"),
  archiveList: document.getElementById("archiveList"),
  form: document.getElementById("competencyForm"),
  title: document.getElementById("competencyTitle"),
  status: document.getElementById("competencyStatus"),
  description: document.getElementById("competencyDescription"),
  detailMeta: document.getElementById("detailMeta"),
  skillTree: document.getElementById("skillTree"),
  competencySection: document.getElementById("competencyDetailSection"),
  skillSection: document.getElementById("skillDetailSection"),
  groupSection: document.getElementById("groupDetailSection"),
  candidateSection: document.getElementById("candidateCompetencySection"),
  candidateCards: document.getElementById("candidateCompetencyCards"),
  candidateOpenCount: document.getElementById("candidateOpenCount"),
  artifactTemplateSection: document.getElementById("artifactTemplateSection"),
  archiveSection: document.getElementById("archiveSection"),
  archiveForm: document.getElementById("archiveForm"),
  archiveSearch: document.getElementById("archiveSearch"),
  archiveScope: document.getElementById("archiveScope"),
  archiveQueryLabel: document.getElementById("archiveQueryLabel"),
  archivedGroupCount: document.getElementById("archivedGroupCount"),
  archivedSkillCount: document.getElementById("archivedSkillCount"),
  archivedIndicatorCount: document.getElementById("archivedIndicatorCount"),
  archiveGroupsBlock: document.getElementById("archiveGroupsBlock"),
  archiveSkillsBlock: document.getElementById("archiveSkillsBlock"),
  archiveIndicatorsBlock: document.getElementById("archiveIndicatorsBlock"),
  archivedGroups: document.getElementById("archivedGroups"),
  archivedSkills: document.getElementById("archivedSkills"),
  archivedIndicators: document.getElementById("archivedIndicators"),
  artifactTemplateForm: document.getElementById("artifactTemplateForm"),
  artifactTemplateId: document.getElementById("artifactTemplateId"),
  artifactTemplateFormTitle: document.getElementById("artifactTemplateFormTitle"),
  artifactTemplateNewButton: document.getElementById("artifactTemplateNewButton"),
  artifactTemplateCode: document.getElementById("artifactTemplateCode"),
  artifactTemplateTitle: document.getElementById("artifactTemplateTitle"),
  artifactTemplateFamily: document.getElementById("artifactTemplateFamily"),
  artifactTemplateStatus: document.getElementById("artifactTemplateStatus"),
  artifactTemplatePriority: document.getElementById("artifactTemplatePriority"),
  artifactTemplateScopeWeight: document.getElementById("artifactTemplateScopeWeight"),
  artifactTemplateDescription: document.getElementById("artifactTemplateDescription"),
  artifactTemplateProjectPattern: document.getElementById("artifactTemplateProjectPattern"),
  artifactTemplateMaterials: document.getElementById("artifactTemplateMaterials"),
  artifactTemplateStorytelling: document.getElementById("artifactTemplateStorytelling"),
  artifactTemplateCriteria: document.getElementById("artifactTemplateCriteria"),
  artifactTemplateScopeType: document.getElementById("artifactTemplateScopeType"),
  artifactTemplateScopeNames: document.getElementById("artifactTemplateScopeNames"),
  artifactTemplateCount: document.getElementById("artifactTemplateCount"),
  artifactTemplateTable: document.getElementById("artifactTemplateTable"),
  profileSection: document.getElementById("profileDetailSection"),
  placeholderSection: document.getElementById("referencePlaceholderSection"),
  placeholderTitle: document.getElementById("referencePlaceholderTitle"),
  placeholderText: document.getElementById("referencePlaceholderText"),
  profileDetail: document.getElementById("profileDetail"),
  skillForm: document.getElementById("skillForm"),
  skillName: document.getElementById("skillCanonicalName"),
  skillStatus: document.getElementById("skillStatus"),
  skillType: document.getElementById("skillType"),
  skillAliases: document.getElementById("skillAliases"),
  skillLinks: document.getElementById("skillLinks"),
  skillIndicators: document.getElementById("skillIndicators"),
  indicatorCreateForm: document.getElementById("indicatorCreateForm"),
  indicatorDimension: document.getElementById("indicatorDimension"),
  indicatorNotes: document.getElementById("indicatorNotes"),
  indicatorText: document.getElementById("indicatorText"),
  groupForm: document.getElementById("groupForm"),
  groupTitle: document.getElementById("groupTitle"),
  groupStatus: document.getElementById("groupStatus"),
  groupDescription: document.getElementById("groupDescription"),
  groupSkillCreateForm: document.getElementById("groupSkillCreateForm"),
  groupCreateForm: document.getElementById("groupCreateForm"),
  groupCreateTitle: document.getElementById("groupCreateTitle"),
  groupCreateDescription: document.getElementById("groupCreateDescription"),
  groupSkillName: document.getElementById("groupSkillName"),
  groupSkillType: document.getElementById("groupSkillType"),
  groupSkillAliases: document.getElementById("groupSkillAliases"),
  groupSkillCount: document.getElementById("groupSkillCount"),
  groupSkillList: document.getElementById("groupSkillList"),
  newSkillButton: document.getElementById("newSkillButton"),
  statusLine: document.getElementById("referenceStatus"),
  pageTitle: document.getElementById("referencePageTitle"),
  pageSubtitle: document.getElementById("referencePageSubtitle"),
  summaryProfiles: document.getElementById("summaryProfiles"),
  summaryCompetencies: document.getElementById("summaryCompetencies"),
  summarySkills: document.getElementById("summarySkills"),
  summaryIndicators: document.getElementById("summaryIndicators"),
  summaryOpenReviews: document.getElementById("summaryOpenReviews"),
  secondaryNav: document.querySelector(".secondary-nav"),
  toolbar: document.getElementById("referenceToolbar"),
  referenceGrid: document.getElementById("referenceGrid"),
  intakeWorkspace: document.getElementById("intakeWorkspace"),
  intakeComposePanel: document.getElementById("intakeComposePanel"),
  intakeForm: document.getElementById("intakeForm"),
  briefText: document.getElementById("briefText"),
  briefFileInput: document.getElementById("briefFileInput"),
  pickerStatus: document.getElementById("pickerStatus"),
  briefSubmitWrap: document.getElementById("briefSubmitWrap"),
  nextIntakeStep: document.getElementById("nextIntakeStep"),
  recentIntakeJobs: document.getElementById("recentIntakeJobs"),
  jobStatusBadge: document.getElementById("jobStatusBadge"),
  jobSummaryText: document.getElementById("jobSummaryText"),
  jobBlockerCount: document.getElementById("jobBlockerCount"),
  jobProgressPercent: document.getElementById("jobProgressPercent"),
  jobStage: document.getElementById("jobStage"),
  jobCreatedAt: document.getElementById("jobCreatedAt"),
  jobSource: document.getElementById("jobSource"),
  jobProgress: document.getElementById("jobProgress"),
  jobProgressFill: document.getElementById("jobProgressFill"),
  jobProgressSteps: document.getElementById("jobProgressSteps"),
  jobNextStepTitle: document.getElementById("jobNextStepTitle"),
  jobNextStepDescription: document.getElementById("jobNextStepDescription"),
  jobNextStepActions: document.getElementById("jobNextStepActions"),
  jobBlockersCard: document.getElementById("jobBlockersCard"),
  jobBlockersPill: document.getElementById("jobBlockersPill"),
  jobBlockers: document.getElementById("jobBlockers"),
  jobCatalogStateCard: document.getElementById("jobCatalogStateCard"),
  jobCatalogState: document.getElementById("jobCatalogState"),
  jobCreatedItemsCard: document.getElementById("jobCreatedItemsCard"),
  jobCreatedItemsPill: document.getElementById("jobCreatedItemsPill"),
  jobCreatedItems: document.getElementById("jobCreatedItems"),
  jobSkillCardsCard: document.getElementById("jobSkillCardsCard"),
  jobSkillCardsPill: document.getElementById("jobSkillCardsPill"),
  jobSkillCards: document.getElementById("jobSkillCards"),
  jobPipelineResultCard: document.getElementById("jobPipelineResultCard"),
  jobPipelineResult: document.getElementById("jobPipelineResult"),
  jobWorkflowSteps: document.getElementById("jobWorkflowSteps"),
  intakePrimaryAction: document.getElementById("intakePrimaryAction"),
};

const MODE_META = {
  workspace: ["Рабочий стол", "Legacy intake workspace: загрузка брифа, решения кандидатов, DAG и сборка УП через общий каталог."],
  skills: ["Skills и индикаторы", "Каталог групп, skills, aliases и индикаторов поверх общей базы."],
  competencies: ["Компетенции", "Компетентностные профили и связанные skills."],
  profiles: ["Профили", "Профили компетенций, деревья skills и индикаторов."],
  reviews: ["Review queue", "Очередь методологических решений и статусы разметки."],
  candidates: ["Кандидатные компетенции", "Legacy screen для rename, merge, accept/reject и переноса skills. Восстанавливается без второго каталога."],
  templates: ["Шаблоны УП", "Рабочие шаблоны артефактов, scope и patterns для сборки УП."],
  archive: ["Архив", "Восстановление архивированных групп, skills и индикаторов."],
};

function initialModeFromLocation() {
  const path = window.location.pathname;
  if (path.startsWith("/intake")) return "workspace";
  if (path.startsWith("/competencies")) return "competencies";
  if (path.startsWith("/profiles")) return "profiles";
  if (path.startsWith("/reviews")) return "reviews";
  if (path.startsWith("/catalog-admin/candidate-competencies")) return "candidates";
  if (path.startsWith("/catalog-admin/artifact-templates")) return "templates";
  if (path.startsWith("/catalog-admin/archive")) return "archive";
  if (path.startsWith("/catalog-admin/skills") || path.startsWith("/catalog-admin/groups")) return "skills";
  return "skills";
}

function intakeJobIdFromLocation() {
  const match = window.location.pathname.match(/^\/intake\/jobs\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function groupIdFromLocation() {
  const match = window.location.pathname.match(/^\/catalog-admin\/groups\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function skillIdFromLocation() {
  const match = window.location.pathname.match(/^\/catalog-admin\/skills\/(\d+)/);
  return match ? Number(match[1]) : null;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function reviewFilterQuery() {
  const params = [
    ["severity", el.reviewSeverityFilter?.value],
    ["entity_type", el.reviewEntityFilter?.value],
    ["reason_code", el.reviewReasonFilter?.value],
  ];
  return params
    .filter(([, value]) => value)
    .map(([key, value]) => `&${key}=${encodeURIComponent(value)}`)
    .join("");
}

async function loadAll() {
  const q = el.searchInput.value.trim();
  const includeService = el.includeServiceProfiles.checked ? "true" : "false";
  const reviewStatus = el.reviewStatusFilter.value;
  const reviewQuery = reviewFilterQuery();
  let summary;
  let competencies;
  let groups;
  let profiles;
  let skills;
  let reviews;
  let candidateWorkspace;
  let artifactTemplates;
  let archive;
  let intakeJobs;
  let currentIntakeJob = null;
  const currentJobId = intakeJobIdFromLocation();
  const archiveScope = el.archiveScope?.value || "all";
  try {
    const payloads = await Promise.all([
      request("/reference/summary"),
      request(`/reference/competencies?limit=80&q=${encodeURIComponent(q)}`),
      request(`/reference/groups?limit=80&q=${encodeURIComponent(q)}`),
      request(`/reference/profiles?limit=80&include_service=${includeService}`),
      request(`/reference/skills?limit=80&include_deprecated=true&q=${encodeURIComponent(q)}`),
      request(`/reference/reviews?status_filter=${encodeURIComponent(reviewStatus)}${reviewQuery}&limit=20`),
      request("/reference/candidate-competencies?limit=80"),
      request("/reference/artifact-templates"),
      request(`/reference/archive?limit=80&q=${encodeURIComponent(q)}&scope=${encodeURIComponent(archiveScope)}`),
      request("/intake/jobs?limit=8"),
      currentJobId ? request(`/intake/jobs/${currentJobId}/status`) : Promise.resolve(null),
    ]);
    [summary, competencies, groups, profiles, skills, reviews, candidateWorkspace, artifactTemplates, archive, intakeJobs, currentIntakeJob] = payloads;
  } catch (error) {
    renderDisconnected(error);
    setListMode(state.mode);
    return;
  }
  state.competencies = competencies;
  state.groups = groups;
  state.profiles = profiles;
  state.skills = skills;
  state.reviews = reviews;
  state.candidateCompetencies = candidateWorkspace?.candidates || [];
  state.candidateOptions = candidateWorkspace?.competency_options || [];
  state.artifactTemplates = artifactTemplates || [];
  state.archive = archive || { groups: [], skills: [], indicators: [], counts: { groups: 0, skills: 0, indicators: 0 } };
  state.intakeJobs = intakeJobs;
  state.currentIntakeJob = currentIntakeJob;
  renderSummary(summary);
  renderCompetencies();
  renderGroups();
  renderProfiles();
  renderSkills();
  renderReviews();
  renderCandidateCompetencies(candidateWorkspace || {});
  renderArtifactTemplates();
  renderArchive();
  renderIntakeJobs();
  renderDeferredLegacyLists();
  setListMode(state.mode);
  if (state.mode === "workspace") {
    renderCurrentIntakeJob();
  } else if (state.mode === "skills") {
    await routeCatalogAdmin();
  } else if (state.mode === "competencies" && !state.current && competencies.length) {
    await selectCompetency(competencies[0].id);
  } else if (state.mode === "profiles" && !state.currentProfile && profiles.length) {
    await selectProfile(profiles[0].id);
  } else if (state.mode === "reviews") {
    showReviewQueueDetail();
  } else if (state.mode === "candidates") {
    showCandidateCompetenciesDetail();
  } else if (state.mode === "templates") {
    showArtifactTemplateDetail();
  } else if (state.mode === "archive") {
    showArchiveDetail();
  } else if (isDeferredMode(state.mode)) {
    showDeferredDetail(state.mode);
  } else if (!competencies.length) {
    renderEmptyDetail("Компетенции не найдены");
  }
}

function renderSummary(summary) {
  el.summaryProfiles.textContent = summary.profiles || state.profiles.length || 0;
  el.summaryCompetencies.textContent = summary.competencies || 0;
  el.summarySkills.textContent = summary.skills || 0;
  el.summaryIndicators.textContent = summary.indicators || 0;
  el.summaryOpenReviews.textContent = summary.open_reviews || 0;
  const labels = [
    ["competencies", "компетенции"],
    ["skills", "skills"],
    ["indicators", "индикаторы"],
    ["open_reviews", "review"],
  ];
  el.summaryCards.innerHTML = labels
    .map(([key, label]) => `<div class="summary-card"><strong>${summary[key] || 0}</strong><span>${label}</span></div>`)
    .join("");
}

function renderDisconnected(error) {
  state.competencies = [];
  state.groups = [];
  state.profiles = [];
  state.skills = [];
  state.reviews = [];
  state.archive = { groups: [], skills: [], indicators: [], counts: { groups: 0, skills: 0, indicators: 0 } };
  state.intakeJobs = [];
  state.currentIntakeJob = null;
  renderSummary({ profiles: 0, competencies: 0, skills: 0, indicators: 0, open_reviews: 0 });
  renderCompetencies();
  renderGroups();
  renderProfiles();
  renderSkills();
  renderReviews();
  renderArchive();
  renderIntakeJobs();
  renderCurrentIntakeJob();
  renderDeferredLegacyLists();
  setStatus(`Backend недоступен: ${error.message}`);
}

function renderCompetencies() {
  el.competencyList.innerHTML = state.competencies
    .map(
      (item) => `
        <button class="list-item" type="button" data-competency-id="${item.id}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${item.profile_count} профилей · ${item.skill_count} skills · ${item.indicator_count} инд.</span>
        </button>`,
    )
    .join("") || '<div class="empty-inline">Компетенции не найдены</div>';
}

function renderGroups() {
  el.groupList.innerHTML = state.groups
    .map(
      (group) => `
        <button class="list-item" type="button" data-group-id="${group.id}">
          <strong>${escapeHtml(group.title)}</strong>
          <span>${group.skill_count} skills · ${group.indicator_count} инд. · ${escapeHtml(group.status)}</span>
        </button>`,
    )
    .join("") || '<div class="empty-inline">Группы не найдены</div>';
}

function renderProfiles() {
  el.profileList.innerHTML = state.profiles
    .map(
      (profile) => `
        <button class="list-item" type="button" data-profile-id="${profile.id}">
          <strong>${escapeHtml(profile.name)}</strong>
          <span>${escapeHtml(profile.source_kind)} · ${profile.competency_count} компетенций · ${profile.skill_count} skills</span>
          ${profile.review_competencies ? `<span class="badge warning">${profile.review_competencies} review</span>` : ""}
        </button>`,
    )
    .join("") || '<div class="empty-inline">Профили не найдены</div>';
}

function renderSkills() {
  el.skillList.innerHTML = state.skills
    .map(
      (skill) => `
        <button class="list-item" type="button" data-skill-id="${skill.skill_id}">
          <strong>${escapeHtml(skill.canonical_name)}</strong>
          <span>${escapeHtml(skill.skill_type)} · ${escapeHtml(skill.status)} · ${skill.aliases.length} aliases</span>
        </button>`,
    )
    .join("") || '<div class="empty-inline">Skills не найдены</div>';
}

function renderReviews() {
  el.reviewList.innerHTML =
    state.reviews
      .map(
        (item) => `
          <article class="review-item" data-review-card="${item.id}">
            <strong>${escapeHtml(item.entity_type)} #${item.entity_id || "-"}</strong>
            <span>${escapeHtml(item.reason_code)} · ${escapeHtml(item.severity)} · ${escapeHtml(item.status)}</span>
            <p class="small">${escapeHtml(item.details || "")}</p>
            <textarea data-review-note rows="2" placeholder="Комментарий решения"></textarea>
            <div class="inline-actions">
              <button type="button" data-review-id="${item.id}" data-review-status="resolved">Resolved</button>
              <button class="btn-ghost" type="button" data-review-id="${item.id}" data-review-status="ignored">Ignored</button>
              <button class="btn-ghost" type="button" data-review-id="${item.id}" data-review-status="open">В очередь</button>
            </div>
          </article>`,
      )
      .join("") || '<div class="empty-inline">Записей нет</div>';
}

function renderIntakeJobs() {
  if (!state.intakeJobs.length) {
    el.recentIntakeJobs.innerHTML = '<div class="empty-inline">Intake-задач пока нет</div>';
    return;
  }
  el.recentIntakeJobs.innerHTML = `
    <table class="data-table intake-history-table">
      <thead>
        <tr>
          <th>Задача</th>
          <th>Источник</th>
          <th>Статус</th>
          <th>Этап</th>
          <th>Жюри</th>
          <th>Открыть</th>
        </tr>
      </thead>
      <tbody>
        ${state.intakeJobs.map((job) => `
          <tr>
            <td>#${job.id}<div class="small muted">${escapeHtml(formatDate(job.created_at))}</div></td>
            <td>${escapeHtml(job.source_name || sourceLabel(job.source_kind))}</td>
            <td><span class="status-badge ${job.status === "failed" ? "warning" : ""}">${escapeHtml(statusLabel(job.status))}</span></td>
            <td>${escapeHtml(stageLabel(job.current_stage))}</td>
            <td>${job.use_council ? "вкл" : "выкл"}</td>
            <td><a href="/intake/jobs/${job.id}">Открыть</a></td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderCurrentIntakeJob() {
  const job = state.currentIntakeJob;
  const stateView = buildIntakeWorkspaceState(job);
  el.pageTitle.textContent = job ? `Рабочий стол брифа #${job.id}` : "Рабочий стол брифа";
  el.pageSubtitle.textContent = job
    ? "Единый маршрут: проверить навыки, применить решения в справочник, подтвердить шаблоны, построить DAG и УП."
    : "Загрузите бриф. Система декомпозирует его в навыки, сопоставит с каталогом и подготовит очередь решений.";
  el.intakePrimaryAction.textContent = job ? "Новый бриф" : "Рабочий стол";
  el.intakeComposePanel.hidden = Boolean(job);
  el.jobStatusBadge.textContent = job ? statusLabel(job.status) : "draft";
  el.jobStatusBadge.classList.toggle("warning", job?.status === "failed");
  el.jobSummaryText.textContent = stateView.nextStep ? `Следующий шаг: ${stateView.nextStep.label}` : "Следующий шаг: загрузить документ или вставить текст";
  el.jobBlockerCount.hidden = !stateView.blockers.length;
  el.jobBlockerCount.textContent = `${stateView.blockers.length} блокеров`;
  el.jobProgressPercent.textContent = `${stateView.progress}%`;
  el.jobStage.textContent = stateView.stage;
  el.jobCreatedAt.textContent = job ? formatDate(job.created_at) : "локальный workspace";
  el.jobSource.textContent = job ? `Источник: ${sourceLabel(job.source_kind)}${job.source_name ? ` · ${job.source_name}` : ""}` : "Источник: текстовый бриф";
  el.jobProgress.textContent = stateView.progressNote;
  el.jobProgressFill.style.width = `${stateView.progress}%`;
  renderProgressSteps(stateView.activeStage);
  renderNextStep(stateView.nextStep);
  renderBlockers(stateView.blockers);
  renderCatalogState(stateView.catalogState);
  renderCreatedItems(stateView.createdItems);
  renderSkillCards(stateView.createdItems);
  renderPipelineResult(stateView.pipelineResult);
  renderWorkflowSteps(stateView.workflowSteps);
  if (job) {
    setStatus(`Intake #${job.id}: ${statusLabel(job.status)}`);
  }
}

function buildIntakeWorkspaceState(job) {
  if (!job) {
    return {
      progress: 0,
      activeStage: "brief",
      stage: "Постановка в очередь",
      progressNote: "Задача появится после запуска обработки брифа.",
      nextStep: {
        label: "Обработать бриф",
        description: "Загрузите документ или вставьте текст, затем запустите intake pipeline.",
        href: null,
        primaryText: "Выполнить следующий шаг",
      },
      blockers: [],
      catalogState: [],
      createdItems: [],
      pipelineResult: [],
      workflowSteps: buildWorkflowSteps(null),
    };
  }
  const result = job.result_payload || {};
  const plan = result.curriculum_plan || {};
  const savedItems = normalizeSavedItems(result);
  const reviewCount = Number(result.review_count || 0);
  const planId = plan.plan_id;
  const failed = job.status === "failed";
  const blockers = buildBlockers(job, result, savedItems);
  return {
    progress: progressForJob(job),
    activeStage: activeProgressStage(job, result),
    stage: stageLabel(job.current_stage),
    progressNote: job.progress_note || "Задача поставлена в очередь.",
    nextStep: buildNextStep(job, reviewCount, planId),
    blockers,
    catalogState: [
      ["Применено в справочник", savedItems.length, "created skills / competencies"],
      ["Открытые решения", reviewCount, "review queue"],
      ["Черновик УП", planId ? `#${planId}` : "—", plan.project_count ? `${plan.project_count} проектов` : "не создан"],
    ],
    createdItems: savedItems,
    pipelineResult: buildPipelineResult(job, result, failed),
    workflowSteps: buildWorkflowSteps(job),
  };
}

function buildBlockers(job, result, savedItems) {
  const plan = result.curriculum_plan || {};
  const blockers = [];
  if (job.status === "failed") {
    blockers.push({
      label: "Ошибка pipeline",
      count: 1,
      severity: "warn",
      description: job.error_text || "Pipeline завершился ошибкой.",
      href: `/intake/jobs/${job.id}/status`,
    });
  }
  if (Number(result.review_count || 0) > 0) {
    blockers.push({
      label: "Открытые решения",
      count: Number(result.review_count || 0),
      severity: "warn",
      description: "Нужно закрыть review queue по новым competency-кандидатам.",
      href: "/reviews?status=open",
    });
  }
  if (job.status === "succeeded" && !savedItems.length) {
    blockers.push({
      label: "Навыки не созданы",
      count: 1,
      severity: "warn",
      description: "Pipeline завершился без созданных skills.",
      href: `/intake/jobs/${job.id}`,
    });
  }
  if (job.status === "succeeded" && !plan.plan_id) {
    blockers.push({
      label: "УП не создан",
      count: 1,
      severity: "info",
      description: "Нет связанного черновика учебного плана.",
      href: "/up",
    });
  }
  return blockers;
}

function buildNextStep(job, reviewCount, planId) {
  if (job.status === "pending" || job.status === "running") {
    return {
      label: "Дождаться обработки",
      description: "Intake-задача ещё выполняется.",
      href: `/intake/jobs/${job.id}`,
      primaryText: "Обновить",
    };
  }
  if (job.status === "failed") {
    return {
      label: "Посмотреть ошибку",
      description: "Pipeline завершился ошибкой. JSON-статус содержит техническую причину.",
      href: `/intake/jobs/${job.id}/status`,
      primaryText: "Открыть status JSON",
    };
  }
  if (reviewCount > 0) {
    return {
      label: "Открыть проверку навыков",
      description: `Осталось спорных решений: ${reviewCount}.`,
      href: "/reviews?status=open",
      primaryText: "Открыть review queue",
    };
  }
  if (planId) {
    return {
      label: "Открыть учебный план",
      description: "Черновик УП готов к проверке.",
      href: "/up",
      primaryText: "Открыть УП",
    };
  }
  return {
    label: "Открыть справочник",
    description: "Каталог обновлён; проверьте созданные skills и компетенции.",
    href: "/catalog-admin/groups",
    primaryText: "Открыть справочник",
  };
}

function buildWorkflowSteps(job) {
  const id = job?.id;
  const result = job?.result_payload || {};
  const planId = result.curriculum_plan?.plan_id;
  const savedCount = normalizeSavedItems(result).length;
  const reviewCount = Number(result.review_count || 0);
  const failed = job?.status === "failed";
  const running = job?.status === "pending" || job?.status === "running";
  return [
    ["Бриф", "Текст или документ принят в обработку.", id ? `/intake/jobs/${id}` : "/intake", id ? "done" : "active"],
    ["Проверка навыков", reviewCount ? `Открыто вопросов: ${reviewCount}.` : "Кандидаты проверены.", reviewCount ? "/reviews?status=open" : (id ? `/intake/jobs/${id}` : "/reviews"), failed ? "warn" : (running ? "active" : "done")],
    ["Справочник и набор навыков", `Применено: ${savedCount}.`, "/catalog-admin/groups", savedCount ? "done" : "pending"],
    ["Шаблоны УП", planId ? "Шаблоны учтены в черновике." : "Появятся после применения навыков.", "/catalog-admin/artifact-templates", planId ? "done" : "pending"],
    ["DAG и УП", planId ? "Черновик доступен." : "Строится после набора навыков.", "/up", planId ? "done" : "pending"],
  ];
}

function renderProgressSteps(activeStage) {
  const order = ["brief", "catalog", "review", "dag", "up"];
  const activeIndex = Math.max(0, order.indexOf(activeStage));
  for (const node of el.jobProgressSteps.querySelectorAll("[data-stage]")) {
    const index = order.indexOf(node.dataset.stage);
    node.classList.toggle("progress-step-done", index >= 0 && index < activeIndex);
    node.classList.toggle("progress-step-active", index === activeIndex);
  }
}

function renderNextStep(nextStep) {
  el.jobNextStepTitle.textContent = nextStep.label;
  el.jobNextStepDescription.textContent = nextStep.description;
  const primary = nextStep.href
    ? `<a id="nextIntakeStep" class="action-btn action-btn-primary" href="${escapeAttribute(nextStep.href)}">${escapeHtml(nextStep.primaryText)}</a>`
    : '<button id="nextIntakeStep" type="button" class="action-btn action-btn-primary" data-intake-start>Выполнить следующий шаг</button>';
  el.jobNextStepActions.innerHTML = `
    ${primary}
    <a class="action-btn action-btn-secondary" href="/reviews">Открытые решения</a>
    <a class="action-btn action-btn-secondary" href="/catalog-admin/groups">Открыть справочник</a>
    <a class="action-btn action-btn-secondary" href="/up">Открыть УП</a>`;
}

function renderBlockers(blockers) {
  el.jobBlockersCard.hidden = !blockers.length;
  el.jobBlockersPill.textContent = `${blockers.length} блокеров`;
  el.jobBlockers.innerHTML = blockers
    .map((blocker) => `
      <a class="workspace-blocker workspace-blocker-${escapeAttribute(blocker.severity)}" href="${escapeAttribute(blocker.href)}">
        <span class="workspace-blocker-count">${escapeHtml(blocker.count)}</span>
        <span class="workspace-blocker-body">
          <strong>${escapeHtml(blocker.label)}</strong>
          <span>${escapeHtml(blocker.description)}</span>
        </span>
      </a>`)
    .join("");
}

function renderCatalogState(items) {
  el.jobCatalogStateCard.hidden = !items.length;
  el.jobCatalogState.innerHTML = items
    .map(([label, value, note]) => `
      <div class="summary-card">
        <div class="summary-label">${escapeHtml(label)}</div>
        <div class="summary-value">${escapeHtml(value)}</div>
        <div class="small muted">${escapeHtml(note)}</div>
      </div>`)
    .join("");
}

function renderCreatedItems(items) {
  el.jobCreatedItemsCard.hidden = !items.length;
  el.jobCreatedItemsPill.textContent = `${items.length} записей`;
  el.jobCreatedItems.innerHTML = items
    .map((item) => `
      <a class="catalog-summary-item" href="/catalog-admin/skills/${item.skill_id}">
        <strong>${escapeHtml(item.name || `Skill #${item.skill_id}`)}</strong>
        <span>${escapeHtml(item.group || "Без группы")}</span>
        <small>${item.created_review ? "review queue" : "accepted"} · ${item.indicator_count || 0} инд.</small>
      </a>`)
    .join("");
}

const RESOLUTION_LABELS = {
  matched: "Покрывает",
  alias: "Синоним",
  fuzzy: "Почти эквивалент",
  new: "Новый",
  unresolved: "Без резолва",
};

const CARD_STATUS_LABELS = {
  accepted: "Принято",
  needs_review: "На проверке",
  rejected: "Отклонено",
  candidate: "Кандидат",
  superseded: "Заменён",
};

function renderSkillCards(items) {
  const cards = items.filter((item) => item && item.name);
  el.jobSkillCardsCard.hidden = !cards.length;
  el.jobSkillCardsPill.textContent = String(cards.length);
  el.jobSkillCards.innerHTML = cards.map(skillCardMarkup).join("");
}

function skillCardMarkup(item) {
  const hint = item.similarity_hint || {};
  const action = item.recommended_action || {};
  const hintClass = hint.class || "neutral";
  const skillHref = encodeURIComponent(item.skill_id);
  const skillAttr = escapeHtml(String(item.skill_id));
  const nearest = item.nearest_name
    ? `<span class="skill-card-nearest">Ближайший в каталоге: <a href="/catalog-admin/skills/${skillHref}">${escapeHtml(item.nearest_name)}</a></span>`
    : "";
  const council = item.council_agreement === null || item.council_agreement === undefined
    ? ""
    : ` · жюри <b>${escapeHtml(String(item.council_agreement))}</b>`;
  const tools = Array.isArray(item.tools) && item.tools.length ? ` · ${escapeHtml(item.tools.join(", "))}` : "";
  return `
    <article class="intake-skill-card" data-skill="${skillAttr}">
      <header class="skill-card-head">
        <div class="skill-card-title">
          <strong>${escapeHtml(item.name)}</strong>
          ${item.bloom ? `<span class="pill bloom-pill">Блум: ${escapeHtml(item.bloom)}</span>` : ""}
        </div>
        <div class="skill-card-actions" role="group" aria-label="Решение методолога">
          <a class="card-act create" title="Создать новый skill" href="/catalog-admin/skills/${skillHref}">＋</a>
          <a class="card-act link" title="Привязать к каталогу" href="/reviews?status=open">⟷</a>
          <a class="card-act reject" title="Открыть в очереди решений" href="/reviews?status=open">✕</a>
        </div>
      </header>
      <p class="skill-card-meta small muted">${escapeHtml(item.group || "Без группы")}${tools}</p>
      <div class="chips-row skill-card-chips">
        <span class="pill resolution-${escapeHtml(item.resolution || "unresolved")}">${escapeHtml(RESOLUTION_LABELS[item.resolution] || item.resolution || "—")}</span>
        <span class="pill sim-${escapeHtml(hintClass)}">${escapeHtml(hint.label || "—")}</span>
        ${nearest}
      </div>
      <div class="skill-card-metrics small">
        похожесть <b>${escapeHtml(item.match_score ?? "—")}</b> · новизна <b>${escapeHtml(item.novelty_score ?? "—")}</b>
        · уверенность <b>${escapeHtml(String(item.confidence ?? "—"))}</b>${council}
        · <span class="status-badge ${item.status === "needs_review" ? "warning" : ""}">${escapeHtml(CARD_STATUS_LABELS[item.status] || item.status || "—")}</span>
      </div>
      ${action.label ? `<div class="skill-card-reco sim-${escapeHtml(hintClass)}"><strong>${escapeHtml(action.label)}</strong><span class="small muted">${escapeHtml(action.detail || "")}</span></div>` : ""}
    </article>`;
}

function renderPipelineResult(items) {
  el.jobPipelineResultCard.hidden = !items.length;
  el.jobPipelineResult.innerHTML = items
    .map(([label, value, note]) => `
      <div class="summary-card">
        <div class="summary-label">${escapeHtml(label)}</div>
        <div class="summary-value">${escapeHtml(value)}</div>
        <div class="small muted">${escapeHtml(note)}</div>
      </div>`)
    .join("");
}

function renderWorkflowSteps(steps) {
  el.jobWorkflowSteps.innerHTML = steps
    .map(([label, description, href, status], index) => `
      <a class="workflow-step workflow-step-${escapeAttribute(status)}" href="${escapeAttribute(href)}">
        <span class="workflow-step-index">${index + 1}</span>
        <span class="workflow-step-body">
          <span class="workflow-step-label">${escapeHtml(label)}</span>
          <span class="workflow-step-description">${escapeHtml(description)}</span>
        </span>
      </a>`)
    .join("");
}

function buildPipelineResult(job, result, failed) {
  if (!job) return [];
  if (failed) {
    return [["Ошибка", job.error_text || "Pipeline завершился ошибкой", "см. status JSON"]];
  }
  const spec = result.spec || {};
  const plan = result.curriculum_plan || {};
  return [
    ["Бриф", result.brief_id || job.brief_id || "—", "profile_brief"],
    ["Роль", spec.role || spec.artifact_type || "—", spec.domain || "домен не указан"],
    ["Компетенции", result.competency_count || 0, "извлечено из брифа"],
    ["УП", plan.plan_id ? `#${plan.plan_id}` : "—", plan.project_count ? `${plan.project_count} проектов` : "нет черновика"],
  ];
}

function normalizeSavedItems(result) {
  if (Array.isArray(result.saved_items) && result.saved_items.length) return result.saved_items;
  return (result.saved_skill_ids || []).map((skillId) => ({
    skill_id: skillId,
    name: `Skill #${skillId}`,
    group: "",
    indicator_count: 0,
    created_review: false,
  }));
}

function progressForJob(job) {
  if (job.status === "succeeded" || job.status === "failed") return 100;
  if (job.status === "running") return 45;
  return 10;
}

function activeProgressStage(job, result) {
  if (job.status === "pending" || job.status === "running") return "catalog";
  if (Number(result.review_count || 0) > 0) return "review";
  if (result.curriculum_plan?.plan_id) return "up";
  return "dag";
}

function statusLabel(status) {
  return ({ pending: "pending", running: "running", succeeded: "готово", failed: "ошибка" })[status] || status || "draft";
}

function stageLabel(stage) {
  return ({
    brief_to_catalog: "Декомпозиция брифа",
    done: "Завершено",
    failed: "Ошибка обработки",
    pending: "Постановка в очередь",
  })[stage] || stage || "Постановка в очередь";
}

function sourceLabel(sourceKind) {
  return sourceKind === "file" ? "документ" : "текстовый бриф";
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU");
}

function renderDeferredLegacyLists() {
  // Reserved for future legacy-only screens that still have no backend adapter.
}

function renderArtifactTemplates() {
  const templates = state.artifactTemplates || [];
  el.artifactTemplateCount.textContent = String(templates.length);
  el.templateList.innerHTML = templates.length
    ? templates
        .map((template) => `
          <button type="button" class="list-item" data-template-edit="${template.id}">
            <strong>${escapeHtml(template.title)}</strong>
            <span>${escapeHtml(template.artifact_family)} · ${escapeHtml(template.status)} · priority ${template.priority}</span>
          </button>`)
        .join("")
    : '<div class="empty-inline">Шаблонов пока нет.</div>';
  el.artifactTemplateTable.innerHTML = templates.length
    ? templates.map(renderArtifactTemplateRow).join("")
    : '<div class="empty-state">Шаблонов пока нет. Создайте первый шаблон выше.</div>';
}

function renderArtifactTemplateRow(template) {
  const scopes = template.scopes?.length
    ? template.scopes.map((scope) => `<span class="pill">${escapeHtml(scope.scope_type)}: ${escapeHtml(scope.scope_name || "*")}</span>`).join(" ")
    : '<span class="muted">Не задан</span>';
  const nextStatus = template.status === "active" ? "deprecated" : "active";
  const actionLabel = template.status === "active" ? "Отключить" : "Включить";
  const actionClass = template.status === "active" ? "action-btn-danger" : "action-btn-primary";
  return `
    <article class="entity-card artifact-template-row" data-template-row="${template.id}">
      <div class="entity-head">
        <div>
          <strong>${escapeHtml(template.title)}</strong>
          <p class="muted">${escapeHtml(template.code)}</p>
          ${template.artifact_description ? `<p>${escapeHtml(template.artifact_description)}</p>` : ""}
        </div>
        <span class="status-badge ${template.status !== "active" ? "warning" : ""}">${escapeHtml(template.status)}</span>
      </div>
      <div class="metrics">
        <span>${escapeHtml(template.artifact_family)}</span>
        <span>priority ${template.priority}</span>
        <span>${escapeHtml(template.source || "manual")}</span>
      </div>
      <div class="chips-row">${scopes}</div>
      <div class="form-actions">
        <button type="button" class="action-btn action-btn-light" data-template-edit="${template.id}">Редактировать</button>
        <button type="button" class="action-btn ${actionClass}" data-template-status="${template.id}" data-status="${nextStatus}">${actionLabel}</button>
      </div>
    </article>`;
}

function renderArchive() {
  const archive = state.archive || {};
  const groups = archive.groups || [];
  const skills = archive.skills || [];
  const indicators = archive.indicators || [];
  const scope = archive.scope || "all";
  const counts = archive.counts || { groups: groups.length, skills: skills.length, indicators: indicators.length };
  el.archiveGroupsBlock.hidden = !["all", "groups"].includes(scope);
  el.archiveSkillsBlock.hidden = !["all", "skills"].includes(scope);
  el.archiveIndicatorsBlock.hidden = !["all", "indicators"].includes(scope);
  if (el.archiveSearch.value !== (archive.query || "") && document.activeElement !== el.archiveSearch) {
    el.archiveSearch.value = archive.query || "";
  }
  el.archiveScope.value = scope;
  el.archiveList.innerHTML = `
    <button class="list-item" type="button" data-archive-jump="groups">
      <strong>Архивные группы</strong>
      <span>${counts.groups || 0} записей</span>
    </button>
    <button class="list-item" type="button" data-archive-jump="skills">
      <strong>Архивные skills</strong>
      <span>${counts.skills || 0} записей</span>
    </button>
    <button class="list-item" type="button" data-archive-jump="indicators">
      <strong>Архивные индикаторы</strong>
      <span>${counts.indicators || 0} записей</span>
    </button>`;
  el.archiveQueryLabel.textContent = archive.query ? `Результаты поиска: ${archive.query}` : "Поиск по всему архиву";
  el.archivedGroupCount.textContent = String(counts.groups || 0);
  el.archivedSkillCount.textContent = String(counts.skills || 0);
  el.archivedIndicatorCount.textContent = String(counts.indicators || 0);
  el.archivedGroups.innerHTML = groups.length
    ? groups.map(renderArchivedGroup).join("")
    : '<div class="empty-state">В архиве нет групп.</div>';
  el.archivedSkills.innerHTML = skills.length
    ? skills.map(renderArchivedSkill).join("")
    : '<div class="empty-state">В архиве нет skills.</div>';
  el.archivedIndicators.innerHTML = indicators.length
    ? indicators.map(renderArchivedIndicator).join("")
    : '<div class="empty-state">В архиве нет индикаторов.</div>';
}

function renderArchivedGroup(group) {
  return `
    <article class="entity-card archive-card" data-archive-card="group-${group.id}">
      <div class="entity-head">
        <div>
          <h2>${escapeHtml(group.title)}</h2>
          <p class="muted">competency #${group.id}</p>
        </div>
        <span class="status-badge warning">${escapeHtml(group.status)}</span>
      </div>
      <div class="metrics">
        <span>${group.skill_count || 0} skills</span>
        <span>${group.indicator_count || 0} индикаторов</span>
        <span>${group.profile_count || 0} профилей</span>
      </div>
      <div class="review-actions">
        <button type="button" class="action-btn action-btn-primary" data-archive-restore="group" data-archive-id="${group.id}">Восстановить группу</button>
      </div>
    </article>`;
}

function renderArchivedSkill(skill) {
  const groups = skill.group_names?.length ? skill.group_names.join(", ") : "Без группы";
  return `
    <article class="entity-card archive-card" data-archive-card="skill-${skill.skill_id}">
      <div class="entity-head">
        <div>
          <h2>${escapeHtml(skill.canonical_name)}</h2>
          <p class="muted">${escapeHtml(groups)}</p>
        </div>
        <span class="status-badge warning">${escapeHtml(skill.status)}</span>
      </div>
      <div class="metrics">
        <span>${escapeHtml(skill.skill_type || "unknown")}</span>
        <span>${skill.indicator_count || 0} индикаторов</span>
        <span>${skill.aliases?.length || 0} aliases</span>
      </div>
      <div class="review-actions">
        <button type="button" class="action-btn action-btn-primary" data-archive-restore="skill" data-archive-id="${skill.skill_id}">Восстановить skill</button>
        <a class="action-btn action-btn-secondary" href="/catalog-admin/skills/${skill.skill_id}">Открыть карточку</a>
      </div>
    </article>`;
}

function renderArchivedIndicator(indicator) {
  return `
    <article class="entity-card archive-card" data-archive-card="indicator-${indicator.id}">
      <div class="entity-head">
        <div>
          <h2>${escapeHtml(indicator.dimension_title || indicator.dimension_code || "Индикатор")}</h2>
          <p class="muted">${escapeHtml(indicator.group_name || "Без группы")} → ${escapeHtml(indicator.skill_name || "Skill не связан")}</p>
        </div>
        <span class="status-badge warning">${escapeHtml(indicator.status)}</span>
      </div>
      <p>${escapeHtml(indicator.text)}</p>
      <div class="metrics">
        <span>${escapeHtml(indicator.profile_name || "reference")}</span>
        <span>${escapeHtml(indicator.notes || "без notes")}</span>
      </div>
      <div class="review-actions">
        <button type="button" class="action-btn action-btn-primary" data-archive-restore="indicator" data-archive-id="${indicator.id}">Восстановить индикатор</button>
        ${indicator.skill_id ? `<a class="action-btn action-btn-secondary" href="/catalog-admin/skills/${indicator.skill_id}">Открыть skill</a>` : ""}
      </div>
    </article>`;
}

function fillArtifactTemplateForm(template = null) {
  const scopeNames = template?.scope_names || [];
  el.artifactTemplateId.value = template?.id || "";
  el.artifactTemplateFormTitle.textContent = template ? "Редактирование шаблона" : "Новый шаблон";
  el.artifactTemplateCode.value = template?.code || "";
  el.artifactTemplateTitle.value = template?.title || "";
  el.artifactTemplateFamily.value = template?.artifact_family || "practice";
  el.artifactTemplateStatus.value = template?.status || "active";
  el.artifactTemplatePriority.value = template?.priority ?? 100;
  el.artifactTemplateScopeWeight.value = template?.scope_weight ?? 1.0;
  el.artifactTemplateDescription.value = template?.artifact_description || "";
  el.artifactTemplateProjectPattern.value = template?.project_name_pattern || "";
  el.artifactTemplateMaterials.value = template?.materials_pattern || "";
  el.artifactTemplateStorytelling.value = template?.storytelling_pattern || "";
  el.artifactTemplateCriteria.value = template?.validation_criteria || "";
  el.artifactTemplateScopeType.value = template?.scope_type || "coverage_area";
  el.artifactTemplateScopeNames.value = scopeNames.join("\n");
}

function artifactTemplatePayload() {
  return {
    code: el.artifactTemplateCode.value.trim(),
    title: el.artifactTemplateTitle.value.trim(),
    artifact_family: el.artifactTemplateFamily.value,
    artifact_description: el.artifactTemplateDescription.value.trim(),
    project_name_pattern: el.artifactTemplateProjectPattern.value.trim(),
    materials_pattern: el.artifactTemplateMaterials.value.trim(),
    storytelling_pattern: el.artifactTemplateStorytelling.value.trim(),
    validation_criteria: el.artifactTemplateCriteria.value.trim(),
    priority: Number(el.artifactTemplatePriority.value || 100),
    status: el.artifactTemplateStatus.value,
    source: "methodologist",
    scope_type: el.artifactTemplateScopeType.value,
    scope_names: splitLines(el.artifactTemplateScopeNames.value),
    scope_weight: Number(el.artifactTemplateScopeWeight.value || 1.0),
  };
}

function renderCandidateCompetencies(workspace) {
  const candidates = workspace.candidates || state.candidateCompetencies || [];
  const openCount = workspace.open_count ?? candidates.filter((item) => item.review_state === "needs_review" || item.review_id).length;
  el.candidateOpenCount.textContent = `${openCount} на проверке`;
  el.candidateList.innerHTML = candidates.length
    ? candidates
        .map((item) => `
          <button type="button" class="list-item" data-candidate-jump="${item.competency_id}">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${item.skill_count || 0} skills · ${candidateReviewLabel(item.review_state)} · ${escapeHtml(item.status)}</span>
          </button>`)
        .join("")
    : '<div class="empty-inline">Открытых кандидатных компетенций нет.</div>';
  el.candidateCards.innerHTML = candidates.length
    ? candidates.map(renderCandidateCompetencyCard).join("")
    : '<div class="empty-state">Открытых кандидатных компетенций нет. Новые группировки появятся после intake.</div>';
}

function renderCandidateCompetencyCard(item) {
  const nearest = item.nearest_competency;
  const statusLabel = item.status === "candidate" ? "кандидат" : item.status === "active" ? "активная" : item.status;
  const reviewLabel = candidateReviewLabel(item.review_state);
  return `
    <details class="candidate-competency-card candidate-competency-window" id="candidate-${item.competency_id}" open>
      <summary class="candidate-competency-summary">
        <span class="candidate-competency-summary-main">
          <strong>${escapeHtml(item.title)}</strong>
          <small>competency #${item.competency_id} · состояние: ${reviewLabel} · статус: ${escapeHtml(statusLabel)}</small>
        </span>
        <span class="candidate-competency-summary-meta">
          <span class="pill">${item.skill_count || 0} skills</span>
          ${item.reason_code ? `<span class="pill">${escapeHtml(candidateReasonLabel(item.reason_code))}</span>` : ""}
          <span class="status-badge ${item.review_state === "needs_review" ? "warning" : ""}">${reviewLabel}</span>
        </span>
      </summary>
      <div class="candidate-competency-body">
        <div class="candidate-competency-main">
          ${renderCandidateSimilarity(item.similar_competencies || [])}
          ${renderCandidateSkillMoves(item)}
          ${item.details ? `<details class="collapse-panel technical-details"><summary>Техническая причина создания</summary><pre>${escapeHtml(item.details)}</pre></details>` : ""}
        </div>
        <div class="candidate-competency-actions">
          <form class="admin-form" data-candidate-action="rename">
            <input type="hidden" name="competency_id" value="${item.competency_id}">
            <label>
              <span>Переименовать</span>
              <input name="new_title" value="${escapeAttribute(item.title)}" required>
            </label>
            <button type="submit" class="action-btn action-btn-light">Сохранить имя</button>
          </form>
          <form class="admin-form" data-candidate-action="merge">
            <input type="hidden" name="competency_id" value="${item.competency_id}">
            <label>
              <span>Слить с существующей</span>
              <select name="target_competency_id" required>
                <option value="">Выберите компетенцию...</option>
                ${renderCandidateOptions(item.competency_id, nearest?.id)}
              </select>
            </label>
            <button type="submit" class="action-btn action-btn-secondary">Слить</button>
          </form>
          <form class="admin-form" data-candidate-action="decision">
            <input type="hidden" name="competency_id" value="${item.competency_id}">
            <textarea name="resolution_note" rows="2" placeholder="Комментарий методолога"></textarea>
            <div class="form-actions">
              <button type="submit" name="action" value="accept" class="action-btn action-btn-primary">Принять новую</button>
              <button type="submit" name="action" value="review" class="action-btn action-btn-light">Вернуть на проверку</button>
              <button type="submit" name="action" value="reject" class="action-btn action-btn-danger">Отклонить</button>
            </div>
          </form>
        </div>
      </div>
    </details>`;
}

function renderCandidateSimilarity(matches) {
  if (!matches.length) return "";
  return `
    <div class="competency-similarity-panel">
      <div class="summary-head"><h3>Похожие компетенции</h3><span class="pill">${matches[0].score}%</span></div>
      <div class="competency-similarity-list">
        ${matches
          .map((match) => `
            <a class="competency-similarity-item competency-similarity-${escapeAttribute(match.recommendation)}" href="/competencies/${match.id}">
              <span>
                <strong>${escapeHtml(match.title)}</strong>
                <small>${escapeHtml(match.label)} · название ${match.title_similarity_pct}% · слова ${match.token_overlap_pct}% · skills ${match.skill_overlap_count}/${match.candidate_skill_count}</small>
              </span>
              <b>${match.score}%</b>
            </a>`)
          .join("")}
      </div>
    </div>`;
}

function renderCandidateSkillMoves(item) {
  const skills = item.skills || [];
  if (!skills.length) return "";
  return `
    <div class="candidate-skill-move-list">
      <h3>Навыки внутри кандидатной компетенции</h3>
      ${skills
        .map((skill) => `
          <div class="candidate-skill-move-row">
            <div>
              <strong>${escapeHtml(skill.canonical_name || skill.source_skill_name)}</strong>
              <div class="small muted">связь #${skill.competency_skill_id} · ${candidateReviewLabel(skill.review_state)}</div>
            </div>
            <form class="inline-form" data-candidate-action="move_skill">
              <input type="hidden" name="competency_id" value="${item.competency_id}">
              <input type="hidden" name="competency_skill_id" value="${skill.competency_skill_id}">
              <select name="target_competency_id" required>
                <option value="">Перенести в компетенцию...</option>
                ${renderCandidateOptions(item.competency_id)}
              </select>
              <button type="submit" class="action-btn action-btn-light">Перенести</button>
            </form>
          </div>`)
        .join("")}
    </div>`;
}

function renderCandidateOptions(currentId, selectedId = null) {
  return (state.candidateOptions || [])
    .filter((option) => Number(option.id) !== Number(currentId))
    .map((option) => `<option value="${option.id}" ${Number(option.id) === Number(selectedId) ? "selected" : ""}>${escapeHtml(option.title)}</option>`)
    .join("");
}

function candidateReviewLabel(value) {
  return ({ needs_review: "на проверке", accepted: "принято", rejected: "отклонено", draft: "черновик" })[value] || value || "на проверке";
}

function candidateReasonLabel(value) {
  return value === "new_competency_candidate" ? "новая кандидатная компетенция" : value;
}

function updateBriefSubmitState() {
  const hasText = Boolean(el.briefText.value.trim());
  const hasFile = Boolean(el.briefFileInput.files?.[0]);
  el.briefSubmitWrap.hidden = !(hasText || hasFile);
}

async function selectCompetency(id) {
  state.current = await request(`/reference/competencies/${id}`);
  showDetailSection("competency");
  el.title.value = state.current.title || "";
  el.status.value = state.current.status || "candidate";
  el.description.value = state.current.description || "";
  el.detailMeta.innerHTML = `
    <span>${state.current.profile_count} профилей</span>
    <span>${state.current.skill_count} skills</span>
    <span>${state.current.indicator_count} индикаторов</span>
  `;
  renderSkillTree();
  setStatus(`Открыто: ${state.current.title}`);
}

async function selectProfile(id) {
  state.currentProfile = await request(`/reference/profiles/${id}`);
  showDetailSection("profile");
  el.profileDetail.innerHTML = `
    <div class="metrics">
      <span>${escapeHtml(state.currentProfile.name)}</span>
      <span>${state.currentProfile.competency_count} компетенций</span>
      <span>${state.currentProfile.indicator_count} индикаторов</span>
    </div>
    ${renderProfileTree(state.currentProfile.competencies || [])}
  `;
  setStatus(`Профиль: ${state.currentProfile.name}`);
}

function renderSkillTree() {
  el.skillTree.innerHTML =
    (state.current.skills || [])
      .map(
        (skill) => `
          <details class="tree-card" open>
            <summary>
              <strong>${escapeHtml(skill.name || "Без названия")}</strong>
              <span class="status-badge">${escapeHtml(skill.status || "unknown")}</span>
            </summary>
            <div class="card-body">
              <div class="inline-actions">
                <button class="btn" type="button" data-edit-skill="${skill.skill_id || ""}">Редактировать skill</button>
                <span class="small">${escapeHtml(skill.profile_name || "")}</span>
              </div>
              ${skill.aliases?.length ? `<p class="small"><strong>Алиасы:</strong> ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
              ${renderIndicators(skill.indicators || [])}
            </div>
          </details>`,
      )
      .join("") || '<div class="empty-inline">Связанные skills и индикаторы пока отсутствуют</div>';
}

function renderProfileTree(competencies) {
  return competencies
    .map(
      (competency) => `
        <details class="tree-card" open>
          <summary>
            <strong>${escapeHtml(competency.title_in_source || competency.title)}</strong>
            <span class="status-badge">${escapeHtml(competency.review_state)}</span>
          </summary>
          <div class="card-body">
            ${competency.prerequisites_text ? `<p class="small"><strong>Prerequisites:</strong> ${escapeHtml(competency.prerequisites_text)}</p>` : ""}
            ${(competency.skills || [])
              .map(
                (skill) => `
                  <details class="indicator-block">
                    <summary>
                      <strong>${escapeHtml(skill.name)}</strong>
                      <span class="pill">${escapeHtml(skill.status)}</span>
                    </summary>
                    ${skill.aliases?.length ? `<p class="small">Aliases: ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
                    ${renderIndicators(skill.indicators || [])}
                  </details>`,
              )
              .join("")}
          </div>
        </details>`,
    )
    .join("") || '<div class="empty-inline">Профиль пуст</div>';
}

function renderIndicators(indicators) {
  return indicators
    .map(
      (indicator) => `
        <div class="indicator-block">
          <div class="indicator-line">
            <span class="pill">${escapeHtml(indicator.dimension_title || indicator.dimension_code || "N/A")}</span>
            <span>${escapeHtml(indicator.text || "")}</span>
          </div>
          ${
            indicator.levels?.length
              ? `<div class="levels-grid">${indicator.levels
                  .map((level) => `<div class="level-cell"><span>${escapeHtml(level.label)}</span><span>${escapeHtml(level.value)}</span></div>`)
                  .join("")}</div>`
              : ""
          }
        </div>`,
    )
    .join("");
}

async function routeCatalogAdmin() {
  const skillId = skillIdFromLocation();
  if (skillId) {
    await selectSkillById(skillId);
    return;
  }
  const groupId = groupIdFromLocation();
  if (groupId) {
    await selectGroup(groupId);
    return;
  }
  renderGroupOverview();
}

function renderGroupOverview() {
  showDetailSection("placeholder");
  el.placeholderTitle.textContent = "Каталог DB";
  el.placeholderText.innerHTML = `
    <p>Черновой CRUD поверх целевой структуры competency group → skill → indicator.</p>
    <div class="reference-list compact">
      ${state.groups
        .map((group) => `
          <a class="list-item" href="/catalog-admin/groups/${group.id}">
            <strong>${escapeHtml(group.title)}</strong>
            <span>${group.skill_count} skills · ${group.indicator_count} индикаторов · ${escapeHtml(group.status)}</span>
          </a>`)
        .join("") || '<div class="empty-inline">Группы не найдены</div>'}
    </div>`;
  setStatus("Каталог DB: группы skills");
}

async function selectGroup(groupId) {
  state.current = await request(`/reference/groups/${groupId}`);
  showDetailSection("group");
  el.pageTitle.textContent = state.current.title || "Группа";
  el.pageSubtitle.textContent = `${state.current.skill_count || 0} skills · ${state.current.indicator_count || 0} индикаторов · ${state.current.status || "candidate"}`;
  el.groupTitle.value = state.current.title || "";
  el.groupStatus.value = state.current.status || "candidate";
  el.groupDescription.value = state.current.description || "";
  const skills = state.current.skills || [];
  el.groupSkillCount.textContent = `${skills.length} skills`;
  el.groupSkillList.innerHTML = skills
    .map((skill) => `
      <article class="review-item">
        <strong><a href="/catalog-admin/skills/${skill.skill_id}">${escapeHtml(skill.name || "Без названия")}</a></strong>
        <span>${escapeHtml(skill.status || "unknown")} · ${skill.indicators?.length || 0} индикаторов</span>
        ${skill.aliases?.length ? `<p class="small"><strong>Алиасы:</strong> ${skill.aliases.map(escapeHtml).join(", ")}</p>` : ""}
        <div class="inline-actions">
          <a class="action-btn action-btn-secondary" href="/catalog-admin/skills/${skill.skill_id}">Открыть skill</a>
        </div>
      </article>`)
    .join("") || '<div class="empty-inline">В группе пока нет skills</div>';
  setStatus(`Группа: ${state.current.title}`);
}

async function selectSkillById(skillId) {
  state.selectedSkill = await request(`/reference/skills/${skillId}`);
  showDetailSection("skill");
  el.pageTitle.textContent = state.selectedSkill.canonical_name || "Skill";
  el.pageSubtitle.textContent = `${state.selectedSkill.links?.length || 0} competency links · ${state.selectedSkill.indicators?.length || 0} индикаторов`;
  fillSkillForm(state.selectedSkill);
  renderSkillDetail(state.selectedSkill);
  setStatus(`Skill: ${state.selectedSkill.canonical_name}`);
}

function renderSkillDetail(skill) {
  el.skillLinks.innerHTML = (skill.links || [])
    .map((link) => `
      <article class="list-item parity-list-item">
        <strong>${escapeHtml(link.competency_title)}</strong>
        <span>${escapeHtml(link.profile_name)} · competency ${escapeHtml(link.competency_status)} · link ${escapeHtml(link.competency_skill_state)} · ${link.indicators?.length || 0} indicators</span>
      </article>`)
    .join("") || '<div class="empty-inline">Skill пока не входит ни в одну competency.</div>';
  el.skillIndicators.innerHTML = renderEditableIndicators(skill.indicators || []);
}

function renderEditableIndicators(indicators) {
  return indicators
    .map((indicator) => `
      <article class="entity-card indicator-editor" data-indicator-card="${indicator.id}">
        <form class="admin-form" data-indicator-form="${indicator.id}">
          <div class="form-grid-2">
            <label>
              Тип
              <select data-indicator-dimension>
                ${dimensionOption("knowledge", "Знает", indicator.dimension_code)}
                ${dimensionOption("ability", "Умеет", indicator.dimension_code)}
                ${dimensionOption("proficiency", "Владеет", indicator.dimension_code)}
                ${dimensionOption("unspecified", "Не указано", indicator.dimension_code)}
              </select>
            </label>
            <label>
              Notes
              <input data-indicator-notes value="${escapeAttribute(indicator.notes || "")}" />
            </label>
          </div>
          <label>
            Текст
            <textarea data-indicator-text rows="3">${escapeHtml(indicator.text || "")}</textarea>
          </label>
          ${renderIndicators([indicator])}
          <div class="form-actions">
            <button type="submit" class="action-btn action-btn-primary">Сохранить индикатор</button>
            <button type="button" class="action-btn action-btn-light" data-delete-indicator="${indicator.id}">Удалить индикатор</button>
          </div>
        </form>
      </article>`)
    .join("") || '<div class="empty-inline">Индикаторы пока не заданы.</div>';
}

function dimensionOption(value, label, current) {
  return `<option value="${value}" ${value === current ? "selected" : ""}>${label}</option>`;
}

function fillSkillForm(skill) {
  el.skillName.value = skill?.canonical_name || "";
  el.skillStatus.value = skill?.status || "active";
  el.skillType.value = skill?.skill_type || "unknown";
  el.skillAliases.value = (skill?.aliases || []).join("\n");
}

function showDetailSection(kind) {
  el.competencySection.hidden = kind !== "competency";
  el.skillSection.hidden = kind !== "skill";
  el.groupSection.hidden = kind !== "group";
  el.candidateSection.hidden = kind !== "candidates";
  el.artifactTemplateSection.hidden = kind !== "templates";
  el.archiveSection.hidden = kind !== "archive";
  el.profileSection.hidden = kind !== "profile";
  el.placeholderSection.hidden = kind !== "placeholder";
}

function setListMode(mode) {
  state.mode = mode;
  setPageChrome(mode);
  const workspaceMode = mode === "workspace";
  document.body.classList.toggle("page-intake", workspaceMode);
  document.body.classList.toggle("page-reference", !workspaceMode);
  el.secondaryNav.hidden = workspaceMode;
  el.toolbar.hidden = workspaceMode;
  el.referenceGrid.hidden = workspaceMode;
  el.intakeWorkspace.hidden = !workspaceMode;
  for (const node of document.querySelectorAll("[data-reference-mode]")) {
    node.classList.toggle("active", node.dataset.referenceMode === mode);
  }
  for (const node of document.querySelectorAll("[data-reference-mode-link]")) {
    node.classList.toggle("active", node.dataset.referenceModeLink === mode);
  }
  for (const node of document.querySelectorAll("[data-primary-route]")) {
    const route = node.dataset.primaryRoute;
    const active = (mode === "workspace" && route === "intake")
      || (mode !== "workspace" && route === "catalog")
      || (location.pathname.startsWith("/up") && route === "curriculum");
    node.classList.toggle("active", active);
  }
  el.groupList.hidden = mode !== "skills";
  if (el.groupCreateForm) el.groupCreateForm.hidden = mode !== "skills";
  el.skillList.hidden = true;
  el.competencyList.hidden = mode !== "competencies";
  el.profileList.hidden = mode !== "profiles";
  el.reviewList.hidden = mode !== "reviews";
  el.candidateList.hidden = mode !== "candidates";
  el.templateList.hidden = mode !== "templates";
  el.archiveList.hidden = mode !== "archive";
  if (workspaceMode) setStatus("Рабочий стол брифа");
  if (mode === "candidates") showCandidateCompetenciesDetail();
  if (mode === "templates") showArtifactTemplateDetail();
  if (mode === "archive") showArchiveDetail();
  if (isDeferredMode(mode)) showDeferredDetail(mode);
}

function setPageChrome(mode) {
  const meta = MODE_META[mode] || MODE_META.skills;
  if (mode === "skills" && window.location.pathname.startsWith("/catalog-admin/groups")) {
    el.pageTitle.textContent = "Каталог DB";
    el.pageSubtitle.textContent = "Черновой CRUD поверх целевой структуры competency group -> skill -> indicator.";
    return;
  }
  el.pageTitle.textContent = meta[0];
  el.pageSubtitle.textContent = meta[1];
  if (mode !== "workspace") el.intakePrimaryAction.textContent = "Рабочий стол";
}

function showDeferredDetail(mode) {
  const meta = MODE_META[mode] || MODE_META.workspace;
  showDetailSection("placeholder");
  el.placeholderTitle.textContent = meta[0];
  el.placeholderText.textContent = meta[1];
  setStatus(`${meta[0]}: экран зафиксирован для parity-переноса`);
}

function showReviewQueueDetail() {
  showDetailSection("placeholder");
  el.placeholderTitle.textContent = "Review queue";
  el.placeholderText.textContent = "Используйте список слева: resolved / ignored / в очередь через `/reference/reviews/{id}`. Apply-catalog и build-DAG выполняются автоматически в intake-задаче (Рабочий стол).";
  setStatus("Очередь проверки");
}

function showCandidateCompetenciesDetail() {
  showDetailSection("candidates");
  setStatus(`Кандидатные компетенции: ${state.candidateCompetencies.length}`);
}

function showArtifactTemplateDetail() {
  showDetailSection("templates");
  if (!el.artifactTemplateId.value && state.artifactTemplates.length) {
    fillArtifactTemplateForm(state.artifactTemplates[0]);
  } else if (!state.artifactTemplates.length) {
    fillArtifactTemplateForm(null);
  }
  setStatus(`Шаблоны УП: ${state.artifactTemplates.length}`);
}

function showArchiveDetail() {
  showDetailSection("archive");
  const counts = state.archive?.counts || { groups: 0, skills: 0, indicators: 0 };
  setStatus(`Архив: ${counts.groups || 0} групп, ${counts.skills || 0} skills, ${counts.indicators || 0} индикаторов`);
}

function isDeferredMode(mode) {
  return false;
}

function deferredCard(title, text) {
  return `<article class="list-item parity-list-item"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span></article>`;
}

function renderEmptyDetail(message) {
  state.current = null;
  el.form.reset();
  el.detailMeta.innerHTML = "";
  el.skillTree.innerHTML = `<div class="empty-inline">${escapeHtml(message)}</div>`;
}

function splitAliases(value) {
  return value.split(/[\n;]+/).map((item) => item.trim()).filter(Boolean);
}

function splitLines(value) {
  return value.split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

function setStatus(message) {
  el.statusLine.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

document.querySelector(".tab-list").addEventListener("click", (event) => {
  const item = event.target.closest("[data-reference-mode]");
  if (item) setListMode(item.dataset.referenceMode);
});
el.searchButton.addEventListener("click", () => loadAll().catch((error) => setStatus(error.message)));
el.reviewStatusFilter.addEventListener("change", () => loadAll().catch((error) => setStatus(error.message)));
for (const filter of [el.reviewSeverityFilter, el.reviewEntityFilter, el.reviewReasonFilter]) {
  filter?.addEventListener("change", () => loadAll().catch((error) => setStatus(error.message)));
}
el.includeServiceProfiles.addEventListener("change", () => loadAll().catch((error) => setStatus(error.message)));
el.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadAll().catch((error) => setStatus(error.message));
});
el.competencyList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-competency-id]");
  if (item) selectCompetency(Number(item.dataset.competencyId)).catch((error) => setStatus(error.message));
});
el.groupList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-group-id]");
  if (item) {
    window.location.href = `/catalog-admin/groups/${item.dataset.groupId}`;
  }
});
el.profileList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-profile-id]");
  if (item) selectProfile(Number(item.dataset.profileId)).catch((error) => setStatus(error.message));
});
el.skillList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-skill-id]");
  if (item) selectSkillById(Number(item.dataset.skillId)).catch((error) => setStatus(error.message));
});
el.skillTree.addEventListener("click", (event) => {
  const item = event.target.closest("[data-edit-skill]");
  if (item) window.location.href = `/catalog-admin/skills/${item.dataset.editSkill}`;
});
el.reviewList.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-review-id]");
  if (!item) return;
  const card = item.closest("[data-review-card]");
  const note = card?.querySelector("[data-review-note]")?.value || "";
  await request(`/reference/reviews/${item.dataset.reviewId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: item.dataset.reviewStatus, note }),
  });
  await loadAll();
});
el.candidateList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-candidate-jump]");
  const card = item ? document.getElementById(`candidate-${item.dataset.candidateJump}`) : null;
  if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
});
el.candidateCards.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-candidate-action]");
  if (!form) return;
  event.preventDefault();
  const data = new FormData(form);
  const kind = form.dataset.candidateAction;
  const submitAction = event.submitter?.value || kind;
  const payload = {
    action: kind === "decision" ? submitAction : kind,
    competency_id: Number(data.get("competency_id")),
    resolution_note: String(data.get("resolution_note") || ""),
    new_title: String(data.get("new_title") || ""),
    target_competency_id: data.get("target_competency_id") ? Number(data.get("target_competency_id")) : null,
    competency_skill_id: data.get("competency_skill_id") ? Number(data.get("competency_skill_id")) : null,
  };
  await request("/reference/candidate-competencies/actions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadAll();
  showCandidateCompetenciesDetail();
  setStatus(`Candidate action: ${payload.action}`);
});
el.archiveList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-archive-jump]");
  const block = item ? document.getElementById(`archive${item.dataset.archiveJump[0].toUpperCase()}${item.dataset.archiveJump.slice(1)}Block`) : null;
  if (block) block.scrollIntoView({ behavior: "smooth", block: "start" });
});
el.archiveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  el.searchInput.value = el.archiveSearch.value.trim();
  await loadAll();
  showArchiveDetail();
});
el.archiveScope.addEventListener("change", () => loadAll().then(showArchiveDetail).catch((error) => setStatus(error.message)));
el.archiveForm.addEventListener("click", async (event) => {
  const reset = event.target.closest("[data-archive-reset]");
  if (!reset) return;
  el.archiveSearch.value = "";
  el.searchInput.value = "";
  el.archiveScope.value = "all";
  await loadAll();
  showArchiveDetail();
});
el.archiveSection.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-archive-restore]");
  if (!button) return;
  await request("/reference/archive/actions", {
    method: "POST",
    body: JSON.stringify({ kind: button.dataset.archiveRestore, id: Number(button.dataset.archiveId) }),
  });
  await loadAll();
  showArchiveDetail();
  setStatus("Запись восстановлена из архива");
});
el.templateList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-template-edit]");
  if (!item) return;
  const template = state.artifactTemplates.find((entry) => Number(entry.id) === Number(item.dataset.templateEdit));
  if (template) {
    fillArtifactTemplateForm(template);
    showArtifactTemplateDetail();
  }
});
el.artifactTemplateTable.addEventListener("click", async (event) => {
  const edit = event.target.closest("[data-template-edit]");
  if (edit) {
    const template = state.artifactTemplates.find((entry) => Number(entry.id) === Number(edit.dataset.templateEdit));
    if (template) {
      fillArtifactTemplateForm(template);
      showArtifactTemplateDetail();
    }
    return;
  }
  const statusButton = event.target.closest("[data-template-status]");
  if (!statusButton) return;
  await request(`/reference/artifact-templates/${statusButton.dataset.templateStatus}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status: statusButton.dataset.status }),
  });
  await loadAll();
  showArtifactTemplateDetail();
  setStatus("Статус шаблона обновлен");
});
el.artifactTemplateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = artifactTemplatePayload();
  if (!payload.title) {
    setStatus("Введите название шаблона");
    return;
  }
  const saved = await request("/reference/artifact-templates", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadAll();
  fillArtifactTemplateForm(saved);
  showArtifactTemplateDetail();
  setStatus("Шаблон УП сохранен");
});
el.artifactTemplateNewButton.addEventListener("click", () => {
  fillArtifactTemplateForm(null);
  showArtifactTemplateDetail();
  setStatus("Новый шаблон УП");
});
el.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.current) return;
  state.current = await request(`/reference/competencies/${state.current.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      title: el.title.value.trim(),
      description: el.description.value.trim(),
      status: el.status.value,
    }),
  });
  await loadAll();
  await selectCompetency(state.current.id);
  setStatus("Компетенция сохранена");
});
el.skillForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    canonical_name: el.skillName.value.trim(),
    skill_type: el.skillType.value.trim() || "unknown",
    status: el.skillStatus.value,
    aliases: splitAliases(el.skillAliases.value),
  };
  const path = state.selectedSkill?.skill_id ? `/reference/skills/${state.selectedSkill.skill_id}` : "/reference/skills";
  const method = state.selectedSkill?.skill_id ? "PATCH" : "POST";
  const saved = await request(path, { method, body: JSON.stringify(payload) });
  await loadAll();
  if (saved?.skill_id) {
    await selectSkillById(saved.skill_id);
  } else {
    fillSkillForm(saved);
    showDetailSection("skill");
  }
  setStatus("Skill сохранен");
});
el.groupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.current?.id) return;
  state.current = await request(`/reference/groups/${state.current.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      title: el.groupTitle.value.trim(),
      description: el.groupDescription.value.trim(),
      status: el.groupStatus.value,
    }),
  });
  await loadAll();
  await selectGroup(state.current.id);
  setStatus("Группа сохранена");
});
el.groupSkillCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.current?.id) return;
  const name = el.groupSkillName.value.trim();
  if (!name) {
    setStatus("Введите название skill");
    return;
  }
  const created = await request(`/reference/groups/${state.current.id}/skills`, {
    method: "POST",
    body: JSON.stringify({
      canonical_name: name,
      skill_type: el.groupSkillType.value.trim() || "unknown",
      aliases: splitAliases(el.groupSkillAliases.value),
    }),
  });
  window.location.href = `/catalog-admin/skills/${created.skill_id}`;
});
el.groupCreateForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = el.groupCreateTitle.value.trim();
  if (!title) {
    setStatus("Введите название группы");
    return;
  }
  try {
    const created = await request("/reference/groups", {
      method: "POST",
      body: JSON.stringify({
        title,
        description: el.groupCreateDescription.value.trim(),
      }),
    });
    el.groupCreateTitle.value = "";
    el.groupCreateDescription.value = "";
    setStatus(`Группа «${created.title}» создана`);
    await loadAll();
  } catch (error) {
    setStatus(error.message || "Не удалось создать группу");
  }
});
el.indicatorCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedSkill?.skill_id) return;
  const text = el.indicatorText.value.trim();
  if (!text) {
    setStatus("Введите текст индикатора");
    return;
  }
  await request(`/reference/skills/${state.selectedSkill.skill_id}/indicators`, {
    method: "POST",
    body: JSON.stringify({
      text,
      dimension_code: el.indicatorDimension.value,
      notes: el.indicatorNotes.value.trim() || "reference-ui",
    }),
  });
  el.indicatorText.value = "";
  await selectSkillById(state.selectedSkill.skill_id);
  setStatus("Индикатор добавлен");
});
el.skillIndicators.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-indicator-form]");
  if (!form) return;
  event.preventDefault();
  const indicatorId = Number(form.dataset.indicatorForm);
  await request(`/reference/indicators/${indicatorId}`, {
    method: "PATCH",
    body: JSON.stringify({
      text: form.querySelector("[data-indicator-text]").value.trim(),
      dimension_code: form.querySelector("[data-indicator-dimension]").value,
      notes: form.querySelector("[data-indicator-notes]").value.trim(),
    }),
  });
  await selectSkillById(state.selectedSkill.skill_id);
  setStatus("Индикатор сохранен");
});
el.skillIndicators.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-delete-indicator]");
  if (!item) return;
  await request(`/reference/indicators/${item.dataset.deleteIndicator}`, { method: "DELETE" });
  await selectSkillById(state.selectedSkill.skill_id);
  setStatus("Индикатор удален");
});
el.newSkillButton.addEventListener("click", () => {
  state.selectedSkill = null;
  fillSkillForm(null);
  showDetailSection("skill");
  setStatus("Новый skill");
});
el.briefText.addEventListener("input", updateBriefSubmitState);
el.briefFileInput.addEventListener("change", () => {
  const file = el.briefFileInput.files?.[0];
  el.pickerStatus.textContent = file ? `Выбран файл: ${file.name}` : "Файл пока не выбран.";
  updateBriefSubmitState();
  setStatus(file ? "Документ выбран; можно запустить обработку" : "Файл не выбран");
});
el.intakeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = el.briefFileInput.files?.[0];
  const text = el.briefText.value.trim();
  const briefText = text || (file ? await file.text() : "");
  if (!briefText.trim()) {
    setStatus("Добавьте текст брифа или выберите текстовый файл");
    return;
  }
  el.jobProgress.textContent = "Запускаем intake pipeline...";
  setStatus("Intake pipeline запущен");
  const job = await request("/intake/jobs", {
    method: "POST",
    body: JSON.stringify({
      brief_text: briefText,
      source_kind: file ? "file" : "text",
      source_name: file?.name || null,
      use_council: true,
      use_llm: false,
    }),
  });
  window.location.href = `/intake/jobs/${job.id}`;
});
el.jobNextStepActions.addEventListener("click", (event) => {
  const start = event.target.closest("[data-intake-start]");
  if (!start) return;
  event.preventDefault();
  el.briefText.focus();
  setStatus("Сначала добавьте текст брифа или выберите документ");
});

setListMode(state.mode);
loadAll().catch((error) => setStatus(error.message));

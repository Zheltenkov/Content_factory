Extract a curriculum competency portrait from the brief.

Return only JSON matching the requested schema:
- `spec`: role, seniority, domain, artifact_type, must_include_areas, sub_queries.
- `evidence_sources`: evidence items with `evidence_id`, `claim`, `source_type`, `snippet`.
- `competencies`: core competency objects with `competency_id`, `canonical_name`, `group`, `coverage_area`,
  `indicators`, `tools`, `confidence`, `atomicity`, `resolution`, `status`.
- `coverage_audit`: compact coverage notes.

Use Russian names and observable learner competencies, not staffing, budget, or program administration.

Brief:
{{ brief }}

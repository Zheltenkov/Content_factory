"""core/methodology/harness.py — рантайм слоя правил (SKILLS_ARCHITECTURE.md §5.2, §6).

Грузит skill-папки, резолвит профиль (base + disables/overrides/adds + dotted-params + program_type),
фильтрует по applies_to.artifact_family, индексирует по (hook, stage) и файрит хуки.

Контракт кода скилла (модуль check.py, всё опционально):
  check(doc, params)  -> list[RuleIssue]   # для post.validate
  prepare(ctx, params)-> dict              # для pre.stage (возвращает обновления контекста)
prompt.augment кода не требует — берёт instructions.md, рендерит {{param}} из params.
"""
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.methodology.rules import GeneratedDoc, RuleIssue

# content_model -> artifact_family (для фильтра applies_to)
FAMILY = {
    "readme_linear": "readme", "readme_cyclic": "readme",
    "lesson_course": "lesson", "lesson_single": "lesson",
    "teacher_guide_kids": "guide", "slides_lesson": "slides",
}


@dataclass
class Skill:
    id: str
    folder: Path
    hooks: list[dict] = field(default_factory=list)
    severity: str = "hard"
    params: dict = field(default_factory=dict)
    applies_to: dict = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    instructions: str | None = None
    check: object | None = None
    prepare: object | None = None


@dataclass
class ResolvedProfile:
    id: str
    skills: dict
    content_model: str | None
    artifact_target: str | None
    artifact_family: str | None
    terminology: dict
    program_type: str | None


def _load_code(folder: Path, attr: str):
    f = folder / "check.py"
    if not f.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"skill_{folder.name}_{id(folder)}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, attr, None)


def load_skill(folder: Path) -> Skill:
    y = yaml.safe_load((folder / "skill.yaml").read_text(encoding="utf-8"))
    instr = None
    ip = folder / (y.get("instructions") or "instructions.md")
    if y.get("instructions") and ip.exists():
        instr = ip.read_text(encoding="utf-8")
    return Skill(
        id=y["id"], folder=folder, hooks=y.get("hooks", []) or [],
        severity=y.get("severity", "hard"), params=dict(y.get("params", {}) or {}),
        applies_to=y.get("applies_to", {}) or {},
        requires=y.get("requires", []) or [], produces=y.get("produces", []) or [],
        instructions=instr,
        check=_load_code(folder, "check"), prepare=_load_code(folder, "prepare"),
    )


def _chain(profile_id: str, root: Path) -> list[dict]:
    out, pid = [], profile_id
    while pid:
        out.append(yaml.safe_load((root / pid / "profile.yaml").read_text(encoding="utf-8")))
        pid = out[-1].get("extends")
    return out  # [most-derived ... base]


def resolve_profile(profile_id: str, root: Path, program_type: str | None = None,
                    artifact_target: str | None = None) -> ResolvedProfile:
    chain = _chain(profile_id, root)
    base_first = list(reversed(chain))                       # [_base ... derived]

    skills: dict = {}
    terminology: dict = {}
    dotted: dict = {}                                        # "skill.key" -> value (base -> derived)

    for prof in base_first:
        pdir = root / prof["id"]
        if prof is base_first[0]:                            # базовые скиллы — из самого базового профиля
            for sk in sorted((pdir / "skills").iterdir()):
                if sk.is_dir():
                    skills[sk.name] = load_skill(sk)
        for d in prof.get("disables", []):
            skills.pop(d, None)
        for o in prof.get("overrides", []):
            skills[o] = load_skill(pdir / "skills" / o)
        for a in prof.get("adds", []):
            skills[a] = load_skill(pdir / "skills" / a)
        terminology.update(prof.get("terminology", {}))
        dotted.update(prof.get("params", {}))

    # program_type: выбирает content_model + artifact_target + params (побеждают последними)
    content_model, pts = None, {}
    for prof in chain:
        if prof.get("program_types"):
            pts = prof["program_types"]; break
    pt = program_type
    if pts:
        pt = pt or next(iter(pts))
        sel = pts[pt]
        content_model = sel.get("content_model")
        artifact_target = artifact_target or sel.get("artifact_target")
        dotted.update(sel.get("params", {}))
    if content_model is None:                                # профиль без program_types (commerce/_base)
        for prof in chain:
            if prof.get("content_model"):
                content_model = prof["content_model"]; break

    # 1) активный content_model как ДЕФОЛТ в скиллы, что его декларируют
    for s in skills.values():
        if "content_model" in s.params and content_model:
            s.params["content_model"] = content_model
    # 2) затем dotted-оверрайды (явное побеждает дефолт; напр. commerce -> readme_cyclic)
    for key, val in dotted.items():
        if "." in key:
            sid, pkey = key.split(".", 1)
            if sid in skills:
                skills[sid].params[pkey] = val

    family = FAMILY.get(content_model)
    if family:                                               # фильтр applies_to.artifact_family
        skills = {k: s for k, s in skills.items()
                  if not s.applies_to.get("artifact_family") or family in s.applies_to["artifact_family"]}

    return ResolvedProfile(profile_id, skills, content_model, artifact_target, family, terminology, pt)


def _render(text: str, params: dict) -> str:
    def sub(m):
        v = params.get(m.group(1).strip())
        return str(v) if v is not None else m.group(0)
    return re.sub(r"\{\{([^}]+)\}\}", sub, text)


class Harness:
    """Привязывает скиллы по (hook, stage) и файрит их. Тонкий слой над engine.py."""

    def __init__(self, profile: ResolvedProfile):
        self.profile = profile
        self.bind: dict = {}
        for s in profile.skills.values():
            for h in s.hooks:  # h = {at, stages}
                for stage in h.get("stages", []):
                    self.bind.setdefault((h["at"], stage), []).append(s)

    def augment(self, stage: str, ctx: dict | None = None) -> str:
        return "\n\n".join(_render(s.instructions, s.params)
                           for s in self.bind.get(("prompt.augment", stage), []) if s.instructions)

    def prepare(self, stage: str, ctx: dict) -> dict:
        for s in self.bind.get(("pre.stage", stage), []):
            if s.prepare:
                ctx = {**ctx, **(s.prepare(ctx, s.params) or {})}
        return ctx

    def validate(self, stage: str, doc: GeneratedDoc, ctx: dict | None = None) -> list[RuleIssue]:
        out: list[RuleIssue] = []
        for s in self.bind.get(("post.validate", stage), []):
            if s.check:
                out.extend(s.check(doc, s.params))
        return out

    def producers_bound_to(self, stage_prefix: str) -> list[str]:
        """CI-инвариант: producer-скиллы (с produces), ошибочно привязанные к stage_prefix.*"""
        bad = set()
        for (_hook, stage), sks in self.bind.items():
            if stage.startswith(stage_prefix):
                bad |= {s.id for s in sks if s.produces}
        return sorted(bad)

#!/usr/bin/env python3
"""Create an evidence-grounded cover-letter draft and fit report.

The generator is intentionally deterministic. It selects only statements from
the reviewed evidence profile and never invents metrics, employers, tools, or
company facts. The result is a draft for human review, not an application-ready
truth claim by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from private_paths import (
    CURRENT_RESUME_TEX,
    CV_BOT_OUTPUT,
    CV_VARIANTS_DIR,
    EVIDENCE_PROFILE,
    JOB_DATABASE,
)
from cv.application_keywords import select_keywords, render_keyword_notes


DEFAULT_PROFILE = EVIDENCE_PROFILE
DEFAULT_OUT_DIR = CV_BOT_OUTPUT
DEFAULT_DATABASE = JOB_DATABASE
DEFAULT_RESUME = CURRENT_RESUME_TEX
DEFAULT_BUNDLE_DIR = CV_VARIANTS_DIR
FULL_TIME_GRADUATION_DATE = "Jun 2027 (Expected)"


@dataclass(frozen=True)
class EvidenceMatch:
    name: str
    evidence: str
    matched_keywords: tuple[str, ...]

    @property
    def score(self) -> int:
        return len(self.matched_keywords)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def keyword_present(keyword: str, text: str) -> bool:
    keyword = normalize(keyword)
    if re.fullmatch(r"[a-z0-9+#.-]+", keyword):
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
    return keyword in text


def select_evidence(profile: dict[str, Any], job_description: str) -> list[EvidenceMatch]:
    normalized_jd = normalize(job_description)
    matches: list[EvidenceMatch] = []
    for group in profile.get("evidence_groups", []):
        keywords = tuple(
            keyword
            for keyword in group.get("keywords", [])
            if keyword_present(str(keyword), normalized_jd)
        )
        matches.append(
            EvidenceMatch(
                name=str(group["name"]),
                evidence=str(group["evidence"]),
                matched_keywords=keywords,
            )
        )
    return sorted(matches, key=lambda item: (-item.score, item.name.casefold()))


def render_report(
    profile: dict[str, Any],
    company: str,
    role: str,
    job_description: str,
    matches: list[EvidenceMatch],
    resume_version: str,
    keyword_selection: dict | None = None,
) -> str:
    identity = profile.get("identity", {})
    display_name = str(identity.get("display_name") or "Candidate").strip()
    selected = select_letter_evidence(matches)

    evidence_paragraphs = "\n\n".join(match.evidence for match in selected)
    match_lines = []
    for match in matches:
        terms = ", ".join(match.matched_keywords) if match.matched_keywords else "none"
        match_lines.append(f"- {match.name}: {match.score} matched terms ({terms})")

    low_confidence = not any(match.score >= 2 for match in selected)
    confidence_note = (
        "Low: the job description has little direct overlap with the reviewed evidence. "
        "Do not strengthen the draft without adding verified evidence."
        if low_confidence
        else "Review required: confirm every selected statement and adapt tone before use."
    )

    keyword_notes = render_keyword_notes(keyword_selection) if keyword_selection else ""
    return f"""# Cover letter review packet

Company: {company}
Role: {role}
Resume version: {resume_version}
Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}

## Fit snapshot

{chr(10).join(match_lines)}

Confidence: {confidence_note}

## Draft

Dear Hiring Team,

I am writing to apply for the {role} position at {company}. {profile['candidate_summary']} I am particularly interested in applying this cross-layer background to practical semiconductor and hardware-design work.

{evidence_paragraphs}

{profile['closing_strength']} I would welcome the opportunity to discuss how this background could contribute to the team at {company}.

Sincerely,  
{display_name}

## Mandatory human review

- Confirm that the company and role names match the posting.
- Remove any evidence that is not relevant to the specific team.
- Do not add an unverified metric, responsibility, tool, authorization, or company fact.
- Check work authorization and sponsorship questions separately; this draft does not answer them.
- Review the final PDF and application fields before any submission.

## Job description record

{job_description.strip()}

{keyword_notes}
"""


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug[:60] or "draft"


def select_letter_evidence(matches: list[EvidenceMatch]) -> list[EvidenceMatch]:
    selected = [match for match in matches if match.score >= 2][:3]
    if len(selected) < 2:
        selected_names = {match.name for match in selected}
        selected.extend(
            match
            for match in matches
            if match.score > 0 and match.name not in selected_names
        )
        selected = selected[:2]
    return selected or matches[:2]


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def ascii_company_label(company: str) -> str:
    aliases = {
        "北京地平线信息技术有限公司": "Horizon Robotics",
        "紫光展锐": "UNISOC",
        "芯原": "VeriSilicon",
    }
    if company in aliases:
        return aliases[company]
    ascii_value = company.encode("ascii", "ignore").decode().strip()
    return ascii_value or "the hiring company"


def ascii_role_label(role: str, matches: list[EvidenceMatch]) -> str:
    if role.isascii():
        return role
    internship = " Intern" if any(token in role for token in ("实习", "實習")) else ""
    ordered_rules = (
        (("DFT",), "DFT Engineer"),
        (("后端", "後端", "物理设计", "物理設計"), "Physical Design Engineer"),
        (("模拟", "模擬", "混合信号", "混合訊號"), "Analog/Mixed-Signal IC Design Engineer"),
        (("EDA", "CAD"), "EDA/CAD Engineer"),
        (("架构", "架構", "体系结构", "體系結構"), "Chip Architecture Engineer"),
        (("处理器建模", "處理器建模", "性能分析"), "Processor Modeling and Performance Engineer"),
        (("验证", "驗證"), "Digital IC Verification Engineer"),
        (("数字", "數字", "芯片设计", "晶片設計", "SoC", "SOC"), "Digital IC/RTL Design Engineer"),
    )
    for terms, label in ordered_rules:
        if any(term in role for term in terms):
            return label + internship
    primary = matches[0].name if matches else "Hardware Engineering"
    fallback = {
        "CPU and computer architecture": "CPU/Computer Architecture Engineer",
        "Digital RTL design": "Digital IC/RTL Design Engineer",
        "Design verification": "Digital IC Verification Engineer",
        "EDA and logic synthesis": "EDA/Logic Synthesis Engineer",
        "Memory architecture": "Memory Architecture Engineer",
        "Analog and mixed-signal design": "Analog/Mixed-Signal IC Engineer",
    }.get(primary, "Hardware Engineering Role")
    return fallback + internship


def tailored_summary(
    profile: dict[str, Any], role: str, matches: list[EvidenceMatch]
) -> str:
    primary = matches[0].name if matches else "Digital RTL and CPU architecture"
    summaries = profile.get("tailored_summaries", {})
    summary = summaries.get(primary) or summaries.get("default")
    if not summary:
        raise RuntimeError(
            f"Private evidence profile lacks a tailored summary for {primary!r}"
        )
    return str(summary)


def set_graduation_date(
    source_text: str,
    graduation_date: str | None,
    graduation_school: str,
) -> str:
    """Override one explicitly configured school's expected graduation date."""
    if not graduation_date:
        return source_text
    if not graduation_school:
        raise RuntimeError("Private evidence profile lacks graduation_school")
    pattern = re.compile(
        rf"(\{{\\bf {re.escape(graduation_school)}\}}\s*\\hfill\s*"
        r"\{\\em\s+[^{}\n]*?--\s*)[^{}\n]+(\})"
    )
    replaced, count = pattern.subn(
        lambda match: f"{match.group(1)}{graduation_date}{match.group(2)}",
        source_text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not locate the configured graduation date in the resume")
    return replaced


def render_tailored_resume(
    profile: dict[str, Any],
    source_text: str,
    role: str,
    matches: list[EvidenceMatch],
    graduation_date: str | None = None,
    keyword_selection: dict | None = None,
) -> str:
    graduation_date = graduation_date or profile.get("expected_graduation_date")
    source_text = set_graduation_date(
        source_text,
        graduation_date,
        str(profile.get("graduation_school") or ""),
    )
    summary = tailored_summary(profile, role, matches)
    pattern = re.compile(
        r"(\\begin\{rSection\}\{Summary\}\s*).*?(\s*\\end\{rSection\})",
        re.S,
    )
    replaced, count = pattern.subn(rf"\1{summary}\2", source_text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate exactly one Summary section in the resume")
    if keyword_selection and keyword_selection.get("technical"):
        labels = [latex_escape(x.get("resume_label", x["english"]))
                  for x in keyword_selection["technical"]]
        skills = re.compile(
            r"(\\begin\{rSection\}\{Technical Skills\}\s*).*?(\s*\\end\{rSection\})",
            re.S,
        )
        replaced, count = skills.subn(
            lambda m: m.group(1) + "; ".join(labels) + ".\n" + m.group(2),
            replaced, count=1,
        )
        if count != 1:
            raise RuntimeError("Could not locate Technical Skills section for keyword tailoring")
    return "% Generated job-specific variant; review before use.\n" + replaced


def render_cover_letter_tex(
    profile: dict[str, Any],
    company: str,
    role: str,
    matches: list[EvidenceMatch],
) -> str:
    identity = profile.get("identity", {})
    display_name = latex_escape(str(identity.get("display_name") or "Candidate"))
    headline_name = latex_escape(str(identity.get("headline_name") or display_name))
    email_address = latex_escape(str(identity.get("email") or ""))
    selected = select_letter_evidence(matches)
    paragraphs = "\n\n".join(latex_escape(match.evidence) for match in selected)
    display_role = ascii_role_label(role, matches)
    display_company = ascii_company_label(company)
    return rf"""\documentclass[11pt]{{article}}
\usepackage[margin=0.8in]{{geometry}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.9em}}
\pagestyle{{empty}}
\begin{{document}}
\textbf{{{headline_name}}}\\
\texttt{{{email_address}}}

\today

Dear Hiring Team,

I am writing to apply for the {latex_escape(display_role)} position at {latex_escape(display_company)}. {latex_escape(profile['candidate_summary'])} I am particularly interested in applying this cross-layer background to practical semiconductor and hardware-design work.

{paragraphs}

{latex_escape(profile['closing_strength'])} I would welcome the opportunity to discuss how this background could contribute to the team at {latex_escape(display_company)}.

Sincerely,\\
{display_name}
\end{{document}}
"""


def compile_latex(tex_path: Path, build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    tex_bin = ROOT / ".TinyTeX" / "bin" / "x86_64-linux" / "latexmk"
    command = [
        str(tex_bin if tex_bin.is_file() else "latexmk"),
        "-g",
        "-pdf",
        "-bibtex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-outdir={build_dir}",
        str(tex_path),
    ]
    environment = os.environ.copy()
    if tex_bin.is_file():
        environment["PATH"] = f"{tex_bin.parent}:{environment.get('PATH', '')}"
    latex_inputs = (ROOT / "cv" / "latex", tex_path.parent.resolve())
    environment["TEXINPUTS"] = ":".join(
        [*(str(path) for path in latex_inputs), environment.get("TEXINPUTS", "")]
    )
    environment["BIBINPUTS"] = ":".join(
        [str(tex_path.parent.resolve()), environment.get("BIBINPUTS", "")]
    )
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        tail = "\n".join(completed.stdout.splitlines()[-40:])
        raise RuntimeError(f"LaTeX build failed for {tex_path}:\n{tail}")
    pdf_path = build_dir / f"{tex_path.stem}.pdf"
    if not pdf_path.is_file():
        raise RuntimeError(f"Expected PDF was not generated: {pdf_path}")
    return pdf_path


def write_bundle(
    profile: dict[str, Any],
    company: str,
    role: str,
    job_description: str,
    matches: list[EvidenceMatch],
    review_packet: str,
    source_resume: Path,
    bundle_root: Path,
    bundle_name: str | None = None,
    graduation_date: str | None = None,
    role_kind: str | None = None,
    keyword_selection: dict | None = None,
) -> Path:
    graduation_date = graduation_date or profile.get("expected_graduation_date")
    if keyword_selection is None:
        keyword_selection = select_keywords(role, job_description)
    bundle_path = bundle_root / (
        bundle_name or f"{safe_slug(company)}_{safe_slug(role)}"
    )
    bundle_path.mkdir(parents=True, exist_ok=True)
    # Keep relative bibliography references usable in the isolated bundle.
    for bibliography in source_resume.parent.glob("*.bib"):
        destination = bundle_path / bibliography.name
        if bibliography.resolve() != destination.resolve():
            shutil.copy2(bibliography, destination)
    resume_tex = bundle_path / "resume.tex"
    cover_tex = bundle_path / "cover_letter.tex"
    review_path = bundle_path / "review_packet.md"
    resume_tex.write_text(
        render_tailored_resume(
            profile,
            source_resume.read_text(encoding="utf-8"),
            role,
            matches,
            graduation_date=graduation_date,
            keyword_selection=keyword_selection,
        ),
        encoding="utf-8",
    )
    cover_tex.write_text(
        render_cover_letter_tex(profile, company, role, matches),
        encoding="utf-8",
    )
    if "## Application keywords" not in review_packet:
        review_packet += "\n" + render_keyword_notes(keyword_selection)
    review_path.write_text(review_packet, encoding="utf-8")
    keyword_path = bundle_path / "application_keywords.json"
    keyword_path.write_text(json.dumps(keyword_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    keyword_path.chmod(0o600)
    build_path = bundle_path / "build"
    resume_pdf = compile_latex(resume_tex, build_path)
    cover_pdf = compile_latex(cover_tex, build_path)
    # Compilation is not visual approval. Keep the page budget and review status
    # visible to both the resume bot and the application preparation workflow.
    log_path = build_path / "resume.log"
    build_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    page_match = re.search(r"Output written on .*?\((\d+) pages?[,)]", build_log, re.S)
    page_count = int(page_match.group(1)) if page_match else None
    manifest = {
        "company": company,
        "role": role,
        "resume_tex": str(resume_tex),
        "resume_pdf": str(resume_pdf),
        "cover_letter_tex": str(cover_tex),
        "cover_letter_pdf": str(cover_pdf),
        "review_packet": str(review_path),
        "role_kind": role_kind,
        "graduation_date": graduation_date,
        "human_review_required": True,
        "layout_review": {
            "recommended_max_pages": 2,
            "page_count": page_count,
            "within_page_budget": page_count <= 2 if page_count is not None else None,
            "rendered_pdf_review": "pending",
            "instruction": "Inspect every rendered page before upload; trim content and repair pagination if over two pages.",
        },
        "application_keywords": str(keyword_path),
    }
    (bundle_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle_path


def load_stored_job(database: Path, url: str) -> tuple[str, str, str]:
    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            "SELECT company, title, description, location FROM jobs WHERE url = ?",
            (url,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise SystemExit(f"Job URL is not stored in {database}: {url}")
    company, title, description, location = (str(value or "").strip() for value in row)
    job_text = "\n".join(value for value in (title, location, description) if value)
    return company, title, job_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a truthful, evidence-grounded cover-letter review packet"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--job-description", help="Path to a UTF-8 job description")
    input_group.add_argument("--job-url", help="Load a job already stored in the local database")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--company", help="Required with --job-description; optional override with --job-url")
    parser.add_argument("--role", help="Required with --job-description; optional override with --job-url")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--keyword-library", type=Path, help="Override the private application keyword library")
    parser.add_argument("--resume-version", default="current.tex")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--generate-bundle", action="store_true")
    parser.add_argument("--resume-source", default=str(DEFAULT_RESUME))
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR))
    parser.add_argument(
        "--role-kind",
        choices=("internship", "full_time"),
        help="Use the full-time graduation-date override for full_time bundles",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    profile_path = Path(args.profile)
    if args.job_url:
        stored_company, stored_role, job_description = load_stored_job(
            Path(args.database), args.job_url
        )
        company = args.company or stored_company
        role = args.role or stored_role
    else:
        if not args.company or not args.role:
            raise SystemExit("--company and --role are required with --job-description")
        job_description = Path(args.job_description).read_text(encoding="utf-8")
        company = args.company
        role = args.role
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    matches = select_evidence(profile, job_description)
    keywords = select_keywords(role, job_description, library_path=args.keyword_library)
    report = render_report(
        profile,
        company,
        role,
        job_description,
        matches,
        args.resume_version,
        keyword_selection=keywords,
    )
    if args.generate_bundle:
        bundle = write_bundle(
            profile,
            company,
            role,
            job_description,
            matches,
            report,
            Path(args.resume_source),
            Path(args.bundle_dir),
            graduation_date=(
                FULL_TIME_GRADUATION_DATE if args.role_kind == "full_time" else None
            ),
            role_kind=args.role_kind,
            keyword_selection=keywords,
        )
        print(bundle)
        return
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_slug(company)}_{safe_slug(role)}.md"
    output_path = out_dir / filename
    output_path.write_text(report, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()

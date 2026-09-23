#!/usr/bin/env python3
"""Render the active Foundation scoring policy and current top matches."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CONFIG = ROOT / "job_bot" / "config.china_hk_ic_foreign.json"
from private_paths import JOBBOT_OUTPUT  # noqa: E402
from job_bot.bot import db_path, load_config  # noqa: E402

DEFAULT_OUT = JOBBOT_OUTPUT


def score_band(score: int | None, bands: dict | None = None) -> str:
    score = score or 0
    bands = bands or {}
    if score >= int(bands.get("high", 75)):
        return "high"
    if score >= int(bands.get("relevant", 60)):
        return "relevant"
    if score >= int(bands.get("adjacent", 45)):
        return "adjacent"
    return "low"


def render(config: dict, rows: list[sqlite3.Row], generated_at: str) -> str:
    scoring = config["scoring"]
    bands = scoring.get("bands", {})
    lines = [
        "# Foundation scoring report",
        "",
        f"Generated: {generated_at}",
        "",
        "A Foundation defines what the role fundamentally is. A role must match "
        "at least one Foundation before resume evidence or preference modifiers "
        "can raise its score.",
        "",
        "## Decision bands",
        "",
        f"- **{bands.get('high', 75)}–100 — high:** draft/application queue candidate after early-career checks.",
        f"- **{bands.get('relevant', 60)}–{int(bands.get('high', 75)) - 1} — relevant:** strong adjacent role; review manually.",
        f"- **{bands.get('adjacent', 45)}–{int(bands.get('relevant', 60)) - 1} — adjacent:** keep in the digest, below automatic drafting threshold.",
        f"- **0–{int(bands.get('adjacent', 45)) - 1} — low:** suppress from the focused application queue.",
        "",
        "## Foundations",
        "",
        "| Foundation | Base | Body-only adjustment | Minimum body hits |",
        "|---|---:|---:|---:|",
    ]
    for group in scoring["foundation_groups"]:
        lines.append(
            f"| {group['name']} | {group['base_score']} | "
            f"{group.get('body_only_adjustment', 0):+d} | "
            f"{group.get('min_body_hits', 1)} |"
        )
    lines.extend(["", "## Foundation keywords", ""])
    for group in scoring["foundation_groups"]:
        lines.extend(
            [
                f"### {group['name']}",
                "",
                ", ".join(f"`{item}`" for item in group["keywords"]),
                "",
            ]
        )
    lines.extend(
        [
            "## Modifiers",
            "",
            "| Modifier | Points | Scope | Keywords |",
            "|---|---:|---|---|",
        ]
    )
    for modifier in scoring["modifiers"]:
        keywords = ", ".join(f"`{item}`" for item in modifier["keywords"])
        lines.append(
            f"| {modifier['name']} | {modifier['points']:+d} | "
            f"{modifier.get('scope', 'all')} | {keywords} |"
        )
    lines.extend(
        [
            "",
            "## Current top active matches",
            "",
            "| Score | Band | Kind | Company | Role | Location | Foundation/reason |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        title = (row["title"] or "").replace("|", "/")
        company = (row["company"] or "").replace("|", "/")
        location = (row["location"] or "").replace("|", "/")
        reason = (row["score_reason"] or "").replace("|", "/")
        score = row["fit_score"] or 0
        lines.append(
            f"| {score} | {score_band(score, bands)} | {row['role_kind'] or 'unknown'} | "
            f"{company} | {title} | {location} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Preference encoded for this resume",
            "",
            "Digital RTL design and CPU/computer architecture start at the highest "
            "bases. Verification and EDA remain viable adjacent paths. Physical "
            "design/DFT and analog/mixed-signal remain searchable but do not outrank "
            "direct digital-design or architecture matches without exceptional evidence. "
            "Senior, non-design, and software-first titles receive explicit penalties.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    conn = sqlite3.connect(db_path(config))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT company, title, location, role_kind, fit_score, score_reason
        FROM jobs
        WHERE is_active = 1 AND fit_score IS NOT NULL
        ORDER BY fit_score DESC, company, title
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"foundation_scoring_{datetime.now():%Y%m%d_%H%M%S}.md"
    output.write_text(render(config, rows, generated_at) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

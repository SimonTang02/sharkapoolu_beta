"""Shared, evidence-scoped keyword selection for CV and application preparation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from private_paths import APPLICATION_KEYWORDS


def _present(term: str, text: str) -> bool:
    term = re.sub(r"\s+", " ", term.casefold()).strip()
    text = re.sub(r"\s+", " ", text.casefold())
    if not term:
        return False
    if term.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


def select_keywords(role: str, job_description: str = "", *,
                    library_path: Path | None = None, preset: str | None = None) -> dict:
    """Read current private data on every call; never promote JD terms into skills."""
    path = Path(library_path) if library_path is not None else APPLICATION_KEYWORDS
    result = {"available": False, "library_path": str(path), "preset": None,
              "technical": [], "collaboration": [], "usage_rules": []}
    if not path.is_file():
        return {**result, "reason": "keyword_library_missing"}
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported application keyword library schema")
    entries = data["technical_keywords"] + data["collaboration_personality_keywords"]
    ids = [x["id"] for x in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate application keyword IDs")
    for entry in entries:
        if not all(entry.get(k) for k in ("english", "chinese", "evidence", "example_en", "source_ids", "claim_status")):
            raise ValueError(f"Keyword lacks evidence or required fields: {entry['id']}")
        if any(s not in data["sources"] for s in entry["source_ids"]):
            raise ValueError(f"Unknown evidence source: {entry['id']}")
    presets = {x["id"]: x for x in data["role_presets"]}
    technical_ids = {x['id'] for x in data['technical_keywords']}
    soft_ids = {x['id'] for x in data['collaboration_personality_keywords']}
    for item in presets.values():
        if not set(item['technical_ids']) <= technical_ids or not set(item['collaboration_ids']) <= soft_ids:
            raise ValueError(f"Invalid keyword preset references: {item['id']}")
    if preset is not None:
        if preset not in presets:
            raise ValueError(f"Unknown keyword preset: {preset}")
        chosen = presets[preset]
    else:
        # Prefer the title; generic requirements in a long JD must not override it.
        chosen = None
        for text in (role, job_description):
            hits = [(sum(_present(t, text) for t in x.get('role_match_terms', [])), x)
                    for x in presets.values()]
            hits = [(score, x) for score, x in hits if score]
            if hits:
                chosen = max(hits, key=lambda pair: pair[0])[1]
                break
    text = role + "\n" + job_description
    def choose(key: str, preset_key: str, allowed: set[str], limit: int) -> list[dict]:
        candidates = [x for x in data[key] if x['claim_status'] in allowed]
        by_id = {x['id']: x for x in candidates}
        preferred = chosen[preset_key] if chosen else []
        # A role preset defines relevance. Explicit JD matches rank its entries.
        order = {value: i for i, value in enumerate(preferred)}
        scored = []
        for entry in candidates:
            terms = [entry['english'], entry['chinese'], *entry.get('match_terms', [])]
            matched = list(dict.fromkeys(t for t in terms if _present(t, text)))
            if entry['id'] in preferred or (not chosen and matched):
                scored.append((entry, matched))
        scored.sort(key=lambda pair: (-len(pair[1]), order.get(pair[0]['id'], len(order))))
        return [{**copy.deepcopy(by_id[e['id']]), 'matched_terms': terms,
                 'selection_reason': 'role_preset' if e['id'] in preferred else 'literal_job_match'}
                for e, terms in scored[:limit]]
    return {**result, 'available': True, 'library_sha256': hashlib.sha256(raw).hexdigest(),
            'library_updated_at': data.get('updated_at'),
            'preset': chosen['id'] if chosen else None,
            'sources': data['sources'], 'usage_rules': data['usage_rules'],
            'technical': choose('technical_keywords', 'technical_ids', {'supported_by_existing_records'}, 10),
            'collaboration': choose('collaboration_personality_keywords', 'collaboration_ids',
                                    {'documented_behavior', 'behavior_based_interpretation'}, 5)}


def apply_keyword_selection(profile: dict, selection: dict) -> dict:
    """Keep manual skills/answers; populate an empty skill list from supported terms."""
    profile = copy.deepcopy(profile)
    previous = profile.get('application_keywords', {})
    labels = [x['english'] for x in selection['technical']]
    old_generated = previous.get('generated_skills')
    if selection['available'] and (not profile.get('skills') or
                                  (old_generated is not None and profile.get('skills') == old_generated)):
        profile['skills'] = labels
        selection = {**selection, 'generated_skills': labels}
    profile['application_keywords'] = copy.deepcopy(selection)
    return profile


def render_keyword_notes(selection: dict) -> str:
    lines = ['## Application keywords', '']
    if not selection['available']:
        return '\n'.join(lines + ['Keyword library unavailable; existing materials left unchanged.', ''])
    lines += [f"Role preset: {selection['preset'] or 'literal matches only'}",
              f"Library SHA-256: {selection['library_sha256']}", '',
              'Technical labels are scoped to the evidence below. Collaboration examples are',
              'behavior-based suggestions, not confirmed personality self-ratings.', '']
    for label, key in [('Technical', 'technical'), ('Collaboration / work style', 'collaboration')]:
        lines += ['### ' + label, '']
        for entry in selection[key]:
            lines += [f"- **{entry['english']}** ({entry['chinese']}): {entry['example_en']}",
                      f"  Evidence / scope: {entry['evidence']}"]
        lines += ['']
    lines += ['### Usage rules', ''] + ['- ' + rule for rule in selection['usage_rules']] + ['']
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True)
    parser.add_argument('--job-description', type=Path)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--preset')
    args = parser.parse_args()
    jd = args.job_description.read_text(encoding='utf-8') if args.job_description else ''
    print(json.dumps(select_keywords(args.role, jd, library_path=args.library, preset=args.preset),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

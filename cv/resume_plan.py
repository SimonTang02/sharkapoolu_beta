"""Select reviewed, source-linked statements without inventing candidate prose."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def length_policy(application: dict, company: str, role: str = '') -> dict:
    """Resolve explicit private policy; do not infer employer culture from a name."""
    policy = application.get('career_preferences', {}).get('resume_language_policy', {})
    if not isinstance(policy, dict):
        raise ValueError('resume_language_policy must be an object')
    maximum = policy.get('max_pages_preferred', 2)
    preferred = policy.get('preferred_pages', maximum)
    if type(preferred) is not int or type(maximum) is not int or not 1 <= preferred <= maximum <= 2:
        raise ValueError('Resume page preferences must be integers between one and two')
    result = {'preferred_pages': preferred, 'max_pages': maximum,
              'word_budget': 700 if preferred == 2 else 350, 'company_guidance': None}
    guidance = policy.get('company_specific_length_guidance', {})
    if not isinstance(guidance, dict):
        raise ValueError('Company length guidance must be an object')
    for name, rule in guidance.items():
        if name.casefold() != company.strip().casefold():
            continue
        # Old URL-only notes are useful context, but cannot silently change length.
        if not isinstance(rule, dict) or 'preferred_pages' not in rule:
            continue
        parsed = urlsplit(str(rule.get('url', '')))
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username:
            raise ValueError('Company guidance needs an HTTPS source URL')
        if not rule.get('checked_on') or not rule.get('kind'):
            raise ValueError('Company guidance needs a check date and scope/kind')
        if rule.get('role') and rule['role'].casefold() != role.casefold():
            continue
        pages = rule['preferred_pages']
        if type(pages) is not int or not 1 <= pages <= maximum:
            raise ValueError('Company page preference exceeds candidate page limit')
        result.update(preferred_pages=pages, word_budget=700 if pages == 2 else 350,
                      company_guidance=rule)
    return result


def validate_content(content: dict, ledger: dict | None = None) -> None:
    """Validate references and state, not semantic truth of a human confirmation."""
    if not isinstance(content, dict) or content.get('version') != 1:
        raise ValueError('resume_content must be an object with version 1')
    projects = content.get('projects')
    if not isinstance(projects, list) or not projects:
        raise ValueError('resume_content.projects must be a nonempty list')
    ids, refs = set(), []
    for project in projects:
        if not isinstance(project, dict):
            raise ValueError('Each resume project must be an object')
        ident = project.get('id')
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError('Resume project IDs must be nonempty and unique')
        ids.add(ident)
        for key in ('title', 'dates'):
            if not isinstance(project.get(key), str) or not project[key].strip():
                raise ValueError('Project title and dates must be reviewed strings')
        if project.get('section', 'Projects') not in ('Projects', 'Research Experience'):
            raise ValueError('Unsupported managed resume section')
        terms = project.get('keywords', [])
        if not isinstance(terms, list) or not all(isinstance(x, str) and x.strip() for x in terms):
            raise ValueError('Project keywords must be nonempty strings')
        claims = project.get('fact_ids')
        if not isinstance(claims, list) or not claims or not all(isinstance(x, str) and x for x in claims):
            raise ValueError('Project fact_ids must be a nonempty string list')
        refs.extend(claims)
    for key in ('summary_fact_ids', 'skill_fact_ids'):
        values = content.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(x, str) and x for x in values):
            raise ValueError('Summary and skills require nonempty fact ID lists')
        refs.extend(values)
    if ledger is None:
        return
    sources = ledger.get('source_documents', [])
    facts = ledger.get('facts', [])
    if not isinstance(sources, list) or not isinstance(facts, list):
        raise ValueError('Fact ledger sources and facts must be lists')
    source_ids = set()
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get('id'), str)
                or not source['id'] or source['id'] in source_ids
                or not re.fullmatch(r'[a-f0-9]{64}', str(source.get('sha256', '')))):
            raise ValueError('Ledger source IDs and SHA256 values must be valid and unique')
        source_ids.add(source['id'])
    by_id = {}
    for fact in facts:
        if not isinstance(fact, dict) or not isinstance(fact.get('id'), str) or not fact['id'] or fact['id'] in by_id:
            raise ValueError('Fact IDs must be nonempty and unique')
        by_id[fact['id']] = fact
    for ref in refs:
        fact = by_id.get(ref)
        if fact is None:
            raise ValueError('Resume references a missing fact')
        confirmation = fact.get('confirmation', {})
        if (fact.get('status') != 'user_confirmed' or fact.get('superseded_by')
                or fact.get('source_id') not in source_ids
                or not isinstance(fact.get('value'), str) or not fact['value'].strip()
                or not isinstance(confirmation, dict) or not confirmation.get('date')
                or not confirmation.get('source')):
            raise ValueError('Resume statements must reference current, user-confirmed textual facts')


def plan_resume(profile: dict, ledger: dict, role: str, jd: str, policy: dict) -> dict:
    content = profile['resume_content']
    validate_content(content, ledger)
    facts = {f['id']: f for f in ledger['facts']}
    def statement(ref: str) -> dict:
        return {'fact_id': ref, 'text': facts[ref]['value'], 'fact_sha256': digest(facts[ref])}
    def hit(term: str, text: str) -> bool:
        # Bound Latin tokens: C must not match circuit, and RTL must not match portal.
        term = term.casefold()
        if re.fullmatch(r'[a-z0-9+#. -]+', term):
            return re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text.casefold()) is not None
        return term in text.casefold()
    ranked = []
    for index, project in enumerate(content['projects']):
        score = sum(3 * hit(t, role) + hit(t, jd) for t in project.get('keywords', []))
        ranked.append((-score, index, project))
    ranked.sort(key=lambda item: item[:2])
    summary = [statement(ref) for ref in content['summary_fact_ids']]
    skills = [statement(ref) for ref in content['skill_fact_ids']]
    def cost(text: str) -> int:
        # Count CJK characters too; whitespace-only word counts underestimate Chinese.
        return len(re.findall(r'[\u3400-\u9fff]|[A-Za-z0-9]+', text))
    used = {s['fact_id'] for s in summary + skills}
    remaining = policy['word_budget'] - sum(cost(s['text']) for s in summary + skills)
    selected, omitted = [], []
    for neg_score, _, project in ranked:
        if neg_score == 0:
            omitted.append({'id': project['id'], 'reason': 'no role/JD keyword overlap'})
            continue
        claims = []
        header_cost = cost(project['title']) + cost(project['dates'])
        for ref in project['fact_ids']:
            if ref in used:
                continue
            claim = statement(ref)
            needed = cost(claim['text']) + (header_cost if not claims else 0)
            if needed > remaining:
                continue
            claims.append(claim)
            used.add(ref)
            remaining -= needed
        if claims:
            selected.append({'id': project['id'], 'title': project['title'],
                             'dates': project['dates'], 'section': project.get('section', 'Projects'),
                             'score': -neg_score, 'statements': claims})
        else:
            omitted.append({'id': project['id'], 'reason': 'duplicate facts or content budget'})
    if not selected:
        raise ValueError('No evidenced project fits this role and content budget; review the plan')
    # Give substantial two-page plans a project boundary rather than spilling a
    # few lines onto page two. Never create a second page for sparse evidence.
    selected.sort(key=lambda p: p['section'] != 'Projects')
    weights = [sum(cost(s['text']) for s in p['statements']) for p in selected]
    total = sum(weights)
    if policy['preferred_pages'] == 2 and len(selected) > 1 and total > 400:
        boundary = min(range(1, len(selected)),
                       key=lambda i: abs(150 + sum(weights[:i]) - sum(weights[i:])))
        selected[boundary]['page_break_before'] = True
    return {'version': 1, 'policy': policy, 'summary': summary, 'skills': skills,
            'projects': selected, 'omitted': omitted,
            'fact_ledger_sha256': digest(ledger), 'evidence_profile_sha256': digest(profile),
            'job_sha256': digest({'role': role, 'description': jd}),
            'content_review': 'pending', 'candidate_review': 'pending',
            'note': 'Exact confirmed statements selected; headings, dates and untouched source sections still need review.'}


def render_plan(source: str, plan: dict, escape) -> str:
    def replace(section: str, body: str, required: bool = True, prefix: str = '') -> None:
        nonlocal source
        pattern = re.compile(r'(\\begin\{rSection\}\{' + re.escape(section)
                             + r'\}\s*).*?(\s*\\end\{rSection\})', re.S)
        count = len(pattern.findall(source))
        if count > 1 or (required and count != 1):
            raise ValueError('Resume requires exactly one managed section: ' + section)
        source = pattern.sub(lambda m: prefix + m[1] + body + m[2], source)
    replace('Summary', '\n'.join(escape(s['text']) for s in plan['summary']))
    replace('Technical Skills', '; '.join(escape(s['text']) for s in plan['skills']))
    for section in ('Projects', 'Research Experience'):
        blocks = []
        section_break = False
        for project in plan['projects']:
            if project['section'] != section:
                continue
            section_break = section_break or (not blocks and bool(project.get('page_break_before')))
            page_break = r'\newpage ' if blocks and project.get('page_break_before') else ''
            blocks.append(page_break + r'\par\noindent\textbf{' + escape(project['title']) + r'}\hfill '
                          + escape(project['dates']) + r'\par\nobreak' + '\n' + r'\begin{itemize}' + '\n'
                          + '\n'.join(r'\item ' + escape(s['text']) for s in project['statements'])
                          + '\n' + r'\end{itemize}')
        # These two sections are owned by the plan; clear stale research text as well.
        replace(section, '\n'.join(blocks), required=(section == 'Projects' or bool(blocks)),
                prefix=r'\newpage ' if section_break else '')
    return source


def verify_bundle(path: Path) -> dict:
    """Check freshness, not approval: hashes never prove a resume claim is true."""
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('pipeline_version') != 2:
        raise ValueError('Legacy bundle lacks versioned input/output fingerprints')
    for entry in manifest['input_files'] + manifest['output_files']:
        if file_hash(Path(entry['path'])) != entry['sha256']:
            raise ValueError('Bundle input/output changed; regenerate and repeat affected reviews')
    return {'fresh': True, 'content_review': manifest['content_review'],
            'rendered_pdf_review': manifest['layout_review']['rendered_pdf_review'],
            'candidate_review': manifest['candidate_review']}


def verify_attachment_bundle(document: Path) -> Path | None:
    """Recheck a versioned CV bundle when preparation consumes its attachment."""
    for parent in (document.parent, document.parent.parent):
        path = parent / 'manifest.json'
        if not path.is_file():
            continue
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest.get('pipeline_version') != 2:
            continue
        outputs = {Path(item['path']).resolve() for item in manifest['output_files']}
        if document.resolve() not in outputs:
            continue
        verify_bundle(path)
        return path
    return None

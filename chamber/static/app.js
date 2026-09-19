'use strict';
// Rendering and interaction only. Every domain rule (grading, scheduling, evidence) lives server-side.
// User text is always inserted as text nodes, never as HTML.

const $main = document.getElementById('main');
const S = { session: null, item: null, case: null, phase: null, attemptId: null, plan: null, reveal: null, meta: null };
const PLAN_LABELS = { objective: 'Objective of this turn', prize_map: 'Prize map / plan for the next turns',
  opponent_plan: "Opponent's likely plan", preserve: 'Key resource to preserve' };
const RECALL = [[1, 'Again'], [2, 'Hard'], [3, 'Good'], [4, 'Easy']];

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else if (k === 'class') el.className = v;
    else if (k === 'value') el.value = v;
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid instanceof Node ? kid : String(kid));
  return el;
}
async function api(method, path, body) {
  const r = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
const show = (...nodes) => $main.replaceChildren(...nodes);
const errorBox = () => h('p', { class: 'error', role: 'alert' });
const fail = (box, e) => { box.textContent = e.message; };
const badge = (text, cls = '') => h('span', { class: `badge ${cls}` }, text);
const lvl = (l) => badge(l, `lvl-${l}`);
const val = (id) => document.getElementById(id).value.trim();
const lines = (s) => s.split('\n').map((x) => x.trim()).filter(Boolean);
const tags = (s) => s.split(',').map((x) => x.trim()).filter(Boolean);
async function meta() { return S.meta || (S.meta = await api('GET', '/api/meta')); }
function field(label, input, note) { return h('div', {}, h('label', { for: input.id }, label), input, note ? h('div', { class: 'muted' }, note) : null); }
function select(id, options, current) {
  return h('select', { id }, options.map((o) => { const [v, t] = Array.isArray(o) ? o : [o, o];
    return h('option', { value: v, selected: String(v) === String(current) }, t); }));
}
function radios(name, options, current) {
  return h('div', { class: 'row', role: 'radiogroup' }, options.map(([v, t]) => h('label', { class: 'choice' },
    h('input', { type: 'radio', name, value: v, checked: String(v) === String(current) }), t)));
}
const picked = (name) => (document.querySelector(`input[name="${name}"]:checked`) || {}).value;

// ------------------------------------------------------------------ TODAY
async function viewToday() {
  const t = await api('GET', '/api/today');
  const box = errorBox();
  const start = h('button', { class: 'primary', id: 'start', disabled: !t.plan.length, on: { click: async () => {
    try { const s = await api('POST', '/api/sessions'); Object.assign(S, { session: s.session_id, case: null });
      location.hash = '#case'; } catch (e) { fail(box, e); } } } }, 'START');
  show(
    h('h1', {}, 'Today'),
    h('section', {}, h('h2', {}, `Recommended session: ${t.plan.length} reps`),
      h('p', { class: 'muted' }, 'Concepts stay hidden until you answer, so the rep tests recognition too.'),
      t.plan.length ? h('ol', { id: 'plan' }, t.plan.map((i) => h('li', {}, badge(i.mode), h('span', { class: 'muted' }, i.reason))))
        : h('p', {}, 'Nothing to drill.'),
      start, box),
    h('section', { id: 'real-evidence' }, h('h2', {}, 'Real-match evidence'),
      h('div', { class: `banner ${t.play.play ? 'warn' : ''}` }, t.play.play ? 'Go play competitive matches. ' : '', t.play.reason)),
    h('section', {}, h('h2', {}, 'Leaks'),
      t.leaks.length ? h('ul', {}, t.leaks.map((l, i) => h('li', {}, `Leak ${i + 1}: ${l.status}; verified errors ${l.recent.errors}/${l.recent.n}, self-reported errors ${l.recent.self_errors}/${l.recent.self_n}`)))
        : h('p', { class: 'muted' }, 'No recorded leak yet. Coverage and probe reps look for unrecorded ones.'),
      h('p', { class: 'muted' }, `Concepts with memory due (FSRS): ${t.due_count}`)),
    h('section', {}, h('h2', {}, 'Deck'), h('p', {}, t.deck.label),
      t.deck.cases_for_older_versions ? h('p', { class: 'warn' }, `${t.deck.cases_for_older_versions} case(s) were written for an older deck version. Check them before trusting them.`) : null));
}

// ------------------------------------------------------------------ CASE
async function loadNext() {
  const n = await api('GET', `/api/sessions/${S.session}/next`);
  if (n.done) { Object.assign(S, { case: null, phase: 'done', session: null }); return; }
  Object.assign(S, { case: n.case, item: n.item, phase: 'plan', attemptId: null, plan: null, reveal: null });
}

function caseHeader(c) {
  return h('section', {},
    h('div', { class: 'row' }, c.synthetic ? badge('SYNTHETIC DEMO', 'warn') : badge('real source'), badge(c.decision_family),
      badge(`transfer ${c.transfer_level}`), badge(`choices ${c.completeness}`), h('span', { class: 'muted' }, `deck ${c.deck_label}`)),
    S.item ? h('p', { class: 'muted' }, `Why now: ${S.item.mode}, ${S.item.reason}`) : null,
    h('h3', {}, 'Position (what you could know)'), h('pre', { id: 'position' }, c.observed_state),
    c.unknown_fields.length ? h('p', { class: 'muted' }, 'Unknown: ', c.unknown_fields.join('; ')) : null,
    h('h2', { id: 'prompt' }, c.prompt));
}

async function viewCase(parts = []) {
  if (parts[1] && (!S.case || S.case.id !== parts[1])) {   // #case/<id>: practise one case outside a session
    Object.assign(S, { session: null, item: null, case: (await api('GET', `/api/cases/${parts[1]}`)).case, phase: 'plan', attemptId: null, plan: null, reveal: null });
  }
  if (!S.case && S.session) await loadNext();
  if (S.phase === 'done') return show(h('h1', {}, 'Session complete'), h('section', {},
    h('p', {}, 'Every planned rep is done. Check Progress, or go play and log real opportunities.'),
    h('a', { href: '#today' }, 'Back to Today')));
  if (!S.case) return show(h('h1', {}, 'Case'), h('section', {}, h('p', {}, 'No active session. '), h('a', { href: '#today' }, 'Start one from Today')));
  const c = S.case;
  if (S.phase === 'plan') return show(caseHeader(c), planForm(c));
  if (S.phase === 'answer') return show(caseHeader(c), lockedPlan(), answerForm(c));
  return show(caseHeader(c), lockedPlan(), revealView(S.reveal));
}

function planForm(c) {
  const fields = c.requires.length ? c.requires : ['objective'];
  const box = errorBox();
  return h('section', {}, h('h2', {}, 'Commit your plan before you choose'),
    h('p', { class: 'muted' }, c.requires.length ? 'Required for this case. The plan is locked once submitted.' : 'Optional for this case.'),
    fields.map((f) => field(PLAN_LABELS[f], h('textarea', { id: `plan-${f}` }))),
    h('button', { class: 'primary', id: 'lock', on: { click: async () => {
      const plan = Object.fromEntries(fields.map((f) => [f, val(`plan-${f}`)]));
      const missing = c.requires.filter((f) => !plan[f]);   // the server enforces this too
      if (missing.length) return fail(box, new Error(`commit your plan first: ${missing.map((f) => PLAN_LABELS[f]).join(', ')}`));
      try { const r = await api('POST', '/api/attempts', { case_id: c.id, session_id: S.session, plan });
        Object.assign(S, { attemptId: r.attempt_id, plan, phase: 'answer' }); viewCase(); } catch (e) { fail(box, e); } } } }, 'Lock plan'),
    box);
}

function lockedPlan() {
  const entries = Object.entries(S.plan || {}).filter(([, v]) => v);
  return h('section', { id: 'locked-plan' }, h('h3', {}, 'Your locked plan'),
    entries.length ? h('ul', {}, entries.map(([k, v]) => h('li', {}, h('strong', {}, `${PLAN_LABELS[k]}: `), v))) : h('p', { class: 'muted' }, '(none declared)'));
}

function answerForm(c) {
  const box = errorBox();
  const hint = h('p', { id: 'hint', class: 'muted' });
  return h('section', {}, h('h2', {}, 'Your decision'),
    c.choices.length ? radios('choice', c.choices.map((x) => [x.key, `${x.key}. ${x.text}`])) : null,
    c.completeness !== 'EXHAUSTIVE' ? h('p', { class: 'muted' }, `Listed choices are ${c.completeness}: your line may not be listed. Describe it below (an unlisted line is not graded).`) : null,
    field(c.choices.length ? 'Other line (optional)' : 'Your line', h('textarea', { id: 'other' })),
    field('Reasoning (optional)', h('textarea', { id: 'reasoning' })),
    h('button', { id: 'hint-btn', on: { click: async (ev) => { try { hint.textContent = `Hint: ${(await api('POST', `/api/attempts/${S.attemptId}/hint`)).hint}`;
      ev.target.disabled = true; } catch (e) { fail(box, e); } } } }, 'Hint (caps memory rating at Hard)'),
    hint,
    h('button', { class: 'primary', id: 'submit', on: { click: async () => {
      try { S.reveal = await api('POST', `/api/attempts/${S.attemptId}/answer`, { choice: picked('choice') || null, other_text: val('other'), reasoning: val('reasoning') });
        S.phase = 'reveal'; viewCase(); } catch (e) { fail(box, e); } } } }, 'Submit decision'),
    box);
}

function verdictBanner(r) {
  const a = r.attempt;
  if (r.graded) return h('div', { id: 'verdict', class: `banner ${a.correct ? 'ok' : 'bad'}` },
    a.correct ? 'Matches the graded evidence (FACT / COACH_GOLD / CONSENSUS).' : 'Contradicted by graded evidence (FACT / COACH_GOLD / CONSENSUS).');
  return h('div', { id: 'verdict', class: 'banner warn' }, 'Not graded: no unanimous FACT, COACH_GOLD or CONSENSUS verdict on your choice. Compare with the evidence below.');
}

function revealView(r) {
  const a = r.attempt, c = r.case;
  const chosen = c.choices.find((x) => x.key === a.choice);
  return h('div', {},
    h('section', { id: 'reveal' }, h('h2', {}, 'Your decision'),
      h('p', {}, chosen ? `${chosen.key}. ${chosen.text}` : `Other line: ${a.other_text}`),
      a.reasoning ? h('p', { class: 'muted' }, `Reasoning: ${a.reasoning}`) : null,
      h('p', { class: 'muted' }, `Decision time after locking the plan: ${(a.latency_ms / 1000).toFixed(1)} s${a.hint_used ? ' · hint used' : ''}${a.retries ? ` · retry #${a.retries} (does not update memory)` : ''}`),
      verdictBanner(r),
      r.disputes.length ? h('div', { id: 'disputes', class: 'banner warn' }, `Evidence disagrees on choice ${r.disputes.join(', ')}. The disagreement is kept, not resolved.`) : null),
    h('section', {}, h('h2', {}, 'Evidence ledger'), h('div', { class: 'scroll' }, h('table', { id: 'ledger' },
      h('tr', {}, ['Level', 'Choice', 'Verdict', 'Claim', 'Source / reviewer'].map((x) => h('th', {}, x))),
      c.evidence.map((x) => h('tr', {}, h('td', {}, lvl(x.level)), h('td', {}, x.choice || '—'),
        h('td', { class: x.verdict === 'good' ? 'ok' : x.verdict === 'bad' ? 'bad' : '' }, x.verdict || '—'),
        h('td', {}, x.claim), h('td', { class: 'muted' }, [x.source_ref, x.reviewer].filter(Boolean).join(' · ') || '—'))))),
      h('p', { class: 'muted' }, 'FACT/COACH_GOLD/CONSENSUS grade. PRO_LINE = a strong player chose it, not proof it is best. SIMULATION = model output. HEURISTIC = useful, unproven. UNKNOWN = not established.'),
      h('h3', {}, 'Reference lines'), h('ul', {}, c.choices.map((x) => h('li', {}, `${x.key}. ${x.text}`))),
      h('h3', {}, 'What is uncertain'), h('ul', {}, h('li', {}, `Choice list completeness: ${c.completeness}`),
        h('li', {}, `Position reconstruction: ${c.reconstruction}`), c.unknown_fields.map((u) => h('li', {}, u))),
      c.full_record ? [h('h3', {}, 'Full record (hindsight, shown only after you answer)'), h('pre', {}, c.full_record)] : null),
    h('section', {}, h('h2', {}, 'Concepts'), c.concepts.map((k) => h('div', {}, h('strong', {}, k.name), badge(k.skill), h('p', {}, k.definition)))),
    coachBox(r),
    reviewForm(r),
    evidenceForm(c, r.evidence_levels));
}

function coachBox(r) {
  const out = h('div', { id: 'coach-out' });
  const render = (x) => out.replaceChildren(!x.available ? h('p', { class: 'muted' }, x.reason) : h('div', {},
    h('div', { class: 'banner warn' }, x.trust, x.off_concept ? ' The coach named a concept not linked to this case.' : ''),
    h('p', {}, h('strong', {}, 'Main concept: '), x.main_concept), h('p', {}, x.explanation),
    h('p', {}, h('strong', {}, 'Mental model: '), x.mental_model), h('p', {}, h('strong', {}, 'Question: '), x.socratic_question),
    h('p', {}, h('strong', {}, 'Next focus: '), x.next_focus),
    x.new_claims.length ? [h('h3', {}, 'Unverified claims (not added to evidence)'), h('ul', {}, x.new_claims.map((cl) => h('li', {}, cl)))] : null));
  if (r.attempt.coach) render(r.attempt.coach);
  const enabled = !!r.coach_enabled;
  return h('section', {}, h('h2', {}, 'Coach (optional LLM)'),
    enabled ? h('button', { id: 'coach-btn', on: { click: async (ev) => { ev.target.disabled = true; out.textContent = 'Asking…';
      try { render(await api('POST', `/api/attempts/${r.attempt.id}/coach`)); } catch (e) { out.textContent = e.message; } } } }, 'Ask coach')
      : h('p', { class: 'muted', id: 'coach-off' }, 'Coach disabled. The Chamber works fully without it.'),
    out);
}

function reviewForm(r) {
  const c = r.case, box = errorBox();
  const done = Object.values(r.attempt.recall).every((x) => x != null);
  const after = h('div', { class: 'row', id: 'after', hidden: !done },
    S.session ? h('button', { class: 'primary', id: 'next', on: { click: async () => { await loadNext(); viewCase(); } } }, 'Next case')
      : h('a', { href: '#today', id: 'next' }, 'Back to Today'),
    h('button', { id: 'retry', on: { click: () => { Object.assign(S, { phase: 'plan', attemptId: null, plan: null, reveal: null }); viewCase(); } } }, 'Retry this case'));
  const form = h('div', { hidden: done },
    h('p', {}, 'How well did you recall each concept BEFORE the reveal? (This schedules memory only.)'),
    c.concepts.map((k) => h('div', {}, h('label', {}, k.name), radios(`recall-${k.id}`, RECALL))),
    r.graded ? null : [h('label', {}, 'Compared with the evidence, was your decision an error you want to stop repeating?'),
      radios('self-outcome', [['ok', 'No, it was fine'], ['error', 'Yes, an error'], ['', 'Not sure']], '')],
    c.concepts.length > 1 ? [h('label', {}, 'If this was an error, which concept(s) actually caused it?'),
      h('p', { class: 'muted' }, 'Leave all unchecked if you are unsure. The Chamber will not blame every linked concept automatically.'),
      h('div', { id: 'error-concepts' }, c.concepts.map((k) => h('label', { class: 'choice' },
        h('input', { type: 'checkbox', name: 'error-concept', value: k.id }), k.name)))] : null,
    field('Error / root-cause tags (comma separated, optional)', h('input', { type: 'text', id: 'error-tags',
      placeholder: c.root_cause_tags.concat(c.symptom_tags).join(', ') })),
    h('button', { class: 'primary', id: 'save-review', on: { click: async () => {
      const ratings = Object.fromEntries(c.concepts.map((k) => [k.id, Number(picked(`recall-${k.id}`))]));
      const errorConcepts = [...document.querySelectorAll('input[name="error-concept"]:checked')].map((x) => x.value);
      try { await api('POST', `/api/attempts/${r.attempt.id}/review`, { ratings, outcome: picked('self-outcome') || null,
        error_tags: tags(val('error-tags')), error_concepts: errorConcepts });
        form.hidden = true; after.hidden = false; } catch (e) { fail(box, e); } } } }, 'Save review'), box);
  return h('section', {}, h('h2', {}, 'Review'), form, after);
}

function evidenceForm(c, levels) {
  const box = errorBox();
  return h('details', { class: 'box' }, h('summary', {}, 'Add evidence to this case (e.g. a coach review). Appended, never replaces.'),
    evidenceFields('new-ev', {}, levels),
    h('button', { on: { click: async () => {
      try { const r = await api('POST', `/api/cases/${c.id}/evidence`, readEvidence('new-ev'));
        if (r.errors.length) throw new Error(r.errors.join('\n'));
        box.textContent = 'Added. It will show on the next attempt.'; } catch (e) { fail(box, e); } } } }, 'Add evidence'), box);
}

function evidenceFields(p, x, levels) {
  return h('div', { class: 'ev-row grid2', 'data-ev': p },
    field('Level', select(`${p}-level`, levels, x.level || 'HEURISTIC')),
    field('Choice key (optional)', h('input', { type: 'text', id: `${p}-choice`, value: x.choice || '' })),
    field('Verdict', select(`${p}-verdict`, [['', '— none —'], 'good', 'bad'], x.verdict || '')),
    field('Claim', h('textarea', { id: `${p}-claim`, value: x.claim || '' })),
    field('Source reference', h('input', { type: 'text', id: `${p}-source_ref`, value: x.source_ref || '' })),
    field('Reviewer (required for COACH_GOLD)', h('input', { type: 'text', id: `${p}-reviewer`, value: x.reviewer || '' })));
}
function readEvidence(p) {
  return { level: val(`${p}-level`), choice: val(`${p}-choice`) || null, verdict: val(`${p}-verdict`) || null,
    claim: val(`${p}-claim`), source_ref: val(`${p}-source_ref`), reviewer: val(`${p}-reviewer`) };
}

// ------------------------------------------------------------------ PROGRESS
function tierCell(t, min) {
  const n = t.ok + t.error, sn = t.self_ok + t.self_error;
  return h('td', {},
    n ? h('div', {}, `${t.ok}/${n} verified ok`) : h('div', { class: 'muted' }, 'no verified result'),
    sn ? h('div', { class: 'muted' }, `${t.self_ok}/${sn} self-reported ok`) : null,
    t.undefined ? h('div', { class: 'muted' }, `${t.undefined} unattributed/ungraded`) : null,
    n < min ? h('div', { class: 'muted' }, 'insufficient verified evidence') : null);
}
function repeatCell(r, min) {
  if (!r.later) return h('td', { class: 'muted' }, '—');
  return h('td', { class: r.errors ? 'bad' : '' }, `${r.errors}/${r.later} later errors`, r.later < min ? h('div', { class: 'muted' }, 'insufficient evidence') : null);
}

async function viewProgress() {
  const [p, m] = [await api('GET', '/api/progress'), await meta()];
  const th = p.thresholds, box = errorBox();
  show(h('h1', {}, 'Progress'),
    h('p', { class: 'muted' }, 'Verified outcomes come from graded evidence. Self-reports are shown separately and never certify transfer. "Memory" is FSRS concept recall, not playing skill. Seen = L0-L1, unseen = L2-L3, real = L4.'),
    h('section', {}, h('h2', {}, 'Repeat errors and transfer by concept'), h('div', { class: 'scroll' }, h('table', { id: 'progress' },
      h('tr', {}, ['Concept', 'Status', 'Repeat after first error: drills', 'Repeat: real games', 'Unseen', 'Real', 'Seen', 'Memory (FSRS)', 'Median decision time'].map((x) => h('th', {}, x))),
      p.concepts.map((s) => h('tr', {}, h('td', {}, s.name), h('td', {}, s.status),
        repeatCell({ later: s.repeat.seen.later + s.repeat.unseen.later, errors: s.repeat.seen.errors + s.repeat.unseen.errors }, th.later),
        repeatCell(s.repeat.real, th.later),
        tierCell(s.tiers.unseen, th.unseen), tierCell(s.tiers.real, th.real), tierCell(s.tiers.seen, 1),
        h('td', {}, !s.memory.reviewed ? 'not reviewed' : `${s.memory.due ? 'due' : 'not due'} · recall p ${s.memory.retrievability}`),
        h('td', {}, s.latency.n ? `${s.latency.median_s} s (n=${s.latency.n})` : '—')))))),
    h('section', {}, h('h2', {}, 'Recurring error tags'),
      p.error_tags.length ? h('ul', {}, p.error_tags.map(([t, n]) => h('li', {}, `${t}: ${n}`))) : h('p', { class: 'muted' }, 'None recorded yet.')),
    h('section', { id: 'log-real' }, h('h2', {}, 'Log a real-match opportunity (L4)'),
      h('p', { class: 'muted' }, 'A spot in a real game where a concept mattered. This is the evidence that drills transfer.'),
      h('div', {}, m.concepts.map((k) => h('label', { class: 'choice' }, h('input', { type: 'checkbox', name: 'real-concept', value: k.id }), k.name))),
      h('label', {}, 'How did you handle it?'),
      radios('real-outcome', [['ok', 'Handled it'], ['error', 'Made the error'], ['', 'Not sure']], ''),
      h('label', {}, 'If it was an error, which selected concept(s) caused it?'),
      h('p', { class: 'muted' }, 'Optional. Leave blank if unsure; the error will not be attributed to every concept.'),
      h('div', {}, m.concepts.map((k) => h('label', { class: 'choice' }, h('input', { type: 'checkbox', name: 'real-error-concept', value: k.id }), k.name))),
      field('Error tags (comma separated)', h('input', { type: 'text', id: 'real-tags' })),
      field('Note', h('textarea', { id: 'real-note' })),
      h('button', { class: 'primary', id: 'log-real-btn', on: { click: async () => {
        const concepts = [...document.querySelectorAll('input[name="real-concept"]:checked')].map((x) => x.value);
        const errorConcepts = [...document.querySelectorAll('input[name="real-error-concept"]:checked')].map((x) => x.value);
        try { await api('POST', '/api/real', { concepts, outcome: picked('real-outcome') || null, note: val('real-note'),
          error_tags: tags(val('real-tags')), error_concepts: errorConcepts });
          viewProgress(); } catch (e) { fail(box, e); } } } }, 'Log opportunity'), box));
}

// ------------------------------------------------------------------ INBOX
async function viewInbox(parts) {
  const m = await meta();
  if (parts[1] === 'source') return viewSource(Number(parts[2]));
  if (parts[1] === 'candidate') return viewCandidate(Number(parts[2]), m);
  const inbox = await api('GET', '/api/inbox');
  const box = errorBox();
  show(h('h1', {}, 'Inbox'),
    h('section', {}, h('h2', {}, 'New raw source'),
      h('p', { class: 'muted' }, 'Stored exactly as given and never modified. Nothing is judged automatically.'),
      h('div', { class: 'grid2' }, field('Type', select('src-type', m.source_types, 'ptcgl_log')),
        field('Matchup', h('input', { type: 'text', id: 'src-matchup' })),
        field('Opponent name (replaced by OPPONENT in derived cases)', h('input', { type: 'text', id: 'src-opp' })),
        field('Deck version', select('src-deck', [['', '— none —'], ...m.decks.map((d) => [d.hash, `${d.deck_id} v${d.version}`])], ''))),
      field('External link (optional)', h('input', { type: 'text', id: 'src-url' })),
      field('Content (battle log, notes…)', h('textarea', { id: 'src-content', rows: 8 })),
      h('button', { class: 'primary', id: 'save-source', on: { click: async () => {
        try { const r = await api('POST', '/api/sources', { source_type: val('src-type'), matchup: val('src-matchup'), opponent_name: val('src-opp'),
          deck_hash: val('src-deck') || null, url: val('src-url'), content: document.getElementById('src-content').value });
          location.hash = `#inbox/source/${r.source_id}`; } catch (e) { fail(box, e); } } } }, 'Save source'), box),
    h('section', {}, h('h2', {}, 'Sources'), inbox.sources.length ? h('ul', { id: 'sources' }, inbox.sources.map((s) => h('li', {},
      h('a', { href: `#inbox/source/${s.id}` }, `#${s.id} ${s.source_type}`), ' ', h('span', { class: 'muted' }, `${s.created_at.slice(0, 10)} ${s.matchup} ${s.preview || s.url}`))))
      : h('p', { class: 'muted' }, 'No sources yet.')),
    h('section', {}, h('h2', {}, 'Candidate cases'), inbox.candidates.length ? h('ul', { id: 'candidates' }, inbox.candidates.map((c) => h('li', {},
      h('a', { href: `#inbox/candidate/${c.id}` }, `candidate #${c.id}`), ' ', badge(c.status), c.case_id ? ` → ${c.case_id}` : '', ' ', h('span', { class: 'muted' }, c.prompt || ''))))
      : h('p', { class: 'muted' }, 'No candidates yet.')));
}

async function viewSource(id) {
  const s = await api('GET', `/api/sources/${id}`);
  const box = errorBox();
  const safeUrl = /^https?:\/\//i.test(s.url) ? h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.url) : s.url;
  const body = s.timeline.length
    ? h('div', { id: 'timeline' }, h('p', { class: 'muted' }, 'Best-effort grouping by turn header only. Tick the lines relevant to the decision.'),
      s.timeline.map((g) => h('div', {}, h('h3', {}, g.title), g.lines.map((l) => h('label', { class: 'logline' },
        h('input', { type: 'checkbox', name: 'logline', value: l.n }), h('span', { class: 'muted' }, String(l.n).padStart(3)), l.text)))))
    : h('pre', { id: 'raw' }, s.content || '(no content)');
  show(h('h1', {}, `Source #${s.id}`), h('p', {}, h('a', { href: '#inbox' }, '← Inbox')),
    h('section', {}, h('p', {}, badge(s.source_type), s.matchup, ' ', safeUrl),
      h('p', { class: 'muted' }, `sha256 ${s.sha256} · ${s.created_at} · immutable`), body,
      h('button', { class: 'primary', id: 'make-candidate', on: { click: async () => {
        const picks = new Set([...document.querySelectorAll('input[name="logline"]:checked')].map((x) => Number(x.value)));
        const excerpt = picks.size ? s.content.split('\n').filter((_, i) => picks.has(i + 1)).join('\n') : s.content;
        try { const r = await api('POST', '/api/candidates', { source_id: s.id, excerpt }); location.hash = `#inbox/candidate/${r.candidate_id}`; }
        catch (e) { fail(box, e); } } } }, 'Create candidate case'), box));
}

async function viewCandidate(id, m) {
  const cand = await api('GET', `/api/candidates/${id}`);
  const d = cand.data, box = errorBox(), draft = cand.status === 'draft';
  let evN = 0;
  const evList = h('div', { id: 'ev-list' });
  const addEv = (x) => { const p = `ev${evN++}`; evList.append(h('div', { 'data-row': p }, evidenceFields(p, x, m.levels),
    h('button', { on: { click: (e) => e.target.parentElement.remove() } }, 'Remove evidence'))); };
  (d.evidence || []).forEach(addEv);
  const collect = () => ({
    id: val('c-id'), prompt: val('c-prompt'), observed_state: document.getElementById('c-observed').value.trim(),
    full_record: document.getElementById('c-full').value, unknown_fields: lines(val('c-unknown')),
    choices: lines(val('c-choices')).map((l) => { const i = l.indexOf(':'); return { key: l.slice(0, i).trim(), text: l.slice(i + 1).trim() }; }),
    completeness: val('c-completeness'), requires: m.plan_fields.filter((f) => document.getElementById(`c-req-${f}`).checked),
    hint: val('c-hint'), decision_family: val('c-family'), criticality: Number(val('c-crit')), criticality_source: val('c-crit-src'),
    matchup: val('c-matchup'), format: val('c-format'), date: val('c-date'), deck_hash: val('c-deck') || null,
    reconstruction: val('c-recon'), transfer_level: val('c-transfer'), variant_of: val('c-variant') || null,
    difficulty: Number(val('c-diff')), synthetic: document.getElementById('c-synth').checked,
    concepts: [...document.querySelectorAll('input[name="c-concept"]:checked')].map((x) => x.value),
    symptom_tags: tags(val('c-symptoms')), root_cause_tags: tags(val('c-causes')),
    evidence: [...evList.querySelectorAll('[data-row]')].map((r) => readEvidence(r.dataset.row)),
  });
  const save = async () => api('PUT', `/api/candidates/${id}`, { data: collect() });
  show(h('h1', {}, `Candidate #${id}`), h('p', {}, h('a', { href: '#inbox' }, '← Inbox'), ' · ', h('a', { href: `#inbox/source/${cand.source_id}` }, `source #${cand.source_id}`)),
    h('p', {}, badge(cand.status), cand.case_id ? `promoted to ${cand.case_id}` : 'Untrusted draft. You validate every field; nothing is judged automatically.'),
    h('section', {},
      field('Case id (optional)', h('input', { type: 'text', id: 'c-id', value: d.id || '' })),
      field('Prompt', h('textarea', { id: 'c-prompt', value: d.prompt })),
      field('Observed state', h('textarea', { id: 'c-observed', rows: 8, value: d.observed_state }), 'ONLY what you could know at decision time. No later turns, no revealed hands.'),
      field('Full record / excerpt (hindsight allowed)', h('textarea', { id: 'c-full', rows: 6, value: d.full_record }), 'Never shown before answering.'),
      field('Unknown fields (one per line)', h('textarea', { id: 'c-unknown', value: (d.unknown_fields || []).join('\n') })),
      field('Choices (one per line, "A: text")', h('textarea', { id: 'c-choices', value: (d.choices || []).map((c) => `${c.key}: ${c.text}`).join('\n') })),
      h('div', { class: 'grid2' },
        field('Choice completeness', select('c-completeness', m.completeness, d.completeness)),
        field('Reconstruction confidence', select('c-recon', m.reconstruction, d.reconstruction), 'FACT evidence needs exact or high.'),
        field('Decision family', select('c-family', m.families, d.decision_family)),
        field('Criticality', select('c-crit', [[0, '0 forced'], [1, '1 routine'], [2, '2 meaningful'], [3, '3 high leverage'], [4, '4 game-defining']], d.criticality)),
        field('Criticality source', h('input', { type: 'text', id: 'c-crit-src', value: d.criticality_source })),
        field('Transfer level', select('c-transfer', [['L0', 'L0 exact replay'], ['L1', 'L1 cosmetic variant'], ['L2', 'L2 near transfer'], ['L3', 'L3 far transfer']], d.transfer_level)),
        field('Variant of case id', h('input', { type: 'text', id: 'c-variant', value: d.variant_of || '' })),
        field('Difficulty', select('c-diff', [1, 2, 3], d.difficulty)),
        field('Matchup', h('input', { type: 'text', id: 'c-matchup', value: d.matchup || '' })),
        field('Format', h('input', { type: 'text', id: 'c-format', value: d.format || '' })),
        field('Date', h('input', { type: 'text', id: 'c-date', value: d.date || '' })),
        field('Deck version', select('c-deck', [['', '— none —'], ...m.decks.map((x) => [x.hash, `${x.deck_id} v${x.version}`])], d.deck_hash || ''))),
      field('Hint (optional)', h('input', { type: 'text', id: 'c-hint', value: d.hint || '' })),
      h('label', {}, 'Plan fields the player must commit'),
      h('div', { class: 'row' }, m.plan_fields.map((f) => h('label', { class: 'choice' }, h('input', { type: 'checkbox', id: `c-req-${f}`, checked: (d.requires || []).includes(f) }), PLAN_LABELS[f]))),
      h('label', { class: 'choice' }, h('input', { type: 'checkbox', id: 'c-synth', checked: !!d.synthetic }), 'Synthetic (not a real position)'),
      h('label', {}, 'Concepts'),
      h('div', { id: 'c-concepts' }, m.concepts.map((k) => h('label', { class: 'choice' },
        h('input', { type: 'checkbox', name: 'c-concept', value: k.id, checked: (d.concepts || []).includes(k.id) }), `${k.name} (${k.skill})`))),
      newConceptForm(m, async () => { await save(); S.meta = null; viewCandidate(id, await meta()); }),
      field('Symptom tags (comma separated)', h('input', { type: 'text', id: 'c-symptoms', value: (d.symptom_tags || []).join(', ') })),
      field('Root-cause tags (comma separated)', h('input', { type: 'text', id: 'c-causes', value: (d.root_cause_tags || []).join(', ') }))),
    h('section', {}, h('h2', {}, 'Evidence'), h('p', { class: 'muted' }, 'At least one item. Use UNKNOWN when nothing is established. PRO_LINE never carries a verdict.'),
      evList, h('button', { id: 'add-ev', on: { click: () => addEv({}) } }, 'Add evidence row')),
    draft ? h('div', {}, h('button', { id: 'save-cand', on: { click: async () => { try { await save(); box.textContent = 'Saved.'; } catch (e) { fail(box, e); } } } }, 'Save draft'),
      h('button', { class: 'primary', id: 'promote', on: { click: async () => {
        try { await save(); const r = await api('POST', `/api/candidates/${id}/promote`);
          if (r.errors.length) throw new Error(r.errors.join('\n'));
          box.replaceChildren(`Promoted to DecisionCase ${r.case_id}. It is now schedulable. `, h('a', { href: `#case/${r.case_id}` }, 'Practise it now'));
          box.className = 'ok'; box.id = 'promoted'; }
        catch (e) { fail(box, e); } } } }, 'Validate and promote to DecisionCase')) : null,
    box);
}

function newConceptForm(m, done) {
  const box = errorBox();
  return h('details', { class: 'box' }, h('summary', {}, 'New concept'),
    h('div', { class: 'grid2' }, field('Id (snake_case)', h('input', { type: 'text', id: 'k-id' })), field('Name', h('input', { type: 'text', id: 'k-name' })),
      field('Skill', select('k-skill', m.skills, 'planning'))),
    field('Definition', h('textarea', { id: 'k-def' })),
    h('button', { id: 'k-save', on: { click: async () => {
      try { await api('POST', '/api/concepts', { id: val('k-id'), name: val('k-name'), skill: val('k-skill'), definition: val('k-def') }); await done(); }
      catch (e) { fail(box, e); } } } }, 'Create concept'), box);
}

// ------------------------------------------------------------------ router
async function render() {
  const parts = (location.hash.slice(1) || 'today').split('/');
  document.querySelectorAll('nav a').forEach((a) => a.classList.toggle('active', a.dataset.view === parts[0]));
  try {
    await ({ today: viewToday, case: viewCase, progress: viewProgress, inbox: viewInbox }[parts[0]] || viewToday)(parts);
  } catch (e) { show(h('p', { class: 'error', role: 'alert' }, e.message)); }
}
window.addEventListener('hashchange', render);
render();

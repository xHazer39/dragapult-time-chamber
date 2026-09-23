'use strict';
// Rendering and interaction only. Every domain rule (grading, scheduling, evidence) lives server-side.
// User text is always inserted as text nodes, never as HTML. Only the constant icon SVGs below use innerHTML.

const $main = document.getElementById('main');
const S = { session: null, reps: 0, done: [], item: null, case: null, phase: null, attemptId: null, plan: null,
  reveal: null, meta: null, retry: 0, lockedAt: null, log: [] };
const PLAN_LABELS = { objective: 'Objective of this turn', prize_map: 'Prize map · next turns',
  opponent_plan: "Opponent's likely plan", preserve: 'Key resource to preserve' };
const RECALL = [[1, 'Again'], [2, 'Hard'], [3, 'Good'], [4, 'Easy']];
const GRADING = ['FACT', 'COACH_GOLD', 'CONSENSUS'];
const MOD = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl';

const ICONS = {
  today: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  case: '<circle cx="12" cy="12" r="10"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/>',
  progress: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  play: '<path d="M6 3l14 9-14 9z" fill="currentColor"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8M16 17H8M10 9H8"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  sidebar: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
  flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
};
const SOURCE_ICON = { ptcgl_log: 'file', pro_match: 'play', coach_note: 'message', manual: 'plus',
  tcgmasters_link: 'link', prizemap_link: 'link', other: 'file' };

function icon(name, size = 16) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [k, v] of Object.entries({ width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) s.setAttribute(k, v);
  s.innerHTML = ICONS[name];   // constant markup, never user text
  return s;
}
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else if (k === 'class') el.className = v;
    else if (k === 'value') el.value = v;
    else if (k === 'style') el.style.cssText = v;   // CSSOM, allowed by the server's CSP (a style attribute is not)
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
const show = (...nodes) => {
  $main.replaceChildren(...nodes.flat(Infinity).filter((n) => n != null && n !== false));
  $main.classList.remove('enter'); void $main.offsetWidth; $main.classList.add('enter');   // what changed: the screen
};
const errorBox = () => h('p', { class: 'error', role: 'alert' });
const fail = (box, e) => { box.textContent = e.message; };
const badge = (text, tone = '') => h('span', { class: `badge ${tone}` }, text);
const ev = (level) => h('span', { class: `ev ev-${level}`, title: GRADING.includes(level) ? 'Can grade (when unanimous)' : level === 'UNKNOWN' ? 'Not established' : 'Never grades alone' }, level.replace('_', ' '));
const kbd = (k) => h('kbd', {}, k);
const val = (id) => document.getElementById(id).value.trim();
const lines = (s) => s.split('\n').map((x) => x.trim()).filter(Boolean);
const tags = (s) => s.split(',').map((x) => x.trim()).filter(Boolean);
const frac = (a, b) => h('span', { class: 'tabular' }, `${a}/${b}`);
async function meta() { return S.meta || (S.meta = await api('GET', '/api/meta')); }
function btn(label, { id, cls = '', key, ic, on, disabled } = {}) {
  return h('button', { id, class: cls, disabled: !!disabled, on: on ? { click: on } : undefined }, ic ? icon(ic) : null, label, key ? kbd(key) : null);
}
function field(label, input, note) {
  return h('div', { class: 'field' }, h('label', { for: input.id }, label), input, note ? h('div', { class: 'hint-text' }, note) : null);
}
function select(id, options, current) {
  return h('select', { id }, options.map((o) => { const [v, t] = Array.isArray(o) ? o : [o, o];
    return h('option', { value: v, selected: String(v) === String(current) }, t); }));
}
function seg(name, options, current, keys = []) {
  return h('div', { class: 'seg', role: 'radiogroup' }, options.map(([v, t], i) => h('label', {},
    h('input', { type: 'radio', name, value: v, checked: current != null && String(v) === String(current) }), t, keys[i] ? kbd(keys[i]) : null)));
}
const picked = (name) => (document.querySelector(`input[name="${name}"]:checked`) || {}).value;
const head = (over, title, action) => h('div', { class: 'head' },
  h('div', { class: 'stack' }, over ? h('div', { class: 'overline' }, over) : null, h('h1', {}, title)), h('div', { class: 'spacer' }), action || null);
function empty(ic, title, text, action) {
  return h('div', { class: 'empty' }, h('div', { class: 'ring' }, icon(ic)), h('h2', {}, title), h('p', {}, text), action || null);
}

// Today's chamber: one arc per planned rep around a core. Decorative only, the number is in the copy.
function orbit(n, core) {
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
  const el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
  svg.setAttribute('viewBox', '0 0 200 200'); svg.setAttribute('aria-hidden', 'true');
  const R = 88, C = 2 * Math.PI * R, gap = n > 1 ? 7 : 0, len = n ? C / n - gap : 0;
  svg.append(el('circle', { class: 'track', cx: 100, cy: 100, r: R, 'stroke-width': 6 }));
  const segs = el('g', { transform: 'rotate(-90 100 100)' });
  for (let i = 0; i < n; i++) segs.append(el('circle', { class: 'seg', cx: 100, cy: 100, r: R, 'stroke-width': 6,
    'stroke-dasharray': `${len} ${C - len}`, 'stroke-dashoffset': -i * (len + gap) }));
  const spin = el('g', { class: 'spin' }), spin2 = el('g', { class: 'spin rev' });
  spin.append(el('circle', { class: 'dash', cx: 100, cy: 100, r: 72, 'stroke-width': 1.5 }));
  spin2.append(el('circle', { class: 'dash', cx: 100, cy: 100, r: 100, 'stroke-width': 1 }));
  svg.append(segs, spin, spin2);
  return h('div', { class: 'orbit' }, svg, h('div', { class: 'core' }, icon(core, 30)));
}

// API status strings → one indicator. Filled = observed signal, hollow = missing evidence.
function statusView(text, label) {
  const t = text || '';
  const [tone, extra] = t.startsWith('repeat error') ? ['danger', 'ring'] : t.startsWith('active leak') ? ['danger', '']
    : t.startsWith('possible leak') ? ['warning', ''] : t.startsWith('known') ? ['warning', '']
      : t.startsWith('transfers in drills') ? ['warning', 'hollow'] : t.startsWith('no current') ? ['success', ''] : ['neutral', 'dashed'];
  return h('span', { class: `status ${tone} ${extra}` }, label || t);
}
const today = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });

// ------------------------------------------------------------------ TODAY
async function viewToday() {
  const t = await api('GET', '/api/today');
  setCount('count-today', t.reps ? `${t.reps} reps` : '');
  const box = errorBox();
  const startSession = async () => {
    try { const s = await api('POST', '/api/sessions');
      Object.assign(S, { session: s.session_id, reps: s.reps, done: [], case: null, phase: null, log: [], retry: 0 });
      location.hash = '#case'; } catch (e) { fail(box, e); } };
  // Today says how much to train, never what it targets: "exploit ×3" or a leak reason read
  // before the decision is priming. Mode and reason appear after the reveal, leaks in Progress.
  const logReal = () => { location.hash = '#progress/log'; };
  const cta = h('div', { class: 'cta' },
    t.play.play ? [btn('Log real match', { cls: 'primary lg glow', ic: 'flag', on: logReal }),
      t.reps ? btn(`Train anyway · ${t.reps} reps`, { id: 'start', cls: 'ghost', on: startSession }) : null]
      : [btn('Start session', { id: 'start', cls: `primary lg${t.reps ? ' glow' : ''}`, ic: 'play', on: startSession, disabled: !t.reps }),
        btn('Log real match', { cls: 'ghost', ic: 'flag', on: logReal })]);
  const hero = h('section', { class: `well today-well${t.reps || t.play.play ? '' : ' is-dim'}`, id: t.play.play ? 'real-evidence' : null },
    h('div', { class: 'copy' },
      h('div', { class: 'overline' }, 'Highest-value training now'),
      t.play.play ? [h('h1', { class: 'row', style: 'gap:12px' }, icon('flag', 26), 'Go play competitive matches'), h('p', { class: 'lede' }, t.play.reason)]
        : t.reps ? h('div', { class: 'big-reps', id: 'plan' }, h('span', { class: 'n' }, String(t.reps)), h('span', { class: 'u' }, 'reps'),
          h('span', { class: 'note' }, 'plan fixed when you start'))
          : h('p', { class: 'lede' }, 'Nothing worth drilling right now.'),
      t.play.play ? null : h('div', { class: 'row caption' }, icon('lock', 14), 'What each rep targets stays hidden until you answer, so every rep also tests recognition.'),
      cta, box),
    orbit(t.play.play ? 0 : t.reps, t.play.play ? 'flag' : 'play'));
  const realOk = !t.play.reason.startsWith('No real-match');
  const older = t.deck.cases_for_older_versions;
  show(
    head(today(), 'Today'),
    hero,
    h('div', { class: 'strip' },
      h('section', {}, h('div', { class: 'overline' }, 'Training load'),
        h('div', { class: 'figure' }, h('span', { class: 'metric' }, String(t.due_count)), h('span', { class: 'small secondary' }, 'concepts with memory due')),
        h('div', { class: 'caption' }, 'FSRS schedules recall of concepts. It is not a skill score.')),
      h('section', { id: t.play.play ? null : 'real-evidence' }, h('div', { class: 'overline' }, 'Real-match evidence'),
        statusView(realOk ? 'no current' : 'transfers in drills', realOk ? 'Real-match evidence logged recently' : 'Needs real-game evidence'),
        h('div', { class: 'caption' }, t.play.reason)),
      h('section', {}, h('div', { class: 'overline' }, 'Deck version'),
        h('div', { class: 'row' }, icon('layers'), h('span', { class: 'mono' }, t.deck.label)),
        older ? statusView('known', `${older} case(s) written for an older deck version · check before trusting`)
          : statusView('no current', 'All active cases match this version'))));
  // Leaks are deliberately absent from Today: reading them just before a session primes the answer.
  // Progress shows every leak in full, with its denominators.
}

// ------------------------------------------------------------------ CASE
async function loadNext() {
  const n = await api('GET', `/api/sessions/${S.session}/next`);
  if (n.done) { Object.assign(S, { case: null, phase: 'done' }); return; }
  if (!S.done.includes(n.case.id)) S.done.push(n.case.id);
  Object.assign(S, { case: n.case, phase: 'plan', attemptId: null, plan: null, reveal: null, retry: 0 });
}

function focusBar() {
  const i = S.done.length;
  return h('div', { class: 'focusbar' },
    S.session ? [h('span', { class: 'tabular' }, `Rep ${i} of ${S.reps}${S.phase === 'reveal' ? ' · Review' : ''}`),
      h('div', { class: 'ticks', 'aria-hidden': 'true' }, Array.from({ length: S.reps }, (_, k) => h('i', { class: k < i - 1 ? 'done' : k === i - 1 ? 'now' : '' })))]
      : h('span', {}, `Single case${S.phase === 'reveal' ? ' · Review' : ''}`),
    // The training mode arrives with the reveal only: knowing a rep targets a leak biases the decision.
    S.phase === 'reveal' && S.reveal?.item ? badge(S.reveal.item.mode, S.reveal.item.mode === 'exploit' ? 'accent' : '') : null,
    h('span', { class: 'spacer' }),
    S.phase === 'answer' ? h('span', { class: 'row caption' }, icon('clock', 14), h('span', { id: 'timer', class: 'tabular' }, '0:00'), 'since lock') : null);
}

function caseMeta(c) {
  return h('div', { class: 'row case-meta' }, c.synthetic ? badge('SYNTHETIC DEMO', 'warning') : badge('Real source'), badge(c.decision_family),
    badge(`Transfer ${c.transfer_level}`), badge(`Choices ${c.completeness}`), h('span', { class: 'caption' }, c.deck_label));
}

function positionPanel(c) {
  return h('section', { class: 'card position', style: 'padding:22px 26px;gap:16px' },
    h('div', { class: 'overline' }, 'Position · what you could know'),
    h('pre', { id: 'position' }, c.observed_state),
    c.unknown_fields.length ? h('div', { class: 'stack', style: 'gap:8px' }, h('div', { class: 'caption' }, 'Unknown to you'),
      h('div', { class: 'row', style: 'gap:6px' }, c.unknown_fields.map((u) => h('span', { class: 'ev ev-UNKNOWN plain' }, u)))) : null);
}

async function viewCase(parts = []) {
  if (parts[1] && (!S.case || S.case.id !== parts[1])) {   // #case/<id>: practise one case outside a session
    Object.assign(S, { session: null, reps: 0, done: [], item: null, case: (await api('GET', `/api/cases/${parts[1]}`)).case,
      phase: 'plan', attemptId: null, plan: null, reveal: null, retry: 0 });
  }
  if (!S.case && S.session && S.phase !== 'done') await loadNext();
  setFocus(S.case && S.phase !== 'done');
  // Deep focus while deciding: chrome recedes around plan and decision, returns for the review.
  document.body.classList.toggle('deep-focus', !!S.case && (S.phase === 'plan' || S.phase === 'answer'));
  window.scrollTo(0, 0);
  if (S.phase === 'done') { show(sessionComplete()); return land('back-today'); }
  if (!S.case) return show(h('section', { class: 'card', style: 'margin-top:48px' }, empty('case', 'No active session',
    'Cases open from a session so the scheduler can mix exploit, coverage and probe reps. Start one from Today, or practise a promoted case from the Inbox.',
    h('a', { class: 'btn primary', href: '#today' }, 'Go to Today', kbd('G T')))));
  const c = S.case;
  if (S.phase === 'reveal') { show(focusBar(), revealView(S.reveal)); return land('story-title'); }
  const side = S.phase === 'plan' ? planForm(c) : answerForm(c);
  show(focusBar(), h('div', { class: 'case-head' }, caseMeta(c), h('h1', { class: 'prompt', id: 'prompt', tabindex: '-1' }, c.prompt)),
    S.retry ? h('div', { class: 'banner dashed' }, icon('clock', 14), `Retry of this case · counts as a seen (L0) attempt · never updates memory · stays out of repeat-error counts`) : null,
    h('div', { class: 'case-grid' }, positionPanel(c), h('div', { class: 'decision' }, side)));
  if (S.phase === 'answer') { startTimer(); return land('prompt'); }
  // with a keyboard, the plan is typed straight away; on touch, no keyboard pops up uninvited
  land(matchMedia('(pointer: fine)').matches ? document.querySelector('textarea[id^="plan-"]')?.id : 'prompt');
}
// Every phase change lands focus on its focal object, so screen readers and the keyboard start there.
function land(id) { const el = id && document.getElementById(id); if (el) el.focus({ preventScroll: true }); }

function planForm(c) {
  const fields = c.requires.length ? c.requires : ['objective'];
  const box = errorBox();
  const lock = async () => {
    const plan = Object.fromEntries(fields.map((f) => [f, val(`plan-${f}`)]));
    const missing = c.requires.filter((f) => !plan[f]);   // the server enforces this too
    if (missing.length) return fail(box, new Error(`commit your plan first: ${missing.map((f) => PLAN_LABELS[f]).join(', ')}`));
    try { const r = await api('POST', '/api/attempts', { case_id: c.id, session_id: S.session, plan });
      Object.assign(S, { attemptId: r.attempt_id, plan, phase: 'answer', lockedAt: Date.now() }); viewCase(); } catch (e) { fail(box, e); }
  };
  return h('div', { class: 'stack', style: 'gap:16px' },
    h('div', { class: 'stack', style: 'gap:2px' }, h('h2', {}, 'Commit your plan first'),
      h('span', { class: 'small secondary' }, c.requires.length ? 'Required for this case. Choices appear only after you lock it.' : 'Optional for this case. Choices appear after you lock it.')),
    fields.map((f) => field(`${PLAN_LABELS[f]}${c.requires.includes(f) ? '  ·  required' : ''}`, h('textarea', { id: `plan-${f}` }))),
    h('div', { class: 'row cta-row', style: 'gap:12px' }, btn('Lock plan', { id: 'lock', cls: 'primary', ic: 'lock', on: lock }),
      h('span', { class: 'caption' }, 'The plan cannot be edited after locking.')),
    box);
}

function lockedPlan() {
  const entries = Object.entries(S.plan || {}).filter(([, v]) => v);
  return h('section', { class: 'locked', id: 'locked-plan' }, h('div', { class: 'row caption' }, icon('lock', 14), 'Plan locked'),
    entries.length ? entries.map(([k, v]) => h('div', { class: 'kv' }, h('span', { class: 'muted' }, PLAN_LABELS[k]), h('span', {}, v)))
      : h('span', { class: 'small muted' }, '(none declared)'));
}

function answerForm(c) {
  const box = errorBox();
  const hint = h('p', { id: 'hint', class: 'small secondary', style: 'margin:0' });
  const useHint = async (e) => { try { hint.textContent = `Hint: ${(await api('POST', `/api/attempts/${S.attemptId}/hint`)).hint}`;
    document.getElementById('hint-btn').disabled = true; } catch (err) { fail(box, err); } };
  const submit = async () => {
    try { S.reveal = await api('POST', `/api/attempts/${S.attemptId}/answer`, { choice: picked('choice') || null, other_text: val('other'), reasoning: val('reasoning') });
      S.phase = 'reveal'; S.reviewed = false; viewCase(); } catch (e) { fail(box, e); } };
  return h('div', { class: 'stack', style: 'gap:16px' }, lockedPlan(), h('h2', {}, 'Your decision'),
    c.choices.length ? h('div', { class: 'stack', style: 'gap:8px', role: 'radiogroup' }, c.choices.map((x) => h('label', { class: 'choice-row' },
      h('input', { type: 'radio', name: 'choice', value: x.key }), h('span', {}, `${x.key}.  ${x.text}`), kbd(x.key)))) : null,
    c.completeness !== 'EXHAUSTIVE' ? h('div', { class: 'row caption' }, icon('info', 14), `Choices are ${c.completeness}: your line may not be listed. Describe it below (not graded).`) : null,
    h('div', { class: 'form-grid answer-extra' },
      field(c.choices.length ? 'Other line · optional' : 'Your line', h('textarea', { id: 'other', placeholder: 'Describe a line that is not listed' })),
      field('Reasoning · optional', h('textarea', { id: 'reasoning', rows: 2 }))),
    h('div', { class: 'row cta-row' }, btn('Submit decision', { id: 'submit', cls: 'primary', on: submit }),
      btn('Hint · caps memory at Hard', { id: 'hint-btn', cls: 'ghost', on: useHint })),
    hint, box);
}

// The reveal reads as one story. The anchor answers "what did I choose, and what can the Chamber honestly say?"
// (01 plan → 02 decision → 03 verdict); then 04 why and 05 evidence; then 06 principle → 07 recall → 08 next.
const step = (n, title, ...kids) => h('section', { class: 'step' },
  h('div', { class: 'step-head' }, h('span', { class: 'node', 'aria-hidden': 'true' }, n), h('h2', {}, title)), ...kids);

function verdict(r) {
  const a = r.attempt;
  // Strength tracks evidence: a graded verdict is solid; "Not graded" stays open, never styled as a failure.
  return h('div', { id: 'verdict' }, r.graded
    ? h('div', { class: `pill ${a.correct ? 'ok' : 'bad'}` }, icon(a.correct ? 'check' : 'x'), a.correct ? 'Matches the graded evidence' : 'Error · Contradicted by graded evidence')
    : h('div', { class: 'pill none' }, 'Not graded'));
}

function revealView(r) {
  const a = r.attempt, c = r.case;
  const chosen = c.choices.find((x) => x.key === a.choice);
  const metaLine = [`Decided ${(a.latency_ms / 1000).toFixed(1)} s after locking`, a.hint_used ? 'hint used' : 'no hint',
    a.retries ? `retry #${a.retries} · does not update memory` : null, a.reasoning ? `“${a.reasoning}”` : null].filter(Boolean).join(' · ');
  const tally = (key) => c.evidence.filter((x) => x.choice === key && x.verdict);
  const best = (key) => { const t = tally(key).filter((x) => GRADING.includes(x.level)); return t.length && t.every((x) => x.verdict === 'good'); };
  const plan = Object.entries(a.plan || S.plan || {}).filter(([, v]) => v);
  const lv = [...new Set(c.evidence.filter((x) => GRADING.includes(x.level) && x.choice === a.choice && x.verdict).map((x) => x.level))].join(' / ');
  const [principle, recall, next] = reviewForm(r);
  return h('div', { class: 'stack', style: 'gap:28px' },
    h('section', { class: `well outcome${r.graded ? '' : ' is-dim'}`, id: 'reveal' },
      h('ol', { class: 'flow' },
        h('li', { class: 'flow-step' }, h('span', { class: 'node solid', 'aria-hidden': 'true' }, '01'), h('div', { class: 'overline' }, 'Your plan'),
          plan.length ? h('div', { class: 'plan-lines' }, plan.map(([k, v]) => h('p', {}, h('span', { class: 'muted' }, `${PLAN_LABELS[k]} · `), v)))
            : h('span', { class: 'small muted' }, '(none declared)')),
        h('li', { class: 'flow-step' }, h('span', { class: 'node solid', 'aria-hidden': 'true' }, '02'), h('div', { class: 'overline' }, 'Your decision'),
          h('div', { class: 'title' }, chosen ? `${chosen.key}.  ${chosen.text}` : `Other line: ${a.other_text}`),
          h('span', { class: 'small secondary tabular' }, metaLine)),
        h('li', { class: 'flow-step verdict-step' }, h('span', { class: `node ${r.graded ? 'solid now' : 'dashed'}`, 'aria-hidden': 'true' }, '03'),
          h('h2', { class: 'overline', id: 'story-title', tabindex: '-1' }, r.graded ? 'Verdict · graded' : 'Verdict · unresolved'), verdict(r)))),
    h('div', { class: 'reveal-grid' },
      h('div', { class: 'story' },
        step('04', 'Why',
          h('p', { class: 'why' }, r.graded ? `Graded by ${lv}: every grading-level item on your choice agrees.`
            : 'No unanimous FACT, COACH_GOLD or CONSENSUS verdict on your choice, so the Chamber does not call it right or wrong. Compare with the evidence; you judge it in Recall.'),
          r.disputes.length ? h('div', { id: 'disputes', class: 'row small warn' }, icon('alert', 14), `Evidence disagrees on choice ${r.disputes.join(', ')} — kept, not resolved.`) : null,
          c.unknown_fields.length ? h('div', { class: 'row', style: 'gap:6px' }, h('span', { class: 'caption' }, 'Uncertain:'), c.unknown_fields.map((u) => h('span', { class: 'ev ev-UNKNOWN plain' }, u))) : null,
          h('span', { class: 'caption' }, `Choice list ${c.completeness} · reconstruction ${c.reconstruction}${c.synthetic ? ' · synthetic demo position' : ''}${c.full_record ? '' : ' · no hindsight record for this case'}`)),
        step('05', 'Evidence on each line',
          c.choices.length ? h('div', { class: 'stack', style: 'gap:8px' }, c.choices.map((x) => h('div', { class: `ref-row${best(x.key) ? ' best' : ''}` }, h('span', {}, `${x.key}.  ${x.text}`),
            x.key === a.choice ? badge('your line', 'accent') : null,
            h('span', { class: 'tally' }, tally(x.key).length ? tally(x.key).map((e) => h('span', { class: 'row', style: 'gap:4px' }, ev(e.level),
              h('span', { class: `caption ${e.verdict === 'good' ? 'ok' : 'bad'}` }, e.verdict === 'good' ? 'supports' : 'against')))
              : h('span', { class: 'caption' }, 'no verdict in evidence')))))
            : h('span', { class: 'small muted' }, 'No listed choices: this case asks for your own line.'),
          h('span', { class: 'caption' }, `Choices listed: ${c.completeness} · a pro line is not proof of best`))),
      h('section', { class: 'card review-panel take' }, principle, recall, next, coachBox(r)),
      h('div', { class: 'ledger-area stack', style: 'gap:18px' },
        h('section', { class: 'stack' }, h('div', { class: 'row' }, h('h2', {}, 'Evidence ledger'), h('span', { class: 'caption' }, `Append-only · ${c.evidence.length} items`)),
          h('div', { class: 'scroll' }, h('table', { id: 'ledger', class: 'ledger' },
            h('tr', {}, ['Level', 'On', 'Verdict', 'Claim', 'Source'].map((x) => h('th', {}, x))),
            c.evidence.map((x) => h('tr', {}, h('td', {}, ev(x.level)), h('td', {}, x.choice || '—'),
              h('td', { class: x.verdict === 'good' ? 'ok' : x.verdict === 'bad' ? 'bad' : '' }, x.verdict === 'good' ? [icon('check', 14), ' supports'] : x.verdict === 'bad' ? [icon('x', 14), ' against'] : '—'),
              h('td', {}, x.claim), h('td', {}, [x.source_ref, x.reviewer].filter(Boolean).join(' · ') || '—')))))),
        h('details', { class: 'card legend' }, h('summary', {}, 'How evidence grades'),
          h('div', {}, h('span', { class: 'label' }, 'Can grade'), GRADING.map(ev), h('span', { class: 'caption' }, 'only when unanimous on your choice')),
          h('div', {}, h('span', { class: 'label' }, 'Never grades alone'), ['PRO_LINE', 'SIMULATION', 'HEURISTIC'].map(ev), h('span', { class: 'caption' }, 'a pro line is not proof of best')),
          h('div', {}, h('span', { class: 'label' }, 'Not established'), ev('UNKNOWN'), h('span', { class: 'caption' }, 'shown, never filled in'))),
        c.full_record ? h('section', { class: 'stack' }, h('h2', {}, 'Full record · hindsight, shown only after you answer'), h('pre', { class: 'excerpt' }, c.full_record)) : null,
        evidenceForm(c, r.evidence_levels))));
}

function coachBox(r) {
  const out = h('div', { id: 'coach-out', class: 'stack small' });
  const render = (x) => out.replaceChildren(!x.available ? h('p', { class: 'muted', style: 'margin:0' }, x.reason) : h('div', { class: 'stack' },
    h('div', { class: 'banner dashed' }, x.trust, x.off_concept ? ' The coach named a concept not linked to this case.' : ''),
    h('p', { style: 'margin:0' }, h('strong', {}, 'Main concept: '), x.main_concept), h('p', { style: 'margin:0' }, x.explanation),
    h('p', { style: 'margin:0' }, h('strong', {}, 'Mental model: '), x.mental_model), h('p', { style: 'margin:0' }, h('strong', {}, 'Question: '), x.socratic_question),
    h('p', { style: 'margin:0' }, h('strong', {}, 'Next focus: '), x.next_focus),
    x.new_claims.length ? [h('h3', {}, 'Unverified claims (not added to evidence)'), h('ul', { style: 'margin:0' }, x.new_claims.map((cl) => h('li', {}, cl)))] : null));
  if (r.attempt.coach) render(r.attempt.coach);
  return h('div', { class: 'stack', style: 'padding-top:14px;border-top:1px solid var(--border-subtle)' },
    h('div', { class: 'row', style: 'align-items:flex-start;gap:10px' }, icon('message'),
      r.coach_enabled ? h('div', { class: 'stack', style: 'gap:8px' }, h('span', { class: 'small' }, 'Coach · optional LLM, never evidence'),
        btn('Ask coach', { id: 'coach-btn', on: async (e) => { e.currentTarget.disabled = true; out.textContent = 'Asking…';
          try { render(await api('POST', `/api/attempts/${r.attempt.id}/coach`)); } catch (err) { out.textContent = err.message; } } }))
        : h('div', { class: 'stack', style: 'gap:2px', id: 'coach-off' }, h('span', { class: 'small secondary' }, 'Coach disabled'),
          h('span', { class: 'caption' }, 'Not configured. Everything here works without it; coach text is never evidence.'))),
    out);
}

function reviewForm(r) {
  const c = r.case, box = errorBox();
  // One rep trains one concept: only the target is rated and only its memory is rescheduled.
  const target = c.concepts.find((k) => k.id === r.attempt.target_concept_id) || c.concepts[0];
  const others = c.concepts.filter((k) => k.id !== target.id);
  const done = r.attempt.recall[target.id] != null;
  const retry = () => { Object.assign(S, { phase: 'plan', attemptId: null, plan: null, reveal: null, retry: S.retry + 1 }); viewCase(); };
  const after = h('div', { class: 'stack', id: 'after', hidden: !done },
    h('div', { class: 'row cta-row' },
      S.session ? btn('Save & next rep', { id: 'next', cls: 'primary', ic: 'arrow', on: async () => { await loadNext(); viewCase(); } })
        : h('a', { href: '#today', id: 'next', class: 'btn primary' }, 'Back to Today'),
      btn('Retry', { id: 'retry', on: retry })),
    h('span', { class: 'caption' }, 'Retry counts as a seen (L0) attempt and never updates memory.'));
  const pending = h('span', { class: 'caption', hidden: done }, 'Save the review to continue.');
  const saved = h('span', { class: 'small secondary', hidden: !done }, 'Review saved.');
  const save = async () => {
    const ratings = { [target.id]: Number(picked(`recall-${target.id}`)) };
    const errorConcepts = [...document.querySelectorAll('input[name="error-concept"]:checked')].map((x) => x.value);
    try { await api('POST', `/api/attempts/${r.attempt.id}/review`, { ratings, outcome: picked('self-outcome') || null,
      error_tags: tags(val('error-tags')), error_concepts: errorConcepts });
      S.log.push({ graded: r.graded, correct: r.attempt.correct, self: picked('self-outcome') || null });
      form.hidden = true; pending.hidden = true; saved.hidden = false; after.hidden = false; S.reviewed = true; land('next'); } catch (e) { fail(box, e); } };
  const form = h('div', { class: 'stack', style: 'gap:18px', hidden: done },
    h('div', { class: 'stack', style: 'gap:8px' }, h('span', { class: 'small' }, `Did you recall “${target.name}” before the reveal?`),
      seg(`recall-${target.id}`, RECALL, null, ['1', '2', '3', '4']),
      h('span', { class: 'caption' }, 'Recall schedules memory (FSRS) for this one concept. It is not a grade and not a skill score.')),
    r.graded ? null : h('div', { class: 'stack', style: 'gap:8px' }, h('span', { class: 'small' }, 'Was your decision an error you want to stop repeating?'),
      seg('self-outcome', [['ok', 'Fine'], ['error', 'Error'], ['', 'Not sure']], '', ['F', 'E', 'N']),
      h('span', { class: 'caption warn' }, 'Self-reported · weak evidence · never overrides graded evidence')),
    c.concepts.length > 1 ? h('div', { class: 'stack', style: 'gap:6px' }, h('span', { class: 'small' }, 'If this was an error, which concept(s) caused it?'),
      h('span', { class: 'caption' }, 'Leave all unchecked if unsure. The Chamber will not blame every linked concept.'),
      h('div', { id: 'error-concepts', class: 'stack', style: 'gap:2px' }, c.concepts.map((k) => h('label', { class: 'check' },
        h('input', { type: 'checkbox', name: 'error-concept', value: k.id }), k.name)))) : null,
    field('Root-cause tags · comma separated, optional', h('input', { type: 'text', id: 'error-tags', placeholder: c.root_cause_tags.concat(c.symptom_tags).join(', ') })),
    h('div', { class: 'row cta-row' }, btn('Save review', { id: 'save-review', cls: 'primary', on: save })), box);
  return [
    step('06', 'Principle · what this rep trained',
      h('div', { class: 'concept', id: 'target-concept' }, h('div', { class: 'row' }, h('h3', { class: 'concept-name' }, target.name), badge(target.skill)),
        h('p', { class: 'small secondary', style: 'margin:0' }, target.definition)),
      others.length ? h('div', { class: 'stack', id: 'linked-concepts', style: 'gap:4px' },
        h('span', { class: 'caption' }, 'Also linked to this case · not scheduled by this rep'),
        h('div', { class: 'row', style: 'gap:6px' }, others.map((k) => badge(k.name)))) : null,
      r.item ? h('span', { class: 'caption' }, `Why this rep: ${r.item.mode} · ${r.item.reason}`) : null),
    step('07', 'Recall', form, saved),
    step('08', 'Next', pending, after),
  ];
}

function evidenceForm(c, levels) {
  const box = errorBox();
  return h('details', { class: 'card' }, h('summary', {}, 'Add evidence to this case (e.g. a coach review) · appended, never replaces'),
    evidenceFields('new-ev', {}, levels),
    h('div', { class: 'row' }, btn('Add evidence', { on: async () => {
      try { const r = await api('POST', `/api/cases/${c.id}/evidence`, readEvidence('new-ev'));
        if (r.errors.length) throw new Error(r.errors.join('\n'));
        box.textContent = 'Added. It will show on the next attempt.'; } catch (e) { fail(box, e); } } })), box);
}

function evidenceFields(p, x, levels) {
  return h('div', { class: 'ev-row form-grid', 'data-ev': p },
    field('Level', select(`${p}-level`, levels, x.level || 'HEURISTIC')),
    field('Choice key · optional', h('input', { type: 'text', id: `${p}-choice`, value: x.choice || '' })),
    field('Verdict', select(`${p}-verdict`, [['', '— none —'], 'good', 'bad'], x.verdict || '')),
    field('Claim', h('textarea', { id: `${p}-claim`, value: x.claim || '' })),
    field('Source reference', h('input', { type: 'text', id: `${p}-source_ref`, value: x.source_ref || '' })),
    field('Reviewer · required for COACH_GOLD', h('input', { type: 'text', id: `${p}-reviewer`, value: x.reviewer || '' })));
}
function readEvidence(p) {
  return { level: val(`${p}-level`), choice: val(`${p}-choice`) || null, verdict: val(`${p}-verdict`) || null,
    claim: val(`${p}-claim`), source_ref: val(`${p}-source_ref`), reviewer: val(`${p}-reviewer`) };
}

function sessionComplete() {
  const graded = S.log.filter((x) => x.graded), ok = graded.filter((x) => x.correct).length;
  const stat = (n, l, cls) => h('div', { class: 'stack', style: 'gap:2px;align-items:center' }, h('span', { class: `metric-sm ${cls}` }, String(n)), h('span', { class: 'caption' }, l));
  return h('section', { class: 'well complete' }, h('div', { class: 'check-ring' }, icon('check')), h('h2', { class: 'title', id: 'complete-title', tabindex: '-1' }, 'Session complete'),
    h('span', { class: 'small secondary tabular' }, `${S.reps} reps planned · ${S.log.length} reviewed in this browser session`),
    h('div', { class: 'row', style: 'gap:28px;justify-content:center' }, stat(ok, 'ok · graded', 'ok'), stat(graded.length - ok, 'errors · graded', 'bad'),
      stat(S.log.length - graded.length, 'ungraded', 'secondary')),
    h('div', { class: 'row', style: 'justify-content:center' }, h('a', { class: 'btn primary', href: '#today', id: 'back-today' }, 'Back to Today'),
      h('a', { class: 'btn', href: '#progress/log' }, icon('flag'), 'Log real match')));
}

let timer = null;
function startTimer() {
  clearInterval(timer);
  timer = setInterval(() => { const el = document.getElementById('timer'); if (!el || !S.lockedAt) return clearInterval(timer);
    const s = Math.floor((Date.now() - S.lockedAt) / 1000); el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }, 1000);
}

// ------------------------------------------------------------------ PROGRESS
function tierCell(t, min) {
  const n = t.ok + t.error, sn = t.self_ok + t.self_error;
  return h('td', {},
    n ? h('div', { class: 'strong' }, `${t.ok}/${n} verified ok`) : h('div', { class: 'muted' }, 'no verified result'),
    sn ? h('div', { class: 'warn' }, `${t.self_ok}/${sn} self-reported ok`) : null,
    t.undefined ? h('div', { class: 'muted' }, `${t.undefined} unattributed/ungraded`) : null,
    n < min ? h('div', { class: 'muted' }, 'insufficient verified evidence') : null);
}
function repeatCell(r, min) {
  if (!r.later) return h('td', { class: 'muted' }, '—');
  return h('td', { class: r.errors ? 'bad' : '' }, `${r.errors}/${r.later} later errors`, r.later < min ? h('div', { class: 'muted' }, 'insufficient evidence') : null);
}
function segbar(ok, err, self = 0) {
  const n = ok + err + self;
  return n ? h('div', { class: 'segbar' }, ok ? h('i', { class: 's-ok', style: `flex:${ok}` }) : null, err ? h('i', { class: 's-err', style: `flex:${err}` }) : null,
    self ? h('i', { class: 's-self', style: `flex:${self}` }) : null) : h('div', { class: 'segbar nodata' });
}
function kpi(label, a, b, unit, needUnit, min, selfLine, provVerified) {
  const enough = b >= min;
  return h('section', { class: `card kpi${enough ? '' : ' insufficient'}` }, h('div', { class: 'overline' }, label),
    h('div', { class: 'value' }, h('span', { class: 'metric' }, enough ? `${a} / ${b}` : String(b)),
      h('span', { class: 'small secondary' }, enough ? unit : `of ${min} ${needUnit} needed`)),
    enough ? segbar(a, b - a) : h('div', { class: 'segbar nodata' }),
    h('div', { class: `prov ${enough ? 'ok' : 'muted'}` }, h('span', { class: `dot ${enough ? 'v' : 'i'}` }), enough ? provVerified : `Insufficient verified evidence · min ${min}`),
    selfLine ? h('div', { class: 'selfline tabular' }, h('span', { class: 'dot s' }), selfLine) : null);
}

// "What should I do next?" Only restates the status labels stats.py already computed, in their own
// severity order. Weak or missing evidence dims the well and says so; it never invents a conclusion.
const NEXT = [
  ['repeat error', 'Repeat error detected', true, (s) => `${s.repeat.real.errors}/${s.repeat.real.later} real-game opportunities after the first verified error repeated it.`, 'real'],
  ['active leak', 'Train this concept', true, (s) => `${s.recent.errors}/${s.recent.n} recent verified results are errors.`, 'unseen'],
  ['possible leak', 'Possible leak · self-reported', false, (s) => `${s.recent.self_n ? `${s.recent.self_errors}/${s.recent.self_n} recent self-reported results are errors` : `${s.tiers.real.self_error} self-reported real-game error(s)`}. Self-reports are weak evidence: a verified result would settle it.`, 'unseen'],
  ['known, not transferring', 'Needs unseen transfer', true, (s) => `Memory is strong, but only ${s.tiers.unseen.ok}/${s.tiers.unseen.ok + s.tiers.unseen.error} verified unseen positions were handled.`, 'unseen'],
  ['transfers in drills', 'Go play real matches', true, (s) => `Drills transfer to unseen positions, but real games have ${s.tiers.real.ok + s.tiers.real.error} verified results.`, 'real'],
  ['known, not yet shown', 'Needs unseen positions', false, () => 'Memory is strong, but too few unseen positions have been answered to say whether it transfers.', 'unseen'],
];
function pathNodes(tiers, th, target) {
  // seen → unseen → real. Solid: enough verified results. Hollow: observed, below the minimum. Dashed: nothing yet.
  const mins = { seen: 1, unseen: th.unseen, real: th.real };
  return h('ol', { class: 'path', 'aria-label': 'Evidence path' }, ['seen', 'unseen', 'real'].map((t) => {
    const v = tiers[t].ok + tiers[t].error, o = v + tiers[t].self_ok + tiers[t].self_error;
    const shape = v >= mins[t] ? 'solid' : o ? 'hollow' : 'dashed';
    return h('li', { class: t === target ? 'now' : '' }, h('span', { class: `node ${shape}`, 'aria-hidden': 'true' }),
      h('span', { class: 'small' }, t[0].toUpperCase() + t.slice(1)),
      h('span', { class: 'caption tabular' }, t === 'seen' ? `${v} verified` : `${v} of ${mins[t]} verified`));
  }));
}
function nextStep(p) {
  const C = p.concepts, th = p.thresholds;
  for (const [prefix, title, strong, why, target] of NEXT) {
    const hit = C.filter((s) => s.status.startsWith(prefix))
      .sort((x, y) => (y.recent.errors + y.recent.self_errors) - (x.recent.errors + x.recent.self_errors));
    if (!hit.length) continue;
    const s = hit[0], play = prefix === 'transfers in drills';
    return h('section', { class: `well next${strong ? '' : ' is-dim'}`, id: 'next-step' },
      h('div', { class: 'stack', style: 'gap:10px' }, h('div', { class: 'overline' }, 'What should I do next?'),
        h('h2', { class: 'next-title' }, title), h('div', { class: 'row' }, statusView(s.status, s.name), h('span', { class: 'caption' }, s.status)),
        h('p', { class: 'why' }, why(s)),
        hit.length > 1 ? h('span', { class: 'caption' }, `Same state: ${hit.slice(1).map((x) => x.name).join(', ')}`) : null,
        h('div', { class: 'row' }, play ? h('a', { class: 'btn primary', href: '#progress/log' }, icon('flag'), 'Log real match')
          : h('a', { class: 'btn primary', href: '#today' }, icon('play'), 'Start a session'),
          h('span', { class: 'caption' }, play ? 'Log each real opportunity below.' : 'The scheduler picks the reps; Progress does not choose them.'))),
      pathNodes(s.tiers, th, target));
  }
  const clean = C.length && C.every((s) => s.status.startsWith('no current'));
  const thin = C.filter((s) => s.status.startsWith('insufficient')).length;
  return h('section', { class: 'well next is-dim', id: 'next-step' },
    h('div', { class: 'stack', style: 'gap:10px' }, h('div', { class: 'overline' }, 'What should I do next?'),
      h('h2', { class: 'next-title' }, clean ? 'No strong conclusion' : 'Insufficient evidence'),
      h('p', { class: 'why' }, clean ? 'No concept shows a current verified leak. That is not proof of mastery: keep logging real games.'
        : `${thin} of ${C.length} concepts are below the minimum sample (${th.unseen} verified unseen, ${th.real} verified real). Nothing can be concluded yet.`),
      h('div', { class: 'row' }, clean ? h('a', { class: 'btn primary', href: '#progress/log' }, icon('flag'), 'Log real match')
        : h('a', { class: 'btn primary', href: '#today' }, icon('play'), 'Start a session'))),
    pathNodes(p.totals, th, clean ? 'real' : 'unseen'));
}

async function viewProgress(parts = []) {
  const [p, m] = [await api('GET', '/api/progress'), await meta()];
  const th = p.thresholds, box = errorBox(), T = p.totals, C = p.concepts;
  const rep = C.reduce((acc, s) => { for (const t of ['seen', 'unseen', 'real']) { acc.later += s.repeat[t].later; acc.errors += s.repeat[t].errors; } return acc; }, { later: 0, errors: 0 });
  const self = (t) => T[t].self_ok + T[t].self_error;
  const leaks = C.filter((s) => /^(repeat error|active leak|possible leak)/.test(s.status));
  const known = C.filter((s) => s.status.startsWith('known'));
  const thin = C.filter((s) => s.status.startsWith('insufficient') || s.status.startsWith('transfers in drills'));
  const due = C.filter((s) => s.memory.due);
  const panel = (title, note, items, render) => h('section', { class: 'card' }, h('h2', {}, title), h('span', { class: 'caption' }, note),
    items.length ? h('div', { class: 'divided' }, items.map((s) => h('div', { class: 'mini' }, render(s)))) : h('span', { class: 'small muted' }, 'None right now.'));
  const memText = (s) => !s.memory.reviewed ? 'never reviewed · due' : `${s.memory.due ? 'due' : 'not due'} · recall p ${s.memory.retrievability}`;
  show(
    head(`${T.seen.ok + T.seen.error + T.unseen.ok + T.unseen.error + T.real.ok + T.real.error} verified results · ${self('seen') + self('unseen') + self('real')} self-reported`, 'Progress'),
    nextStep(p),
    h('div', { class: 'legend-line' }, h('span', {}, h('span', { class: 'dot v' }), 'Verified: graded by FACT / COACH_GOLD / CONSENSUS'),
      h('span', {}, h('span', { class: 'dot s' }), 'Self-reported: weak evidence, never certifies transfer'),
      h('span', {}, h('span', { class: 'dot i' }), 'Insufficient: below minimum sample'),
      h('span', {}, h('span', { class: 'dot m' }), 'Memory (FSRS): recall of a concept, not performance')),
    h('div', { class: 'strip' },
      kpi('Repeat error rate', rep.errors, rep.later, 'later opportunities repeated an earlier error', 'verified later opportunities', th.later, null, 'Verified repeats after a first verified error'),
      kpi('Unseen transfer', T.unseen.ok, T.unseen.ok + T.unseen.error, 'unseen positions ok', 'verified unseen results', th.unseen,
        self('unseen') ? `+ ${T.unseen.self_ok}/${self('unseen')} self-reported ok · not counted` : null, 'Graded by FACT / COACH_GOLD / CONSENSUS'),
      kpi('Real-game transfer', T.real.ok, T.real.ok + T.real.error, 'real opportunities handled', 'verified real-game results', th.real,
        self('real') ? `${T.real.self_ok}/${self('real')} self-reported ok · cannot certify transfer` : null, 'Verified real-game outcomes')),
    h('section', { class: 'card', style: 'gap:0;padding-bottom:8px' },
      h('div', { class: 'row', style: 'padding-bottom:10px' }, h('h2', {}, 'Active leaks'), h('span', { class: 'caption' }, 'Concepts whose recent results include errors')),
      leaks.length ? h('div', { class: 'scroll' }, h('table', { id: 'leaks' },
        h('tr', {}, ['Concept', 'Status', 'Recent verified', 'Recent self-reported', 'Repeats: drills', 'Repeats: real'].map((x) => h('th', {}, x))),
        leaks.map((s) => h('tr', {}, h('td', { class: 'strong' }, s.name, s.status.startsWith('repeat error') ? h('div', { style: 'margin-top:4px' }, badge('Critical', 'danger glow')) : null),
          h('td', {}, statusView(s.status)),
          h('td', {}, s.recent.n ? [h('div', { class: 'tabular' }, `${s.recent.errors}/${s.recent.n} errors`), segbar(s.recent.n - s.recent.errors, s.recent.errors)] : h('span', { class: 'muted' }, '—')),
          h('td', { class: 'warn tabular' }, s.recent.self_n ? `${s.recent.self_errors}/${s.recent.self_n} errors` : h('span', { class: 'muted' }, '—')),
          h('td', { class: 'tabular' }, s.repeat.seen.later + s.repeat.unseen.later ? `${s.repeat.seen.errors + s.repeat.unseen.errors}/${s.repeat.seen.later + s.repeat.unseen.later}` : '—'),
          h('td', { class: 'tabular' }, s.repeat.real.later ? `${s.repeat.real.errors}/${s.repeat.real.later}` : '—')))))
        : empty('progress', 'No active leak', 'No concept has recent verified or self-reported errors.')),
    h('div', { class: 'grid3' },
      panel('Known, not automated', 'Memory is strong but unseen positions still fail. Recalling a concept is not using it.', known,
        (s) => [statusView(s.status, s.name), h('span', { class: 'caption tabular' }, `${memText(s)} · unseen ${s.tiers.unseen.ok}/${s.tiers.unseen.ok + s.tiers.unseen.error} verified ok`)]),
      panel('Insufficient evidence', 'Below the minimum sample. Counts are shown, never a guess.', thin,
        (s) => [statusView(s.status, s.name), h('span', { class: 'caption tabular' }, `unseen ${s.tiers.unseen.ok + s.tiers.unseen.error} of ${th.unseen} · real ${s.tiers.real.ok + s.tiers.real.error} of ${th.real} verified`)]),
      panel('Memory (FSRS)', 'When a concept is worth recalling again. Recall probability is memory, never playing skill.', due,
        (s) => [h('span', { class: 'status accent' }, s.name), h('span', { class: 'caption tabular' }, memText(s))])),
    h('section', { class: 'card' }, h('div', { class: 'row' }, h('h2', {}, 'All concepts'), h('span', { class: 'caption' }, 'Drill-down · verified and self-reported counted separately')),
      h('div', { class: 'scroll' }, h('table', { id: 'progress' },
        h('tr', {}, ['Concept', 'Status', 'Repeat after first error: drills', 'Repeat: real games', 'Unseen', 'Real', 'Seen', 'Memory (FSRS)', 'Median decision'].map((x) => h('th', {}, x))),
        C.map((s) => h('tr', {}, h('td', { class: 'strong' }, s.name), h('td', {}, statusView(s.status)),
          repeatCell({ later: s.repeat.seen.later + s.repeat.unseen.later, errors: s.repeat.seen.errors + s.repeat.unseen.errors }, th.later),
          repeatCell(s.repeat.real, th.later),
          tierCell(s.tiers.unseen, th.unseen), tierCell(s.tiers.real, th.real), tierCell(s.tiers.seen, 1),
          h('td', {}, memText(s)),
          h('td', {}, s.latency.n ? `${s.latency.median_s} s (n=${s.latency.n})` : '—')))))),
    h('div', { class: 'grid3', style: 'grid-template-columns:minmax(0,1fr) minmax(0,2fr)' },
      h('section', { class: 'card' }, h('h2', {}, 'Recurring error tags'),
        p.error_tags.length ? h('div', { class: 'stack', style: 'gap:6px' }, p.error_tags.map(([t, n]) => h('span', { class: 'small tabular' }, `${t}: ${n}`)))
          : h('span', { class: 'small muted' }, 'None recorded yet.')),
      h('section', { class: 'card', id: 'log-real' }, h('h2', {}, 'Log a real-match opportunity (L4)'),
        h('span', { class: 'caption' }, 'A spot in a real game where a concept mattered. Real-game outcomes are self-reported: weak evidence.'),
        h('div', { class: 'row', style: 'gap:6px 16px' }, m.concepts.map((k) => h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'real-concept', value: k.id }), k.name))),
        h('span', { class: 'small' }, 'How did you handle it?'),
        seg('real-outcome', [['ok', 'Handled it'], ['error', 'Made the error'], ['', 'Not sure']], ''),
        h('span', { class: 'small' }, 'If it was an error, which selected concept(s) caused it?'),
        h('span', { class: 'caption' }, 'Optional. Leave blank if unsure; the error will not be attributed to every concept.'),
        h('div', { class: 'row', style: 'gap:6px 16px' }, m.concepts.map((k) => h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'real-error-concept', value: k.id }), k.name))),
        h('div', { class: 'form-grid' }, field('Error tags · comma separated', h('input', { type: 'text', id: 'real-tags' })), field('Note', h('input', { type: 'text', id: 'real-note' }))),
        h('div', { class: 'row' }, btn('Log opportunity', { id: 'log-real-btn', cls: 'primary', ic: 'flag', on: async () => {
          const concepts = [...document.querySelectorAll('input[name="real-concept"]:checked')].map((x) => x.value);
          const errorConcepts = [...document.querySelectorAll('input[name="real-error-concept"]:checked')].map((x) => x.value);
          try { await api('POST', '/api/real', { concepts, outcome: picked('real-outcome') || null, note: val('real-note'),
            error_tags: tags(val('real-tags')), error_concepts: errorConcepts });
            viewProgress(); } catch (e) { fail(box, e); } } })), box)));
  if (parts[1] === 'log') document.getElementById('log-real').scrollIntoView({ block: 'start' });
}

// ------------------------------------------------------------------ INBOX
async function viewInbox(parts) {
  const m = await meta();
  if (parts[1] === 'source') return viewSource(Number(parts[2]));
  if (parts[1] === 'candidate') return viewCandidate(Number(parts[2]), m);
  const inbox = await api('GET', '/api/inbox');
  const drafts = inbox.candidates.filter((c) => c.status === 'draft'), promoted = inbox.candidates.filter((c) => c.status === 'promoted');
  setCount('count-inbox', drafts.length ? String(drafts.length) : '');
  const bySource = (id) => inbox.candidates.filter((c) => c.source_id === id);
  const detail = h('section', { class: 'card', id: 'inbox-detail', style: 'padding:18px 20px;gap:14px' });
  const composer = () => { const box = errorBox(); detail.replaceChildren(
    h('div', { class: 'stack', style: 'gap:2px' }, h('h2', {}, 'New raw source'), h('span', { class: 'caption' }, 'Stored exactly as given, hashed, never modified. Nothing is judged automatically.')),
    h('div', { class: 'form-grid' }, field('Type', select('src-type', m.source_types, 'ptcgl_log')), field('Matchup', h('input', { type: 'text', id: 'src-matchup' }))),
    field('Opponent name · replaced by OPPONENT in derived cases', h('input', { type: 'text', id: 'src-opp' })),
    field('Deck version', select('src-deck', [['', '— none —'], ...m.decks.map((d) => [d.hash, `${d.deck_id} v${d.version}`])], '')),
    field('External link · optional, never fetched', h('input', { type: 'text', id: 'src-url' })),
    field('Content · battle log, notes…', h('textarea', { id: 'src-content', rows: 8 })),
    h('div', { class: 'row' }, btn('Save source', { id: 'save-source', cls: 'primary', ic: 'plus', on: async () => {
      try { const r = await api('POST', '/api/sources', { source_type: val('src-type'), matchup: val('src-matchup'), opponent_name: val('src-opp'),
        deck_hash: val('src-deck') || null, url: val('src-url'), content: document.getElementById('src-content').value });
        location.hash = `#inbox/source/${r.source_id}`; } catch (e) { fail(box, e); } } })), box); };
  const candidateDetail = async (c, rowEl) => {
    document.querySelectorAll('.lrow.selected').forEach((x) => x.classList.remove('selected')); rowEl.classList.add('selected');
    const d = (await api('GET', `/api/candidates/${c.id}`)).data;
    const has = (ok, label) => h('div', { class: 'row small', style: 'gap:10px' }, h('span', { class: ok ? 'ok' : 'bad' }, icon(ok ? 'check' : 'x', 14)), h('span', { class: ok ? 'secondary' : '' }, label));
    detail.replaceChildren(
      h('div', { class: 'row' }, h('span', { class: 'small secondary' }, `Candidate #${c.id}`), badge(c.status === 'draft' ? 'Draft · untrusted' : c.status, c.status === 'promoted' ? 'success' : ''),
        h('span', { class: 'spacer' }), h('button', { class: 'icon', 'aria-label': 'Close', on: { click: () => { rowEl.classList.remove('selected'); composer(); } } }, icon('x'))),
      h('div', { class: 'title' }, d.prompt || '(no prompt yet)'),
      h('div', { class: 'kvs' },
        h('div', {}, h('span', { class: 'caption' }, 'Source'), h('a', { href: `#inbox/source/${c.source_id}` }, `#${c.source_id}`)),
        h('div', {}, h('span', { class: 'caption' }, 'Reconstruction'), badge(d.reconstruction, ['exact', 'high'].includes(d.reconstruction) ? 'success' : 'warning')),
        h('div', {}, h('span', { class: 'caption' }, 'Choices'), badge(`${d.completeness} · ${(d.choices || []).length} listed`)),
        h('div', {}, h('span', { class: 'caption' }, 'Deck'), h('span', { class: 'mono' }, d.deck_hash || 'unspecified'))),
      h('div', { class: 'stack', style: 'gap:8px;padding-top:12px;border-top:1px solid var(--border-subtle)' },
        h('div', { class: 'row' }, h('h2', {}, 'Draft fields'), h('span', { class: 'caption' }, 'The server validates on promote')),
        has(!!(d.observed_state || '').trim(), 'Observed state · pre-decision information only'), has(!!(d.prompt || '').trim(), 'Prompt'),
        has((d.concepts || []).length > 0, 'At least one concept linked'), has((d.evidence || []).length > 0, 'At least one evidence item (UNKNOWN allowed)'),
        has(!!(d.criticality_source || '').trim(), 'Criticality source')),
      h('div', { class: 'row' }, h('a', { class: 'btn primary', id: 'open-editor', href: `#inbox/candidate/${c.id}` }, c.status === 'draft' ? 'Open editor' : 'View')));
  };
  const lrow = (ic, title, metaText, trail, on) => h('button', { class: 'lrow', on: { click: on } }, icon(ic), h('span', { class: 't' }, title), h('span', { class: 'm' }, metaText), h('span', { class: 'tr' }, trail), icon('chevron', 14));
  const list = h('div', { class: 'list' },
    h('div', { class: 'group overline' }, `Candidates · needs validation · ${drafts.length}`),
    drafts.length ? drafts.map((c) => { const row = lrow('file', c.prompt || '(untitled draft)', `#${c.id} · source #${c.source_id}`, 'draft', () => candidateDetail(c, row)); return row; })
      : h('div', { class: 'small muted', style: 'padding:6px 12px' }, 'No drafts waiting.'),
    h('div', { class: 'group overline' }, `Raw sources · ${inbox.sources.length}`),
    h('div', { id: 'sources', class: 'list' }, inbox.sources.map((s) => { const cs = bySource(s.id), pr = cs.filter((c) => c.status === 'promoted').length;
      return lrow(SOURCE_ICON[s.source_type] || 'file', s.matchup || (s.preview || s.url || '').split('\n')[0] || s.source_type,
        `#${s.id} · ${s.source_type} · ${s.created_at.slice(0, 10)}`, cs.length ? `${cs.length} candidate${cs.length > 1 ? 's' : ''}${pr ? ` · ${pr} promoted` : ''}` : 'no candidates',
        () => { location.hash = `#inbox/source/${s.id}`; }); })),
    promoted.length ? [h('div', { class: 'group overline' }, `Promoted · ${promoted.length}`),
      promoted.map((c) => lrow('check', c.prompt || c.case_id, `#${c.id} → ${c.case_id}`, 'practise', () => { location.hash = `#case/${c.case_id}`; }))] : null);
  const stage = (n, label, note, active) => h('div', { class: `stage${active ? ' active' : ''}${n ? '' : ' none'}` }, h('span', { class: 'metric-sm' }, String(n)),
    h('div', { class: 'stack', style: 'gap:0' }, h('span', { class: 'small' }, label), h('span', { class: 'caption' }, note)));
  const nothing = !inbox.sources.length && !inbox.candidates.length;
  show(head('Nothing here is judged automatically', 'Inbox'),
    h('div', { class: 'pipeline' }, stage(inbox.sources.length, 'Raw sources', 'immutable · hashed'), h('i', { class: 'wire', 'aria-hidden': 'true' }),
      stage(drafts.length, 'Candidates', 'untrusted drafts · you validate', drafts.length > 0), h('i', { class: 'wire', 'aria-hidden': 'true' }),
      stage(promoted.length, 'Promoted to cases', 'validated · schedulable')),
    h('div', { class: 'inbox-grid' },
      nothing ? h('section', { class: 'card' }, empty('inbox', 'Nothing in the Inbox yet', 'Paste a PTCG Live battle log after your next match, or add a pro match, coach note, external link or manual spot in the panel.'))
        : h('section', { class: 'card', style: 'padding:6px' }, list),
      detail));
  composer();
}

async function viewSource(id) {
  const s = await api('GET', `/api/sources/${id}`);
  const box = errorBox();
  const safeUrl = /^https?:\/\//i.test(s.url) ? h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.url) : s.url;
  const count = h('span', {}, '0');
  const preview = h('pre', { class: 'excerpt mono' });
  const refresh = () => { const picks = [...document.querySelectorAll('input[name="logline"]:checked')].map((x) => Number(x.value));
    count.textContent = String(picks.length);
    preview.textContent = picks.length ? s.content.split('\n').filter((_, i) => picks.includes(i + 1)).join('\n') : 'No lines ticked: the whole source becomes the excerpt.'; };
  const body = s.timeline.length
    ? h('section', { class: 'card', id: 'timeline', style: 'gap:2px' }, h('span', { class: 'caption', style: 'margin-bottom:6px' }, 'Best-effort grouping by “Turn #” headers only. No action is interpreted. Tick the lines relevant to the decision.'),
      s.timeline.map((g) => [h('h3', { class: 'secondary', style: 'padding:12px 0 4px' }, g.title), g.lines.map((l) => h('label', { class: 'logline' },
        h('input', { type: 'checkbox', name: 'logline', value: l.n, on: { change: refresh } }), h('span', { class: 'n' }, String(l.n)), l.text))]))
    : h('section', { class: 'card' }, h('pre', { id: 'raw', class: 'excerpt' }, s.content || '(no content)'));
  const opp = s.metadata && s.metadata.opponent_name;
  show(h('div', { class: 'row small muted' }, h('a', { href: '#inbox' }, 'Inbox'), icon('chevron', 14), `Source #${s.id}`),
    h('div', { class: 'stack', style: 'gap:8px' }, h('h1', { class: 'title' }, s.matchup || s.source_type),
      h('div', { class: 'row caption' }, badge(s.source_type), icon('lock', 14), `Immutable · sha256 ${s.sha256.slice(0, 8)}…${s.sha256.slice(-4)} · stored ${s.created_at.slice(0, 16).replace('T', ' ')}`, safeUrl)),
    h('div', { class: 'inbox-grid' }, body,
      h('section', { class: 'card', style: 'gap:14px' }, h('h2', {}, 'New candidate from ', count, ' lines'), preview,
        opp ? h('div', { class: 'row small secondary' }, h('span', { class: 'ok' }, icon('check', 14)), `Opponent name “${opp}” → OPPONENT in derived data`) : null,
        h('span', { class: 'caption' }, 'Next you write the observed state yourself: only what you knew at the decision. Later lines belong in the full record (hindsight), never shown before answering.'),
        h('div', { class: 'row' }, btn('Create candidate', { id: 'make-candidate', cls: 'primary', ic: 'plus', on: async () => {
          const picks = new Set([...document.querySelectorAll('input[name="logline"]:checked')].map((x) => Number(x.value)));
          const excerpt = picks.size ? s.content.split('\n').filter((_, i) => picks.has(i + 1)).join('\n') : s.content;
          try { const r = await api('POST', '/api/candidates', { source_id: s.id, excerpt }); location.hash = `#inbox/candidate/${r.candidate_id}`; }
          catch (e) { fail(box, e); } } })), box)));
  refresh();
}

async function viewCandidate(id, m) {
  const cand = await api('GET', `/api/candidates/${id}`);
  const d = cand.data, box = errorBox(), draft = cand.status === 'draft';
  let evN = 0;
  const evList = h('div', { id: 'ev-list', class: 'stack' });
  const addEv = (x) => { const p = `ev${evN++}`; evList.append(h('div', { 'data-row': p, class: 'stack' }, evidenceFields(p, x, m.levels),
    h('div', { class: 'row' }, h('button', { class: 'ghost', on: { click: (e) => e.currentTarget.closest('[data-row]').remove() } }, 'Remove evidence')))); };
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
  const promote = async () => {
    try { await save(); const r = await api('POST', `/api/candidates/${id}/promote`);
      if (r.errors.length) throw new Error(r.errors.join('\n'));
      box.replaceChildren(`Promoted to DecisionCase ${r.case_id}. It is now schedulable. `, h('a', { href: `#case/${r.case_id}` }, 'Practise it now'));
      box.className = 'ok small'; box.id = 'promoted'; box.removeAttribute('role'); }
    catch (e) { fail(box, e); } };
  show(h('div', { class: 'row small muted' }, h('a', { href: '#inbox' }, 'Inbox'), icon('chevron', 14), h('a', { href: `#inbox/source/${cand.source_id}` }, `Source #${cand.source_id}`), icon('chevron', 14), `Candidate #${id}`),
    h('div', { class: 'row' }, h('h1', { class: 'title' }, `Candidate #${id}`), badge(draft ? 'Draft · untrusted' : cand.status, cand.status === 'promoted' ? 'success' : ''),
      h('span', { class: 'caption' }, cand.case_id ? `promoted to ${cand.case_id}` : 'You validate every field; nothing is judged automatically.')),
    h('div', { class: 'inbox-grid' },
      h('div', { class: 'stack', style: 'gap:16px' },
        h('section', { class: 'card', style: 'gap:14px' }, h('h2', {}, 'Position and question'),
          field('Case id · optional', h('input', { type: 'text', id: 'c-id', value: d.id || '' })),
          field('Prompt', h('textarea', { id: 'c-prompt', value: d.prompt })),
          field('Observed state', h('textarea', { id: 'c-observed', rows: 8, value: d.observed_state }), 'ONLY what you could know at decision time. No later turns, no revealed hands.'),
          field('Full record / excerpt · hindsight allowed', h('textarea', { id: 'c-full', rows: 6, value: d.full_record }), 'Never shown before answering.'),
          field('Unknown fields · one per line', h('textarea', { id: 'c-unknown', value: (d.unknown_fields || []).join('\n') })),
          field('Choices · one per line, "A: text"', h('textarea', { id: 'c-choices', value: (d.choices || []).map((c) => `${c.key}: ${c.text}`).join('\n') })),
          field('Hint · optional', h('input', { type: 'text', id: 'c-hint', value: d.hint || '' }))),
        h('section', { class: 'card', style: 'gap:14px' }, h('h2', {}, 'Evidence'), h('span', { class: 'caption' }, 'At least one item. Use UNKNOWN when nothing is established. PRO_LINE never carries a verdict.'),
          evList, h('div', { class: 'row' }, btn('Add evidence row', { id: 'add-ev', ic: 'plus', on: () => addEv({}) })))),
      h('div', { class: 'stack', style: 'gap:16px' },
        h('section', { class: 'card', style: 'gap:14px' }, h('h2', {}, 'Provenance and training'),
          h('div', { class: 'form-grid' },
            field('Choice completeness', select('c-completeness', m.completeness, d.completeness)),
            field('Reconstruction confidence', select('c-recon', m.reconstruction, d.reconstruction), 'FACT evidence needs exact or high.'),
            field('Decision family', select('c-family', m.families, d.decision_family)),
            field('Criticality', select('c-crit', [[0, '0 forced'], [1, '1 routine'], [2, '2 meaningful'], [3, '3 high leverage'], [4, '4 game-defining']], d.criticality)),
            field('Transfer level', select('c-transfer', [['L0', 'L0 exact replay'], ['L1', 'L1 cosmetic variant'], ['L2', 'L2 near transfer'], ['L3', 'L3 far transfer']], d.transfer_level)),
            field('Difficulty', select('c-diff', [1, 2, 3], d.difficulty))),
          field('Criticality source', h('input', { type: 'text', id: 'c-crit-src', value: d.criticality_source })),
          field('Variant of case id', h('input', { type: 'text', id: 'c-variant', value: d.variant_of || '' })),
          h('div', { class: 'form-grid' }, field('Matchup', h('input', { type: 'text', id: 'c-matchup', value: d.matchup || '' })),
            field('Format', h('input', { type: 'text', id: 'c-format', value: d.format || '' })),
            field('Date', h('input', { type: 'text', id: 'c-date', value: d.date || '' }))),
          field('Deck version', select('c-deck', [['', '— none —'], ...m.decks.map((x) => [x.hash, `${x.deck_id} v${x.version}`])], d.deck_hash || '')),
          h('span', { class: 'label' }, 'Plan fields the player must commit'),
          h('div', { class: 'stack', style: 'gap:6px' }, m.plan_fields.map((f) => h('label', { class: 'check' }, h('input', { type: 'checkbox', id: `c-req-${f}`, checked: (d.requires || []).includes(f) }), PLAN_LABELS[f]))),
          h('label', { class: 'check' }, h('input', { type: 'checkbox', id: 'c-synth', checked: !!d.synthetic }), 'Synthetic (not a real position)')),
        h('section', { class: 'card', style: 'gap:10px' }, h('h2', {}, 'Concepts'),
          h('div', { id: 'c-concepts', class: 'stack', style: 'gap:6px' }, m.concepts.map((k) => h('label', { class: 'check' },
            h('input', { type: 'checkbox', name: 'c-concept', value: k.id, checked: (d.concepts || []).includes(k.id) }), `${k.name} (${k.skill})`))),
          newConceptForm(m, async () => { await save(); S.meta = null; viewCandidate(id, await meta()); }),
          field('Symptom tags · comma separated', h('input', { type: 'text', id: 'c-symptoms', value: (d.symptom_tags || []).join(', ') })),
          field('Root-cause tags · comma separated', h('input', { type: 'text', id: 'c-causes', value: (d.root_cause_tags || []).join(', ') }))),
        draft ? h('section', { class: 'card', style: 'gap:10px' }, h('div', { class: 'row' },
          btn('Save draft', { id: 'save-cand', on: async () => { try { await save(); box.textContent = 'Saved.'; } catch (e) { fail(box, e); } } }),
          btn('Validate and promote', { id: 'promote', cls: 'primary', ic: 'check', on: promote })),
          h('span', { class: 'caption' }, 'Promoted drafts are frozen; later evidence is appended to the case.'), box) : box)));
}

function newConceptForm(m, done) {
  const box = errorBox();
  return h('details', {}, h('summary', {}, 'New concept'),
    h('div', { class: 'stack', style: 'gap:10px;padding-top:10px' },
      h('div', { class: 'form-grid' }, field('Id · snake_case', h('input', { type: 'text', id: 'k-id' })), field('Name', h('input', { type: 'text', id: 'k-name' })),
        field('Skill', select('k-skill', m.skills, 'planning'))),
      field('Definition', h('textarea', { id: 'k-def' })),
      h('div', { class: 'row' }, btn('Create concept', { id: 'k-save', on: async () => {
        try { await api('POST', '/api/concepts', { id: val('k-id'), name: val('k-name'), skill: val('k-skill'), definition: val('k-def') }); await done(); }
        catch (e) { fail(box, e); } } })), box));
}

// ------------------------------------------------------------------ shell, keyboard, router
function setCount(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }
function setFocus(on) { document.body.classList.toggle('focus', !!on); }
function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch { return null; } return null; }

function shell() {
  document.getElementById('mark').append(icon('clock', 16));
  document.getElementById('collapse').append(icon('sidebar'));
  const cmd = document.getElementById('cmdk');
  cmd.prepend(icon('search', 15)); cmd.append(kbd(`${MOD} K`)); cmd.addEventListener('click', openPalette);
  document.querySelectorAll('[data-icon]').forEach((el) => el.replaceWith(icon(el.dataset.icon)));
  document.getElementById('collapse').addEventListener('click', () => { document.body.classList.toggle('rail'); store('rail', document.body.classList.contains('rail') ? '1' : '0'); });
  if (store('rail') === '1') document.body.classList.add('rail');
  meta().then((m) => { const d = m.decks[m.decks.length - 1];
    if (d) document.getElementById('deck-chip').replaceChildren(h('div', { class: 'row', style: 'gap:8px' }, icon('layers', 14), `${d.deck_id} · v${d.version}`),
      h('span', { class: 'mono' }, `${d.hash.slice(0, 8)} · ${d.format || 'format unset'}`)); }).catch(() => {});
}

// ------------------------------------------------------------------ keyboard: one truth for keys, action bar and palette
// An action is available only when its control is on screen and enabled; onKey, the action bar and the palette all ask live().
const live = (id) => { const el = document.getElementById(id); return el && !el.disabled && el.offsetParent !== null ? el : null; };
const isTyping = (t) => !!(t && t.matches && t.matches('input[type=text], textarea, select, [contenteditable]'));
const currentView = () => (location.hash.slice(1) || 'today').split('/')[0];
const PRIMARY = [['lock', 'Lock plan'], ['submit', 'Submit decision'], ['promote', 'Validate and promote'], ['save-source', 'Save source'], ['make-candidate', 'Create candidate']];
const escTarget = () => (document.body.classList.contains('focus') ? ['#today', 'Exit focus'] : location.hash.startsWith('#inbox/') ? ['#inbox', 'Back to Inbox'] : null);
const nextLabel = () => (live('next')?.tagName === 'A' ? 'Back to Today' : 'Next rep');

function shortcuts() {
  const view = currentView(), typing = isTyping(document.activeElement), out = [];
  const add = (keys, label, ok = true) => { if (ok) out.push([keys, label]); };
  const primary = PRIMARY.find(([id]) => live(id));
  if (primary) add([MOD, '↵'], primary[1]);
  if (!typing) {
    if (view === 'today') { add(['↵'], 'Start session', live('start')); add(['L'], 'Log real match'); }
    if (view === 'case' && S.phase === 'answer') {
      const keys = [...document.querySelectorAll('input[name="choice"]')].map((x) => x.value);
      add(keys.length > 2 ? [keys[0], '–', keys[keys.length - 1]] : keys, 'Choose', keys.length);
      add(['H'], 'Hint', live('hint-btn'));
    }
    if (view === 'case' && S.phase === 'reveal') {
      add(['1', '–', '4'], 'Rate recall', !!document.querySelector('input[name^="recall-"]')?.offsetParent);
      add(['F', 'E', 'N'], 'Fine · Error · Not sure', !!document.querySelector('input[name="self-outcome"]')?.offsetParent);
      add(['↵'], nextLabel(), live('next')); add(['R'], 'Retry', live('retry'));
    }
    if (view === 'case' && S.phase === 'done') { add(['↵'], 'Back to Today', live('back-today')); add(['L'], 'Log real match'); }
    if (view === 'inbox') add(['E'], 'Open editor', live('open-editor'));
  }
  if (typing) add(['Esc'], 'Leave field'); else if (escTarget()) add(['Esc'], escTarget()[1]);
  add([MOD, 'K'], 'Commands');
  return out;
}
const $bar = document.getElementById('actionbar');
let barKey = '', barQueued = false;
function refreshBar() {
  if (barQueued) return; barQueued = true;
  requestAnimationFrame(() => { barQueued = false;
    const items = shortcuts(), key = JSON.stringify(items);
    if (key === barKey) return; barKey = key;   // no DOM churn when nothing changed (the timer ticks every second)
    $bar.replaceChildren(...items.map(([keys, label]) => h('span', { class: 'act' }, keys.map((k) => (k === '–' ? h('i', {}, '–') : kbd(k))), h('span', {}, label))));
  });
}

// ------------------------------------------------------------------ command palette (Ctrl/⌘ K)
const $pal = document.getElementById('palette'), $pin = document.getElementById('palette-input'), $plist = document.getElementById('palette-list');
let pal = { items: [], i: 0, back: null, cases: [] };
function commands() {
  const out = [], go = (hash) => () => { location.hash = hash; };
  for (const [v, t, k] of [['today', 'Today', 'G T'], ['case', 'Case', 'G C'], ['progress', 'Progress', 'G P'], ['inbox', 'Inbox', 'G I']])
    out.push({ group: 'Go to', label: t, hint: k, run: go(`#${v}`) });
  const via = (id, label, group = 'Actions') => { const el = live(id); if (el) out.push({ group, label, run: () => el.click() }); };
  via('start', 'Start session'); via('lock', 'Lock plan'); via('submit', 'Submit decision'); via('hint-btn', 'Use hint · caps memory at Hard');
  via('save-review', 'Save review'); via('next', nextLabel()); via('retry', 'Retry this case'); via('back-today', 'Back to Today');
  via('save-source', 'Save source'); via('make-candidate', 'Create candidate'); via('promote', 'Validate and promote'); via('open-editor', 'Open candidate editor');
  out.push({ group: 'Actions', label: 'Log real match', run: go('#progress/log') });
  if (escTarget()) out.push({ group: 'View', label: escTarget()[1], hint: 'Esc', run: go(escTarget()[0]) });
  if (live('collapse')) out.push({ group: 'View', label: document.body.classList.contains('rail') ? 'Show navigation labels' : 'Compact navigation', run: () => live('collapse').click() });
  for (const c of pal.cases) out.push({ group: 'Practise', label: c.prompt || c.case_id, run: go(`#case/${c.case_id}`) });
  return out;
}
function match(q, text) {   // substring beats in-order letters; 0 = no match
  const t = text.toLowerCase(); if (!q) return 1;
  const at = t.indexOf(q); if (at >= 0) return at === 0 || t[at - 1] === ' ' ? 4 : 3;
  let j = 0; for (const ch of t) if (ch === q[j]) j++;
  return j === q.length ? 1 : 0;
}
function paintPalette() {
  const q = $pin.value.trim().toLowerCase();
  pal.items = commands().map((c, n) => ({ ...c, score: match(q, `${c.label} ${c.group}`), n })).filter((c) => c.score)
    .sort((a, b) => b.score - a.score || a.n - b.n);
  pal.i = Math.min(pal.i, Math.max(pal.items.length - 1, 0));
  $plist.replaceChildren(...(pal.items.length ? pal.items.map((c, n) => h('li', { role: 'option', id: `pal-${n}`, 'aria-selected': n === pal.i ? 'true' : 'false',
    on: { click: () => runCommand(n), mousemove: () => { if (pal.i !== n) { pal.i = n; paintPalette(); } } } },
    h('span', { class: 'pal-label' }, c.label), h('span', { class: 'pal-group' }, c.group), c.hint ? kbd(c.hint) : null))
    : [h('li', { class: 'pal-empty', role: 'presentation' }, 'No matching command')]));
  if (pal.items.length) { $pin.setAttribute('aria-activedescendant', `pal-${pal.i}`); document.getElementById(`pal-${pal.i}`).scrollIntoView({ block: 'nearest' }); }
  else $pin.removeAttribute('aria-activedescendant');
}
function openPalette() {
  if ($pal.open) return;
  pal.back = document.activeElement; pal.i = 0; $pin.value = '';
  paintPalette(); $pal.showModal(); $pin.focus();
  api('GET', '/api/inbox').then((x) => { pal.cases = x.candidates.filter((c) => c.status === 'promoted' && c.case_id); if ($pal.open) paintPalette(); }).catch(() => {});
}
function runCommand(n) { const c = pal.items[n]; $pal.close(); if (c) c.run(); }
$pal.addEventListener('close', () => { const b = pal.back; pal.back = null;
  if (b && b.isConnected && b !== document.body && document.activeElement !== b) b.focus({ preventScroll: true }); refreshBar(); });
$pal.addEventListener('click', (e) => { if (e.target === $pal) $pal.close(); });   // click on the backdrop
$pin.addEventListener('input', () => { pal.i = 0; paintPalette(); });
$pin.addEventListener('keydown', (e) => {
  const n = pal.items.length;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (n) { pal.i = (pal.i + (e.key === 'ArrowDown' ? 1 : n - 1)) % n; paintPalette(); } }
  else if (e.key === 'Enter') { e.preventDefault(); if (n) runCommand(pal.i); }
});

let gPending = false;
function onKey(e) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); return $pal.open ? $pal.close() : openPalette(); }
  if ($pal.open) return;   // the palette handles its own keys; Esc closes it natively
  document.body.classList.add('kbd');
  const t = e.target, typing = isTyping(t);
  const click = (id) => { const el = live(id); if (el) { e.preventDefault(); el.click(); return true; } return false; };
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { PRIMARY.some(([id]) => click(id)); return; }
  if (e.key === 'Escape') { if (typing) return t.blur(); const to = escTarget(); if (to) location.hash = to[0]; return; }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (gPending) { gPending = false; const to = { t: 'today', c: 'case', p: 'progress', i: 'inbox' }[k]; if (to) { location.hash = `#${to}`; e.preventDefault(); } return; }
  if (k === 'g') { gPending = true; setTimeout(() => { gPending = false; }, 1200); return; }
  const view = currentView();
  // Enter acts only when no control has focus (a focused button or link handles Enter natively)
  if (e.key === 'Enter' && (t === document.body || t.getAttribute('tabindex') === '-1')) { click('start') || click('next') || click('back-today'); return; }
  if ((view === 'today' || (view === 'case' && S.phase === 'done')) && k === 'l') { location.hash = '#progress/log'; return; }
  if (view === 'inbox' && k === 'e') return void click('open-editor');
  if (view !== 'case') return;
  if (S.phase === 'answer') {
    if (k === 'h') return void click('hint-btn');
    const choice = document.querySelector(`input[name="choice"][value="${e.key.toUpperCase()}"]`);
    if (choice) { e.preventDefault(); choice.checked = true; choice.focus(); }
    return;
  }
  if (S.phase === 'reveal') {
    if (k === 'r' && click('retry')) return;
    if (['1', '2', '3', '4'].includes(k)) {   // rate the first concept that has no recall yet
      const groups = [...new Set([...document.querySelectorAll('input[name^="recall-"]')].map((x) => x.name))];
      const next = groups.find((g) => !document.querySelector(`input[name="${g}"]:checked`)) || groups[groups.length - 1];
      const r = next && document.querySelector(`input[name="${next}"][value="${k}"]`); if (r) { r.checked = true; r.focus(); }
      return;
    }
    const so = { f: 'ok', e: 'error', n: '' }[k];
    if (so !== undefined) { const r = document.querySelector(`input[name="self-outcome"][value="${so}"]`); if (r) { r.checked = true; r.focus(); } }
  }
}

async function render() {
  const parts = (location.hash.slice(1) || 'today').split('/');
  document.querySelectorAll('.nav a').forEach((a) => { const on = a.dataset.view === parts[0]; a.classList.toggle('active', on); if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  if (parts[0] !== 'case') { setFocus(false); document.body.classList.remove('deep-focus'); }
  clearInterval(timer);
  try {
    await ({ today: viewToday, case: viewCase, progress: viewProgress, inbox: viewInbox }[parts[0]] || viewToday)(parts);
  } catch (e) { show(h('p', { class: 'error', role: 'alert' }, e.message)); }
  refreshBar();
}
shell();
window.addEventListener('hashchange', render);
document.addEventListener('keydown', onKey);
document.addEventListener('pointerdown', () => document.body.classList.remove('kbd'));
document.addEventListener('focusin', refreshBar);
document.addEventListener('focusout', refreshBar);
new MutationObserver(refreshBar).observe($main, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'disabled'] });
render();

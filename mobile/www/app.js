/*
 * CampusHub mobile app (PWA / Capacitor).
 * Talks to the unchanged FastAPI backend (main.py). Screens, validation rules and
 * messages mirror ui.py. Plain JavaScript: no build step, no CDN, works offline.
 */
(() => {
  'use strict';

  // ============================================================
  // CONSTANTS  (keep identical to ui.py / schemas.py)
  // ============================================================
  const UNIVERSITIES = [
    'Midlands State University',
    'University of Zimbabwe',
    'National University of Science and Technology',
    'Harare Institute of Technology',
    'Great Zimbabwe University',
  ];
  const EXPENSE_CATEGORIES = ['Food', 'Transport', 'Data', 'Printing', 'Accommodation', 'Other'];
  const WEEKS = ['Week 1', 'Week 2', 'Week 3', 'Week 4'];
  const FEEDBACK_TYPES = ['Bug report', 'Suggestion', 'Compliment', 'Other'];
  const NAV = [
    { name: 'Dashboard', slug: 'dashboard' },
    { name: 'Study Hub', slug: 'study' },
    { name: 'Budget Assistance', slug: 'budget' },
    { name: 'Marketplace', slug: 'marketplace' },
    { name: 'Events', slug: 'events' },
    { name: 'Settings', slug: 'settings' },
  ];
  const SUPPORT_EMAIL = 'support@campushub.example'; // replace with your real contact address
  const LEGAL_UPDATED = '30 September 2026';
  const REQUEST_TIMEOUT = 15000;
  const AI_TIMEOUT = 180000; // local Ollama models can be slow on a laptop CPU
  const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

  const PRIVACY_POLICY = `**Last updated: ${LEGAL_UPDATED}**

CampusHub is a student platform that combines study tools, a budget assistant, a student marketplace and a campus events board. This policy explains what information the app handles and why.

**1. Information we collect**
- **Account details:** your name, university email address, university and password. Your password is stored only as a salted hash, never in readable form.
- **Budget data:** the income figure you save and the expenses you log.
- **Marketplace listings:** item names, prices and the contact details you choose to publish.
- **Study content:** notes you upload and questions you ask the AI study partner.
- **Feedback:** messages you send from the Settings page.

**2. How we use your information**
- To create your account and keep you signed in.
- To provide the Study Hub, Budget Assistance, Marketplace and Events features.
- To improve the app using the feedback you send.

**3. AI processing**
When you summarise notes, generate a quiz or ask a question, the text is sent to third-party AI providers (currently Google Gemini and Groq) to produce a response. CampusHub does not keep a copy of uploaded files or AI responses. The providers handle data under their own policies, so please do not upload private or confidential material.

**4. Who can see your information**
- Marketplace listings, including the contact details you enter and your name as seller, are visible to other signed-in students.
- Your income, expenses and feedback are private to your account.
- We do not sell your personal information.

**5. Security**
Passwords are hashed and sessions use signed tokens that expire. No system is completely secure, so please use a strong, unique password.

**6. Retention and deletion**
Your information is kept until you delete your account. You can do this at any time under **Settings > Account**, which permanently removes your profile, expenses, marketplace listings and feedback.

**7. Your rights**
You may ask to see, correct or delete the information we hold about you. Contact us at ${SUPPORT_EMAIL}.

**8. Changes**
We may update this policy. The date above shows when it last changed.`;

  const USER_AGREEMENT = `**Last updated: ${LEGAL_UPDATED}**

By creating an account or using CampusHub you agree to these terms.

**1. Eligibility and accounts**
CampusHub is intended for university students. You are responsible for the accuracy of your details and for keeping your password secure. Do not share your account.

**2. Acceptable use**
You agree not to:
- post illegal, stolen, counterfeit or dangerous items in the Marketplace;
- harass, deceive or threaten other users;
- attempt to break, overload or gain unauthorised access to the service;
- upload material you do not have the right to share.

**3. Marketplace**
CampusHub only lets students list and find items. We are not a party to any sale and do not inspect, guarantee or insure items. Meet in safe, public campus locations and check items before paying.

**4. AI study tools**
AI output can be inaccurate or incomplete. Verify important information with your lecturers and course materials. Follow your university's academic integrity rules when using AI assistance for coursework.

**5. Budget Assistance**
The budget tools are for personal tracking only and are not financial advice.

**6. Your content**
You keep ownership of what you post. You give CampusHub permission to store and display it as needed to run the service, for example showing your listing to other students.

**7. Suspension and deletion**
We may suspend accounts that break these terms. You can delete your account at any time under **Settings > Account**.

**8. Service and liability**
The service is provided "as is", without guarantees of uninterrupted operation. To the extent the law allows, CampusHub is not liable for losses arising from use of the service or from dealings between users.

**9. Changes and contact**
We may update these terms, and continued use means you accept the changes. Questions: ${SUPPORT_EMAIL}.`;

  // ============================================================
  // HELPERS
  // ============================================================
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (v) =>
    String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const money = (n) =>
    '$' + Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const validEmail = (e) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const store = {
    get(key, dflt) {
      try {
        const raw = localStorage.getItem('ch_' + key);
        return raw === null ? dflt : JSON.parse(raw);
      } catch { return dflt; }
    },
    set(key, value) { try { localStorage.setItem('ch_' + key, JSON.stringify(value)); } catch { /* storage unavailable */ } },
    del(key) { try { localStorage.removeItem('ch_' + key); } catch { /* ignore */ } },
  };

  /** Minimal, safe Markdown renderer for AI output and legal text (escapes HTML first). */
  function md(src) {
    const inline = (s) =>
      esc(s)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    const lines = String(src ?? '').replace(/\r/g, '').split('\n');
    let out = '', list = null, para = [], code = null;
    const flushPara = () => { if (para.length) { out += '<p>' + para.map(inline).join('<br>') + '</p>'; para = []; } };
    const closeList = () => { if (list) { out += `</${list}>`; list = null; } };
    for (const raw of lines) {
      if (code !== null) {
        if (/^```/.test(raw)) { out += '<pre><code>' + esc(code.join('\n')) + '</code></pre>'; code = null; }
        else code.push(raw);
        continue;
      }
      if (/^```/.test(raw)) { flushPara(); closeList(); code = []; continue; }
      const line = raw.trimEnd();
      if (!line.trim()) { flushPara(); closeList(); continue; }
      let m;
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
        flushPara(); closeList();
        const lvl = Math.min(m[1].length + 2, 6);
        out += `<h${lvl}>${inline(m[2])}</h${lvl}>`;
        continue;
      }
      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { flushPara(); closeList(); out += '<hr>'; continue; }
      if ((m = line.match(/^\s*[-*+]\s+(.*)$/))) {
        flushPara();
        if (list !== 'ul') { closeList(); out += '<ul>'; list = 'ul'; }
        out += `<li>${inline(m[1])}</li>`;
        continue;
      }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
        flushPara();
        if (list !== 'ol') { closeList(); out += '<ol>'; list = 'ol'; }
        out += `<li>${inline(m[1])}</li>`;
        continue;
      }
      closeList();
      para.push(line);
    }
    if (code !== null) out += '<pre><code>' + esc(code.join('\n')) + '</code></pre>';
    flushPara(); closeList();
    return out;
  }

  // ============================================================
  // STATE
  // ============================================================
  const S = {
    token: store.get('token', ''),
    user: store.get('user', null),
    page: 'Dashboard',
    tabs: {},
    flash: null,
    timer: { end: null, total: 0, done: false, duration: 25 },
  };
  let renderSeq = 0;
  let timerHandle = null;
  let flushing = false;

  // ============================================================
  // API LAYER  (the only place that talks to the backend)
  // ============================================================
  class ApiError extends Error {
    constructor(message, status = null, network = false) {
      super(message);
      this.status = status;
      this.network = network;
    }
  }

  /** True when this page is served by the backend itself (same origin), e.g. http://PC:8000/app/ */
  const sameOrigin = () => location.protocol.startsWith('http') && location.pathname.startsWith('/app');

  function normaliseServerUrl(value) {
    let v = String(value || '').trim().replace(/\/+$/, '');
    if (v && !/^https?:\/\//i.test(v)) v = 'http://' + v;
    return v;
  }
  const apiBase = () => (sameOrigin() ? location.origin : normaliseServerUrl(store.get('server', '')));

  function errorMessage(body, status) {
    if (body && typeof body === 'object') {
      const detail = body.detail || body.message || body.error;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail) && detail.length && typeof detail[0] === 'object') {
        const field = (detail[0].loc || []).slice(1).join('.');
        const message = detail[0].msg || 'Invalid input.';
        return field ? `${field}: ${message}` : message;
      }
      if (detail) return String(detail);
    }
    return `Request failed (${status}).`;
  }

  async function api(method, path, { json, form, auth = true, timeout = REQUEST_TIMEOUT } = {}) {
    const base = apiBase();
    if (!base) throw new ApiError('Enter the server address under Server settings first.');
    const headers = {};
    if (auth && S.token) headers.Authorization = `Bearer ${S.token}`;
    let body;
    if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
    else if (form) body = form;

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    let res;
    try {
      res = await fetch(base + path, { method, headers, body, signal: ctrl.signal });
    } catch (err) {
      if (err && err.name === 'AbortError') throw new ApiError('The server took too long to respond. Please try again.');
      setOffline(true);
      throw new ApiError('Cannot reach the server. Check that the backend is running.', null, true);
    } finally {
      clearTimeout(timer);
    }
    setOffline(false);

    if (!res.ok) {
      let parsed = null;
      try { parsed = await res.json(); } catch { /* not JSON */ }
      throw new ApiError(errorMessage(parsed, res.status), res.status);
    }
    const text = await res.text();
    if (!text) return {};
    try { return JSON.parse(text); } catch { return {}; }
  }

  const apiRegister = (name, email, university, password) =>
    api('POST', '/auth/register', { json: { name, email, university, password }, auth: false });

  async function apiLogin(email, password) {
    const data = await api('POST', '/auth/login', { json: { email, password }, auth: false });
    const token = data.access_token || data.token;
    if (!token) throw new ApiError('The server did not return a login token.');
    let user = data.user;
    if (!user) { S.token = token; user = await api('GET', '/auth/me'); }
    return { token, user };
  }

  const apiGetIncome = async () => Number((await api('GET', '/income')).income || 0);
  const apiSetIncome = (amount) => api('PUT', '/income', { json: { income: Number(amount) } });
  async function apiGetExpenses() {
    let rows = await api('GET', '/expenses');
    if (rows && !Array.isArray(rows)) rows = rows.items || [];
    return rows.map((r) => ({
      week: r.week || r.Week, category: r.category || r.Category, amount: Number(r.amount || r.Amount || 0),
    }));
  }
  const apiAddExpense = (week, category, amount) =>
    api('POST', '/expenses', { json: { week, category, amount: Number(amount) } });
  async function apiGetListings() {
    const rows = await api('GET', '/marketplace');
    return Array.isArray(rows) ? rows : rows.items || [];
  }
  const apiAddListing = (title, price, contact) =>
    api('POST', '/marketplace', { json: { title, price: Number(price), contact } });
  async function apiGetEvents() {
    const rows = await api('GET', '/events');
    return Array.isArray(rows) ? rows : rows.items || [];
  }
  async function apiAiProcessFile(action, file) {
    const form = new FormData();
    form.append('file', file, file.name);
    const data = await api('POST', action === 'Summarize Notes' ? '/ai/summarize' : '/ai/quiz', { form, timeout: AI_TIMEOUT });
    return data.result || '';
  }
  async function apiAiAsk(moduleCode, question) {
    const data = await api('POST', '/ai/ask', { json: { module_code: moduleCode, question }, timeout: AI_TIMEOUT });
    return data.result || '';
  }
  const apiSendFeedback = (category, message) => api('POST', '/feedback', { json: { category, message } });
  const apiDeleteAccount = (password) => api('POST', '/account/delete', { json: { password } });

  // ============================================================
  // OFFLINE SUPPORT: cached reads + queued expenses
  // ============================================================
  function setOffline(value) {
    document.body.classList.toggle('is-offline', !!value);
    if (!value) flushQueue();
  }

  const cacheKey = (k) => `cache:${S.user ? S.user.email : ''}:${k}`;
  const queueKey = () => `queue:${S.user ? S.user.email : ''}`;
  const getQueue = () => (S.user ? store.get(queueKey(), []) : []);

  async function cachedGet(key, fn, dflt) {
    try {
      const value = await fn();
      store.set(cacheKey(key), value);
      return value;
    } catch (err) {
      if (err.network) {
        const saved = store.get(cacheKey(key), null);
        return saved !== null ? saved : dflt;
      }
      handleError(err);
      return dflt;
    }
  }

  async function flushQueue() {
    if (!S.token || !S.user || flushing) return;
    const queue = getQueue();
    if (!queue.length) return;
    flushing = true;
    try {
      await api('POST', '/budget/sync-push', { json: queue.map(({ week, category, amount }) => ({ week, category, amount })) });
      store.set(queueKey(), []);
      toast('success', `Synced ${queue.length} offline expense${queue.length > 1 ? 's' : ''}.`);
      if (S.page === 'Budget Assistance' || S.page === 'Dashboard') renderPage();
    } catch (err) {
      if (err.status === 401) handleError(err);
      // otherwise keep the items queued and try again later
    } finally {
      flushing = false;
    }
  }

  const loadIncome = () => cachedGet('income', apiGetIncome, 0);
  const loadListings = () => cachedGet('listings', apiGetListings, []);
  const loadEvents = () => cachedGet('events', apiGetEvents, []);
  async function loadExpenses() {
    const server = await cachedGet('expenses', apiGetExpenses, []);
    const pending = getQueue().map((q) => ({ week: q.week, category: q.category, amount: q.amount, pending: true })).reverse();
    return [...pending, ...server];
  }

  // ============================================================
  // UI PRIMITIVES
  // ============================================================
  function toast(type, message) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    const box = $('#toasts');
    while (box.children.length >= 3) box.firstChild.remove(); // never stack more than three messages
    box.appendChild(el);
    setTimeout(() => el.remove(), type === 'error' ? 5500 : 3500);
  }

  function showLoader(message) { $('#loaderText').textContent = message; $('#loader').hidden = false; }
  function hideLoader() { $('#loader').hidden = true; }

  function handleError(err) {
    if (err.status === 401 && S.token) {
      signOut();
      render();
      toast('error', err.message);
      return;
    }
    if (err.status === 401) return;
    toast('error', err.message || 'Something went wrong.');
  }

  function tabsHtml(id, names) {
    const cur = S.tabs[id] ?? 0;
    return `<div class="tabs" data-tabs="${id}" role="tablist">${names
      .map((n, i) => `<button type="button" class="tab ${i === cur ? 'active' : ''}" data-i="${i}" role="tab">${esc(n)}</button>`)
      .join('')}</div>`;
  }
  const panel = (id, i, html) =>
    `<section data-panel="${id}:${i}" ${(S.tabs[id] ?? 0) === i ? '' : 'hidden'}>${html}</section>`;

  function bindTabs(root) {
    $$('.tabs[data-tabs]', root).forEach((bar) => {
      const id = bar.dataset.tabs;
      bar.addEventListener('click', (ev) => {
        const btn = ev.target.closest('.tab');
        if (!btn) return;
        const i = Number(btn.dataset.i);
        S.tabs[id] = i;
        $$('.tab', bar).forEach((t) => t.classList.toggle('active', Number(t.dataset.i) === i));
        $$(`[data-panel^="${id}:"]`, root).forEach((p) => { p.hidden = p.dataset.panel !== `${id}:${i}`; });
      });
    });
  }

  const inlineLoader = (msg = 'Loading...') =>
    `<div class="inline-loader"><div class="loader-ring"></div><span>${esc(msg)}</span></div>`;

  const options = (list, selected) =>
    list.map((o) => `<option value="${esc(o)}" ${o === selected ? 'selected' : ''}>${esc(o)}</option>`).join('');

  async function busy(button, label, fn) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = label;
    try { return await fn(); }
    finally { button.disabled = false; button.textContent = original; }
  }

  // ============================================================
  // SESSION
  // ============================================================
  function signOut() {
    S.token = '';
    S.user = null;
    S.timer = { end: null, total: 0, done: false, duration: 25 };
    S.tabs = {};
    renderSeq++; // cancel any page that is still loading for the signed-out user
    stopTimer();
    store.del('token');
    store.del('user');
    document.body.classList.remove('nav-open');
    if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    S.page = 'Dashboard';
  }

  // ============================================================
  // AUTHENTICATION
  // ============================================================
  function authView() {
    const flash = S.flash;
    S.flash = null;
    const showServer = !sameOrigin();
    const server = esc(store.get('server', ''));
    return `
      <div class="auth">
        <section class="brand-panel">
          <div class="brand-mark">CH</div>
          <h1>CampusHub</h1>
          <p style="font-size:1.1rem;">Your campus. Your community. Your digital hub.</p>
          <p>CampusHub brings your academic, financial and student activities together in one platform.</p>
          <div class="brand-features">
            <div class="brand-feature"><b>Study</b><span>Access your study tools.</span></div>
            <div class="brand-feature"><b>Connect</b><span>Interact with other students.</span></div>
            <div class="brand-feature"><b>Manage</b><span>Manage your campus life.</span></div>
          </div>
        </section>
        <section class="login-panel">
          ${flash ? `<div class="alert success">${esc(flash)}</div>` : ''}
          ${tabsHtml('auth', ['Login', 'Create Account'])}
          ${panel('auth', 0, `
            <h2>Welcome back</h2>
            <p class="caption">Sign in to continue to your CampusHub dashboard.</p>
            <form id="loginForm" novalidate>
              <label class="field"><span>University email</span>
                <input type="email" name="email" placeholder="student@example.com" autocomplete="username" autocapitalize="none"></label>
              <label class="field"><span>Password</span>
                <input type="password" name="password" placeholder="Enter your password" autocomplete="current-password"></label>
              <button class="btn" type="submit">Login to CampusHub</button>
            </form>`)}
          ${panel('auth', 1, `
            <h2>Create your account</h2>
            <p class="caption">Register as a student to access the CampusHub platform.</p>
            <form id="registerForm" novalidate>
              <div class="row">
                <label class="field"><span>Full name</span><input type="text" name="name" placeholder="Enter your full name" autocomplete="name"></label>
                <label class="field"><span>University email</span><input type="email" name="email" placeholder="student@example.com" autocomplete="email" autocapitalize="none"></label>
              </div>
              <label class="field"><span>University</span><select name="university">${options(UNIVERSITIES)}</select></label>
              <div class="row">
                <label class="field"><span>Create password</span><input type="password" name="password" placeholder="Minimum 6 characters" autocomplete="new-password"></label>
                <label class="field"><span>Confirm password</span><input type="password" name="confirm" placeholder="Re-enter your password" autocomplete="new-password"></label>
              </div>
              <label class="check"><input type="checkbox" name="agree">
                <span>I agree to the CampusHub User Agreement and Privacy Policy (available under Settings after you sign in).</span></label>
              <button class="btn" type="submit">Create Account</button>
            </form>`)}
          ${showServer ? `
            <details class="server" ${server ? '' : 'open'}>
              <summary>Server settings</summary>
              <label class="field" style="margin-top:10px"><span>Server address</span>
                <input type="url" id="serverInput" value="${server}" placeholder="http://192.168.1.10:8000" autocapitalize="none" autocomplete="off"></label>
              <p class="caption">The address of the PC running CampusHub. Android emulator: http://10.0.2.2:8000</p>
            </details>` : ''}
        </section>
      </div>`;
  }

  function bindAuth(root) {
    bindTabs(root);
    const serverInput = $('#serverInput', root);
    if (serverInput) serverInput.addEventListener('change', () => store.set('server', normaliseServerUrl(serverInput.value)));

    const requireServer = () => {
      if (!serverInput) return true;
      const v = normaliseServerUrl(serverInput.value);
      if (!v) {
        toast('error', 'Enter the server address under Server settings.');
        const d = $('details.server', root);
        if (d) d.open = true;
        serverInput.focus();
        return false;
      }
      store.set('server', v);
      serverInput.value = v;
      return true;
    };

    $('#loginForm', root).addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      const email = f.email.value.trim().toLowerCase();
      const password = f.password.value;
      if (!email || !password) return toast('error', 'Enter both your email and password.');
      if (!requireServer()) return;

      showLoader('Signing you in...');
      let result;
      try {
        result = await apiLogin(email, password);
      } catch (err) {
        hideLoader();
        S.token = '';
        return toast('error', err.message);
      }
      S.token = result.token;
      S.user = {
        name: result.user.name || '',
        email: result.user.email || email,
        university: result.user.university || '',
      };
      store.set('token', S.token);
      store.set('user', S.user);

      $('#loaderText').textContent = 'Preparing your dashboard...';
      await sleep(900);
      hideLoader();
      S.page = pageFromHash();
      render();
      flushQueue();
    });

    $('#registerForm', root).addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      const name = f.name.value.trim();
      const email = f.email.value.trim().toLowerCase();
      const { password, confirm, university } = { password: f.password.value, confirm: f.confirm.value, university: f.university.value };
      if (!name) return toast('error', 'Enter your full name.');
      if (!email) return toast('error', 'Enter your university email.');
      if (!validEmail(email)) return toast('error', 'Enter a valid email address.');
      if (!password) return toast('error', 'Create a password.');
      if (password.length < 6) return toast('error', 'The password must contain at least 6 characters.');
      if (password !== confirm) return toast('error', 'The passwords do not match.');
      if (!f.agree.checked) return toast('error', 'You must agree to the terms and conditions.');
      if (!requireServer()) return;

      const btn = $('button[type=submit]', f);
      try {
        await busy(btn, 'Creating your account...', () => apiRegister(name, email, university, password));
      } catch (err) {
        return toast('error', err.message);
      }
      S.tabs.auth = 0;
      S.flash = 'Account created successfully. You can now sign in.';
      render();
      const login = $('#loginForm');
      if (login) login.email.value = email;
    });
  }

  // ============================================================
  // SHELL (top bar, sidebar)
  // ============================================================
  function shellView() {
    return `
      <div class="shell">
        <header class="topbar">
          <button class="icon-btn" id="menuBtn" aria-label="Open menu">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>
          <div class="topbar-title">CampusHub</div>
        </header>
        <div class="offline-banner">Offline. Showing saved data. New expenses will sync when you reconnect.</div>
        <div class="scrim" id="scrim"></div>
        <aside class="sidebar" id="sidebar">
          <div class="side-brand"><b>CampusHub</b><small>Your Campus, Connected</small></div>
          <div class="user-card">
            <div class="n">${esc(S.user.name)}</div>
            <div class="e">${esc(S.user.email)}</div>
            <div class="u">${esc(S.user.university)}</div>
          </div>
          <div class="side-h">Navigation</div>
          <nav id="nav">${NAV.map((n) => `<button class="nav-link" data-slug="${n.slug}">${esc(n.name)}</button>`).join('')}</nav>
          <div class="side-spacer"></div>
          <hr style="border-color:rgba(255,255,255,.18)">
          <button class="side-btn" id="logoutBtn">Log Out</button>
        </aside>
        <main class="content" id="content"></main>
      </div>`;
  }

  function bindShell() {
    const closeNav = () => document.body.classList.remove('nav-open');
    $('#menuBtn').addEventListener('click', () => document.body.classList.add('nav-open'));
    $('#scrim').addEventListener('click', closeNav);
    $('#nav').addEventListener('click', (ev) => {
      const b = ev.target.closest('.nav-link');
      if (!b) return;
      closeNav();
      go(NAV.find((n) => n.slug === b.dataset.slug).name);
    });
    $('#logoutBtn').addEventListener('click', () => { signOut(); render(); });
  }

  function updateNav() {
    $$('.nav-link').forEach((b) => b.classList.toggle('active', NAV.find((n) => n.slug === b.dataset.slug).name === S.page));
  }

  const slugOf = (name) => NAV.find((n) => n.name === name).slug;
  function pageFromHash() {
    const slug = location.hash.replace(/^#\/?/, '');
    const hit = NAV.find((n) => n.slug === slug);
    return hit ? hit.name : 'Dashboard';
  }
  function go(name) {
    if (name === S.page) return renderPage();
    location.hash = '#/' + slugOf(name); // the hashchange handler renders; keeps the Android back button working
  }

  // ============================================================
  // PAGES
  // ============================================================
  async function pageDashboard(el, seq) {
    const [expenses, listings, events] = await Promise.all([loadExpenses(), loadListings(), loadEvents()]);
    if (seq !== renderSeq) return;
    const total = expenses.reduce((s, e) => s + e.amount, 0);
    const card = (page, title, body) => `
      <button class="info-card nav-card" data-go="${esc(page)}">
        <h3>${esc(title)}</h3><p>${esc(body)}</p><span class="card-cta">Open ${esc(title)} &rarr;</span>
      </button>`;
    el.innerHTML = `
      <h1>Welcome, ${esc(S.user.name)}</h1>
      <p>Everything you need for your university life in one place.</p>
      <div class="metrics">
        <div class="metric"><div class="label">Study Hub</div><div class="value">Active</div></div>
        <div class="metric"><div class="label">Expenses</div><div class="value">${money(total)}</div></div>
        <div class="metric"><div class="label">Marketplace Listings</div><div class="value">${listings.length}</div></div>
        <div class="metric"><div class="label">Events</div><div class="value">${events.length}</div></div>
      </div>
      <p class="caption">Select a card to open it.</p>
      <div class="grid-2">
        ${card('Study Hub', 'Study Hub', 'Upload lecture materials, generate summaries, create quizzes and ask questions about your modules.')}
        ${card('Budget Assistance', 'Budget Assistance', 'Track weekly student expenses and monitor your spending patterns.')}
        ${card('Marketplace', 'Student Marketplace', 'Buy and sell textbooks, electronics, hostel items and other campus products.')}
        ${card('Events', 'Campus Events', 'Stay updated with university deadlines, club activities and student events.')}
      </div>`;
    $$('[data-go]', el).forEach((b) => b.addEventListener('click', () => go(b.dataset.go)));
  }

  // ---------- Study Hub ----------
  function stopTimer() { if (timerHandle) { clearInterval(timerHandle); timerHandle = null; } }

  function timerTick() {
    const box = $('#timerBox');
    if (!box) return stopTimer();
    const T = S.timer;
    if (T.end === null) {
      stopTimer();
      box.innerHTML = T.done
        ? '<div class="progress"><div class="progress-fill" style="width:100%"></div></div><div class="progress-text">Session complete</div><div class="alert success">Study session complete. Take a short break.</div>'
        : '<div class="alert info">No study session is running.</div>';
      return;
    }
    const remaining = Math.ceil((T.end - Date.now()) / 1000);
    if (remaining <= 0) {
      T.end = null; T.done = true;
      try { navigator.vibrate && navigator.vibrate([200, 100, 200]); } catch { /* unsupported */ }
      return timerTick();
    }
    const fraction = Math.min(Math.max(1 - remaining / T.total, 0), 1);
    const mm = String(Math.floor(remaining / 60)).padStart(2, '0');
    const ss = String(remaining % 60).padStart(2, '0');
    box.innerHTML = `<div class="progress"><div class="progress-fill" style="width:${(fraction * 100).toFixed(1)}%"></div></div>
      <div class="progress-text">Time remaining: ${mm}:${ss}</div>`;
  }

  async function pageStudy(el) {
    el.innerHTML = `
      <h1>Study Hub</h1>
      <p>Your central area for academic productivity.</p>
      ${tabsHtml('study', ['Study Timer', 'Study Materials', 'AI Partner'])}
      ${panel('study', 0, `
        <h2>Lecture Reminder and Study Timer</h2>
        <div class="grid-2">
          <div class="info-card">
            <h3>Next Lecture</h3>
            <p><b>CS201 Software Engineering</b></p><p>08:30 AM</p><p>Batanai Campus</p>
          </div>
          <div class="box">
            <label class="field"><span>Study duration (minutes)</span>
              <input type="number" id="timerDuration" min="1" max="180" step="1" inputmode="numeric" value="${S.timer.duration}"></label>
            <div class="row">
              <button class="btn" id="timerStart" type="button">Start Session</button>
              <button class="btn" id="timerStop" type="button">Stop Session</button>
            </div>
            <div id="timerBox" style="margin-top:12px"></div>
          </div>
        </div>`)}
      ${panel('study', 1, `
        <h2>Upload Study Material</h2>
        <input type="file" id="studyFile" accept=".txt,.pdf,text/plain,application/pdf">
        <div id="fileActions"></div>
        <div id="fileResult" class="result"></div>`)}
      ${panel('study', 2, `
        <h2>Ask Your AI Study Partner</h2>
        <label class="field"><span>Module code</span><input type="text" id="moduleCode" placeholder="Example: CS101" autocapitalize="characters"></label>
        <label class="field"><span>Your question</span><textarea id="studyQuestion" placeholder="Ask anything about your module..."></textarea></label>
        <button class="btn" id="askAi" type="button">Ask AI</button>
        <div id="askResult" class="result"></div>`)}`;
    bindTabs(el);

    // Timer
    const startTimerLoop = () => { stopTimer(); timerHandle = setInterval(timerTick, 1000); };
    $('#timerStart').addEventListener('click', () => {
      const minutes = Math.min(Math.max(parseInt($('#timerDuration').value, 10) || 25, 1), 180);
      S.timer = { duration: minutes, total: minutes * 60, end: Date.now() + minutes * 60 * 1000, done: false };
      $('#timerDuration').value = minutes;
      timerTick(); startTimerLoop();
    });
    $('#timerStop').addEventListener('click', () => { S.timer.end = null; S.timer.done = false; timerTick(); });
    timerTick();
    if (S.timer.end !== null) startTimerLoop();

    // Study materials
    const fileInput = $('#studyFile');
    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      $('#fileResult').innerHTML = '';
      if (!file) { $('#fileActions').innerHTML = ''; return; }
      $('#fileActions').innerHTML = `
        <div class="alert success">${esc(file.name)} is ready to process.</div>
        <div class="radio-row">
          <label><input type="radio" name="aiAction" value="Summarize Notes" checked> Summarize Notes</label>
          <label><input type="radio" name="aiAction" value="Generate Quiz"> Generate Quiz</label>
        </div>
        <button class="btn" id="processBtn" type="button">Process Material</button>`;
      $('#processBtn').addEventListener('click', async (ev) => {
        if (file.size > MAX_UPLOAD_BYTES) return toast('error', 'File is too large (5 MB maximum).');
        const action = $('input[name=aiAction]:checked').value;
        try {
          const result = await busy(ev.target, 'Processing your material...', () => apiAiProcessFile(action, file));
          $('#fileResult').innerHTML = result
            ? `<h3>Result</h3><div class="md">${md(result)}</div>`
            : '<div class="alert info">The server returned an empty result.</div>';
        } catch (err) { handleError(err); }
      });
    });

    // AI partner
    $('#askAi').addEventListener('click', async (ev) => {
      const code = $('#moduleCode').value.trim();
      const question = $('#studyQuestion').value.trim();
      if (!code || !question) return toast('error', 'Enter a module code and a question.');
      try {
        const answer = await busy(ev.target, 'Thinking...', () => apiAiAsk(code.toUpperCase(), question));
        $('#askResult').innerHTML = answer
          ? `<h3>Answer</h3><div class="md">${md(answer)}</div>`
          : '<div class="alert info">The server returned an empty answer.</div>';
      } catch (err) { handleError(err); }
    });
  }

  // ---------- Budget ----------
  function weeklyBarsHtml(totals) {
    const peak = Math.max(...Object.values(totals), 1);
    return `<div class="info-card">${WEEKS.map((w) => `
      <div class="bar-row">
        <span class="bar-label">${esc(w)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${((totals[w] / peak) * 100).toFixed(1)}%"></div></div>
        <span class="bar-value">${money(totals[w])}</span>
      </div>`).join('')}</div>`;
  }

  function expensesTableHtml(expenses) {
    const rows = expenses.slice(0, 100).map((r) =>
      `<tr><td>${esc(r.week)}</td><td>${esc(r.category)}${r.pending ? '<span class="tag">Pending sync</span>' : ''}</td><td>${money(r.amount)}</td></tr>`).join('');
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Week</th><th>Category</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  async function pageBudget(el, seq) {
    const [income, expenses] = await Promise.all([loadIncome(), loadExpenses()]);
    if (seq !== renderSeq) return;
    const spent = expenses.reduce((s, e) => s + e.amount, 0);
    const totals = Object.fromEntries(WEEKS.map((w) => [w, 0]));
    expenses.forEach((e) => { if (e.week in totals) totals[e.week] += e.amount; });

    el.innerHTML = `
      <h1>Budget Assistance</h1>
      <p class="caption">Manual finance tracking is enabled. Automatic EcoCash or bank synchronization has not been connected.</p>
      <div class="grid-2">
        <div class="box">
          <h2>Log Finances</h2>
          <label class="field"><span>Income total ($)</span>
            <input type="number" id="incomeInput" min="0" step="1" inputmode="decimal" value="${income}"></label>
          <button class="btn" id="saveIncome" type="button">Save Income</button>
          <hr>
          <label class="field"><span>Expense amount ($)</span>
            <input type="number" id="expAmount" min="0" step="0.5" inputmode="decimal" value="0"></label>
          <div class="row">
            <label class="field"><span>Expense category</span><select id="expCat">${options(EXPENSE_CATEGORIES)}</select></label>
            <label class="field"><span>Target week</span><select id="expWeek">${options(WEEKS)}</select></label>
          </div>
          <button class="btn" id="addExpense" type="button">Add Expense</button>
        </div>
        <div>
          <h2>Financial Summary</h2>
          <div class="metrics stack">
            <div class="metric"><div class="label">Income</div><div class="value">${money(income)}</div></div>
            <div class="metric"><div class="label">Total Expenses</div><div class="value">${money(spent)}</div></div>
            <div class="metric"><div class="label">Remaining Balance</div><div class="value">${money(income - spent)}</div></div>
          </div>
        </div>
      </div>
      <hr>
      <h2>Weekly Spending</h2>
      ${expenses.length ? `<div class="grid-2"><div>${weeklyBarsHtml(totals)}</div><div><b>Expense history</b><div style="margin-top:8px">${expensesTableHtml(expenses)}</div></div></div>`
        : '<div class="alert info">No expenses recorded yet.</div>'}`;

    $('#saveIncome').addEventListener('click', async (ev) => {
      const value = parseFloat($('#incomeInput').value);
      if (!(value >= 0)) return toast('error', 'Enter a valid income amount.');
      try {
        await busy(ev.target, 'Saving...', () => apiSetIncome(value));
        toast('success', 'Income saved.');
        renderPage();
      } catch (err) { handleError(err); }
    });

    $('#addExpense').addEventListener('click', async (ev) => {
      const amount = parseFloat($('#expAmount').value);
      const category = $('#expCat').value;
      const week = $('#expWeek').value;
      if (!(amount > 0)) return toast('error', 'The expense amount must be greater than zero.');
      try {
        await busy(ev.target, 'Saving...', () => apiAddExpense(week, category, amount));
        toast('success', 'Expense recorded successfully.');
        renderPage();
      } catch (err) {
        if (err.network) {
          // Offline: keep the expense on the device and sync it with /budget/sync-push later.
          store.set(queueKey(), [...getQueue(), { week, category, amount, ts: Date.now() }]);
          toast('info', 'You are offline. Expense saved on this device and will sync automatically.');
          renderPage();
        } else handleError(err);
      }
    });
  }

  // ---------- Marketplace ----------
  async function pageMarketplace(el, seq) {
    const listings = await loadListings();
    if (seq !== renderSeq) return;
    const cards = listings.length
      ? `<div class="grid-2">${listings.map((i) => `
          <div class="market-card">
            <h3>${esc(i.title || '')}</h3>
            <p><b>Price:</b> ${money(i.price)}</p>
            <p><b>Contact:</b> ${esc(i.contact || '')}</p>
            <p><b>Seller:</b> ${esc(i.seller || 'Student')}</p>
          </div>`).join('')}</div>`
      : '<div class="alert info">No items have been listed yet.</div>';

    el.innerHTML = `
      <h1>Student Marketplace</h1>
      <p class="caption">Buy and sell items within the student community.</p>
      ${tabsHtml('market', ['Browse Listings', 'Sell an Item'])}
      ${panel('market', 0, `<h2>Available Campus Items</h2>${cards}`)}
      ${panel('market', 1, `
        <h2>Create Marketplace Listing</h2>
        <form id="sellForm" novalidate>
          <label class="field"><span>Item name</span><input type="text" name="title" placeholder="Example: Programming textbook"></label>
          <div class="row">
            <label class="field"><span>Asking price ($)</span><input type="number" name="price" min="0" step="1" inputmode="decimal" value="0"></label>
            <label class="field"><span>Contact details</span><input type="text" name="contact" placeholder="Phone / WhatsApp"></label>
          </div>
          <button class="btn" type="submit">Publish Listing</button>
        </form>`)}`;
    bindTabs(el);

    $('#sellForm').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      const title = f.title.value.trim();
      const price = parseFloat(f.price.value);
      const contact = f.contact.value.trim();
      if (!(title && price > 0 && contact)) return toast('error', 'Complete all listing fields.');
      try {
        await busy($('button[type=submit]', f), 'Publishing...', () => apiAddListing(title, price, contact));
        toast('success', 'Your listing has been published.');
        renderPage();
      } catch (err) { handleError(err); }
    });
  }

  // ---------- Events ----------
  async function pageEvents(el, seq) {
    const events = await loadEvents();
    if (seq !== renderSeq) return;
    const body = events.length
      ? [...events].sort((a, b) => String(a.deadline || '').localeCompare(String(b.deadline || ''))).map((e) => `
          <div class="event-card"><div class="event-top">
            <div><h3>${esc(e.title || '')}</h3><p>Category: <b>${esc(e.type || '')}</b></p></div>
            <div class="date-badge"><small>Date / Deadline</small><h3>${esc(e.deadline || '')}</h3></div>
          </div></div>`).join('')
      : '<div class="alert info">There are no upcoming events.</div>';
    el.innerHTML = `<h1>Campus Events</h1><p>Stay updated with university deadlines, activities and student events.</p>${body}`;
  }

  // ---------- Settings ----------
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    store.set('theme', theme);
    const meta = $('meta[name=theme-color]');
    if (meta) meta.content = theme === 'dark' ? '#060b16' : '#0f172a';
  }

  async function pageSettings(el) {
    const dark = document.documentElement.dataset.theme === 'dark';
    el.innerHTML = `
      <h1>Settings</h1>
      <p>Manage your appearance, legal information, feedback and account.</p>
      ${tabsHtml('settings', ['Appearance', 'Privacy and Terms', 'Feedback', 'Account'])}
      ${panel('settings', 0, `
        <h2>Theme</h2>
        <label class="switch"><input type="checkbox" id="darkToggle" ${dark ? 'checked' : ''}><span>Dark mode</span></label>
        <p class="caption" style="margin-top:8px">Switch between the light and dark theme. The choice applies immediately.</p>`)}
      ${panel('settings', 1, `
        <h2>Privacy Policy and User Agreement</h2>
        <details class="legal"><summary>Privacy Policy</summary><div class="md">${md(PRIVACY_POLICY)}</div></details>
        <details class="legal"><summary>User Agreement</summary><div class="md">${md(USER_AGREEMENT)}</div></details>`)}
      ${panel('settings', 2, `
        <h2>Send Feedback</h2>
        <p class="caption">Report a problem, suggest an improvement or tell us what works well.</p>
        <form id="feedbackForm" novalidate>
          <label class="field"><span>Feedback type</span><select name="category">${options(FEEDBACK_TYPES)}</select></label>
          <label class="field"><span>Your feedback</span><textarea name="message" maxlength="1000" placeholder="Write your feedback here..."></textarea></label>
          <button class="btn" type="submit">Send Feedback</button>
        </form>`)}
      ${panel('settings', 3, `
        <h2>Your account</h2>
        <div class="info-card">
          <h3>${esc(S.user.name)}</h3><p>${esc(S.user.email)}</p><p>${esc(S.user.university)}</p>
        </div>
        <h2>Delete account</h2>
        <div class="alert warning">Deleting your account permanently removes your profile, expenses, marketplace listings and feedback. This cannot be undone.</div>
        <form id="deleteForm" class="danger-zone" novalidate>
          <label class="field"><span>Confirm your password</span>
            <input type="password" name="password" placeholder="Enter your password" autocomplete="current-password"></label>
          <label class="check"><input type="checkbox" name="understood"><span>I understand that this cannot be undone.</span></label>
          <button class="btn" type="submit">Delete My Account</button>
        </form>`)}`;
    bindTabs(el);

    $('#darkToggle').addEventListener('change', (ev) => applyTheme(ev.target.checked ? 'dark' : 'light'));

    $('#feedbackForm').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      const message = f.message.value.trim();
      if (message.length < 5) return toast('error', 'Please write at least a few words of feedback.');
      try {
        await busy($('button[type=submit]', f), 'Sending...', () => apiSendFeedback(f.category.value, message));
        toast('success', 'Thank you. Your feedback has been sent.');
        f.message.value = '';
      } catch (err) { handleError(err); }
    });

    $('#deleteForm').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      if (!f.password.value) return toast('error', 'Enter your password to confirm.');
      if (!f.understood.checked) return toast('error', 'Tick the box to confirm you understand.');
      try {
        await busy($('button[type=submit]', f), 'Deleting your account...', () => apiDeleteAccount(f.password.value));
      } catch (err) { return handleError(err); }
      const email = S.user.email;
      store.del(`queue:${email}`);
      ['income', 'expenses', 'listings', 'events'].forEach((k) => store.del(`cache:${email}:${k}`));
      signOut();
      S.flash = 'Your account has been deleted.';
      render();
    });
  }

  // ============================================================
  // ROUTER
  // ============================================================
  const PAGES = {
    'Dashboard': pageDashboard,
    'Study Hub': pageStudy,
    'Budget Assistance': pageBudget,
    'Marketplace': pageMarketplace,
    'Events': pageEvents,
    'Settings': pageSettings,
  };

  async function renderPage() {
    const el = $('#content');
    if (!el || !S.user) return;
    const seq = ++renderSeq;
    stopTimer();
    updateNav();
    el.innerHTML = inlineLoader();
    window.scrollTo(0, 0);
    try {
      await (PAGES[S.page] || pageDashboard)(el, seq);
    } catch (err) {
      if (seq === renderSeq) { el.innerHTML = '<div class="alert error">Could not load this page.</div>'; console.error(err); }
    }
  }

  function render() {
    const app = $('#app');
    stopTimer();
    if (S.token && S.user) {
      app.innerHTML = shellView();
      bindShell();
      renderPage();
    } else {
      app.innerHTML = authView();
      bindAuth(app);
    }
  }

  // ============================================================
  // START
  // ============================================================
  window.addEventListener('hashchange', () => {
    if (!S.user) return;
    S.page = pageFromHash();
    document.body.classList.remove('nav-open');
    renderPage();
  });
  window.addEventListener('online', () => { setOffline(false); flushQueue(); if (S.user) renderPage(); });
  window.addEventListener('offline', () => setOffline(true));

  S.page = pageFromHash();
  render();
  if (!navigator.onLine) setOffline(true);

  // Cache the app shell for offline use (service workers need https or localhost; the Android app bundles files anyway).
  const native = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  if ('serviceWorker' in navigator && !native && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    navigator.serviceWorker.register('sw.js').catch(() => { /* offline shell unavailable; app still works online */ });
  }
})();

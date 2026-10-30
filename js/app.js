const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
const slug = s => s.toLowerCase().replace(/\s+/g, "-");
const MOCK = CONFIG.USE_MOCK;
const ROLE_LABEL = { user: "Employee / Student", admin: "IT Support Admin" };
let user = null;

/* ---------- Helpers: toast, busy button, inline errors ---------- */
function toast(msg, type = "ok") {
  const t = el("div", "toast " + type, msg); $("#toasts").append(t);
  setTimeout(() => t.remove(), 3500);
}
function setBusy(btn, on) { btn.disabled = on; btn.classList.toggle("loading", on); }
function showErrors(form, errs) {
  $$("[data-err]", form).forEach(s => s.textContent = errs[s.dataset.err] || "");
  $$("input,select,textarea", form).forEach(i => { const bad = !!errs[i.name]; i.classList.toggle("invalid", bad); i.setAttribute("aria-invalid", bad); });
  const first = $(".invalid", form); if (first) first.focus();
}
document.addEventListener("input", e => { if (e.target.classList.contains("invalid")) { e.target.classList.remove("invalid"); const s = e.target.closest("label"); if (s) $("[data-err]", s).textContent = ""; } });
$$("[data-mock-note]").forEach(n => { if (MOCK) n.textContent = "Mock mode: showing sample data. Nothing is sent to or saved on a backend."; else n.hidden = true; });
$$("[data-mock-demo]").forEach(n => { if (MOCK) n.textContent = "Mock mode: use any email and a password of 6+ characters. Try student@college.edu (sees own tickets) or admin@college.edu with the IT Support Admin role. This simulates login and is not real security."; else n.hidden = true; });

/* ---------- Authentication (simulated session in localStorage) ---------- */
let authMode = "login", authRole = "user";
const authForm = $("#authForm");
function setMode(m) {
  authMode = m;
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.mode === m));
  $("[data-signup]").hidden = m !== "signup";
  $("#authBtn").textContent = m === "login" ? "Log in" : "Create account";
  authForm.password.autocomplete = m === "login" ? "current-password" : "new-password";
  $("#authResult").className = ""; $("#authResult").textContent = ""; showErrors(authForm, {});
}
$$(".tab").forEach(t => t.addEventListener("click", () => setMode(t.dataset.mode)));
$("#roleSeg").addEventListener("click", e => {
  const b = e.target.closest(".seg-btn"); if (!b) return;
  authRole = b.dataset.role; $$(".seg-btn").forEach(x => x.classList.toggle("active", x === b));
});
authForm.addEventListener("submit", async ev => {
  ev.preventDefault();
  const d = Object.fromEntries(new FormData(authForm)), errs = {};
  if (authMode === "signup" && d.name.trim().length < 2) errs.name = "Enter your full name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email.trim())) errs.email = "Enter a valid email address.";
  if (d.password.length < 6) errs.password = "Password must be at least 6 characters.";
  showErrors(authForm, errs);
  const res = $("#authResult"); res.className = ""; res.textContent = "";
  if (Object.keys(errs).length) return;
  setBusy($("#authBtn"), true);
  try {
    const payload = { name: d.name, email: d.email.trim(), password: d.password, role: authRole };
    const r = authMode === "login" ? await Api.login(payload) : await Api.signup(payload);
    Session.set({ user: r.user, token: r.token }); user = r.user;
    authForm.reset(); location.hash = "#home"; showApp(); toast("Welcome, " + user.name.split(" ")[0] + "!");
  } catch (e) { res.className = "error-box"; res.textContent = e.message || "Couldn't sign you in. Try again."; }
  finally { setBusy($("#authBtn"), false); }
});
$("#logoutBtn").addEventListener("click", () => {
  Session.clear(); user = null; location.hash = ""; showAuth(); toast("You have been logged out.");
});
function showAuth() { $("#app").hidden = true; $("#auth").hidden = false; setMode("login"); }
function showApp() {
  $("#auth").hidden = true; $("#app").hidden = false;
  const initials = user.name.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
  $("#avatar").textContent = initials; $("#uName").textContent = user.name;
  $("#uRole").textContent = ROLE_LABEL[user.role]; $("#uRole").className = "pill r-" + user.role;
  document.body.dataset.role = user.role;
  $("#welcome").textContent = "Welcome back, " + user.name.split(" ")[0] + ". " + (user.role === "admin" ? "Showing all tickets." : "Showing your tickets.");
  $("#ticketsTitle").textContent = user.role === "admin" ? "All tickets" : "My tickets";
  route();
}

/* ---------- Router ---------- */
const pages = $$(".page").map(p => p.dataset.page);
function route() {
  if (!user) return;
  const name = pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  $$(".page").forEach(p => p.hidden = p.dataset.page !== name);
  $$("#navLinks a:not(.btn)").forEach(a => a.classList.toggle("active", a.hash === "#" + name));
  $("#navLinks").classList.remove("open"); $("#menuBtn").setAttribute("aria-expanded", "false");
  window.scrollTo(0, 0);
  if (name === "dashboard") loadDashboard();
  if (name === "tickets") loadTicketsPage();
}
window.addEventListener("hashchange", route);
$("#menuBtn").addEventListener("click", () => {
  const open = $("#navLinks").classList.toggle("open"); $("#menuBtn").setAttribute("aria-expanded", open);
});
const refresh = () => location.hash === "#dashboard" ? loadDashboard() : loadTicketsPage();

/* ---------- Ticket table + details dialog ---------- */
function renderTable(list, container, emptyMsg) {
  container.replaceChildren();
  if (!list.length) { container.append(el("div", "empty", emptyMsg || "No tickets to show here yet.")); return; }
  const wrap = el("div", "table-wrap"), t = el("table");
  t.innerHTML = "<thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th><th>Created</th><th></th></tr></thead>";
  const tb = el("tbody");
  list.forEach(tk => {
    const tr = el("tr");
    [tk.id, tk.title, tk.category].forEach(v => tr.append(el("td", "", v)));
    const p = el("td"); p.append(el("span", "pri p-" + slug(tk.priority), tk.priority)); tr.append(p);
    const s = el("td"); s.append(el("span", "badge s-" + slug(tk.status), tk.status)); tr.append(s);
    tr.append(el("td", "", tk.created));
    const a = el("td"), b = el("button", "link", "View"); b.addEventListener("click", () => openTicket(tk)); a.append(b); tr.append(a);
    tb.append(tr);
  });
  t.append(tb); wrap.append(t); container.append(wrap);
}
function showLoading(c) { const d = el("div", "loading"); d.append(el("span", "spinner"), document.createTextNode(" Loading…")); c.replaceChildren(d); }
function showError(c, msg, retry) {
  c.replaceChildren(); const d = el("div", "error-box", msg + " "); const b = el("button", "btn small", "Try again"); b.addEventListener("click", retry); d.append(b); c.append(d);
}
function openTicket(tk) {
  const body = $("#dialogBody"); body.replaceChildren(el("h3", "", tk.title));
  [["ID", tk.id], ["Category", tk.category], ["Priority", tk.priority], ["Status", tk.status], ["Created", tk.created], ["Description", tk.description]]
    .forEach(([k, v]) => { const r = el("p"); r.append(el("strong", "", k + ": "), document.createTextNode(v)); body.append(r); });
  if (user.role === "admin") {
    const row = el("div", "admin-row"), sel = el("select"), save = el("button", "btn small", "Update status");
    ["Open", "In Progress", "Resolved"].forEach(s => { const o = el("option", "", s); o.selected = s === tk.status; sel.append(o); });
    save.addEventListener("click", async () => {
      setBusy(save, true);
      try { await Api.updateTicketStatus(tk.id, sel.value); toast("Status updated to " + sel.value + (MOCK ? " (mock, resets on reload)" : "")); $("#ticketDialog").close(); refresh(); }
      catch (e) { toast(e.message || "Couldn't update the status.", "err"); } finally { setBusy(save, false); }
    });
    row.append(sel, save); body.append(row);
  }
  $("#ticketDialog").showModal();
}
$("#closeDialog").addEventListener("click", () => $("#ticketDialog").close());

/* ---------- Dashboard ---------- */
async function loadDashboard() {
  const stats = $("#stats"), recent = $("#recentTickets"); stats.replaceChildren(); showLoading(recent);
  try {
    const tickets = await Api.getTickets(), count = s => tickets.filter(t => t.status === s).length;
    const cards = [["Total tickets", tickets.length], ["Open", count("Open")], ["In progress", count("In Progress")], ["Resolved", count("Resolved")]];
    if (user.role === "admin") cards.push(["High priority, unresolved", tickets.filter(t => t.priority === "High" && t.status !== "Resolved").length]);
    cards.forEach(([l, n]) => { const c = el("div", "stat"); c.append(el("div", "num", String(n)), el("div", "lbl", l)); stats.append(c); });
    renderTable([...tickets].sort((a, b) => b.created.localeCompare(a.created)).slice(0, 5), recent, "No tickets yet. Raise one when you need help.");
  } catch (e) { showError(recent, "Couldn't load tickets. Check your connection and try again.", loadDashboard); }
}

/* ---------- Tickets page ---------- */
let currentFilter = "All";
async function loadTicketsPage() {
  const box = $("#ticketList"); showLoading(box);
  try {
    const all = await Api.getTickets(), list = currentFilter === "All" ? all : all.filter(t => t.status === currentFilter);
    renderTable(list, box, all.length ? "No " + currentFilter + " tickets. Try another filter." : "You have no tickets yet.");
  } catch (e) { showError(box, "Couldn't load tickets. Check your connection and try again.", loadTicketsPage); }
}
$("#filters").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  $$(".chip").forEach(c => c.classList.toggle("active", c === b)); currentFilter = b.dataset.status; loadTicketsPage();
});

/* ---------- Chat ---------- */
const messages = $("#messages"), input = $("#chatInput"), sendBtn = $("#sendBtn");
function resetChat() { messages.replaceChildren(el("div", "empty", "Ask an IT question to get started. Example: “My laptop is connected to Wi-Fi, but I cannot access the internet.”")); }
function addMsg(text, who, sources, mock) {
  if (messages.querySelector(".empty")) messages.replaceChildren();
  const m = el("div", "msg " + who), b = el("div", "bubble", text); m.append(b);
  if (mock) b.prepend(el("span", "badge s-mock", "MOCK RESPONSE"), el("br"));
  if (who.includes("typing")) b.prepend(el("span", "spinner"), document.createTextNode(" "));
  if (sources && sources.length) { const s = el("div", "sources"); s.append(el("strong", "", "Sources: "), document.createTextNode(sources.join(", "))); m.append(s); }
  messages.append(m); messages.scrollTop = messages.scrollHeight; return m;
}
async function sendQuestion() {
  const q = input.value.trim(); if (!q) return;
  addMsg(q, "user"); input.value = ""; setBusy(sendBtn, true);
  const typing = addMsg("AI is thinking…", "ai typing");
  try { const r = await Api.askAI(q); typing.remove(); addMsg(r.answer, "ai", r.sources, MOCK); }
  catch (e) { typing.remove(); addMsg("Sorry, that question couldn't be answered. Check your connection and try again, or raise a ticket.", "ai error"); }
  finally { setBusy(sendBtn, false); input.focus(); }
}
$("#chatForm").addEventListener("submit", e => { e.preventDefault(); sendQuestion(); });
input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuestion(); } });
$("#clearChat").addEventListener("click", resetChat); resetChat();

/* ---------- Ticket form ---------- */
const form = $("#ticketForm");
form.addEventListener("submit", async ev => {
  ev.preventDefault();
  const d = Object.fromEntries(new FormData(form)), errs = {}, res = $("#formResult");
  if (d.title.trim().length < 5) errs.title = "Enter a title of at least 5 characters.";
  if (d.description.trim().length < 15) errs.description = "Describe the problem in at least 15 characters.";
  if (!d.category) errs.category = "Choose a category.";
  if (!d.priority) errs.priority = "Choose a priority.";
  showErrors(form, errs); res.className = ""; res.textContent = "";
  if (Object.keys(errs).length) return;
  setBusy($("#submitBtn"), true);
  try {
    await Api.createTicket({ ...d, requester: user.email });
    res.className = "ok-box"; res.textContent = MOCK ? "Mock submission successful. This ticket was NOT saved anywhere." : "Ticket submitted.";
    toast(MOCK ? "Mock ticket submitted (not saved)" : "Ticket submitted"); form.reset();
  } catch (e) { res.className = "error-box"; res.textContent = "Couldn't submit the ticket. Your answers are kept; try again."; }
  finally { setBusy($("#submitBtn"), false); }
});

/* ---------- Start: restore session or show login ---------- */
const saved = Session.get();
if (saved && saved.user) { user = saved.user; showApp(); } else showAuth();

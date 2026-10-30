// API service layer. The UI calls only Api.*; switching mock/real is CONFIG.USE_MOCK.
const Session = {   // real mode: store the token the backend returns
  get() { try { return JSON.parse(localStorage.getItem("sd_session")); } catch { return null; } },
  set(s) { localStorage.setItem("sd_session", JSON.stringify(s)); },
  clear() { localStorage.removeItem("sd_session"); }
};

async function http(path, method = "GET", body) {
  const s = Session.get(), headers = { "Content-Type": "application/json" };
  if (s && s.token) headers.Authorization = "Bearer " + s.token;   // TODO: confirm auth scheme
  let res;
  try { res = await fetch(CONFIG.API_BASE + path, { method, headers, body: body && JSON.stringify(body) }); }
  catch { throw new Error("Cannot reach the server."); }
  if (res.status === 401 && s) { Session.clear(); location.reload(); }
  if (!res.ok) {
    let msg = "Request failed (" + res.status + ")";
    try { const j = await res.json(); msg = j.detail || j.message || msg; } catch {}   // TODO: confirm error format
    throw new Error(msg);
  }
  return res.json();
}

const E = CONFIG.ENDPOINTS;
// Expected shapes (to agree with backend):
//  login/signup -> { user: {name, email, role: "user"|"admin"}, token }
//  getTickets   -> [{ id, title, category, priority, status, created, description }]
//  askAI        -> { answer: string, sources: string[] }
const RealApi = {
  login: b => http(E.login, "POST", b),
  signup: b => http(E.signup, "POST", b),
  getTickets: () => http(E.tickets),
  updateTicketStatus: (id, status) => http(E.ticketStatus(id), "PATCH", { status }),
  askAI: question => http(E.chat, "POST", { question }),
  createTicket: t => http(E.tickets, "POST", t)
};
const Api = CONFIG.USE_MOCK ? MockApi : RealApi;

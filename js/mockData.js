// MOCK ONLY: sample data and a fake service. Never loaded logic for the real backend.
// IDs start with "MOCK-" so they are never mistaken for real tickets.
const MOCK_TICKETS = [
  { id: "MOCK-001", owner: "student@college.edu", title: "Wi-Fi connected but no internet", category: "Network", priority: "High", status: "Open", created: "2026-10-17", description: "Laptop shows connected to campus Wi-Fi but no pages load." },
  { id: "MOCK-002", owner: "priya@college.edu", title: "Cannot log in to student portal", category: "Account Access", priority: "Medium", status: "In Progress", created: "2026-10-16", description: "Password reset email never arrives." },
  { id: "MOCK-003", owner: "student@college.edu", title: "Install Python on lab PC", category: "Software", priority: "Low", status: "Resolved", created: "2026-10-12", description: "Need Python 3.12 for the data science lab." },
  { id: "MOCK-004", owner: "rahul@college.edu", title: "Keyboard keys not responding", category: "Hardware", priority: "Medium", status: "Open", created: "2026-10-15", description: "Several keys on the left side stopped working." },
  { id: "MOCK-005", owner: "priya@college.edu", title: "VPN disconnects every few minutes", category: "Network", priority: "High", status: "In Progress", created: "2026-10-14", description: "VPN drops during video calls." },
  { id: "MOCK-006", owner: "student@college.edu", title: "Printer not listed on my laptop", category: "Hardware", priority: "Low", status: "Resolved", created: "2026-10-09", description: "Library printer missing from the list." }
];
const MOCK_CHAT_REPLY = {
  answer: "This is a MOCK response, not a real AI answer.\n\nTypical Wi-Fi-but-no-internet checklist:\n1) Turn Wi-Fi off and on.\n2) Restart the router and laptop.\n3) Forget the network and reconnect.\n4) Check whether other devices work.\n5) Raise a ticket if it persists.",
  sources: ["Mock source: Network Troubleshooting Guide", "Mock source: Wi-Fi FAQ"]
};
function mockUser(email, role, name) {
  const n = name || email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  return { user: { name: n, email: email.toLowerCase(), role }, token: "mock-token" };
}
// Same method names as RealApi in api.js. Mock login trusts the chosen role: simulation only, NOT real security.
const MockApi = {
  async login({ email, role }) { await delay(700); return mockUser(email, role); },
  async signup({ name, email, role }) { await delay(900); return mockUser(email, role, name); },
  async getTickets() {
    await delay(600);
    const u = (Session.get() || {}).user || {};
    return MOCK_TICKETS.filter(t => u.role === "admin" || t.owner === u.email).map(t => ({ ...t }));
  },
  async updateTicketStatus(id, status) {   // lasts until page reload
    await delay(400);
    const t = MOCK_TICKETS.find(x => x.id === id); if (!t) throw new Error("Ticket not found");
    t.status = status; return { ...t };
  },
  async askAI(q) { await delay(1200); if (q.toLowerCase().includes("fail")) throw new Error("Mock failure"); return MOCK_CHAT_REPLY; },
  async createTicket() { await delay(800); return { mock: true }; }   // nothing is saved
};

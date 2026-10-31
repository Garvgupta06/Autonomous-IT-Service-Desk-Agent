// Central settings. Backend teammates: change these, not the UI code.
const CONFIG = {
  USE_MOCK: true,                         // true = sample data, no backend. false = real API.
  API_BASE:"http://127.0.0.1:8000",   // PLACEHOLDER: agree the real URL with the backend team
  ENDPOINTS: {                            // PLACEHOLDERS: none of these are confirmed to exist
    login: "/auth/login",
    signup: "/auth/signup",
    tickets: "/tickets",
    ticketStatus: id => `/tickets/${encodeURIComponent(id)}/status`,
    chat: "/chat"
  }
};
const delay = ms => new Promise(r => setTimeout(r, ms));

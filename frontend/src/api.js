const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}/api${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail = "Ошибка запроса";
    try {
      const data = await res.json();
      detail = data.detail
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail)
        : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  dashboard: () => request("/dashboard"),
  accounts: () => request("/accounts"),
  createAccount: (body) => request("/accounts", { method: "POST", body: JSON.stringify(body) }),
  updateAccount: (id, body) =>
    request(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveAccount: (id) => request(`/accounts/${id}`, { method: "DELETE" }),

  categories: (kind) => request(`/categories${kind ? `?kind=${kind}` : ""}`),
  createCategory: (body) =>
    request("/categories", { method: "POST", body: JSON.stringify(body) }),
  archiveCategory: (id) => request(`/categories/${id}`, { method: "DELETE" }),

  transactions: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, v);
    });
    const qs = q.toString();
    return request(`/transactions${qs ? `?${qs}` : ""}`);
  },
  createTransaction: (body) =>
    request("/transactions", { method: "POST", body: JSON.stringify(body) }),
  deleteTransaction: (id) => request(`/transactions/${id}`, { method: "DELETE" }),

  rateUsdRub: () => request("/rates/usd-rub"),
  report: (from, to) => request(`/reports/summary?from_date=${from}&to_date=${to}`),
};

export function money(value, currency = "RUB") {
  const n = Number(value);
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function monthRange(d = new Date()) {
  const y = d.getFullYear();
  const m = d.getMonth();
  const from = new Date(y, m, 1).toISOString().slice(0, 10);
  const to = new Date(y, m + 1, 0).toISOString().slice(0, 10);
  return { from, to };
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, money, monthRange, todayISO } from "./api";

const TABS = [
  { id: "dashboard", label: "Обзор" },
  { id: "ops", label: "Операция" },
  { id: "history", label: "История" },
  { id: "accounts", label: "Счета" },
  { id: "categories", label: "Категории" },
  { id: "reports", label: "Отчёты" },
];

function App() {
  const [tab, setTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const range = useMemo(() => monthRange(), []);

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [dash, accs, cats, txs, rep] = await Promise.all([
        api.dashboard(),
        api.accounts(),
        api.categories(),
        api.transactions({ limit: 100 }),
        api.report(range.from, range.to),
      ]);
      setDashboard(dash);
      setAccounts(accs);
      setCategories(cats);
      setTransactions(txs);
      setReport(rep);
    } catch (e) {
      setError(e.message || "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Cashflow</h1>
          <p>Доходы, расходы и счета · RUB / USD</p>
        </div>
        {dashboard?.usd_rub_rate != null && (
          <div className="rate-pill">
            USD/RUB {Number(dashboard.usd_rub_rate).toFixed(2)}
          </div>
        )}
      </header>

      <nav className="nav">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Загрузка…</p>}

      {!loading && tab === "dashboard" && dashboard && (
        <DashboardView data={dashboard} />
      )}
      {!loading && tab === "ops" && (
        <OpsView
          accounts={accounts}
          categories={categories}
          onDone={async () => {
            await reload();
            setTab("history");
          }}
        />
      )}
      {!loading && tab === "history" && (
        <HistoryView
          accounts={accounts}
          categories={categories}
          items={transactions}
          onChange={reload}
        />
      )}
      {!loading && tab === "accounts" && (
        <AccountsView accounts={accounts} onChange={reload} />
      )}
      {!loading && tab === "categories" && (
        <CategoriesView categories={categories} onChange={reload} />
      )}
      {!loading && tab === "reports" && (
        <ReportsView initial={report} accounts={accounts} />
      )}
    </div>
  );
}

function DashboardView({ data }) {
  return (
    <div className="stack">
      <div className="totals">
        <div className="stat">
          <div className="label">Всего в ₽</div>
          <div className="value">{money(data.total_in_rub, "RUB")}</div>
        </div>
        <div className="stat">
          <div className="label">RUB</div>
          <div className="value">{money(data.total_rub, "RUB")}</div>
        </div>
        <div className="stat">
          <div className="label">USD</div>
          <div className="value">{money(data.total_usd, "USD")}</div>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>Счета</h2>
          <div className="list">
            {data.accounts.map((a) => (
              <div className="row" key={a.id}>
                <div className="meta">
                  <strong>{a.name}</strong>
                  <span>
                    {a.type} · {a.currency}
                  </span>
                </div>
                <div className="amount">{money(a.balance, a.currency)}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Последние операции</h2>
          <div className="list">
            {data.recent.length === 0 && (
              <p className="muted">Пока пусто — добавьте первую операцию</p>
            )}
            {data.recent.map((tx) => (
              <TxRow key={tx.id} tx={tx} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function TxRow({ tx, onDelete }) {
  const sign =
    tx.type === "income" ? "+" : tx.type === "expense" || tx.type === "transfer" ? "−" : "";
  const cls = tx.type === "income" ? "income" : "expense";
  const title =
    tx.type === "transfer"
      ? `${tx.account_name} → ${tx.to_account_name}`
      : tx.category_name || tx.type;
  return (
    <div className="row">
      <div className="meta">
        <strong>{title}</strong>
        <span>
          {tx.occurred_on}
          {tx.note ? ` · ${tx.note}` : ""}
        </span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <div className={`amount ${cls}`}>
          {sign}
          {money(tx.amount, tx.currency)}
        </div>
        {onDelete && (
          <button className="btn btn-danger" onClick={() => onDelete(tx.id)}>
            ×
          </button>
        )}
      </div>
    </div>
  );
}

function OpsView({ accounts, categories, onDone }) {
  const [type, setType] = useState("expense");
  const [form, setForm] = useState({
    amount: "",
    occurred_on: todayISO(),
    account_id: accounts[0]?.id || "",
    to_account_id: accounts[1]?.id || "",
    category_id: "",
    note: "",
    to_amount: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const filteredCats = categories.filter((c) => c.kind === type);

  useEffect(() => {
    if (type !== "transfer") {
      const first = categories.find((c) => c.kind === type);
      setForm((f) => ({ ...f, category_id: first?.id || "" }));
    }
  }, [type, categories]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const body = {
        type,
        amount: Number(form.amount),
        occurred_on: form.occurred_on,
        account_id: Number(form.account_id),
        note: form.note || null,
      };
      if (type === "transfer") {
        body.to_account_id = Number(form.to_account_id);
        if (form.to_amount) body.to_amount = Number(form.to_amount);
      } else {
        body.category_id = Number(form.category_id);
      }
      await api.createTransaction(body);
      await onDone();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Новая операция</h2>
      <div className="chip-row">
        {[
          ["expense", "Расход"],
          ["income", "Доход"],
          ["transfer", "Перевод"],
        ].map(([id, label]) => (
          <button
            key={id}
            className={`chip ${type === id ? "active" : ""}`}
            onClick={() => setType(id)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      <form className="form" onSubmit={submit}>
        <div className="form-row">
          <label>
            Сумма
            <input
              required
              type="number"
              step="0.01"
              min="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />
          </label>
          <label>
            Дата
            <input
              required
              type="date"
              value={form.occurred_on}
              onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
            />
          </label>
        </div>

        <div className="form-row">
          <label>
            {type === "transfer" ? "Откуда" : "Счёт"}
            <select
              required
              value={form.account_id}
              onChange={(e) => setForm({ ...form, account_id: e.target.value })}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
          </label>

          {type === "transfer" ? (
            <label>
              Куда
              <select
                required
                value={form.to_account_id}
                onChange={(e) => setForm({ ...form, to_account_id: e.target.value })}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.currency})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              Категория
              <select
                required
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              >
                {filteredCats.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        {type === "transfer" && (
          <label>
            Сумма на счёте получателя (если валюты разные; иначе курс подтянется сам)
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={form.to_amount}
              onChange={(e) => setForm({ ...form, to_amount: e.target.value })}
              placeholder="Необязательно"
            />
          </label>
        )}

        <label>
          Комментарий
          <input
            value={form.note}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
            placeholder="Опционально"
          />
        </label>

        {err && <p className="error">{err}</p>}

        <div className="actions">
          <button className="btn btn-primary" disabled={busy} type="submit">
            {busy ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </form>
    </section>
  );
}

function HistoryView({ accounts, categories, items, onChange }) {
  const [filters, setFilters] = useState({
    from_date: "",
    to_date: "",
    account_id: "",
    type: "",
  });
  const [list, setList] = useState(items);

  useEffect(() => setList(items), [items]);

  async function apply() {
    const data = await api.transactions({
      ...filters,
      limit: 200,
    });
    setList(data);
  }

  async function remove(id) {
    if (!confirm("Удалить операцию?")) return;
    await api.deleteTransaction(id);
    await onChange();
  }

  return (
    <section className="panel">
      <h2>История</h2>
      <div className="filters">
        <label>
          С
          <input
            type="date"
            value={filters.from_date}
            onChange={(e) => setFilters({ ...filters, from_date: e.target.value })}
          />
        </label>
        <label>
          По
          <input
            type="date"
            value={filters.to_date}
            onChange={(e) => setFilters({ ...filters, to_date: e.target.value })}
          />
        </label>
        <label>
          Счёт
          <select
            value={filters.account_id}
            onChange={(e) => setFilters({ ...filters, account_id: e.target.value })}
          >
            <option value="">Все</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Тип
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          >
            <option value="">Все</option>
            <option value="income">Доход</option>
            <option value="expense">Расход</option>
            <option value="transfer">Перевод</option>
          </select>
        </label>
      </div>
      <div className="actions" style={{ marginBottom: 14 }}>
        <button className="btn btn-ghost" type="button" onClick={apply}>
          Применить
        </button>
      </div>
      <div className="list">
        {list.map((tx) => (
          <TxRow key={tx.id} tx={tx} onDelete={remove} />
        ))}
        {list.length === 0 && <p className="muted">Ничего не найдено</p>}
      </div>
    </section>
  );
}

function AccountsView({ accounts, onChange }) {
  const [form, setForm] = useState({
    name: "",
    type: "card",
    currency: "RUB",
    opening_balance: "0",
  });
  const [err, setErr] = useState("");

  async function create(e) {
    e.preventDefault();
    setErr("");
    try {
      await api.createAccount({
        ...form,
        opening_balance: Number(form.opening_balance || 0),
      });
      setForm({ name: "", type: "card", currency: "RUB", opening_balance: "0" });
      await onChange();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  async function archive(id) {
    if (!confirm("Архивировать счёт?")) return;
    await api.archiveAccount(id);
    await onChange();
  }

  return (
    <div className="grid-2">
      <section className="panel">
        <h2>Счета</h2>
        <div className="list">
          {accounts.map((a) => (
            <div className="row" key={a.id}>
              <div className="meta">
                <strong>{a.name}</strong>
                <span>
                  {a.type} · {a.currency}
                </span>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <div className="amount">{money(a.balance, a.currency)}</div>
                <button className="btn btn-danger" onClick={() => archive(a.id)}>
                  Архив
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Новый счёт</h2>
        <form className="form" onSubmit={create}>
          <label>
            Название
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <div className="form-row">
            <label>
              Тип
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                <option value="cash">Наличные</option>
                <option value="card">Карта</option>
                <option value="bank">Банк</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label>
              Валюта
              <select
                value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value })}
              >
                <option value="RUB">RUB</option>
                <option value="USD">USD</option>
              </select>
            </label>
          </div>
          <label>
            Начальный остаток
            <input
              type="number"
              step="0.01"
              value={form.opening_balance}
              onChange={(e) => setForm({ ...form, opening_balance: e.target.value })}
            />
          </label>
          {err && <p className="error">{err}</p>}
          <button className="btn btn-primary" type="submit">
            Создать
          </button>
        </form>
      </section>
    </div>
  );
}

function CategoriesView({ categories, onChange }) {
  const [form, setForm] = useState({ name: "", kind: "expense" });
  const [err, setErr] = useState("");

  async function create(e) {
    e.preventDefault();
    setErr("");
    try {
      await api.createCategory(form);
      setForm({ name: "", kind: form.kind });
      await onChange();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  async function archive(id) {
    if (!confirm("Архивировать категорию?")) return;
    await api.archiveCategory(id);
    await onChange();
  }

  return (
    <div className="grid-2">
      <section className="panel">
        <h2>Категории</h2>
        <div className="list">
          {categories.map((c) => (
            <div className="row" key={c.id}>
              <div className="meta">
                <strong>{c.name}</strong>
                <span>{c.kind === "income" ? "Доход" : "Расход"}</span>
              </div>
              <button className="btn btn-danger" onClick={() => archive(c.id)}>
                Архив
              </button>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Новая категория</h2>
        <form className="form" onSubmit={create}>
          <label>
            Название
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label>
            Тип
            <select
              value={form.kind}
              onChange={(e) => setForm({ ...form, kind: e.target.value })}
            >
              <option value="expense">Расход</option>
              <option value="income">Доход</option>
            </select>
          </label>
          {err && <p className="error">{err}</p>}
          <button className="btn btn-primary" type="submit">
            Создать
          </button>
        </form>
      </section>
    </div>
  );
}

function ReportsView({ initial }) {
  const initialRange = monthRange();
  const [from, setFrom] = useState(initialRange.from);
  const [to, setTo] = useState(initialRange.to);
  const [report, setReport] = useState(initial);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      setReport(await api.report(from, to));
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <h2>Отчёт за период</h2>
        <div className="form-row">
          <label>
            С
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label>
            По
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <div className="actions" style={{ marginTop: 12 }}>
          <button className="btn btn-primary" type="button" onClick={load}>
            Посчитать
          </button>
        </div>
        {err && <p className="error">{err}</p>}
      </section>

      {report && (
        <>
          <div className="totals">
            <div className="stat">
              <div className="label">Доходы (в ₽)</div>
              <div className="value amount income">
                {money(report.totals_in_rub.income, "RUB")}
              </div>
            </div>
            <div className="stat">
              <div className="label">Расходы (в ₽)</div>
              <div className="value amount expense">
                {money(report.totals_in_rub.expense, "RUB")}
              </div>
            </div>
            <div className="stat">
              <div className="label">Итого</div>
              <div className="value">{money(report.totals_in_rub.net, "RUB")}</div>
            </div>
          </div>

          <section className="panel">
            <h2>По категориям</h2>
            <div className="list">
              {report.by_category.map((item, idx) => (
                <div className="row" key={idx}>
                  <div className="meta">
                    <strong>{item.category_name}</strong>
                    <span>
                      {item.kind === "income" ? "Доход" : "Расход"} · {item.currency}
                    </span>
                  </div>
                  <div className={`amount ${item.kind === "income" ? "income" : "expense"}`}>
                    {money(item.total, item.currency)}
                  </div>
                </div>
              ))}
              {report.by_category.length === 0 && (
                <p className="muted">Нет операций за период</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default App;

import { FormEvent, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Database,
  Gauge,
  History,
  KeyRound,
  LayoutDashboard,
  ListFilter,
  MessageSquareText,
  Play,
  RefreshCw,
  Server,
  Settings2,
  ShieldCheck,
  Table2,
  Trash2,
  Wand2,
} from "lucide-react";

type View = "Overview" | "Query" | "Connections" | "Schema" | "History" | "Models/Providers" | "Settings";
type Connection = { id: string; name: string; dialect: string; created_at?: string };
type Table = {
  name: string;
  columns: { name: string; type: string; nullable?: boolean }[];
  primary_keys?: string[];
  foreign_keys?: Array<Record<string, unknown>>;
  indexes?: Array<Record<string, unknown>>;
};
type HistoryItem = { id: string; sql: string; connection_id: string; status: string; timestamp: string; latency_ms?: number; error_category?: string | null; repaired?: boolean };
type FormState = { name: string; dialect: string; host: string; port: string; database: string; username: string; password: string; ssl: boolean; url: string };

type ProviderSettings = {
  provider: string;
  model: string;
  baseUrl: string;
  apiKey: string;
  embeddingProvider: string;
  embeddingModel: string;
};

const DEV_API = "http://127.0.0.1:47821/api/v1";
const emptyForm: FormState = { name: "", dialect: "sqlite", host: "", port: "", database: "", username: "", password: "", ssl: false, url: "" };
const defaultProviderSettings: ProviderSettings = {
  provider: "lmstudio",
  model: "",
  baseUrl: "http://localhost:1234/v1",
  apiKey: "",
  embeddingProvider: "lmstudio",
  embeddingModel: "text-embedding-nomic-embed-text-v1.5",
};

async function requestWithBase<T>(base: string, path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ?? detail.message ?? "Request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState("");
  const [question, setQuestion] = useState("Show the top 10 customers by revenue.");
  const [sql, setSql] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("Checking engine...");
  const [active, setActive] = useState<View>("Overview");
  const [showConnection, setShowConnection] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [api, setApi] = useState(DEV_API);
  const [settings, setSettings] = useState({
    maxRows: 500,
    queryTimeout: 30,
    resultLimit: 2_000_000,
    theme: "dark",
    defaultProvider: "lmstudio",
  });
  const [providerSettings, setProviderSettings] = useState<ProviderSettings>(defaultProviderSettings);

  const requestApi = <T,>(path: string, options?: RequestInit) => requestWithBase<T>(api, path, options);
  const selectedConnection = useMemo(() => connections.find((item) => item.id === selected) ?? null, [connections, selected]);

  async function refreshConnections() {
    try {
      const [items, savedHistory] = await Promise.all([
        requestApi<Connection[]>("/connections"),
        requestApi<HistoryItem[]>("/history"),
      ]);
      setConnections(items);
      setHistory(savedHistory);
      setStatus("Engine ready");
    } catch {
      setStatus("Engine offline");
    }
  }

  async function loadSchema(connectionId = selected) {
    if (!connectionId) {
      setTables([]);
      return;
    }
    try {
      const result = await requestApi<{ tables: Table[] }>(`/connections/${connectionId}/schema`);
      setTables(result.tables);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Schema failed");
    }
  }

  useEffect(() => {
    const initialise = async () => {
      try {
        const dynamicApi = await invoke<string>("engine_url");
        setApi(dynamicApi);
        await requestApi("/health");
        await refreshConnections();
      } catch {
        setStatus("Engine offline");
      }
    };
    initialise();
  }, []);

  async function saveConnection(event: FormEvent) {
    event.preventDefault();
    try {
      const payload = { ...form, port: form.port ? Number(form.port) : undefined, url: form.url || undefined };
      const connection = await requestApi<Connection>("/connections", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await requestApi(`/connections/${connection.id}/test`, { method: "POST" });
      setConnections((current) => [...current, connection]);
      setSelected(connection.id);
      setShowConnection(false);
      setForm(emptyForm);
      setStatus("Connection saved and tested");
      await loadSchema(connection.id);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Connection failed");
    }
  }

  async function syncSchema() {
    if (!selected) {
      setStatus("Select a connection first");
      return;
    }
    try {
      const result = await requestApi<{ changes: Record<string, number> }>(`/connections/${selected}/sync`, { method: "POST" });
      await loadSchema();
      setStatus(`Schema synced: ${result.changes.added} added, ${result.changes.changed} changed`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Sync failed");
    }
  }

  async function runQuery(sqlValue: string) {
    if (!selected) {
      setStatus("Add a database connection first");
      return;
    }
    try {
      const dialect = selectedConnection?.dialect ?? "postgres";
      const result = await requestApi<{ rows: Record<string, unknown>[]; sql: string; row_count?: number; latency_ms?: number; truncated?: boolean }>("/query", {
        method: "POST",
        body: JSON.stringify({ connection_id: selected, sql: sqlValue, dialect, max_rows: settings.maxRows }),
      });
      setSql(result.sql);
      setRows(result.rows ?? []);
      setHistory(await requestApi<HistoryItem[]>("/history"));
      setStatus(result.truncated ? `Query completed with truncation (${result.row_count ?? result.rows.length} results)` : `Query completed in ${result.latency_ms ?? 0} ms`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Query failed");
    }
  }

  async function generateAndRun() {
    if (!selected) {
      setStatus("Add a database connection first");
      return;
    }
    try {
      const dialect = selectedConnection?.dialect ?? "postgres";
      const generated = await requestApi<{ sql: string }>("/query/generate", {
        method: "POST",
        body: JSON.stringify({ connection_id: selected, question, dialect }),
      });
      setSql(generated.sql);
      await runQuery(generated.sql);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Generation failed");
    }
  }

  async function deleteConnectionItem() {
    if (!selected) return;
    try {
      await requestApi(`/connections/${selected}`, { method: "DELETE" });
      const nextConnections = connections.filter((item) => item.id !== selected);
      setConnections(nextConnections);
      setSelected(nextConnections[0]?.id ?? "");
      setTables([]);
      await refreshConnections();
      setStatus("Connection deleted");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delete failed");
    }
  }

  const navItems: Array<{ label: View; icon: typeof LayoutDashboard }> = [
    { label: "Overview", icon: LayoutDashboard },
    { label: "Query", icon: Play },
    { label: "Connections", icon: Database },
    { label: "Schema", icon: Table2 },
    { label: "History", icon: History },
    { label: "Models/Providers", icon: Wand2 },
    { label: "Settings", icon: Settings2 },
  ];

  const renderOverview = () => (
    <div className="card-grid">
      <div className="stat-card"><div className="card-label"><Gauge size={16} /> Status</div><strong>{status}</strong><span>{selectedConnection ? `${selectedConnection.name} (${selectedConnection.dialect})` : "No active connection"}</span></div>
      <div className="stat-card"><div className="card-label"><Server size={16} /> Engine</div><strong>{api}</strong><span>Localhost-only runtime</span></div>
      <div className="stat-card"><div className="card-label"><Database size={16} /> Connections</div><strong>{connections.length}</strong><span>Saved database links</span></div>
      <div className="stat-card"><div className="card-label"><Table2 size={16} /> Schema</div><strong>{tables.length}</strong><span>Synced objects</span></div>
      <div className="stat-card"><div className="card-label"><History size={16} /> History</div><strong>{history.length}</strong><span>Tracked queries</span></div>
      <div className="stat-card"><div className="card-label"><ShieldCheck size={16} /> Security</div><strong>Read-only</strong><span>SQLGlot validation enabled</span></div>
    </div>
  );

  const renderQuery = () => (
    <div className="two-column">
      <div className="panel-card wide">
        <div className="panel-head">
          <div>
            <span className="eyebrow">NATURAL LANGUAGE</span>
            <h2>Question</h2>
          </div>
          <button className="primary" onClick={generateAndRun}><MessageSquareText size={15} /> Generate</button>
        </div>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} />
        <div className="panel-head small-gap">
          <div>
            <span className="eyebrow">SQL</span>
            <h2>Editor</h2>
          </div>
          <button className="secondary" onClick={() => void runQuery(sql)}><Play size={15} /> Execute</button>
        </div>
        <textarea value={sql} onChange={(event) => setSql(event.target.value)} rows={12} className="sql-box" placeholder="Generated or edited SQL appears here." />
      </div>

      <div className="panel-card sticky">
        <div className="panel-head">
          <div>
            <span className="eyebrow">RESULTS</span>
            <h2>Preview</h2>
          </div>
          <span className="chip">{rows.length} rows</span>
        </div>
        <div className="table-wrap">
          {rows.length ? (
            <table>
              <thead>
                <tr>{Object.keys(rows[0]).map((key) => <th key={key}>{key}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${index}-${Object.values(row).join("-")}`}>
                    {Object.values(row).map((value, cellIndex) => <td key={`${index}-${cellIndex}`}>{String(value ?? "null")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">Run a validated query to preview results.</div>
          )}
        </div>
      </div>
    </div>
  );

  const renderConnections = () => (
    <div className="two-column">
      <div className="panel-card">
        <div className="panel-head">
          <div>
            <span className="eyebrow">MANAGE</span>
            <h2>Connections</h2>
          </div>
          <button className="primary" onClick={() => setShowConnection((value) => !value)}><Database size={15} /> {showConnection ? "Close" : "New"}</button>
        </div>
        {showConnection && (
          <form className="form-grid" onSubmit={saveConnection}>
            <label>Name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>Database type<select value={form.dialect} onChange={(event) => setForm({ ...form, dialect: event.target.value })}><option value="sqlite">SQLite</option><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option><option value="mariadb">MariaDB</option><option value="mssql">SQL Server</option></select></label>
            <label>Host<input value={form.host} onChange={(event) => setForm({ ...form, host: event.target.value })} /></label>
            <label>Port<input type="number" value={form.port} onChange={(event) => setForm({ ...form, port: event.target.value })} /></label>
            <label>Database / path<input value={form.database} onChange={(event) => setForm({ ...form, database: event.target.value })} /></label>
            <label>Schema<input value={form.database} onChange={(event) => setForm({ ...form, database: event.target.value })} /></label>
            <label>Username<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
            <label>Password<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
            <label className="checkbox-row"><input type="checkbox" checked={form.ssl} onChange={(event) => setForm({ ...form, ssl: event.target.checked })} /> Require SSL/TLS</label>
            <label className="full-width">Advanced connection URL<input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} /></label>
            <button className="primary" type="submit">Test and save</button>
          </form>
        )}
      </div>

      <div className="panel-card">
        <div className="panel-head">
          <div>
            <span className="eyebrow">SAVED</span>
            <h2>Database list</h2>
          </div>
        </div>
        <div className="connection-list">
          {connections.length ? connections.map((connection) => (
            <button className={`connection-row ${selected === connection.id ? "selected" : ""}`} key={connection.id} onClick={() => { setSelected(connection.id); void loadSchema(connection.id); }}>
              <div>
                <strong>{connection.name}</strong>
                <small>{connection.dialect}</small>
              </div>
              <span>{connection.created_at ? new Date(connection.created_at).toLocaleDateString() : "Saved"}</span>
            </button>
          )) : <div className="empty-state">No database connections saved yet.</div>}
        </div>
      </div>
    </div>
  );

  const renderSchema = () => (
    <div className="panel-card">
      <div className="panel-head">
        <div>
          <span className="eyebrow">SCHEMA</span>
          <h2>Objects and relationships</h2>
        </div>
        <button className="secondary" onClick={syncSchema}><RefreshCw size={15} /> Sync</button>
      </div>
      {tables.length ? (
        <div className="table-list">
          {tables.map((table) => (
            <div className="schema-block" key={table.name}>
              <div className="schema-title"><Table2 size={15} /> {table.name}</div>
              <div className="meta-row">
                <span>{table.columns.length} columns</span>
                {table.primary_keys?.length ? <span>{table.primary_keys.length} primary keys</span> : null}
                {table.foreign_keys?.length ? <span>{table.foreign_keys.length} foreign keys</span> : null}
              </div>
              <ul>
                {table.columns.map((column) => (<li key={`${table.name}.${column.name}`}><strong>{column.name}</strong> <em>{column.type}</em>{column.nullable === false ? " required" : " nullable"}</li>))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">No schema loaded for the current connection.</div>
      )}
    </div>
  );

  const renderHistory = () => (
    <div className="panel-card">
      <div className="panel-head">
        <div>
          <span className="eyebrow">AUDIT</span>
          <h2>Query history</h2>
        </div>
        <button className="secondary" onClick={() => setHistory([])}><ListFilter size={15} /> Clear visible</button>
      </div>
      <div className="history-list">
        {history.length ? history.map((item) => (
          <div className="history-item-card" key={item.id}>
            <div className="history-header">
              <strong>{item.status}</strong>
              <span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : "Recent"}</span>
            </div>
            <code>{item.sql}</code>
            <div className="history-meta">
              <span>{item.error_category ?? "ok"}</span>
              <span>{item.latency_ms ?? 0}ms</span>
              {item.repaired ? <span>repaired</span> : <span>clean</span>}
            </div>
          </div>
        )) : <div className="empty-state">No query history has been captured yet.</div>}
      </div>
    </div>
  );

  const renderProviders = () => (
    <div className="two-column">
      <div className="panel-card">
        <div className="panel-head">
          <div>
            <span className="eyebrow">MODELS</span>
            <h2>Provider settings</h2>
          </div>
          <button className="secondary" onClick={() => setProviderSettings(defaultProviderSettings)}><RefreshCw size={15} /> Reset</button>
        </div>
        <div className="form-grid compact-form">
          <label>Provider<select value={providerSettings.provider} onChange={(event) => setProviderSettings({ ...providerSettings, provider: event.target.value })}><option value="lmstudio">LM Studio</option><option value="ollama">Ollama</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="gemini">Gemini</option></select></label>
          <label>Model<input value={providerSettings.model} onChange={(event) => setProviderSettings({ ...providerSettings, model: event.target.value })} /></label>
          <label>Base URL<input value={providerSettings.baseUrl} onChange={(event) => setProviderSettings({ ...providerSettings, baseUrl: event.target.value })} /></label>
          <label>API key<input type="password" value={providerSettings.apiKey} onChange={(event) => setProviderSettings({ ...providerSettings, apiKey: event.target.value })} /></label>
          <label>Embedding provider<select value={providerSettings.embeddingProvider} onChange={(event) => setProviderSettings({ ...providerSettings, embeddingProvider: event.target.value })}><option value="lmstudio">LM Studio</option><option value="ollama">Ollama</option><option value="openai">OpenAI</option></select></label>
          <label>Embedding model<input value={providerSettings.embeddingModel} onChange={(event) => setProviderSettings({ ...providerSettings, embeddingModel: event.target.value })} /></label>
        </div>
      </div>
      <div className="panel-card">
        <div className="panel-head">
          <div>
            <span className="eyebrow">STATUS</span>
            <h2>Runtime check</h2>
          </div>
        </div>
        <div className="status-stack">
          <div className="status-pill"><KeyRound size={15} /> Local provider detection: ready when running</div>
          <div className="status-pill"><Server size={15} /> Cloud provider config: validate before use</div>
          <div className="status-pill"><ShieldCheck size={15} /> Secrets remain local and never logged</div>
        </div>
      </div>
    </div>
  );

  const renderSettings = () => (
    <div className="panel-card">
      <div className="panel-head">
        <div>
          <span className="eyebrow">SETTINGS</span>
          <h2>Application</h2>
        </div>
        <button className="secondary" onClick={() => setSettings({ maxRows: 500, queryTimeout: 30, resultLimit: 2_000_000, theme: "dark", defaultProvider: "lmstudio" })}><RefreshCw size={15} /> Defaults</button>
      </div>
      <div className="form-grid compact-form">
        <label>Default provider<select value={settings.defaultProvider} onChange={(event) => setSettings({ ...settings, defaultProvider: event.target.value })}><option value="lmstudio">LM Studio</option><option value="ollama">Ollama</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select></label>
        <label>Max rows<input type="number" value={settings.maxRows} onChange={(event) => setSettings({ ...settings, maxRows: Number(event.target.value) })} /></label>
        <label>Query timeout (s)<input type="number" value={settings.queryTimeout} onChange={(event) => setSettings({ ...settings, queryTimeout: Number(event.target.value) })} /></label>
        <label>Result size limit (bytes)<input type="number" value={settings.resultLimit} onChange={(event) => setSettings({ ...settings, resultLimit: Number(event.target.value) })} /></label>
        <label>Theme<select value={settings.theme} onChange={(event) => setSettings({ ...settings, theme: event.target.value })}><option value="dark">Dark</option><option value="light">Light</option></select></label>
      </div>
      <div className="danger-box">
        <strong>Reset local data</strong>
        <p>Clears local application metadata and schema state for this machine. This does not remove database credentials from the OS keychain unless you explicitly delete them.</p>
        <button className="danger-button" onClick={() => setStatus("Reset warning shown. Use OS-level credential cleanup for complete removal.")}><Trash2 size={15} /> Reset local state</button>
      </div>
    </div>
  );

  let viewContent;
  switch (active) {
    case "Overview":
      viewContent = renderOverview();
      break;
    case "Query":
      viewContent = renderQuery();
      break;
    case "Connections":
      viewContent = renderConnections();
      break;
    case "Schema":
      viewContent = renderSchema();
      break;
    case "History":
      viewContent = renderHistory();
      break;
    case "Models/Providers":
      viewContent = renderProviders();
      break;
    case "Settings":
      viewContent = renderSettings();
      break;
    default:
      viewContent = renderOverview();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">N</span>
          <div>
            <strong>NL2SQL</strong>
            <small>DESKTOP BETA</small>
          </div>
        </div>

        <nav className="nav">
          {navItems.map(({ label, icon: Icon }) => (
            <button className={active === label ? "active" : ""} key={label} onClick={() => setActive(label)}>
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        <div className="engine-status">
          <span className={status === "Engine ready" ? "dot ready" : "dot"} />
          <span>{status}</span>
          <button title="Refresh status" onClick={() => void refreshConnections()}><RefreshCw size={14} /></button>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">WORKSPACE / {active.toUpperCase()}</p>
            <h1>Ask your data.</h1>
          </div>

          <div className="connection-picker">
            <label>
              ACTIVE DATABASE
              <select value={selected} onChange={(event) => { setSelected(event.target.value); void loadSchema(event.target.value); }}>
                <option value="">Select connection</option>
                {connections.map((connection) => (
                  <option value={connection.id} key={connection.id}>{connection.name} · {connection.dialect}</option>
                ))}
              </select>
            </label>
            <button className="small-button" onClick={() => setShowConnection(true)}><Database size={14} /> Add connection</button>
            {selected && <button className="small-button danger" onClick={() => void deleteConnectionItem()}><Trash2 size={14} /> Delete</button>}
          </div>
        </header>

        {viewContent}
      </main>
    </div>
  );
}

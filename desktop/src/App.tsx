import { FormEvent, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Database, History, LayoutDashboard, Play, RefreshCw, Settings2, Table2, Trash2 } from "lucide-react";

type Table = { name: string; columns: { name: string; type: string }[] };
type Connection = { id: string; name: string; dialect: string };
type HistoryItem = { id: string; sql: string; connection_id: string; status: string; timestamp: string; latency_ms?: number };
type FormState = { name: string; dialect: string; host: string; port: string; database: string; username: string; password: string; ssl: boolean; url: string };

const DEV_API = "http://127.0.0.1:47821/api/v1";
const emptyForm: FormState = { name: "", dialect: "sqlite", host: "", port: "", database: "", username: "", password: "", ssl: false, url: "" };

async function requestWithBase<T>(base: string, path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
  return response.status === 204 ? (undefined as T) : response.json();
}

export function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState("");
  const [question, setQuestion] = useState("Show me the first 25 records");
  const [sql, setSql] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("Checking engine...");
  const [active, setActive] = useState("Query");
  const [showConnection, setShowConnection] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [api, setApi] = useState(DEV_API);

  const requestApi = <T,>(path: string, options?: RequestInit) => requestWithBase<T>(api, path, options);

  async function refresh() {
    try {
      const [items, savedHistory] = await Promise.all([requestApi<Connection[]>("/connections"), requestApi<HistoryItem[]>("/history")]);
      setConnections(items); setHistory(savedHistory); setStatus("Engine ready");
    } catch { setStatus("Engine offline"); }
  }
  useEffect(() => { invoke<string>("engine_url").then(setApi).catch(() => undefined); requestApi("/health").then(refresh).catch(() => setStatus("Engine offline")); }, []);

  async function loadSchema(connectionId = selected) {
    if (!connectionId) return;
    try { const result = await requestApi<{ tables: Table[] }>(`/connections/${connectionId}/schema`); setTables(result.tables); } catch (error) { setStatus(error instanceof Error ? error.message : "Schema failed"); }
  }

  async function saveConnection(event: FormEvent) {
    event.preventDefault();
    try {
      const connection = await requestApi<Connection>("/connections", { method: "POST", body: JSON.stringify({ ...form, port: form.port ? Number(form.port) : undefined, url: form.url || undefined }) });
      await requestApi(`/connections/${connection.id}/test`, { method: "POST" });
      setConnections((current) => [...current, connection]); setSelected(connection.id); setShowConnection(false); setForm(emptyForm); setStatus("Connection saved and tested");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Connection failed"); }
  }

  async function syncSchema() {
    if (!selected) return setStatus("Select a connection first");
    try { const result = await requestApi<{ changes: Record<string, number> }>(`/connections/${selected}/sync`, { method: "POST" }); await loadSchema(); setStatus(`Schema synced: ${result.changes.added} added, ${result.changes.changed} changed`); } catch (error) { setStatus(error instanceof Error ? error.message : "Sync failed"); }
  }

  async function generateAndRun() {
    if (!selected) return setStatus("Add a database connection first");
    try {
      const dialect = connections.find((item) => item.id === selected)?.dialect ?? "postgres";
      const generated = await requestApi<{ sql: string }>("/query/generate", { method: "POST", body: JSON.stringify({ connection_id: selected, question, dialect }) });
      setSql(generated.sql);
      const result = await requestApi<{ rows: Record<string, unknown>[]; sql: string }>("/query", { method: "POST", body: JSON.stringify({ connection_id: selected, question, sql: generated.sql, dialect, max_rows: 1000 }) });
      setSql(result.sql); setRows(result.rows); setHistory(await requestApi<HistoryItem[]>("/history")); setStatus("Query completed");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Query failed"); }
  }

  async function runManual() {
    if (!selected || !sql.trim()) return setStatus("Select a connection and enter SQL first");
    try {
      const dialect = connections.find((item) => item.id === selected)?.dialect ?? "postgres";
      const result = await requestApi<{ rows: Record<string, unknown>[]; sql: string }>("/query", { method: "POST", body: JSON.stringify({ connection_id: selected, sql, dialect, max_rows: 1000 }) });
      setSql(result.sql); setRows(result.rows); setHistory(await requestApi<HistoryItem[]>("/history")); setStatus("Manual query completed");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Manual query failed"); }
  }

  async function deleteConnection() {
    if (!selected) return;
    await requestApi(`/connections/${selected}`, { method: "DELETE" }); setSelected(""); setTables([]); await refresh(); setStatus("Connection deleted");
  }

  const nav = [{ label: "Overview", icon: LayoutDashboard }, { label: "Query", icon: Play }, { label: "Connections", icon: Database }, { label: "Schema", icon: Table2 }, { label: "History", icon: History }, { label: "Settings", icon: Settings2 }];
  return <div className="app-shell">
    <aside><div className="brand"><span className="brand-mark">N</span><div><strong>NL2SQL</strong><small>INTELLIGENCE WORKBENCH</small></div></div><nav>{nav.map(({ label, icon: Icon }) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><Icon size={17} />{label}</button>)}</nav><div className="engine-status"><span className={status === "Engine ready" ? "dot ready" : "dot"} />{status}<button title="Refresh engine status" onClick={refresh}><RefreshCw size={14} /></button></div></aside>
    <main><header><div><p className="eyebrow">WORKSPACE / {active.toUpperCase()}</p><h1>Ask your data.</h1></div><div className="connection-picker"><label>ACTIVE DATABASE<select value={selected} onChange={(event) => { setSelected(event.target.value); loadSchema(event.target.value); }}><option value="">Select connection</option>{connections.map((connection) => <option value={connection.id} key={connection.id}>{connection.name} · {connection.dialect}</option>)}</select></label><button className="small-button" onClick={() => setShowConnection(true)}><Database size={14} /> Add connection</button></div></header>
      {showConnection && <form className="connection-form" onSubmit={saveConnection}><div className="section-heading"><div><span className="eyebrow">NEW CONNECTION</span><h2>Connect a database</h2></div><button type="button" className="icon-button" onClick={() => setShowConnection(false)}>×</button></div><div className="form-grid"><label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>Database type<select value={form.dialect} onChange={(event) => setForm({ ...form, dialect: event.target.value })}><option value="sqlite">SQLite</option><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option><option value="mssql">SQL Server</option><option value="oracle">Oracle</option><option value="bigquery">BigQuery</option></select></label><label>Host<input value={form.host} onChange={(event) => setForm({ ...form, host: event.target.value })} /></label><label>Port<input value={form.port} onChange={(event) => setForm({ ...form, port: event.target.value })} /></label><label>Database / path<input required value={form.database} onChange={(event) => setForm({ ...form, database: event.target.value })} /></label><label>Username<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label><label>Password<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label><label className="check"><input type="checkbox" checked={form.ssl} onChange={(event) => setForm({ ...form, ssl: event.target.checked })} /> Require SSL</label></div><label>Advanced connection URL<input placeholder="Optional SQLAlchemy URL" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} /></label><button className="primary" type="submit"><Database size={16} /> Test and save</button></form>}
      <section className="query-panel"><div className="panel-label">NATURAL LANGUAGE QUERY</div><textarea value={question} onChange={(event) => setQuestion(event.target.value)} /><button className="primary" onClick={generateAndRun}><Play size={16} />Generate and run</button><div className="query-note">Read-only execution · results capped at 1,000 rows</div></section>
      <section className="workspace-grid"><div className="result-area"><div className="section-heading"><div><span className="eyebrow">GENERATED SQL</span><h2>Compiled query</h2></div><button className="icon-button" title="Run manual SQL" onClick={runManual}><Play size={16} /></button></div><textarea className="sql-editor" value={sql} onChange={(event) => setSql(event.target.value)} placeholder="Generated SQL appears here. You can edit it before running." /><div className="section-heading"><div><span className="eyebrow">RESULTS</span><h2>Preview</h2></div><span className="result-count">{rows.length} rows</span></div><div className="table-wrap">{rows.length ? <table><thead><tr>{Object.keys(rows[0]).map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{Object.values(row).map((value, cell) => <td key={cell}>{String(value ?? "null")}</td>)}</tr>)}</tbody></table> : <div className="empty">Ask a question to generate a validated query.</div>}</div></div><aside className="schema-panel"><div className="section-heading"><div><span className="eyebrow">SCHEMA CONTEXT</span><h2>Tables</h2></div><div><button className="icon-button" title="Sync schema" onClick={syncSchema}><RefreshCw size={16} /></button>{selected && <button className="icon-button danger" title="Delete connection" onClick={deleteConnection}><Trash2 size={16} /></button>}</div></div>{tables.length ? tables.map((table) => <div className="table-item" key={table.name}><Table2 size={15} /><div><strong>{table.name}</strong><small>{table.columns.length} columns</small></div></div>) : <div className="empty compact">Select a connection and sync its schema.</div>}<div className="history-list"><span className="eyebrow">RECENT HISTORY</span>{history.slice(0, 4).map((item) => <div className="history-item" key={item.id}><strong>{item.status}</strong><small>{item.sql.slice(0, 34)} · {item.latency_ms ?? 0}ms</small></div>)}</div></aside></section>
    </main>
  </div>;
}

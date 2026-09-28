import { useEffect, useState } from "react";
import { Database, History, KeyRound, LayoutDashboard, Play, RefreshCw, Settings2, Table2 } from "lucide-react";

type Table = { name: string; columns: { name: string; type: string }[] };
type Connection = { id: string; name: string; dialect: string };
const API = "http://127.0.0.1:47821/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
  return response.json();
}

export function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [selected, setSelected] = useState("");
  const [question, setQuestion] = useState("Show me the first 25 records");
  const [sql, setSql] = useState("SELECT 1");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("Checking engine...");
  const [active, setActive] = useState("Query");

  useEffect(() => { request<{ status: string }>("/health").then(() => setStatus("Engine ready")).catch(() => setStatus("Engine offline")); }, []);
  useEffect(() => { request<Connection[]>("/connections").then(setConnections).catch(() => undefined); }, []);

  async function runQuery() {
    if (!selected) return setStatus("Add a database connection first");
    try {
      const result = await request<{ sql: string; rows: Record<string, unknown>[] }>("/query", { method: "POST", body: JSON.stringify({ connection_id: selected, sql, dialect: connections.find((item) => item.id === selected)?.dialect ?? "postgres", max_rows: 1000 }) });
      setSql(result.sql); setRows(result.rows); setStatus("Query completed");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Query failed"); }
  }

  async function loadSchema() {
    if (!selected) return;
    const result = await request<Table[]>(`/connections/${selected}/tables`); setTables(result); setStatus(`${result.length} tables indexed`);
  }

  const nav = [{ label: "Overview", icon: LayoutDashboard }, { label: "Query", icon: Play }, { label: "Connections", icon: Database }, { label: "Schema", icon: Table2 }, { label: "History", icon: History }, { label: "Models", icon: KeyRound }, { label: "Settings", icon: Settings2 }];
  return <div className="app-shell">
    <aside><div className="brand"><span className="brand-mark">N</span><div><strong>NL2SQL</strong><small>INTELLIGENCE WORKBENCH</small></div></div><nav>{nav.map(({ label, icon: Icon }) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><Icon size={17} />{label}</button>)}</nav><div className="engine-status"><span className={status === "Engine ready" ? "dot ready" : "dot"} />{status}<button title="Refresh engine status" onClick={() => request("/health").then(() => setStatus("Engine ready")).catch(() => setStatus("Engine offline"))}><RefreshCw size={14} /></button></div></aside>
    <main><header><div><p className="eyebrow">WORKSPACE / {active.toUpperCase()}</p><h1>Ask your data.</h1></div><div className="connection-picker"><label>ACTIVE DATABASE<select value={selected} onChange={(event) => { setSelected(event.target.value); setTimeout(loadSchema, 0); }}><option value="">Select connection</option>{connections.map((connection) => <option value={connection.id} key={connection.id}>{connection.name} · {connection.dialect}</option>)}</select></label></div></header>
      <section className="query-panel"><div className="panel-label">NATURAL LANGUAGE QUERY</div><textarea value={question} onChange={(event) => setQuestion(event.target.value)} /><button className="primary" onClick={runQuery}><Play size={16} />Run query</button><div className="query-note">Read-only execution · results capped at 1,000 rows</div></section>
      <section className="workspace-grid"><div className="result-area"><div className="section-heading"><div><span className="eyebrow">GENERATED SQL</span><h2>Compiled query</h2></div><button className="icon-button" title="Run query" onClick={runQuery}><Play size={16} /></button></div><pre className="sql"><code>{sql}</code></pre><div className="section-heading"><div><span className="eyebrow">RESULTS</span><h2>Preview</h2></div><span className="result-count">{rows.length} rows</span></div><div className="table-wrap">{rows.length ? <table><thead><tr>{Object.keys(rows[0]).map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{Object.values(row).map((value, cell) => <td key={cell}>{String(value ?? "null")}</td>)}</tr>)}</tbody></table> : <div className="empty">Run a validated query to see results here.</div>}</div></div><aside className="schema-panel"><div className="section-heading"><div><span className="eyebrow">SCHEMA CONTEXT</span><h2>Tables</h2></div><button className="icon-button" title="Refresh schema" onClick={loadSchema}><RefreshCw size={16} /></button></div>{tables.length ? tables.map((table) => <div className="table-item" key={table.name}><Table2 size={15} /><div><strong>{table.name}</strong><small>{table.columns.length} columns</small></div></div>) : <div className="empty compact">Select a connection to inspect its schema.</div>}</aside></section>
    </main>
  </div>;
}

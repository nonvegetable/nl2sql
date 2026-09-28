"""
Enterprise NL2SQL Analytics Dashboard.
Provides a Streamlit web interface for users to ask natural language questions,
displays the generated SQL, raw data, and intelligent auto-generated charts.
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st

from generate_sql import execute_sql_with_self_correction
from providers import (
    api_key_env_name,
    get_lm_studio_loaded_llm_models,
    get_ollama_llm_models,
    list_cloud_chat_models,
    lm_studio_no_model_message,
    lm_studio_origin,
    missing_api_key_message,
    ollama_no_model_message,
    ollama_origin,
    ollama_unreachable_message,
)
from sync_schema import sync_database_schema
from dotenv import load_dotenv

load_dotenv()

CLOUD_PROVIDERS = {"OPENAI", "ANTHROPIC", "GEMINI"}
CUSTOM_MODEL_SENTINEL = "Custom model id…"
PROVIDER_DISPLAY = {
    "LMSTUDIO": "LM Studio",
    "OLLAMA": "Ollama",
    "OPENAI": "OpenAI",
    "ANTHROPIC": "Claude (Anthropic)",
    "GEMINI": "Gemini",
}


def _select_model(model_options, env_model, allow_custom=False, widget_ns="model"):
    """Ask which generation model to use from a discovered list."""
    if model_options:
        options = list(model_options)
        if allow_custom:
            options.append(CUSTOM_MODEL_SENTINEL)
            if env_model and env_model not in model_options:
                default_index = options.index(CUSTOM_MODEL_SENTINEL)
            else:
                default_index = options.index(env_model) if env_model in options else 0
        else:
            default_index = options.index(env_model) if env_model in options else 0
        choice = st.selectbox(
            "Generation Model",
            options,
            index=default_index,
            key=f"{widget_ns}_select",
        )
        if choice == CUSTOM_MODEL_SENTINEL:
            custom_key = f"{widget_ns}_custom"
            if custom_key not in st.session_state:
                st.session_state[custom_key] = env_model or ""
            typed = st.text_input(
                "Model id",
                placeholder="e.g. gpt-4o",
                key=custom_key,
            )
            return typed.strip() or None
        return choice
    if allow_custom:
        typed_key = f"{widget_ns}_typed"
        if typed_key not in st.session_state:
            st.session_state[typed_key] = env_model or ""
        typed = st.text_input(
            "Generation Model",
            placeholder="Type a model id",
            key=typed_key,
        )
        return typed.strip() or None
    st.selectbox(
        "Generation Model",
        ["— no model available —"],
        index=0,
        disabled=True,
        key=f"{widget_ns}_empty",
    )
    return None


def render_provider_settings(selected_provider: str):
    """Sidebar widgets: discover local models or ask for a cloud API key + model."""
    env_model = os.getenv("LLM_MODEL_NAME")
    api_key = None
    model_options = []
    allow_custom = selected_provider in CLOUD_PROVIDERS
    caption = None
    error = None

    if selected_provider == "LMSTUDIO":
        try:
            discovered = get_lm_studio_loaded_llm_models()
            if discovered:
                model_options = discovered
                caption = f"Select a chat model currently loaded in LM Studio at {lm_studio_origin()}."
            else:
                error = lm_studio_no_model_message()
        except Exception as exc:
            error = (
                f"Could not reach LM Studio at {lm_studio_origin()}. {exc}\n"
                "Start the server with `lms server start` and load a model."
            )

    elif selected_provider == "OLLAMA":
        try:
            discovered = get_ollama_llm_models()
            if discovered:
                model_options = discovered
                caption = f"Select a model pulled in Ollama at {ollama_origin()}."
            else:
                error = ollama_no_model_message()
        except Exception as exc:
            error = str(exc) or ollama_unreachable_message()

    elif selected_provider in CLOUD_PROVIDERS:
        env_name = api_key_env_name(selected_provider)
        default_key = os.getenv(env_name, "") if env_name else ""
        if selected_provider == "GEMINI" and not default_key:
            default_key = os.getenv("GOOGLE_API_KEY", "")
        widget_key = f"{selected_provider}_api_key"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = default_key
        key_labels = {
            "OPENAI": "OpenAI API key",
            "ANTHROPIC": "Anthropic (Claude) API key",
            "GEMINI": "Gemini API key",
        }
        api_key = st.text_input(
            key_labels[selected_provider],
            type="password",
            key=widget_key,
            help=(
                "Required to list models and make calls. Kept for this session only "
                f"unless {env_name} is set in .env."
            ),
        ).strip()
        if not api_key:
            error = missing_api_key_message(selected_provider)
        else:
            try:
                model_options = list_cloud_chat_models(selected_provider, api_key)
                if model_options:
                    caption = "Select which model to use for SQL generation."
                else:
                    error = (
                        f"No chat models were returned by {PROVIDER_DISPLAY[selected_provider]}. "
                        "Type a model id below."
                    )
            except Exception as exc:
                error = str(exc)
                caption = "Could not list models automatically. Type a model id below."

    if error:
        st.error(error)
    if caption:
        st.caption(caption)

    selected_model = _select_model(
        model_options,
        env_model,
        allow_custom=allow_custom and bool(api_key),
        widget_ns=selected_provider.lower(),
    )
    return selected_model, api_key or None


def style_chart(figure):
    """Apply the dashboard's visual system to generated Plotly figures."""
    figure.update_layout(
        paper_bgcolor="#12181c",
        plot_bgcolor="#0b1013",
        font=dict(color="#e9edf0", family="Space Grotesk"),
        colorway=["#d6ff4b", "#7cd7c3", "#ffb86b", "#8eb8ff"],
        title_font=dict(color="#e9edf0", size=16),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#89939b")),
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis=dict(gridcolor="#263138", zerolinecolor="#354149"),
        yaxis=dict(gridcolor="#263138", zerolinecolor="#354149"),
    )
    return figure


# =====================================================================
# UI CONFIGURATION & CUSTOM STYLING
# =====================================================================
st.set_page_config(
    page_title="NL2SQL Enterprise Dashboard",
    page_icon="DB",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    :root {
        --ink: #e9edf0;
        --muted: #89939b;
        --dim: #59636b;
        --line: #2a3339;
        --panel: #12181c;
        --panel-raised: #182126;
        --canvas: #0b1013;
        --signal: #d6ff4b;
        --signal-soft: rgba(214, 255, 75, 0.12);
    }

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }

    .stApp {
        background: var(--canvas);
        color: var(--ink);
        background-image: linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
        background-size: 32px 32px;
    }

    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: #0e1417;
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
    [data-testid="stSidebar"] hr { border-color: var(--line); margin: 1.25rem 0; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: var(--ink);
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    [data-testid="stSidebar"] .stCaption { color: var(--dim); }

    .brand-lockup {
        border-left: 3px solid var(--signal);
        padding: 0.15rem 0 0.15rem 0.9rem;
        margin-bottom: 2.5rem;
    }
    .brand-lockup .eyebrow, .section-kicker {
        color: var(--signal);
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }
    .brand-lockup h1 {
        color: var(--ink);
        font-size: 1.15rem;
        letter-spacing: 0.08em;
        margin: 0.35rem 0 0;
        text-transform: uppercase;
    }
    .hero {
        border-bottom: 1px solid var(--line);
        margin: 1.5rem 0 2.25rem;
        padding: 1.25rem 0 1.5rem;
    }
    .hero h1 {
        color: var(--ink);
        font-size: clamp(2.2rem, 5vw, 4.8rem);
        font-weight: 600;
        letter-spacing: -0.04em;
        line-height: 0.98;
        margin: 0.45rem 0 0.9rem;
        max-width: 780px;
    }
    .hero p { color: var(--muted); font-size: 1rem; margin: 0; }
    .query-shell {
        background: var(--panel);
        border: 1px solid var(--line);
        border-top: 2px solid var(--signal);
        padding: 1.25rem 1.35rem 1.4rem;
        margin-bottom: 2rem;
    }
    .stTextInput input {
        background: #0c1114 !important;
        border: 1px solid #354149 !important;
        border-radius: 2px !important;
        color: var(--ink) !important;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.93rem;
        padding: 1rem !important;
    }
    .stTextInput input:focus { border-color: var(--signal) !important; box-shadow: 0 0 0 1px var(--signal) !important; }
    .stButton > button {
        background: var(--signal) !important;
        border: 1px solid var(--signal) !important;
        border-radius: 2px !important;
        color: #11170b !important;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .stButton > button:hover { background: #edff9c !important; border-color: #edff9c !important; }
    .stButton > button:disabled { background: #2c353a !important; border-color: #2c353a !important; color: #69747b !important; }
    .stSelectbox > div > div, .stTextInput > div > div, .stNumberInput > div > div {
        border-radius: 2px !important;
        border-color: #354149 !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid var(--line); }
    .stTabs [data-baseweb="tab"] { color: var(--muted); padding: 0.75rem 1.2rem; }
    .stTabs [aria-selected="true"] { color: var(--signal) !important; border-bottom-color: var(--signal) !important; }
    .stCodeBlock, [data-testid="stDataFrame"] { border: 1px solid var(--line); }
    .metric-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-left: 3px solid var(--signal);
        padding: 1.2rem 1.35rem;
    }
    .metric-card h4 { color: var(--muted) !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.1em; }
    .metric-card h1 { color: var(--signal) !important; font-size: 2.35rem !important; }
    [data-testid="stStatusWidget"] { border-radius: 2px; border-color: var(--line); }
</style>
""", unsafe_allow_html=True)

# Sidebar Configuration Block
with st.sidebar:
    st.markdown('<div class="brand-lockup"><div class="eyebrow">Query / Intelligence / 01</div><h1>NL2SQL Engine</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Model Configuration")
    
    # Dynamic runtime options for model agnosticism
    provider_options = ["LMSTUDIO", "OLLAMA", "OPENAI", "ANTHROPIC", "GEMINI"]
    env_provider = os.getenv("LLM_PROVIDER", "lmstudio").upper().replace("-", "").replace("_", "").replace(" ", "")
    if env_provider not in provider_options:
        provider_options.append(env_provider)
        
    selected_provider = st.selectbox(
        "LLM Provider",
        provider_options,
        index=provider_options.index(env_provider),
        format_func=lambda p: PROVIDER_DISPLAY.get(p, p),
    )

    selected_model, provider_api_key = render_provider_settings(selected_provider)
    
    max_retries = st.slider("Max Retries for LLM Auto-Fix", 1, 5, 3)
    st.markdown("---")
    st.markdown("### Database Connection")
    db_method = st.radio("Connection Source", ["Use .env config", "Manual Configuration"], label_visibility="collapsed")
    
    custom_db_url = None
    if db_method == "Manual Configuration":
        with st.expander("Configure Connection", expanded=True):
            dialect = st.selectbox("Dialect", ["postgresql", "mysql", "sqlite", "mssql", "oracle"])
            if dialect == "sqlite":
                sqlite_path = st.text_input("File Path", "sqlite:///my_db.sqlite")
                custom_db_url = sqlite_path
            else:
                host = st.text_input("Host", "localhost")
                port = st.text_input("Port", "5432" if dialect == "postgresql" else "3306")
                db_user = st.text_input("Username", "")
                db_pass = st.text_input("Password", type="password")
                db_name = st.text_input("Database Name", "")
                
                driver = "+psycopg2" if dialect == "postgresql" else "+pymysql" if dialect == "mysql" else ""
                if db_user and db_name:
                    auth = f"{db_user}:{db_pass}@" if db_pass else f"{db_user}@"
                    custom_db_url = f"{dialect}{driver}://{auth}{host}:{port}/{db_name}"
        
        if custom_db_url:
            st.caption("Credentials should be explicitly read-only.")
            if st.button("Sync schema to vector DB", use_container_width=True):
                with st.spinner("Syncing Schema..."):
                    try:
                        sync_database_schema(custom_db_url)
                        st.success("Successfully vectorized custom schema!")
                    except Exception as e:
                        st.error(f"Sync failed: {e}")

    st.markdown("---")
    st.caption("SYSTEM BUILD 2026.09 / AI ANALYTICS")

# Header Layout
st.markdown('<div class="hero"><div class="section-kicker">Natural language query interface</div><h1>Database intelligence,<br>without the friction.</h1><p>Translate intent into executable SQL, validated results, and decision-ready visualizations.</p></div>', unsafe_allow_html=True)

# Input Section
col1, col2, col3 = st.columns([1, 6, 1])
with col2:
    st.markdown('<div class="query-shell"><div class="section-kicker">Input / Ask the warehouse</div>', unsafe_allow_html=True)
    question = st.text_input("Ask a question", placeholder="e.g. Show revenue by payment type for the last quarter", label_visibility="collapsed")
    run_btn = st.button(
        "Analyze data",
        type="primary",
        use_container_width=True,
        disabled=(
            not selected_model
            or (selected_provider in CLOUD_PROVIDERS and not provider_api_key)
        ),
    )
    st.markdown('</div>', unsafe_allow_html=True)

if run_btn and question:
    if selected_provider == "LMSTUDIO" and not selected_model:
        st.error(lm_studio_no_model_message())
        st.stop()
    if selected_provider == "OLLAMA" and not selected_model:
        st.error(ollama_no_model_message())
        st.stop()
    if selected_provider in CLOUD_PROVIDERS and not provider_api_key:
        st.error(missing_api_key_message(selected_provider))
        st.stop()
    if not selected_model:
        st.error("Select a generation model first.")
        st.stop()
    st.markdown("---")
    with st.status("Synthesizing query", expanded=True) as status:
        st.write(f"Routing request to {selected_provider} / {selected_model}...")
        try:
            result_payload = execute_sql_with_self_correction(
                question, 
                max_retries=max_retries, 
                db_url=custom_db_url,
                provider=selected_provider,
                model_name=selected_model,
                api_key=provider_api_key,
            )
            status.update(label="Query compiled successfully", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Query synthesis failed", state="error", expanded=False)
            st.error(f"Application error: {str(e)}")
            st.stop()
            
    if "error" in result_payload:
        st.error("### ⚠️ Query Execution Failed")
        st.warning(result_payload["error"])
        with st.expander("View Attempted SQL"):
            st.code(result_payload.get("sql", "N/A"), language="sql")
    else:
        sql_query = result_payload.get("sql", "N/A")
        data_rows = result_payload.get("results", [])
        
        tab1, tab2, tab3 = st.tabs(["Visualization", "Raw data", "Generated SQL"])
        
        with tab3:
            st.markdown("### Generated SQL")
            st.code(sql_query, language="sql")
            
        with tab2:
            st.markdown("### Result set")
            if not data_rows:
                st.info("The query executed perfectly, but returned 0 rows.")
            else:
                st.dataframe(pd.DataFrame(data_rows))
                
        with tab1:
            if not data_rows:
                st.warning("No data returned to visualize.")
            else:
                df = pd.DataFrame(data_rows)
                
                # CRITICAL VIZ FIX: Force parse objects/Decimal classes into native numeric floats
                for col in df.columns:
                    if df[col].dtype == 'object':
                        try:
                            df[col] = pd.to_numeric(df[col], errors='raise')
                        except Exception:
                            pass
                
                # Dynamic Column Categorization
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                date_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
                for col in df.select_dtypes(include=['object']):
                    if df[col].astype(str).str.match(r'^\d{4}-\d{2}-\d{2}').any():
                        date_cols.append(col)
                        
                cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]
                
                try:
                    # Case A: Single numeric metrics
                    if len(df) == 1 and len(numeric_cols) > 0:
                        st.markdown("### Key metrics")
                        cols = st.columns(len(numeric_cols))
                        for i, col in enumerate(numeric_cols):
                            val = df[col].iloc[0]
                            value_str = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                            cols[i].markdown(f'''
                            <div class="metric-card">
                                <h4 style="color:#A0AEC0; margin-top:0px; font-weight:500;">{col.replace('_', ' ').upper()}</h4>
                                <h1 style="color:#00C9FF; margin-bottom:0px; font-size:3rem;">{value_str}</h1>
                            </div>
                            ''', unsafe_allow_html=True)
                            
                    # Case B: Time-series curve reports
                    elif len(date_cols) > 0 and len(numeric_cols) > 0:
                        x_axis = date_cols[0]
                        fig = style_chart(px.area(df, x=x_axis, y=numeric_cols, title=f"Performance Trend over {x_axis}", template="plotly_dark"))
                        fig.update_traces(mode="lines+markers", fill='tozeroy', line=dict(width=3))
                        st.plotly_chart(fig, use_container_width=True)
                        
                    # Case C: Categorical Reports (e.g., Revenue by Payment Method)
                    elif len(cat_cols) > 0 and len(numeric_cols) > 0:
                        x_axis = cat_cols[0]
                        y_axis = numeric_cols[0]
                        
                        # For clean report building, present visual breakdowns side-by-side if categories are concise
                        if df[x_axis].nunique() <= 7 and len(numeric_cols) == 1:
                            v_col1, v_col2 = st.columns(2)
                            with v_col1:
                                fig_bar = style_chart(px.bar(df, x=x_axis, y=y_axis, title=f"{y_axis.title()} by {x_axis.title()}", template="plotly_dark", color=x_axis))
                                st.plotly_chart(fig_bar, use_container_width=True)
                            with v_col2:
                                fig_pie = style_chart(px.pie(df, names=x_axis, values=y_axis, hole=0.4, title=f"{y_axis.title()} Distribution Mix", template="plotly_dark"))
                                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                                st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            fig = style_chart(px.bar(df, x=x_axis, y=numeric_cols, title=f"{', '.join(numeric_cols).title()} Grouped by {x_axis.title()}", barmode='group', template="plotly_dark"))
                            st.plotly_chart(fig, use_container_width=True)
                        
                    # Case D: Scatter Plot correlation reports
                    elif len(numeric_cols) >= 2:
                        fig = style_chart(px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=f"Correlation: {numeric_cols[1].title()} vs {numeric_cols[0].title()}", template="plotly_dark"))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Data compiled successfully. Open the Raw data tab for the tabular result.")
                except Exception as e:
                    st.warning(f"Could not render automated visual reports: {e}")
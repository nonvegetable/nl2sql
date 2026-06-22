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
from sync_schema import sync_database_schema
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# UI CONFIGURATION & CUSTOM STYLING
# =====================================================================
st.set_page_config(
    page_title="NL2SQL Enterprise Dashboard",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .glow-text {
        font-size: 3.5rem;
        font-weight: 900;
        background: -webkit-linear-gradient(45deg, #00C9FF, #92FE9D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 5px;
    }
    .sub-glow {
        text-align: center;
        color: #A0AEC0;
        margin-bottom: 40px;
        font-size: 1.3rem;
        font-weight: 500;
    }
    .metric-card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15);
        border: 1px solid #334155;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .stTextInput input {
        border-radius: 10px !important;
        border: 1px solid #334155 !important;
        padding: 15px !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Configuration Block
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8342/8342886.png", width=80)
    st.markdown("## 🌌 NL2SQL Engine")
    st.markdown("Welcome to the **Enterprise Analytics Portal**.")
    st.markdown("---")
    st.markdown("### 🔧 Model Configuration Panel")
    
    # Dynamic runtime options for model agnosticism
    provider_options = ["OLLAMA", "OPENAI", "ANTHROPIC", "GEMINI"]
    env_provider = os.getenv("LLM_PROVIDER", "ollama").upper()
    if env_provider not in provider_options:
        provider_options.append(env_provider)
        
    selected_provider = st.selectbox(
        "LLM Provider", 
        provider_options, 
        index=provider_options.index(env_provider)
    )
    
    # Auto-populate target models based on provider selection
    if selected_provider == "OPENAI":
        model_options = ["gpt-4o", "gpt-4o-mini", "o1-mini"]
    elif selected_provider == "ANTHROPIC":
        model_options = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229"]
    elif selected_provider == "GEMINI":
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro"]
    else:
        model_options = ["qwen3:4b", "gemma4:e2b", "llama3"]
        
    env_model = os.getenv("LLM_MODEL_NAME", model_options[0])
    if env_model not in model_options:
        model_options.insert(0, env_model)
        
    selected_model = st.selectbox(
        "Generation Model", 
        model_options, 
        index=model_options.index(env_model)
    )
    
    max_retries = st.slider("Max Retries for LLM Auto-Fix", 1, 5, 3)
    st.markdown("---")
    st.markdown("### 🗄️ Database Connection")
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
            st.caption("⚠️ Ensure credentials provided are explicitly **read-only**.")
            if st.button("🔄 Sync Schema to Vector DB", use_container_width=True):
                with st.spinner("Syncing Schema..."):
                    try:
                        sync_database_schema(custom_db_url)
                        st.success("Successfully vectorized custom schema!")
                    except Exception as e:
                        st.error(f"Sync failed: {e}")

    st.markdown("---")
    st.caption("© 2026 AI Analytics Inc.")

# Header Layout
st.markdown('<p class="glow-text">Next-Gen Database Intelligence</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-glow">Ask database queries in natural language and generate reports instantly.</p>', unsafe_allow_html=True)

# Input Section
col1, col2, col3 = st.columns([1, 6, 1])
with col2:
    question = st.text_input(
        "Ask a question",
        placeholder="✨ e.g., 'Create a report based on revenue based on payment types'",
        label_visibility="collapsed"
    )
    col_btn1, col_btn2, col_btn3 = st.columns([2, 3, 2])
    with col_btn2:
        run_btn = st.button("🚀 Analyze Data", type="primary", use_container_width=True)

if run_btn and question:
    st.markdown("---")
    with st.status("🧠 Synthesizing Intelligence...", expanded=True) as status:
        st.write(f"🔍 Directing prompt to {selected_provider} ({selected_model})...")
        try:
            result_payload = execute_sql_with_self_correction(
                question, 
                max_retries=max_retries, 
                db_url=custom_db_url,
                provider=selected_provider,
                model_name=selected_model
            )
            status.update(label="✅ Success! Intelligence Compiled.", state="complete", expanded=False)
        except Exception as e:
            status.update(label="❌ Failed to synthesize data.", state="error", expanded=False)
            st.error(f"Application crash detected: {str(e)}")
            st.stop()
            
    if "error" in result_payload:
        st.error("### ⚠️ Query Execution Failed")
        st.warning(result_payload["error"])
        with st.expander("View Attempted SQL"):
            st.code(result_payload.get("sql", "N/A"), language="sql")
    else:
        sql_query = result_payload.get("sql", "N/A")
        data_rows = result_payload.get("results", [])
        
        tab1, tab2, tab3 = st.tabs(["📊 Executive Visualization", "📋 Raw Data", "💻 Underlying SQL"])
        
        with tab3:
            st.markdown("### 🧩 Generated PostgreSQL")
            st.code(sql_query, language="sql")
            
        with tab2:
            st.markdown("### 📋 Acquired Dataset")
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
                        st.markdown("### 📈 Key Metrics")
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
                        fig = px.area(df, x=x_axis, y=numeric_cols, title=f"Performance Trend over {x_axis}", template="plotly_dark")
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
                                fig_bar = px.bar(df, x=x_axis, y=y_axis, title=f"{y_axis.title()} by {x_axis.title()}", template="plotly_dark", color=x_axis)
                                st.plotly_chart(fig_bar, use_container_width=True)
                            with v_col2:
                                fig_pie = px.pie(df, names=x_axis, values=y_axis, hole=0.4, title=f"{y_axis.title()} Distribution Mix", template="plotly_dark")
                                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                                st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            fig = px.bar(df, x=x_axis, y=numeric_cols, title=f"{', '.join(numeric_cols).title()} Grouped by {x_axis.title()}", barmode='group', template="plotly_dark")
                            st.plotly_chart(fig, use_container_width=True)
                        
                    # Case D: Scatter Plot correlation reports
                    elif len(numeric_cols) >= 2:
                        fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=f"Correlation: {numeric_cols[1].title()} vs {numeric_cols[0].title()}", template="plotly_dark")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("✨ Data compiled perfectly. Check the 'Raw Data' tab for table reports.")
                except Exception as e:
                    st.warning(f"Could not render automated visual reports: {e}")
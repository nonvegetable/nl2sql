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

# Custom CSS for a "wow" factor
st.markdown("""
<style>
    /* Glow text effect */
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
    /* Metric Card styling */
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

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8342/8342886.png", width=80)
    st.markdown("## 🌌 NL2SQL Engine")
    st.markdown("Welcome to the **Enterprise Analytics Portal**.")
    st.info(
        "💡 **How it works:** \n\n"
        "1. You type a natural language prompt.\n"
        "2. We embed it and search our semantic schema DB.\n"
        "3. The active LLM compiles accurate PostgreSQL.\n"
        "4. We safely query read-only replicas.\n"
        "5. We map the data back to interactive charts."
    )
    st.markdown("---")
    st.markdown("### 🔧 Settings")
    
    # Read environment variables dynamically
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").upper()
    llm_model = os.getenv("LLM_MODEL_NAME", "qwen3:4b")
    
    # Display the active model state agnostically
    st.info(f"**Active Provider:** {llm_provider}\n\n**Gen Model:** {llm_model}")
    
    st.slider("Max Retries for LLM Auto-Fix", 1, 5, 3)
    st.markdown("---")
    st.caption("© 2026 AI Analytics Inc.")

# Header
st.markdown('<p class="glow-text">Next-Gen Database Intelligence</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-glow">Ask your database questions in natural language and get instantaneous visualization.</p>', unsafe_allow_html=True)

# =====================================================================
# INPUT SECTION
# =====================================================================
col1, col2, col3 = st.columns([1, 6, 1])
with col2:
    question = st.text_input(
        "Ask a question",
        placeholder="✨ e.g., 'What were the total sales for clothing items last quarter?'",
        label_visibility="collapsed"
    )
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 3, 2])
    with col_btn2:
        run_btn = st.button("🚀 Analyze Data", type="primary", use_container_width=True)

if run_btn and question:
    st.markdown("---")
    
    with st.status("🧠 Synthesizing Intelligence...", expanded=True) as status:
        st.write("🔍 Embedding prompt & fetching semantic schemas...")
        st.write("🤖 Querying local LLM to generate PostgreSQL...")
        st.write("🛡️ Executing securely against read-only node...")
        try:
            result_payload = execute_sql_with_self_correction(question)
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
        
        # Gorgeous Tabs!
        tab1, tab2, tab3 = st.tabs(["📊 Visualization", "📋 Raw Data", "💻 Underlying SQL"])
        
        with tab3:
            st.markdown("### 🧩 Generated PostgreSQL")
            st.code(sql_query, language="sql")
            
        with tab2:
            st.markdown("### 📋 Acquired Dataset")
            if not data_rows:
                st.info("The query executed perfectly, but returned 0 rows.")
            else:
                df = pd.DataFrame(data_rows)
                st.dataframe(df)  # Removed deprecated keyword argument
                
        with tab1:
            if not data_rows:
                st.warning("No data returned to visualize.")
            else:
                df = pd.DataFrame(data_rows)
                
                # Detect columns
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                date_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
                for col in df.select_dtypes(include=['object']):
                    if df[col].astype(str).str.match(r'^\d{4}-\d{2}-\d{2}').any():
                        date_cols.append(col)
                        
                cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]
                
                try:
                    # Case A: Single numeric aggregates
                    if len(df) == 1 and len(numeric_cols) > 0:
                        st.markdown("### 📈 Key Metrics")
                        st.write("")
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
                            
                    # Case B: Time-series
                    elif len(date_cols) > 0 and len(numeric_cols) > 0:
                        x_axis = date_cols[0]
                        fig = px.area(df, x=x_axis, y=numeric_cols, title=f"Performance Trend over {x_axis}", template="plotly_dark")
                        fig.update_traces(mode="lines+markers", fill='tozeroy', line=dict(width=3))
                        st.plotly_chart(fig, use_container_width=True)
                        
                    # Case C: Grouped categorical
                    elif len(cat_cols) > 0 and len(numeric_cols) > 0:
                        x_axis = cat_cols[0]
                        y_axis = numeric_cols[0]
                        
                        if df[x_axis].nunique() <= 7 and len(numeric_cols) == 1:
                            fig = px.pie(df, names=x_axis, values=y_axis, hole=0.4, title=f"{y_axis.title()} Distribution by {x_axis.title()}", template="plotly_dark")
                            fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#000000', width=2)))
                        else:
                            fig = px.bar(df, x=x_axis, y=numeric_cols, title=f"{', '.join(numeric_cols).title()} grouped by {x_axis.title()}", barmode='group', template="plotly_dark")
                            fig.update_traces(marker_line_color='rgb(8,48,107)', marker_line_width=1.5, opacity=0.8)
                        st.plotly_chart(fig, use_container_width=True)
                        
                    # Case D: Scatter
                    elif len(numeric_cols) >= 2:
                        fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=f"Correlation: {numeric_cols[1].title()} vs {numeric_cols[0].title()}", template="plotly_dark", size=numeric_cols[1] if len(numeric_cols) > 2 else None)
                        st.plotly_chart(fig, use_container_width=True)
                        
                    else:
                        st.info("✨ Data fetched successfully. Raw data is available in the next tab.")
                        
                except Exception as e:
                    st.warning(f"Could not render an automated chart: {e}")

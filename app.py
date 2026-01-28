import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
import time

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="VANTAGE // INTELLIGENCE", layout="wide", initial_sidebar_state="collapsed")

# Model Selection (User requested specifics, mapped to Groq capability)
# Note: Using Llama 3.3 70B as the execution engine for Agent 3
AI_MODEL = "openai/gpt-oss-120b" 

# --- 2. CSS ARCHITECTURE (THE BLACK TIE THEME) ---
st.markdown("""
<style>
    /* GLOBAL RESET & FONT */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
    
    .stApp { 
        background-color: #050505; 
        color: #e0e0e0; 
        font-family: 'Inter', sans-serif; 
    }
    
    /* REMOVE STREAMLIT PADDING */
    .block-container { 
        padding-top: 1.5rem !important; 
        padding-bottom: 2rem !important; 
        max-width: 98% !important;
    }
    header, footer { display: none !important; }

    /* --- DASHBOARD PANELS --- */
    .panel-container {
        background-color: #09090b;
        border: 1px solid #1a1a1a;
        border-radius: 8px;
        padding: 20px;
        height: 500px; /* FIXED HEIGHT FOR ALIGNMENT */
        overflow-y: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        position: relative;
    }

    /* --- METRIC CARDS (TOP ROW) --- */
    .metric-box {
        background: #09090b;
        border: 1px solid #1a1a1a;
        padding: 15px;
        border-radius: 6px;
        text-align: center;
    }
    .metric-val { font-family: 'JetBrains Mono', monospace; font-size: 24px; color: #fff; font-weight: 700; }
    .metric-label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }
    .metric-red { color: #FF3333 !important; text-shadow: 0 0 10px rgba(255, 51, 51, 0.3); }

    /* --- THE ACTIVATION BUTTON (INITIAL STATE) --- */
    div.stButton > button {
        background: linear-gradient(45deg, #09090b, #111);
        border: 1px solid #00D4FF;
        color: #00D4FF;
        height: 100%;
        min-height: 400px; /* FILLS THE PANEL */
        width: 100%;
        font-family: 'JetBrains Mono', monospace;
        font-size: 16px;
        letter-spacing: 2px;
        text-transform: uppercase;
        transition: all 0.4s ease;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.05);
    }
    div.stButton > button:hover {
        background: rgba(0, 212, 255, 0.05);
        box-shadow: 0 0 40px rgba(0, 212, 255, 0.2);
        border-color: #fff;
        color: #fff;
    }
    div.stButton > button:active {
        background: #00D4FF;
        color: #000;
    }

    /* --- THE "RED STRIPE" CARDS (RESULT STATE) --- */
    .risk-card {
        background-color: #0c0c0e;
        border: 1px solid #1f1f1f;
        border-left: 3px solid #FF3333;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 0 4px 4px 0;
        animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn { 0% { opacity: 0; transform: translateY(10px); } 100% { opacity: 1; transform: translateY(0); } }
    
    .risk-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 5px;
    }
    .risk-title {
        color: #e0e0e0;
        font-weight: 600;
        font-size: 14px;
        font-family: 'JetBrains Mono', monospace;
    }
    .risk-tag {
        background: rgba(255, 51, 51, 0.15);
        color: #FF3333;
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 2px;
        border: 1px solid rgba(255, 51, 51, 0.3);
    }
    .risk-body {
        color: #888;
        font-size: 12px;
        line-height: 1.4;
    }

    /* SCROLLBAR */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: #000; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

</style>
""", unsafe_allow_html=True)

# --- 3. STATE MANAGEMENT (THE BRAIN) ---
if 'scan_complete' not in st.session_state:
    st.session_state['scan_complete'] = False
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = []

# --- 4. DATA CONNECTIONS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: groq_client = None
except:
    st.error("CRITICAL ERROR: SECRETS DISCONNECTED.")
    st.stop()

@st.cache_data(ttl=10)
def load_data():
    try:
        r = supabase.table("audit_ledger").select("*").execute()
        return pd.DataFrame(r.data)
    except: return pd.DataFrame()

df = load_data()

# --- 5. AGENT 3 LOGIC (THE DETECTIVE) ---
def run_agent_3(data):
    if not groq_client: return ["SYSTEM OFFLINE"]
    
    # 1. Aggregate
    stats = data.groupby('vendor_name').agg(
        spend=('total_amount', 'sum'),
        txns=('invoice_id', 'count')
    ).reset_index().sort_values('spend', ascending=False).head(15)
    
    # 2. Evidence String
    evidence = [f"{r['vendor_name']}: ${r['spend']:,.0f} ({r['txns']} inv)" for _, r in stats.iterrows()]
    
    # 3. The Prompt
    prompt = f"""
    ROLE: Forensic Financial Auditor.
    DATA: {evidence}
    TASK: Identify the top 5 highest risk vendors.
    
    PATTERNS TO DETECT:
    1. DOMINANCE (Too much % of total spend).
    2. VELOCITY (Too many invoices).
    3. STRUCTURING (Amounts near $2.5k, $5k, $10k).
    
    OUTPUT FORMAT ONLY:
    [VENDOR NAME] :: [PATTERN] -> [Short Evidence]
    """
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=AI_MODEL,
            temperature=0.1
        )
        return res.choices[0].message.content.split('\n')
    except Exception as e:
        return [f"ERROR :: API_FAIL -> {str(e)}"]

# --- 6. UI RENDER ---

if not df.empty:
    # PRE-PROCESS
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    if 'risk_score' not in df.columns: df['risk_score'] = 0
    
    # CALCULATE TOP METRICS
    total_exposure = df[df['risk_score'] > 50]['total_amount'].sum()
    high_risk_vendors = df[df['risk_score'] > 50]['vendor_name'].nunique()
    avg_risk = df['risk_score'].mean()

    # --- TOP ROW: KPI HUD ---
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f"<div class='metric-box'><div class='metric-val metric-red'>${total_exposure:,.0f}</div><div class='metric-label'>Total Exposure</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='metric-box'><div class='metric-val'>{high_risk_vendors}</div><div class='metric-label'>Active Targets</div></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='metric-box'><div class='metric-val'>{len(df)}</div><div class='metric-label'>Txn Volume</div></div>", unsafe_allow_html=True)
    k4.markdown(f"<div class='metric-box'><div class='metric-val'>{avg_risk:.0f}%</div><div class='metric-label'>Avg Risk Score</div></div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- MAIN CONSOLE (2 COLUMNS) ---
    c_left, c_right = st.columns([1.5, 1])
    
    # === LEFT PANEL: THE MAP (Chart) ===
    with c_left:
        st.markdown('<div class="panel-container">', unsafe_allow_html=True)
        st.markdown("<h3 style='color:#666; font-size:12px; margin-bottom:10px'>CAPITAL DISTRIBUTION MAP</h3>", unsafe_allow_html=True)
        
        # Aggregation for Chart
        chart_df = df.groupby('vendor_name')['total_amount'].sum().reset_index().sort_values('total_amount', ascending=False)
        
        # Professional Colors (Burgundy/Grey Scale)
        colors = ['#881111', '#aa2222', '#cc3333', '#2a2a2a', '#3a3a3a', '#4a4a4a']
        
        fig = go.Figure(data=[go.Pie(
            labels=chart_df['vendor_name'],
            values=chart_df['total_amount'],
            hole=0.7,
            marker=dict(colors=colors, line=dict(color='#09090b', width=3)),
            textinfo='label+percent',
            textposition='outside',
        )])
        
        fig.update_layout(
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=20, b=20, l=40, r=40),
            height=400,
            annotations=[dict(text='RISK<br>INDEX', x=0.5, y=0.5, font_size=14, showarrow=False, font_color='#666')]
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # === RIGHT PANEL: THE AGENT (Stateful Switch) ===
    with c_right:
        st.markdown('<div class="panel-container">', unsafe_allow_html=True)
        
        # STATE 1: SHOW BUTTON
        if not st.session_state['scan_complete']:
            # The CSS above makes this button fill the container height
            if st.button("INITIALIZE DEEP SCAN\n[ AGENT 3 ]"):
                with st.spinner("AGENT 3: HUNTING PATTERNS..."):
                    results = run_agent_3(df)
                    st.session_state['scan_results'] = results
                    st.session_state['scan_complete'] = True
                    st.rerun()
        
        # STATE 2: SHOW RESULTS (Replaces Button)
        else:
            st.markdown("<h3 style='color:#FF3333; font-size:12px; margin-bottom:15px; border-bottom:1px solid #333; padding-bottom:10px'>DETECTED ANOMALIES (LIVE)</h3>", unsafe_allow_html=True)
            
            # Reset Button (Small, Top Right)
            if st.button("RESET SYSTEM", key="reset"):
                st.session_state['scan_complete'] = False
                st.rerun()

            # Render Cards
            results = st.session_state['scan_results']
            if not results:
                st.info("System Clear. No Anomalies.")
            
            for item in results:
                if "::" in item:
                    parts = item.split("::")
                    name = parts[0].replace("*", "").strip()
                    rest = parts[1] if len(parts) > 1 else ""
                    
                    risk = "ANOMALY"
                    desc = rest
                    
                    if "->" in rest:
                        sub = rest.split("->")
                        risk = sub[0].strip()
                        desc = sub[1].strip()

                    # HTML CARD INJECTION
                    st.markdown(f"""
                    <div class="risk-card">
                        <div class="risk-header">
                            <span class="risk-title">{name}</span>
                            <span class="risk-tag">{risk}</span>
                        </div>
                        <div class="risk-body">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BOTTOM: LEDGER ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#666; font-size:14px'>GLOBAL EVIDENCE LEDGER</h3>", unsafe_allow_html=True)
    
    st.dataframe(
        df[['invoice_id', 'vendor_name', 'total_amount', 'risk_score', 'description']].sort_values('risk_score', ascending=False),
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d%%"),
            "total_amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        },
        hide_index=True
    )

else:
    st.warning("SYSTEM STANDBY: DATABASE CONNECTION LOST.")

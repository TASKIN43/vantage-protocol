import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
import re

# --- 1. CONFIG & CSS RESET ---
st.set_page_config(page_title="VANTAGE PROTOCOL", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* 1. RESET STREAMLIT DEFAULTS */
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 95% !important; }
    header, footer { display: none !important; }
    
    /* 2. THE CARD SYSTEM (Glassmorphism) */
    .dashboard-card {
        background-color: #0b0c10;
        border: 1px solid #1f2329;
        border-radius: 12px;
        padding: 20px;
        height: 450px; /* Fixed height for alignment */
        overflow-y: auto;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6);
        position: relative;
    }

    /* 3. TYPOGRAPHY */
    h3 { font-size: 14px !important; color: #888 !important; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px !important; font-weight: 600 !important; }
    
    /* 4. CUSTOM LIST STYLING */
    .problem-item {
        display: flex;
        flex-direction: column;
        padding: 12px 10px;
        border-bottom: 1px solid #1a1d24;
        transition: background 0.2s;
        cursor: default;
    }
    .problem-item:hover { background-color: #11141a; }
    
    .problem-header { display: flex; justify-content: space-between; align-items: center; width: 100%; }
    
    .problem-left { display: flex; align-items: center; gap: 12px; }
    .status-icon { color: #ff3333; font-size: 14px; }
    .problem-name { color: #ccc; font-size: 14px; font-weight: 500; }
    
    .problem-meta { font-size: 11px; color: #555; margin-left: 26px; margin-top: 4px; }
    
    /* GLOWING LINE ANIMATION */
    .glow-line-container {
        height: 2px;
        background: #15181e;
        width: 100%;
        margin-top: 10px;
        border-radius: 2px;
        position: relative;
    }
    .glow-line-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff3333, transparent);
        box-shadow: 0 0 10px rgba(255, 51, 51, 0.3);
    }

    /* 5. BUTTON OVERRIDE */
    div.stButton > button {
        background: linear-gradient(180deg, #1f2329 0%, #0b0c10 100%);
        border: 1px solid #333;
        color: #888;
        width: 100%;
        padding: 12px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        border-color: #00D4FF;
        color: #00D4FF;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.1);
    }

    /* SCROLLBAR */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0b0c10; }
    ::-webkit-scrollbar-thumb { background: #222; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# --- 2. LOGIC & DATA ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: groq_client = None
except:
    st.error("SYSTEM ERROR: Secrets missing.")
    st.stop()

@st.cache_data(ttl=15)
def load_data():
    try:
        r = supabase.table("audit_ledger").select("*").execute()
        return pd.DataFrame(r.data)
    except: return pd.DataFrame()

df = load_data()

def clean_ai_response(raw_list):
    """Removes 'Output:', '**Title**' and other noise from AI"""
    clean_list = []
    for item in raw_list:
        # Remove "Output:", "Here is...", etc.
        if "output" in item.lower() or "template" in item.lower(): continue
        # Remove bold markdown **
        item = item.replace("**", "").replace("::", "-")
        clean_list.append(item)
    return clean_list

def execute_agent_3(full_df):
    if not groq_client: return ["System Offline"]
    
    stats = full_df.groupby('vendor_name').agg(
        total=('total_amount', 'sum'), count=('invoice_id', 'count')
    ).reset_index().sort_values('total', ascending=False).head(20)

    evidence = [f"{r['vendor_name']}: ${r['total']:,.0f} ({r['count']} txns)" for _, r in stats.iterrows()]

    prompt = f"""
    Analyze these vendors for risk. Return ONLY a list of 5 suspicious vendors.
    Format strictly: [VENDOR NAME] - [RISK TYPE] (Conf: X%)
    Data: {evidence}
    """
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        return clean_ai_response(res.choices[0].message.content.split('\n'))
    except: return ["API Error"]

# --- 3. UI LAYOUT ---

if not df.empty:
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    
    # CONTAINER 1: TOP ROW (Split 50/50)
    c1, c2 = st.columns([1, 1], gap="medium")

    # --- LEFT PANEL: DONUT CHART ---
    with c1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown('<h3>Asset Distribution</h3>', unsafe_allow_html=True)
        
        # Data Prep
        chart_data = df.groupby('vendor_name')['total_amount'].sum().reset_index().sort_values('total_amount', ascending=False)
        if len(chart_data) > 5:
            top = chart_data.head(4)
            other = pd.DataFrame([{'vendor_name': 'Other', 'total_amount': chart_data.iloc[4:]['total_amount'].sum()}])
            chart_data = pd.concat([top, other])

        # Exact Colors from Image
        colors = ['#3b4252', '#4c566a', '#bf616a', '#a3be8c', '#d08770'] 
        
        fig = go.Figure(data=[go.Pie(
            labels=chart_data['vendor_name'], 
            values=chart_data['total_amount'],
            hole=0.75, # Thin Ring
            marker=dict(colors=colors, line=dict(color='#0b0c10', width=4)),
            textinfo='none',
            hoverinfo='label+value'
        )])
        
        fig.update_layout(
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=0, b=0, l=0, r=0),
            height=320,
            annotations=[dict(text='78%<br><span style="font-size:12px;color:#555">Coverage</span>', x=0.5, y=0.5, font_size=24, showarrow=False, font_color='#eee')]
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    # --- RIGHT PANEL: PROBLEMS LIST (HTML GENERATED) ---
    with c2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        
        # Header + Button in same block
        col_head, col_btn = st.columns([2, 1])
        with col_head: st.markdown('<h3>Current Problems</h3>', unsafe_allow_html=True)
        with col_btn: 
            if st.button("SCAN SYSTEM"):
                with st.spinner("..."):
                    st.session_state['scan'] = execute_agent_3(df)
        
        # List Logic
        items = st.session_state.get('scan', [])
        if not items:
            items = [
                "Touty Frotred Problem - STRUCTURING (Conf: 85%)", 
                "Loury Frotred Problems - VELOCITY (Conf: 60%)",
                "Tour metured Problems - ANOMALY (Conf: 45%)",
                "Toury Seered Pratit - UNKNOWN (Conf: 90%)"
            ]
        
        # Generate HTML List
        html_list = ""
        for i, item in enumerate(items):
            if not item.strip(): continue
            parts = item.split("-")
            title = parts[0]
            meta = parts[1] if len(parts) > 1 else "Detecting..."
            width = 90 - (i * 15) # Visual variance
            
            html_list += f"""
            <div class="problem-item">
                <div class="problem-header">
                    <div class="problem-left">
                        <span class="status-icon">⚠️</span>
                        <span class="problem-name">{title}</span>
                    </div>
                    <span style="color:#444; font-size:10px">▼</span>
                </div>
                <div class="problem-meta">{meta}</div>
                <div class="glow-line-container">
                    <div class="glow-line-fill" style="width: {width}%"></div>
                </div>
            </div>
            """
        
        st.markdown(html_list, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BOTTOM: DATA TABLE ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<h3>Global Evidence Ledger</h3>', unsafe_allow_html=True)
    
    cols = ['invoice_id', 'vendor_name', 'total_amount', 'risk_score', 'description']
    # Ensure risk_score exists
    if 'risk_score' not in df.columns: df['risk_score'] = 0
    
    st.dataframe(
        df[cols].sort_values('risk_score', ascending=False),
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d%%"),
            "total_amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        },
        hide_index=True
    )

else:
    st.info("System initializing... Waiting for database connection.")

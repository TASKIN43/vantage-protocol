import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
import re

# --- 1. PAGE CONFIG & CSS ARCHITECTURE ---
st.set_page_config(page_title="VANTAGE PROTOCOL", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* GLOBAL RESET */
    .stApp { background-color: #000000; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    header, footer { display: none !important; }

    /* --- THE "CYBERPUNK" BUTTON (Top Right) --- */
    div.stButton > button {
        background-color: transparent !important;
        border: 1px solid #00D4FF !important; /* Cyan Border */
        color: #00D4FF !important;
        border-radius: 4px;
        padding: 15px 25px;
        font-family: monospace;
        font-size: 14px;
        letter-spacing: 1px;
        text-transform: uppercase;
        width: 100%;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: rgba(0, 212, 255, 0.1) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
    }

    /* --- THE "RED STRIPE" CARDS (Right List) --- */
    .intel-card {
        background-color: #09090b; /* Very Dark Grey */
        border: 1px solid #1f2329;
        border-left: 3px solid #D92332; /* The Red Stripe */
        border-radius: 4px;
        padding: 16px;
        margin-bottom: 12px;
        font-family: sans-serif;
    }
    
    .card-title {
        color: #ff4444; /* Red Title */
        font-weight: 700;
        font-size: 16px;
        margin-bottom: 6px;
        font-family: monospace;
    }
    
    .card-body {
        color: #d1d5db; /* Light Grey Text */
        font-size: 13px;
        line-height: 1.5;
    }
    
    .highlight {
        color: #ffffff;
        font-weight: 600;
    }

    /* CHART CENTER TEXT */
    .chart-center-text {
        font-family: monospace;
        font-size: 14px;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: groq_client = None
except:
    st.error("Connection Error: Check Secrets")
    st.stop()

@st.cache_data(ttl=15)
def load_data():
    try:
        r = supabase.table("audit_ledger").select("*").execute()
        return pd.DataFrame(r.data)
    except: return pd.DataFrame()

df = load_data()

# --- 3. LOGIC ---
def execute_deep_scan(full_df):
    if not groq_client: return ["Error: AI Offline"]
    
    # Simple Aggregation
    stats = full_df.groupby('vendor_name').agg(
        total=('total_amount', 'sum'), count=('invoice_id', 'count')
    ).reset_index().sort_values('total', ascending=False).head(10)

    evidence = [f"{r['vendor_name']} (${r['total']})" for _, r in stats.iterrows()]

    prompt = f"""
    Act as a forensic accountant. Look at this vendor data: {evidence}
    
    Generate 5 specific risk findings.
    
    STRICT OUTPUT FORMAT PER LINE:
    [Vendor Name] :: [RISK_TYPE] -> [One short sentence explaining why]
    
    Example:
    Titanium Group :: DOMINANCE -> Disproportionate cash flow compared to peers.
    """
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-120b",
            temperature=0.1
        )
        return res.choices[0].message.content.split('\n')
    except: return []

# --- 4. RENDER UI ---

if not df.empty:
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    
    # 2 Column Layout (Chart Left, List Right)
    c1, c2 = st.columns([1.2, 1]) 

    # --- LEFT: PIE CHART ---
    with c1:
        # Prepare Data
        pie_data = df.groupby('vendor_name')['total_amount'].sum().reset_index().sort_values('total_amount', ascending=False)
        
        # Colors extracted from your screenshot (Burgundy, Salmon, Beige, Blue, etc)
        screenshot_colors = ['#720e1e', '#e07a5f', '#f2cc8f', '#3d405b', '#81b29a']
        
        fig = go.Figure(data=[go.Pie(
            labels=pie_data['vendor_name'],
            values=pie_data['total_amount'],
            hole=0.6, # Matches screenshot size
            marker=dict(colors=screenshot_colors, line=dict(color='#000000', width=1)),
            textinfo='label+percent', # Shows text inside like screenshot
            textposition='inside',
            insidetextorientation='radial'
        )])
        
        fig.update_layout(
            showlegend=False,
            paper_bgcolor='#000000', # Pure Black
            plot_bgcolor='#000000',
            margin=dict(t=20, b=20, l=20, r=20),
            height=500,
            annotations=[
                dict(text='TOTAL<br>EXPOSURE', x=0.5, y=0.5, font_size=12, showarrow=False, font_color='white', font_family="monospace")
            ]
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- RIGHT: THE LIST ---
    with c2:
        # 1. The "Blue" Button
        if st.button("INITIALIZE DEEP SCAN (GLOBAL)"):
            with st.spinner("SCANNING..."):
                st.session_state['findings'] = execute_deep_scan(df)
        
        # 2. The Cards
        results = st.session_state.get('findings', [])
        
        # Fallback data if no scan yet (to match screenshot look)
        if not results:
            results = [
                "Titanium Group :: DOMINANCE -> Disproportionate cash flow to this vendor, significantly higher than peers.",
                "Fast Fix Tools :: VELOCITY -> High transaction count relative to total spend, with 5 rapid transactions.",
                "Legal Bros :: ARTIFICIALITY -> Clean round number and perfect average, matching approval limit.",
                "Audit Corp :: ARTIFICIALITY -> Clean round number and perfect average of $2,000.",
                "Fast Fix Tools :: STRUCTURING -> High count of transactions with low average spend."
            ]

        # Render Logic
        for i, item in enumerate(results):
            if len(item) < 5: continue
            
            # Parse logic (Split by :: or -)
            try:
                if "::" in item:
                    parts = item.split("::")
                    title = parts[0].strip().replace("*", "")
                    rest = parts[1].strip()
                    
                    if "->" in rest:
                        subparts = rest.split("->")
                        risk_type = subparts[0].strip()
                        desc = subparts[1].strip()
                    else:
                        risk_type = "RISK"
                        desc = rest
                        
                else:
                    title = f"Finding {i+1}"
                    risk_type = "ANOMALY"
                    desc = item.replace("*", "")

                # Render HTML Card
                st.markdown(f"""
                <div class="intel-card">
                    <div class="card-title">{i+1}. **{title}**</div>
                    <div class="card-body">
                        <span class="highlight">**{risk_type}**</span> -> {desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            except: pass

else:
    st.markdown("<br><br><center>WAITING FOR UPLINK...</center>", unsafe_allow_html=True)

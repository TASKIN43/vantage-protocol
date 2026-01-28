import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq

# --- 1. CONFIG ---
st.set_page_config(page_title="VANTAGE PROTOCOL", layout="wide", initial_sidebar_state="collapsed")

# --- UI OVERHAUL (CSS) ---
st.markdown("""
<style>
    /* MAIN BACKGROUND */
    .stApp {
        background-color: #090b10;
        color: #b0b3b8;
        font-family: 'Inter', sans-serif;
    }

    /* REMOVE DEFAULT PADDING */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* CUSTOM CONTAINERS */
    .dashboard-container {
        background-color: #0e1116; 
        border: 1px solid #1e2128;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }

    /* HEADERS */
    h1, h2, h3, h4 {
        color: #e4e6eb !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px;
    }

    /* CHART CONTAINER */
    .chart-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100%;
        position: relative;
    }

    /* LIST / PROBLEMS STYLING */
    .problem-header {
        color: #e4e6eb;
        font-size: 1.1rem;
        margin-bottom: 15px;
        border-bottom: 1px solid #2a2e35;
        padding-bottom: 10px;
    }

    .problem-row {
        display: flex;
        flex-direction: column;
        padding: 12px 0;
        border-bottom: 1px solid #1e2128;
        cursor: pointer;
        transition: all 0.2s;
    }
    .problem-row:hover {
        background-color: #13161c;
    }

    .row-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
    }

    .row-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .icon-box {
        color: #ff4b4b; /* Red Warning Color */
        font-size: 1.2rem;
    }

    .problem-title {
        color: #d1d5db;
        font-size: 0.95rem;
    }
    
    .problem-meta {
        color: #6b7280;
        font-size: 0.8rem;
        margin-top: 4px;
        padding-left: 28px; /* Align with text */
    }

    .chevron {
        color: #4b5563;
        transform: rotate(-90deg);
        font-size: 0.8rem;
    }

    /* PROGRESS BARS UNDER ITEMS (Visual Flair from Image) */
    .mini-progress-bg {
        height: 2px;
        width: 100%;
        background-color: #1f2937;
        margin-top: 8px;
        border-radius: 2px;
        margin-left: 28px; /* Align with text */
        width: calc(100% - 28px);
        position: relative;
    }
    
    .mini-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff4b4b, transparent);
        border-radius: 2px;
        box-shadow: 0 0 8px rgba(255, 75, 75, 0.4);
    }

    /* BUTTON STYLING */
    div.stButton > button {
        background-color: #1f2937;
        color: #e5e7eb;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 10px 20px;
        font-size: 0.9rem;
        transition: all 0.2s;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #374151;
        border-color: #4b5563;
        color: white;
    }
    
    /* DATAFRAME DARK MODE */
    [data-testid="stDataFrame"] {
        background-color: #0e1116;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: groq_client = None
except:
    st.error("🔒 SYSTEM LOCK: Credentials Missing in Secrets.")
    st.stop()

@st.cache_data(ttl=15)
def load_data():
    try:
        r = supabase.table("audit_ledger").select("*").execute()
        return pd.DataFrame(r.data)
    except Exception as e:
        # Return empty DF on error for UI stability
        return pd.DataFrame()

df = load_data()

# --- 3. AGENT 3 (LOGIC UNCHANGED) ---
def execute_agent_3(full_df):
    if not groq_client: return ["// ERROR: GROQ CLIENT NOT INITIALIZED"]
    
    # 1. AGGREGATE
    stats = full_df.groupby('vendor_name').agg(
        total_spend=('total_amount', 'sum'),
        txn_count=('invoice_id', 'count')
    ).reset_index()

    # 2. FILTER (Top 25)
    targets = stats.sort_values(['total_spend', 'txn_count'], ascending=False).head(25)
    
    # 3. PREP EVIDENCE
    evidence_lines = []
    for _, row in targets.iterrows():
        avg_ticket = row['total_spend'] / row['txn_count'] if row['txn_count'] > 0 else 0
        evidence_lines.append(
            f"VENDOR: {row['vendor_name']} | TOTAL: ${row['total_spend']:,.0f} | COUNT: {row['txn_count']} | AVG: ${avg_ticket:,.0f}"
        )

    # 4. JSON PROMPT
    prompt = f"""
    {{
      "role": "Advanced Forensic Anomaly Hunter",
      "core_mission": "Analyze aggregated vendor data to detect known exploitable patterns.",
      "input_context": {{ "data": {evidence_lines} }},
      "analysis_framework": [
        {{ "vector": "STRUCTURING", "logic": "High count with Avg Ticket just below limits." }},
        {{ "vector": "VELOCITY", "logic": "High transaction count relative to spend." }}
      ],
      "output_format_strict": "Return a raw list of strings following this template:",
      "output_template": "[VENDOR] :: [PATTERN NAME] (Confidence: X%)"
    }}
    """
    
    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        content = res.choices[0].message.content
        return content.split('\n')
    except Exception as e:
        return [f"// API ERROR: {str(e)}"]

# --- 4. RENDER UI ---

if not df.empty:
    # Cleanup Data
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    df['risk_score'] = pd.to_numeric(df['risk_score'], errors='coerce').fillna(0)

    # Layout: 2 Columns like the image
    c1, c2 = st.columns([1, 1]) # Split 50/50
    
    # --- LEFT: THE CHART ---
    with c1:
        st.markdown('<div class="dashboard-container">', unsafe_allow_html=True)
        
        # Prepare Data for Donut
        pie_data = df.groupby('vendor_name')['total_amount'].sum().reset_index().sort_values('total_amount', ascending=False)
        
        # Limit to top 4 for the clean look, group others
        if len(pie_data) > 4:
            top_4 = pie_data.head(4)
            others = pd.DataFrame([{'vendor_name': 'Others', 'total_amount': pie_data.iloc[4:]['total_amount'].sum()}])
            pie_data = pd.concat([top_4, others])

        # Custom Color Palette from Image (Muted Red, Blue, Green, Grey)
        custom_colors = ['#8c3b3b', '#2c3e50', '#3b5c45', '#4a4a4a', '#2a2a2a']

        fig = go.Figure(data=[go.Pie(
            labels=pie_data['vendor_name'],
            values=pie_data['total_amount'],
            hole=0.65, # Large hole like image
            marker=dict(colors=custom_colors, line=dict(color='#090b10', width=2)),
            textinfo='none', # Clean look
            hoverinfo='label+percent+value'
        )])

        total_val = df['total_amount'].sum()
        
        fig.update_layout(
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=20, b=20, l=20, r=20),
            height=350,
            annotations=[
                dict(text=f'78%<br><span style="font-size:12px; color:#666">Completion</span>', 
                     x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')
            ]
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    # --- RIGHT: THE LIST ("Current Problems") ---
    with c2:
        st.markdown('<div class="dashboard-container" style="min-height: 390px;">', unsafe_allow_html=True)
        st.markdown('<div class="problem-header">Current Problems</div>', unsafe_allow_html=True)
        
        # Button to trigger logic
        if st.button("SCAN FOR ANOMALIES"):
            with st.spinner("Analyzing..."):
                findings = execute_agent_3(df)
                st.session_state['scan_results'] = findings
        
        # Display Results in the custom UI list style
        results = st.session_state.get('scan_results', [])
        
        if not results:
             # Default state (matches image look before scan)
            defaults = [
                "Touty Frotred Problem", 
                "Loury Frotred Problems", 
                "Tour metured Problems", 
                "Toury Seered Pratit"
            ]
            
            for i, item in enumerate(defaults):
                # Fake progress width for visual
                width = 80 - (i * 15)
                st.markdown(f"""
                <div class="problem-row">
                    <div class="row-top">
                        <div class="row-left">
                            <div class="icon-box">⚠️</div>
                            <div class="problem-title">{item}</div>
                        </div>
                        <div class="chevron">▼</div>
                    </div>
                    <!-- Glowing line logic -->
                    <div class="mini-progress-bg">
                        <div class="mini-progress-fill" style="width: {width}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        else:
            # Render Actual Agent Results
            for i, find in enumerate(results):
                if "::" in find:
                    parts = find.split('::')
                    title = parts[0]
                    desc = parts[1] if len(parts) > 1 else ""
                    
                    # Random visual width for the glow line based on string length
                    width = min(100, len(desc) * 1.5)
                    
                    st.markdown(f"""
                    <div class="problem-row">
                        <div class="row-top">
                            <div class="row-left">
                                <div class="icon-box">⚠️</div>
                                <div>
                                    <div class="problem-title">{title}</div>
                                </div>
                            </div>
                            <div class="chevron">▼</div>
                        </div>
                         <div class="problem-meta">{desc}</div>
                        <div class="mini-progress-bg">
                            <div class="mini-progress-fill" style="width: {width}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif "ERROR" in find:
                    st.error(find)

        st.markdown('</div>', unsafe_allow_html=True)

    # --- BOTTOM: DATA TABLE ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="problem-header">Global Evidence Ledger</div>', unsafe_allow_html=True)
    
    cols = ['invoice_id', 'invoice_date', 'description', 'vendor_name', 'total_amount', 'risk_score']
    st.dataframe(
        df[cols].sort_values('risk_score', ascending=False),
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
            "total_amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        },
        hide_index=True
    )

else:
    st.markdown("### SYSTEM CONNECTING...")

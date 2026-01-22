import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
from groq import Groq

# --- 1. CONFIG ---
st.set_page_config(page_title="VANTAGE PROTOCOL", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* GLOBAL THEME */
    .stApp { background-color: #050505; color: #E0E0E0; font-family: 'Courier New', monospace; }
    
    /* CARD SYSTEM */
    .intel-card {
        background-color: #111;
        border-left: 3px solid #00D4FF;
        border-bottom: 1px solid #222;
        padding: 15px;
        margin-bottom: 12px;
        border-radius: 4px;
    }
    .intel-header { color: #00D4FF; font-weight: bold; font-size: 1.0em; letter-spacing: 1px; }
    .intel-body { color: #EEE; font-size: 0.9em; margin-top: 5px; font-family: sans-serif; line-height: 1.4; }
    
    /* CRITICAL OVERRIDE */
    .critical { border-left: 3px solid #FF3333 !important; }
    .critical .intel-header { color: #FF3333 !important; }

    /* BUTTONS */
    div.stButton > button {
        background-color: #000;
        border: 1px solid #00D4FF;
        color: #00D4FF;
        width: 100%;
        font-family: monospace;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: bold;
        transition: 0.3s;
        padding: 20px;
    }
    div.stButton > button:hover {
        background-color: #00D4FF;
        color: #000;
        border: 1px solid #00D4FF;
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
        st.error(f"DB ERROR: {e}")
        return pd.DataFrame()

df = load_data()

# --- 3. AGENT 3 (DEBUGGED) ---
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
      "core_mission": "Analyze aggregated vendor data to detect known exploitable patterns (Structuring, Velocity) AND emergent anomalies.",
      "input_context": {{
        "data": {evidence_lines}
      }},
      "analysis_framework": [
        {{ "vector": "STRUCTURING", "logic": "High count with Avg Ticket just below approval limits ($2.5k, $5k, $10k)." }},
        {{ "vector": "VELOCITY", "logic": "High transaction count relative to total spend." }},
        {{ "vector": "ARTIFICIALITY", "logic": "Clean round numbers or perfect averages." }},
        {{ "vector": "DOMINANCE", "logic": "Disproportionate cash flow to one vendor." }}
      ],
      "output_format_strict": "Return a raw list of strings following this template:",
      "output_template": "[VENDOR] :: [PATTERN NAME] (Confidence: X%) -> [REASONING]"
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

# --- 4. RENDER ---
st.markdown("<h1>VANTAGE PROTOCOL // GLOBAL OVERSIGHT</h1>")

if not df.empty:
    # Cleanup
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    df['risk_score'] = pd.to_numeric(df['risk_score'], errors='coerce').fillna(0)

    # Meta Extraction
    def get_meta(x, key):
        try:
            import json
            if isinstance(x, dict): return x.get(key, '-')
            return json.loads(x).get(key, '-')
        except: return '-'
    df['approver'] = df['risk_flags'].apply(lambda x: get_meta(x, 'approver'))
    df['description'] = df['risk_flags'].apply(lambda x: get_meta(x, 'description'))

    c1, c2 = st.columns(2)
    
    # --- LEFT: PIE CHART ---
    with c1:
        st.markdown("#### CAPITAL DISTRIBUTION MAP")
        pie_data = df.groupby('vendor_name')['total_amount'].sum().reset_index().sort_values('total_amount', ascending=False)
        
        fig = px.pie(
            pie_data, values='total_amount', names='vendor_name',
            hole=0.6, color_discrete_sequence=px.colors.sequential.RdBu
        )
        fig.update_layout(
            paper_bgcolor="#000", plot_bgcolor="#000",
            font=dict(color="#DDD", family="Courier New"),
            showlegend=False,
            annotations=[dict(text='TOTAL<br>EXPOSURE', x=0.5, y=0.5, font_size=14, showarrow=False, font_color='white')]
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

    # --- RIGHT: AGENT 3 ---
    with c2:
        st.markdown("#### PROBABILISTIC ANOMALY DETECTION")
        
        if st.button("INITIALIZE DEEP SCAN (GLOBAL)", key="global_scan"):
            with st.spinner("AGENT 3: RUNNING BAYESIAN INFERENCE..."):
                findings = execute_agent_3(df)
                
                if not findings:
                    st.warning("AI Returned Empty Response.")
                
                for find in findings:
                    if "::" in find:
                        parts = find.split('::')
                        title = parts[0]
                        body = parts[1]
                        
                        # Style Critical
                        css = "intel-card"
                        if "High" in body or "8" in body or "9" in body or "STRUCTURING" in title:
                            css += " critical"
                        
                        st.markdown(f"""
                        <div class="{css}">
                            <div class="intel-header">{title}</div>
                            <div class="intel-body">{body}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    elif "ERROR" in find:
                        st.error(find)
        else:
            st.markdown("<div style='border:1px dashed #333; padding:60px; text-align:center; color:#555;'>AWAITING TRIGGER</div>", unsafe_allow_html=True)

    # --- BOTTOM: LEDGER ---
    st.markdown("---")
    st.markdown("#### GLOBAL EVIDENCE LEDGER")
    cols = ['invoice_id', 'invoice_date', 'description', 'vendor_name', 'total_amount', 'approver', 'risk_score']
    
    st.dataframe(
        df[cols].sort_values('risk_score', ascending=False),
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
            "total_amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        },
        hide_index=True
    )
    st.markdown("<br><center style='color:#444'>[ END OF TRANSMISSION ]</center>", unsafe_allow_html=True)

else:
    st.markdown("### SYSTEM STANDBY... CHECK UPLINK")

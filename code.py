import streamlit as st
import pandas as pd
import time
from pytrends.request import TrendReq

# --- Streamlit UI ---
st.set_page_config("Google Trends Analyzer", layout="centered")

# Header with logo
st.markdown("""
<div style='text-align: center;'>
    <img src='https://funnel.io/hubfs/Google-trends.png' width='150'/>
</div>
""", unsafe_allow_html=True)

st.title("📈 Google Trends Analyzer")
st.markdown("Compare interest over time for multiple keywords, normalized to an anchor keyword.")

# Keyword input
keywords_input = st.text_input("🔍 Enter keywords (comma-separated)", "AI, ChatGPT, Bard, Claude, Llama")
keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]

# Anchor keyword
anchor = st.text_input("📌 Anchor keyword (used for normalization)", "AI")

# Country selection (default = global)
country = st.text_input("🌍 Country code (e.g., 'US', 'GB', 'AE'; leave empty for worldwide)", "").upper()

# Date range
start_date, end_date = st.date_input("📅 Date range", [pd.to_datetime("2024-01-01"), pd.to_datetime("today")])

# --- Get and Normalize Data ---
@st.cache_data(show_spinner="Fetching Google Trends data...")
def fetch_and_normalize_trends(keywords, anchor, geo, start_date, end_date):
    if anchor not in keywords:
        keywords = [anchor] + keywords

    pytrend = TrendReq(hl='en-US', tz=360)
    full_df = pd.DataFrame()

    for i in range(0, len(keywords), 4):
        batch = keywords[i:i + 4]
        if anchor not in batch:
            batch = [anchor] + batch

        pytrend.build_payload(batch, timeframe=f"{start_date} {end_date}", geo=geo)
        time.sleep(2)  # rate limit protection
        df = pytrend.interest_over_time().drop(columns=['isPartial']).reset_index()

        for kw in batch:
            if kw != anchor:
                # Normalize to anchor
                df[kw] = df[kw] * 100.0 / df[anchor]
        df = df[["date"] + [kw for kw in batch if kw != anchor]]
        df.set_index("date", inplace=True)

        if full_df.empty:
            full_df = df
        else:
            full_df = full_df.join(df, how='outer')

    full_df = full_df.interpolate().fillna(0)
    return full_df

if keywords and anchor:
    st.markdown("## 📊 Trend Comparison")
    try:
        df = fetch_and_normalize_trends(keywords, anchor, country, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        st.line_chart(df)
        st.dataframe(df.reset_index(), use_container_width=True)
    except Exception as e:
        st.error(f"Error fetching data: {e}")

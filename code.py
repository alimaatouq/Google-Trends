import streamlit as st
import pandas as pd
from pytrends.request import TrendReq

# Page configuration
st.set_page_config(page_title="Google Trends Analyzer", layout="centered")

# Title and intro
st.title("📈 Google Trends Analyzer")
st.markdown("Enter one or more keywords (comma-separated) to compare their Google search interest over time.")

# User input for keywords
keywords_input = st.text_input("🔍 Keywords", placeholder="e.g., AI, climate change, Bitcoin")

# Date range filter
date_range = st.date_input("📅 Date range", [])
start_date, end_date = None, None
if len(date_range) == 2:
    start_date, end_date = date_range

# Function to fetch Google Trends data
@st.cache_data
def get_trends_data(keywords):
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=keywords)
    df = pytrend.interest_over_time()
    if df.empty:
        return df
    df = df.drop(columns=['isPartial'])
    df.reset_index(inplace=True)
    return df

# Process and display data
if keywords_input:
    keywords = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
    if keywords:
        df = get_trends_data(keywords)

        if df.empty:
            st.warning("No data found. Try different keywords.")
        else:
            # Apply date filter if selected
            if start_date and end_date:
                df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]

            st.subheader("📊 Trend Comparison")
            chart_df = df.set_index("date")[keywords]
            st.line_chart(chart_df)

            with st.expander("🔎 View raw data"):
                st.dataframe(df, use_container_width=True)

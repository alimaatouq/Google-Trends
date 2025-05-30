import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
import time

# Page config
st.set_page_config(
    page_title="Google Trends Analyzer",
    layout="centered",
    page_icon="https://ssl.gstatic.com/trends_nrtr/4031_RC01/favicon.ico" # Add this line
)

# Add logo and title
# Centered logo using HTML
st.markdown(
    """
    <div style='text-align: center;'>
        <img src='https://funnel.io/hubfs/Google-trends.png' width='150'/>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("📈 Google Trends Analyzer")
st.markdown("Enter one or more keywords (comma-separated) to compare their Google search interest over time.")

# User input for keywords
keywords_input = st.text_input("🔍 Keywords (comma-separated, max 20)", placeholder="e.g., AI, climate change, Bitcoin")

# Anchor keyword for normalization
anchor_keyword = st.text_input("⚓ Anchor Keyword (for normalization)", placeholder="e.g., Technology")
st.markdown("<small><i>This keyword will be used in every batch to normalize data across all other keywords.</i></small>", unsafe_allow_html=True)

# Country filter
country_input = st.text_input("🌍 Country (2-letter code, e.g., US, GB, AE)", placeholder="e.g., US")

# Date range filter
date_range = st.date_input("📅 Date range", [])
start_date, end_date = None, None
if len(date_range) == 2:
    start_date, end_date = date_range

# Function to fetch Google Trends data with batching and normalization
@st.cache_data(show_spinner="Fetching Google Trends data...")
def get_trends_data_batched(keywords, anchor, geo_code, start_date_str, end_date_str):
    pytrend = TrendReq(hl='en-US', tz=360) # tz=360 for GMT+6, adjust as needed

    if not anchor:
        st.error("Please provide an Anchor Keyword for normalization.")
        return pd.DataFrame()

    all_keywords = [kw.strip() for kw in keywords.split(',') if kw.strip()]
    if anchor not in all_keywords:
        all_keywords.insert(0, anchor) # Ensure anchor is in the list for initial processing

    # Remove the anchor from the main list for batching if it was implicitly added by the user
    try:
        keywords_for_batching = [kw for kw in all_keywords if kw != anchor]
    except ValueError:
        keywords_for_batching = list(all_keywords)

    if len(keywords_for_batching) > 19: # 1 anchor + 19 others = 20 total
        st.warning(f"You have entered {len(keywords_for_batching) + 1} keywords. The maximum supported is 20. Only the first 19 plus the anchor will be processed.")
        keywords_for_batching = keywords_for_batching[:19]


    date_period = f"{start_date_str} {end_date_str}" if start_date_str and end_date_str else "today 5-y"

    # Initialize master dataframe
    master_df = pd.DataFrame()

    # Process anchor keyword alone to get its base trend
    try:
        pytrend.build_payload(kw_list=[anchor], geo=geo_code, timeframe=date_period)
        anchor_df_raw = pytrend.interest_over_time()
        if anchor_df_raw.empty:
            st.warning(f"No data found for the anchor keyword: '{anchor}'. Please try a different anchor or time range.")
            return pd.DataFrame()
        anchor_series_base = anchor_df_raw[anchor].rename(f"{anchor}_base")
        master_df = pd.DataFrame(index=anchor_series_base.index) # Use anchor index as base
        master_df[anchor] = anchor_series_base.values # Add the anchor as the first column, directly from its base query
    except Exception as e:
        st.error(f"Error fetching data for anchor keyword '{anchor}': {e}")
        return pd.DataFrame()
    time.sleep(1) # Rate limiting

    # Batch process other keywords
    # Group other keywords into batches of 4, and add the anchor to each.
    batches = [keywords_for_batching[i:i + 4] for i in range(0, len(keywords_for_batching), 4)]

    for batch in batches:
        current_batch_keywords = [anchor] + batch
        try:
            pytrend.build_payload(kw_list=current_batch_keywords, geo=geo_code, timeframe=date_period)
            batch_df = pytrend.interest_over_time()

            if not batch_df.empty:
                # Normalize all keywords in the batch based on the anchor's trend within this batch
                # To prevent division by zero, replace 0s in the anchor column with NaN for normalization
                # Then, forward-fill or replace NaN after normalization if needed for visualization.
                anchor_in_batch = batch_df[anchor].replace(0, pd.NA)

                for kw in batch:
                    if kw in batch_df.columns:
                        # Normalize: (keyword_value / anchor_value_in_batch) * anchor_value_from_base_query
                        # This scales all keywords to the overall anchor's trend
                        normalized_series = (batch_df[kw] / anchor_in_batch) * master_df[anchor]
                        # Fill NA values that resulted from division by zero with 0 or a sensible default
                        master_df[kw] = normalized_series.fillna(0) # Fill NA with 0 or use forward/backward fill based on desired behavior
            else:
                st.warning(f"No data found for batch: {', '.join(current_batch_keywords)}")

        except Exception as e:
            st.error(f"Error fetching data for batch {', '.join(current_batch_keywords)}: {e}")
        time.sleep(1) # Rate limiting between batches

    master_df.reset_index(inplace=True)
    return master_df

# Process and display data
if st.button("Analyze Trends"):
    if not keywords_input:
        st.warning("Please enter at least one keyword.")
    elif not anchor_keyword:
        st.warning("Please enter an Anchor Keyword.")
    else:
        start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None
        end_date_str = end_date.strftime('%Y-%m-%d') if end_date else None

        df = get_trends_data_batched(keywords_input, anchor_keyword, country_input, start_date_str, end_date_str)

        if df.empty:
            st.warning("No data found for the specified keywords and date range. Please try different inputs.")
        else:
            # Apply date filter if selected and it wasn't already applied by timeframe in pytrends
            if start_date and end_date:
                df['date'] = pd.to_datetime(df['date'])
                df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]
                if df.empty:
                    st.warning("No data found within the selected date range after fetching.")
                    st.stop()


            st.subheader("📊 Trend Comparison")
            # Ensure all requested keywords are in the DataFrame for charting
            chart_columns = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            if anchor_keyword not in chart_columns: # Add anchor to chart if not already included
                chart_columns.insert(0, anchor_keyword)

            # Filter chart_columns to only include those actually present in df
            final_chart_columns = [col for col in chart_columns if col in df.columns]

            if not final_chart_columns:
                st.warning("No valid keywords to display in the chart.")
            else:
                # Handle potential `isPartial` column if it somehow gets through, though it should be dropped by pytrends
                if 'isPartial' in df.columns:
                    df = df.drop(columns=['isPartial'])

                # Set date as index before charting
                chart_df = df.set_index("date")[final_chart_columns]
                st.line_chart(chart_df)

            with st.expander("🔎 View raw data"):
                st.dataframe(df, use_container_width=True)

import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
import time

# Page config
st.set_page_config(
    page_title="Google Trends Analyzer",
    layout="centered",
    page_icon="https://ssl.gstatic.com/trends_nrtr/4031_RC01/favicon.ico"
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
st.markdown("Enter one or more keywords or topics (comma-separated) to compare their Google search interest over time.")

# User input for search type
search_type = st.radio(
    "Select Search Type:",
    ("Keywords (Terms)", "Topics")
)

keywords_input = ""
anchor_keyword = ""
topic_input = ""
anchor_topic = ""
topics_data_map = {} # To store mapping from descriptive name to {mid, keyword}

if search_type == "Keywords (Terms)":
    # User input for keywords
    keywords_input = st.text_input("🔍 Keywords (comma-separated, max 20)", placeholder="e.g., AI, climate change, Bitcoin")
    # Anchor keyword for normalization
    anchor_keyword = st.text_input("⚓ Anchor Keyword (for normalization)", placeholder="e.g., Technology")
    st.markdown("<small><i>This keyword will be used in every batch to normalize data across all other keywords.</i></small>", unsafe_allow_html=True)
else: # search_type == "Topics"
    topic_input = st.text_input("💡 Topics (comma-separated, enter descriptive terms)", placeholder="e.g., Artificial intelligence, Blockchain")
    anchor_topic = st.text_input("⚓ Anchor Topic (for normalization, enter descriptive term)", placeholder="e.g., Technology")
    st.markdown("<small><i>For topics, the app will attempt to find the best matching Google Trends Topic ID.</i></small>", unsafe_allow_html=True)


# Country filter
country_input = st.text_input("🌍 Country (2-letter code, e.g., US, GB, AE)", placeholder="e.g., US")

# Date range filter
date_range = st.date_input("📅 Date range", [])
start_date, end_date = None, None
if len(date_range) == 2:
    start_date, end_date = date_range

# Helper function to get topic suggestions
def get_topic_info(pytrend, query):
    suggestions = pytrend.suggestions(keyword=query)
    for suggestion in suggestions:
        if suggestion and 'mid' in suggestion and 'type' in suggestion and suggestion['type'] == 'Topic':
            return {'mid': suggestion['mid'], 'keyword': suggestion['title']}
    return None # No suitable topic found

# Function to fetch Google Trends data with batching and normalization
@st.cache_data(show_spinner="Fetching Google Trends data...")
def get_trends_data_flexible(input_str, anchor_str, geo_code, start_date_str, end_date_str, search_type):
    pytrend = TrendReq(hl='en-US', tz=360) # tz=360 for GMT+6, adjust as needed

    if not anchor_str:
        st.error(f"Please provide an Anchor {search_type.replace('s (Terms)', '').replace(' (Terms)', '')} for normalization.")
        return pd.DataFrame()

    all_items_raw = [item.strip() for item in input_str.split(',') if item.strip()]
    anchor_item_raw = anchor_str.strip()

    payload_items_for_trends = []
    anchor_item_for_payload = None
    display_names = [] # To keep track of names for DataFrame columns and display

    if search_type == "Keywords (Terms)":
        if anchor_item_raw not in all_items_raw:
            all_items_raw.insert(0, anchor_item_raw)
        
        payload_items_for_trends = all_items_raw
        anchor_item_for_payload = anchor_item_raw
        display_names = all_items_raw # Keywords are their own display names

    else: # search_type == "Topics"
        st.info("Attempting to find Google Trends Topic IDs...")
        
        # Get info for anchor topic
        anchor_topic_info = get_topic_info(pytrend, anchor_item_raw)
        if not anchor_topic_info:
            st.error(f"Could not find a suitable Topic for anchor: '{anchor_item_raw}'. Please try a different descriptive term.")
            return pd.DataFrame()
        
        anchor_item_for_payload = anchor_topic_info
        display_names.append(anchor_topic_info['keyword']) # Add topic's display name

        # Get info for other topics
        for item_raw in all_items_raw:
            if item_raw == anchor_item_raw: # Skip if it's the anchor itself
                continue
            topic_info = get_topic_info(pytrend, item_raw)
            if topic_info:
                payload_items_for_trends.append(topic_info)
                display_names.append(topic_info['keyword'])
            else:
                st.warning(f"Could not find a suitable Topic for '{item_raw}'. Skipping this term.")
        
        # Add anchor to the beginning of the payload items if not already added by iteration logic
        if anchor_item_for_payload not in payload_items_for_trends:
             payload_items_for_trends.insert(0, anchor_item_for_payload)


    if len(payload_items_for_trends) > 20: # pytrends max 5 items per payload, but 20 unique items total if batched against single anchor
        st.warning(f"You have entered {len(payload_items_for_trends)} items. The maximum supported for comparison is 20 (including anchor). Only the first 20 will be processed.")
        payload_items_for_trends = payload_items_for_trends[:20]
        display_names = display_names[:20] # Keep display names in sync

    date_period = f"{start_date_str} {end_date_str}" if start_date_str and end_date_str else "today 5-y"

    master_df = pd.DataFrame()

    # Fetch base trend for the anchor (either term or topic)
    try:
        pytrend.build_payload(kw_list=[anchor_item_for_payload], geo=geo_code, timeframe=date_period)
        anchor_df_raw = pytrend.interest_over_time()
        
        if anchor_df_raw.empty:
            st.warning(f"No data found for the anchor {search_type.replace('s (Terms)', '').replace(' (Terms)', '')}: '{anchor_str}'. Please try a different anchor or time range.")
            return pd.DataFrame()
        
        # Extract the correct column name from the anchor_df_raw, which might be the keyword or topic title
        anchor_col_name = anchor_item_for_payload['keyword'] if isinstance(anchor_item_for_payload, dict) else anchor_item_for_payload
        
        anchor_series_base = anchor_df_raw[anchor_col_name].rename(f"{anchor_col_name}_base")
        master_df = pd.DataFrame(index=anchor_series_base.index)
        master_df[anchor_col_name] = anchor_series_base.values
    except Exception as e:
        st.error(f"Error fetching data for anchor {search_type.replace('s (Terms)', '').replace(' (Terms)', '')} '{anchor_str}': {e}")
        return pd.DataFrame()
    time.sleep(1) # Rate limiting

    # Prepare other items for batching (excluding the anchor as it's handled separately)
    other_items_for_batching = [item for item in payload_items_for_trends if item != anchor_item_for_payload]

    # Group other items into batches of up to 4 (since total 5 per payload with anchor)
    batches = [other_items_for_batching[i:i + 4] for i in range(0, len(other_items_for_batching), 4)]

    for batch in batches:
        current_batch_keywords_payload = [anchor_item_for_payload] + batch
        try:
            pytrend.build_payload(kw_list=current_batch_keywords_payload, geo=geo_code, timeframe=date_period)
            batch_df = pytrend.interest_over_time()

            if not batch_df.empty:
                # Get the correct column name for the anchor within this batch
                anchor_col_in_batch = anchor_item_for_payload['keyword'] if isinstance(anchor_item_for_payload, dict) else anchor_item_for_payload
                
                anchor_in_batch = batch_df[anchor_col_in_batch].replace(0, pd.NA)

                for item_payload in batch:
                    # Get the correct column name for the current item in the batch
                    item_col_in_batch = item_payload['keyword'] if isinstance(item_payload, dict) else item_payload
                    
                    if item_col_in_batch in batch_df.columns:
                        normalized_series = (batch_df[item_col_in_batch] / anchor_in_batch) * master_df[anchor_col_name]
                        master_df[item_col_in_batch] = normalized_series.fillna(0)
            else:
                batch_display_names = [item['keyword'] if isinstance(item, dict) else item for item in current_batch_keywords_payload]
                st.warning(f"No data found for batch: {', '.join(batch_display_names)}")

        except Exception as e:
            batch_display_names = [item['keyword'] if isinstance(item, dict) else item for item in current_batch_keywords_payload]
            st.error(f"Error fetching data for batch {', '.join(batch_display_names)}: {e}")
        time.sleep(1) # Rate limiting between batches

    # Ensure all columns in master_df are named by their display names
    # This loop is crucial because `pytrends.interest_over_time()` uses the 'keyword' from the payload dict as column name
    # We want to use the friendly 'keyword' for topics as column names.
    final_cols = []
    for item_payload in payload_items_for_trends:
        col_name = item_payload['keyword'] if isinstance(item_payload, dict) else item_payload
        if col_name in master_df.columns:
            final_cols.append(col_name)
    
    master_df = master_df[final_cols] # Select only the relevant columns and maintain order
    master_df.reset_index(inplace=True)
    return master_df

# Process and display data
if st.button("Analyze Trends"):
    input_to_function = ""
    anchor_to_function = ""
    if search_type == "Keywords (Terms)":
        input_to_function = keywords_input
        anchor_to_function = anchor_keyword
        if not keywords_input:
            st.warning("Please enter at least one keyword.")
            st.stop()
        elif not anchor_keyword:
            st.warning("Please enter an Anchor Keyword.")
            st.stop()
    else: # Topics
        input_to_function = topic_input
        anchor_to_function = anchor_topic
        if not topic_input:
            st.warning("Please enter at least one topic.")
            st.stop()
        elif not anchor_topic:
            st.warning("Please enter an Anchor Topic.")
            st.stop()
            
    if not country_input:
        st.warning("Please enter a Country code.")
        st.stop()

    start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None
    end_date_str = end_date.strftime('%Y-%m-%d') if end_date else None

    df = get_trends_data_flexible(input_to_function, anchor_to_function, country_input, start_date_str, end_date_str, search_type)

    if df.empty:
        st.warning("No data found for the specified inputs and date range. Please try different inputs.")
    else:
        # Apply date filter if selected and it wasn't already applied by timeframe in pytrends
        # (pytrends timeframe is usually enough, but this ensures strict filtering)
        if start_date and end_date:
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]
            if df.empty:
                st.warning("No data found within the selected date range after fetching.")
                st.stop()

        st.subheader("📊 Trend Comparison")
        
        # Determine which columns to chart based on the actual fetched data, excluding 'isPartial'
        chart_columns = [col for col in df.columns if col != 'date' and col != 'isPartial']

        if not chart_columns:
            st.warning("No valid data columns to display in the chart.")
        else:
            chart_df = df.set_index("date")[chart_columns]
            st.line_chart(chart_df)

        with st.expander("🔎 View raw data"):
            st.dataframe(df, use_container_width=True)

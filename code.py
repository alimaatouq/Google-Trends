import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

# get google trends data from keyword list
@st.cache
def get_data(keyword):
    keyword = [keyword]
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=keyword)
    df = pytrend.interest_over_time()
    df.drop(columns=['isPartial'], inplace=True)
    df.reset_index(inplace=True)
    df.columns = ["ds", "y"]
    return df

# sidebar
st.sidebar.write("## Trend based on keyword")
keyword = st.sidebar.text_input("Enter a keyword", help="Look up on Google Trends")

if keyword:
    df = get_data(keyword)
    st.dataframe(df)
    fig, ax = plt.subplots()
    ax = df['y'].plot()
    st.pyplot(fig)


import streamlit as st
from sqlalchemy import create_engine

@st.cache_resource
def get_engine():
    db = st.secrets["database"]
    url = (
        f"postgresql+psycopg2://{db['user']}:{db['password']}"
        f"@{db['host']}:{db['port']}/{db['dbname']}"
    )
    return create_engine(url)

import streamlit as st
import requests

# Backend Configuration (Update this URL after deploying the FastAPI backend)
BACKEND_URL = "http://localhost:8000/api/crawl"

st.set_page_config(page_title="Web Contact Extractor", page_icon="🔍", layout="wide")

st.title("🔍 Website Contact Information Extractor")
st.markdown("Extract public email addresses and phone numbers from an internal domain crawl.")

# Sidebar Configuration
st.sidebar.header("Crawl Settings")
max_pages = st.sidebar.slider("Maximum Pages to Crawl", min_value=1, max_value=100, value=10)
delay = st.sidebar.slider("Delay Between Requests (seconds)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

# Main UI Input
target_url = st.text_input("Enter Target Website URL:", placeholder="https://example.com")

if st.button("Start Extraction", type="primary"):
    if not target_url:
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner("Crawling target domain and extracting data... This may take a moment."):
            payload = {
                "url": target_url,
                "max_pages": max_pages,
                "delay": delay
            }
            
            try:
                response = requests.post(BACKEND_URL, json=payload, timeout=300)
                
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"Successfully scanned {data['pages_crawled']} page(s)!")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader(f"✉️ Emails Found ({len(data['emails'])})")
                        if data['emails']:
                            st.dataframe(data['emails'], column_config={"value": "Email Address"}, use_container_width=True)
                        else:
                            st.info("No emails identified.")
                            
                    with col2:
                        st.subheader(f"📞 Phone Numbers Found ({len(data['phones'])})")
                        if data['phones']:
                            st.dataframe(data['phones'], column_config={"value": "Phone Number"}, use_container_width=True)
                        else:
                            st.info("No phone numbers identified.")
                else:
                    st.error(f"Backend returned an error: {response.json().get('detail', 'Unknown error')}")
                    
            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to the backend server: {e}")
"""
Reset utility for Generative SQL Intelligence App
Run this to clear session state and ensure landing page shows on next startup
"""

import streamlit as st
import os

st.set_page_config(page_title="Reset App", page_icon="🔄", layout="centered")

st.title("🔄 Reset App to Landing Page")

st.write("This utility helps you reset the app to show the landing page on next startup.")

if st.button("🏠 Reset to Landing Page", type="primary"):
    # Clear all relevant session state keys
    keys_to_clear = ["entered_app", "current_page", "history", "nl_query", "last_sql", "last_df"]
    
    cleared_keys = []
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
            cleared_keys.append(key)
    
    if cleared_keys:
        st.success(f"✅ Cleared session keys: {', '.join(cleared_keys)}")
    else:
        st.info("ℹ️ No session keys to clear")
    
    st.balloons()
    
    with st.expander("What happens next?"):
        st.write("""
        - The next time you run `streamlit run app.py`, you'll see the landing page
        - All previous session data has been cleared
        - You can now start fresh with the beautiful landing page experience
        """)

if st.button("🚀 Go to Main App"):
    st.session_state["entered_app"] = True
    st.switch_page("app.py")

st.divider()

st.subheader("Current Session State")
if st.session_state:
    for key, value in st.session_state.items():
        if not key.startswith("_"):  # Hide internal streamlit keys
            st.text(f"{key}: {type(value).__name__}")
else:
    st.write("No session state found")
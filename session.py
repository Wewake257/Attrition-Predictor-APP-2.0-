
import time
import streamlit as st

SESSION_TIMEOUT = 30 * 60  # 30 minutes

def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False


from audit import log_session_expiry

def check_session_timeout():
    if st.session_state.logged_in:
        elapsed = time.time() - st.session_state.login_time
        if elapsed > SESSION_TIMEOUT:
            log_session_expiry(st.session_state.user["username"])
            st.warning("Session expired. Please login again.")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()



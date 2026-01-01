import streamlit as st
import time
from audit import log_session_expiry

SESSION_TIMEOUT = 3600  # 1 hour


def init_session():
    """
    Initialize required session keys
    """
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "login_time" not in st.session_state:
        st.session_state.login_time = None


def check_session_timeout():
    """
    Enforce session timeout and auto logout
    """
    if not st.session_state.get("logged_in"):
        return

    login_time = st.session_state.get("login_time")
    if not login_time:
        return

    elapsed = time.time() - login_time

    if elapsed > SESSION_TIMEOUT:
        username = st.session_state.get("user", {}).get("username")
        if username:
            log_session_expiry(username)

        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.error("Session expired. Please log in again.")
        st.stop()

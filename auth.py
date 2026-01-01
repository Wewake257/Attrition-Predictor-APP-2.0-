import pandas as pd
import os
from datetime import datetime

AUDIT_FILE = "data/login_audit.csv"


def _ensure_audit_file():
    """
    Ensure audit file exists with correct schema
    """
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(AUDIT_FILE):
        df = pd.DataFrame(columns=[
            "username",
            "role",
            "login_time",
            "logout_time",
            "logout_reason"
        ])
        df.to_csv(AUDIT_FILE, index=False)


def log_login(username: str, role: str):
    """
    Log user login
    """
    _ensure_audit_file()

    entry = {
        "username": username,
        "role": role,
        "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "logout_time": "",
        "logout_reason": ""
    }

    df = pd.read_csv(AUDIT_FILE)
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(AUDIT_FILE, index=False)


def log_logout(username: str, reason: str = "Manual Logout"):
    """
    Update latest open session for user with logout info
    """
    _ensure_audit_file()

    df = pd.read_csv(AUDIT_FILE)

    # Find latest session without logout_time
    mask = (df["username"] == username) & (df["logout_time"] == "")
    if mask.any():
        idx = df[mask].index[-1]
        df.loc[idx, "logout_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.loc[idx, "logout_reason"] = reason

    df.to_csv(AUDIT_FILE, index=False)


def log_session_expiry(username: str):
    """
    Explicit helper for session timeout
    """
    log_logout(username, reason="Session Expired")

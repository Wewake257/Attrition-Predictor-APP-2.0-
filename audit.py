import pandas as pd
from datetime import datetime

AUDIT_FILE = "login_audit.csv"

def log_login(username, role):
    entry = {
        "username": username,
        "role": role,
        "login_time": datetime.now(),
        "logout_time": ""
    }

    df = pd.read_csv(AUDIT_FILE)
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(AUDIT_FILE, index=False)

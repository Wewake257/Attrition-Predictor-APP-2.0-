import pandas as pd
import os

USERS_FILE = "users.csv"

def authenticate_user(username: str, password: str):
    username = username.strip().lower()
    password = password.strip()

    if not os.path.exists(USERS_FILE):
        return None

    users_df = pd.read_csv(USERS_FILE)

    user_row = users_df[
        (users_df["username"].str.lower() == username) &
        (users_df["password"] == password)
    ]

    if user_row.empty:
        return None

    user = user_row.iloc[0]

    return {
        "username": user["username"],
        "role": user["role"],
        "department": user["department"]
    }

    

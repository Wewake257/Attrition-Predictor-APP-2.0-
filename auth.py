import pandas as pd
import os

USERS_FILE = "users.csv"


def authenticate_user(username: str, password: str):
    """
    Authenticate user from users.csv
    Expected columns:
    username | password | role | department
    """
    if not os.path.exists(USERS_FILE):
        return None

    df = pd.read_csv(USERS_FILE)

    user = df[
        (df["username"].astype(str) == str(username)) &
        (df["password"].astype(str) == str(password))
    ]

    if user.empty:
        return None

    row = user.iloc[0]

    return {
        "username": row["username"],
        "role": row["role"],
        "department": row["department"]
    }

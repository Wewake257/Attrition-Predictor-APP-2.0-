import pandas as pd
import os

USERS_FILE = "data/users.csv"


def authenticate_user(username: str, password: str):
    """
    Plain-text authentication (prototype mode)

    Expected users.csv columns:
    username,password,role,department
    """

    if not os.path.exists(USERS_FILE):
        return None

    users_df = pd.read_csv(USERS_FILE)

    if users_df.empty:
        return None

    user_row = users_df[
        (users_df["username"] == username) &
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

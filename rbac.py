import pandas as pd


def filter_employee_data(df: pd.DataFrame, role: str, department: str):
    """
    Role-Based Access Control (RBAC)

    CHRO / Admin  -> Full access
    HRBP         -> Department-level access
    Manager      -> Department-level access (can be refined later)
    """

    if df is None or df.empty:
        return df

    # Full access roles
    if role in ["CHRO", "Admin"]:
        return df

    # HRBP / Manager scoped by department
    if role in ["HRBP", "Manager"]:
        if department == "All":
            return df
        return df[df["Department"] == department]

    # Default: no restriction
    return df

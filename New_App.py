import streamlit as st
import pandas as pd
import time
import os
import difflib
import json
import plotly.express as px
from io import BytesIO

# Assumed local modules - keeping these as per instruction
from auth import authenticate_user
from session import init_session, check_session_timeout, SESSION_TIMEOUT
from audit import log_login
from rbac import filter_employee_data

# ---------------- CONFIGURATION ----------------
st.set_page_config(page_title="OrgaKnow | Retention Intelligence", layout="wide")

# ---------------- GLOBAL CONSTANTS ----------------
EMPLOYEE_FILE = "employees.csv"
EXIT_FILE = "exit_intelligence.csv"
RISK_CONFIG_FILE = "risk_config.json"
ACTIONS_FILE = "attrition_actions.csv"

# ---------------- HELPER FUNCTIONS ----------------

def load_risk_weights():
    defaults = {
        "js": 0.25,      # Job Satisfaction
        "wl": 0.20,      # Work-Life Balance
        "ms": 0.20,      # Manager Support
        "cg": 0.15,      # Career Growth
        "stress": 0.30   # Stress
    }
    if os.path.exists(RISK_CONFIG_FILE):
        with open(RISK_CONFIG_FILE, "r") as f:
            return json.load(f)
    return defaults

def calculate_attrition_risk(js, wl, ms, cg, stress, weights=None):
    # Load global weights if none provided
    if weights is None:
        # We need to access CURRENT_WEIGHTS, assuming it's loaded in global scope later
        # Or re-load defaults to be safe if variable not yet bound
        weights = load_risk_weights()
        
    # Ensure weights sum to 1.0 (Normalization protection)
    total_weight = sum(weights.values())
    if total_weight == 0: total_weight = 1
    
    # Calculate weighted score
    raw_score = (
        (6 - js) * (weights["js"] / total_weight) + 
        (6 - wl) * (weights["wl"] / total_weight) + 
        (6 - ms) * (weights["ms"] / total_weight) + 
        (6 - cg) * (weights["cg"] / total_weight) + 
        stress * (weights["stress"] / total_weight)
    )

    # Max possible raw_score is roughly 6 (since inputs are 1-5, inverted logic)
    attrition_risk_pct = (raw_score / 6) * 100
    return round(min(attrition_risk_pct, 100), 2)

def risk_band(score):
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"

def guard(allowed_roles):
    if st.session_state.user["role"] not in allowed_roles:
        st.error("Access denied")
        st.stop()

def risk_color(val):
    if val == "High":
        return "background-color: #7f1d1d; color: white;"
    elif val == "Medium":
        return "background-color: #78350f; color: white;"
    else:
        return "background-color: #14532d; color: white;"

def risk_arrow(change):
    if change > 0:
        return "↓ Risk Reduced"
    elif change < 0:
        return "↑ Risk Increased"
    else:
        return "→ No Change"

def style_risk_rows(row):
    if "RiskBand" not in row:
        return [""] * len(row)

    if row["RiskBand"] == "High":
        return ["background-color: #7f1d1d; color: white"] * len(row)
    elif row["RiskBand"] == "Medium":
        return ["background-color: #78350f; color: white"] * len(row)
    elif row["RiskBand"] == "Low":
        return ["background-color: #14532d; color: white"] * len(row)
    else:
        return [""] * len(row)

def kpi_card(title, value, tone="neutral"):
    colors = {
        "high": "#7f1d1d",
        "medium": "#78350f",
        "low": "#14532d",
        "neutral": "#0f172a"
    }
    bg = colors.get(tone, "#0f172a")

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {bg}, #020617);
            border: 1px solid #1e293b;
            border-radius: 18px;
            padding: 18px 20px;
            text-align: center;
            box-shadow: 0 12px 28px rgba(0,0,0,0.45);
        ">
            <div style="
                font-size: 0.8rem;
                color: #94a3b8;
                font-weight: 600;
                margin-bottom: 6px;
            ">
                {title}
            </div>
            <div style="
                font-size: 1.8rem;
                color: #e5e7eb;
                font-weight: 800;
            ">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------- SESSION INITIALIZATION ----------------
init_session()
CURRENT_WEIGHTS = load_risk_weights()

# ---------------- LOGIN SCREEN ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False



    # ---------------- LOGIN STYLING ----------------
if not st.session_state.logged_in:

    # ---------- LOGIN STYLING ----------
    st.markdown("""
    <style>
    .login-card {
        background: linear-gradient(180deg, #0f172a, #020617);
        border: 1px solid #1e293b;
        border-radius: 26px;
        padding: 36px 34px;
        box-shadow: 0 35px 80px rgba(0,0,0,0.7);
        text-align: center;
    }

    .login-title {
        font-size: 2rem;
        font-weight: 900;
        color: #e5e7eb;
    }

    .login-subtitle {
        font-size: 0.9rem;
        color: #94a3b8;
        margin-bottom: 24px;
    }

    .login-note {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 16px;
    }

    div[data-testid="stTextInput"] input {
        background-color: #020617;
        border-radius: 12px;
        border: 1px solid #1e293b;
    }

    div[data-testid="stButton"] button {
        background: linear-gradient(135deg, #38bdf8, #2563eb);
        color: #020617;
        font-weight: 700;
        border-radius: 14px;
        height: 44px;
        border: none;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # ---------- CENTERED COLUMN ----------
    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.markdown("""
        <div class="login-card">
            <div class="login-title">OrgaKnow</div>
            <div class="login-subtitle">
                Enterprise Retention Intelligence Platform
            </div>
        </div>
        """, unsafe_allow_html=True)

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Secure Login", use_container_width=True):
            user = authenticate_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.login_time = time.time()
                st.session_state.user = user
                
                log_login(user["username"], user["role"])

                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials. Contact admin.")

        st.markdown("""
        <div class="login-note">
            🔒 Secure access · Role-based visibility · Audit logged
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ---------------- AUTHENTICATED LOGIC STARTS HERE ----------------
check_session_timeout()
user = st.session_state.user
role = user["role"]
dept = user["department"]

# ---------------- DATA LOADING ----------------

# 1. Load Employees
if os.path.exists(EMPLOYEE_FILE):
    employee_df_full = pd.read_csv(EMPLOYEE_FILE)
else:
    employee_df_full = pd.DataFrame(columns=[
        "EmployeeID", "Name", "Department", "Role", "Tenure",
        "JobSatisfaction", "WorkLifeBalance", "ManagerSupport",
        "CareerGrowth", "StressLevel", "AttritionRisk", "RiskBand"
    ])

# 2. Load Actions
if os.path.exists(ACTIONS_FILE):
    actions_df = pd.read_csv(ACTIONS_FILE)
else:
    actions_df = pd.DataFrame(columns=[
        "EmployeeID", "EmployeeName", "Department", "Manager",
        "RiskScore", "RiskBand", "SelectedAction", "ActionStatus",
        "ManagerComment", "OutcomeStatus", "OutcomeDate"
    ])

# Ensure columns exist if loading from old file
if "OutcomeStatus" not in actions_df.columns:
    actions_df["OutcomeStatus"] = "Pending"
if "OutcomeDate" not in actions_df.columns:
    actions_df["OutcomeDate"] = ""

# 3. Load Exits
if os.path.exists(EXIT_FILE):
    exit_df = pd.read_csv(EXIT_FILE)
else:
    exit_df = pd.DataFrame(columns=[
        "EmployeeID", "ExitDate", "ExitType",
        "PrimaryExitReason", "SecondaryExitReason",
        "ActionTaken", "ActionHelped", "HRComment"
    ])

# 4. RBAC Filtered View
employee_df_view = filter_employee_data(
    employee_df_full,
    user["role"],
    user["department"]
)

# ---------------- GLOBAL EXIT LEARNING LAYER ----------------
# Pre-calculate for Tab 3 and Tab 7
if not exit_df.empty:
    exit_merged = exit_df.merge(
        actions_df,
        on="EmployeeID",
        how="left"
    ).merge(
        employee_df_full,
        on="EmployeeID",
        how="left",
        suffixes=("_Action", "_Employee")
    )
    
    # Learn historically failed actions
    action_learning = exit_merged[exit_merged["ActionTaken"] == "Yes"]
    action_learning_summary = action_learning.groupby(
        ["PrimaryExitReason", "SelectedAction"]
    ).size().reset_index(name="FailureCount")

    failed_action_map = (
        action_learning_summary
        .sort_values("FailureCount", ascending=False)
        .groupby("PrimaryExitReason")
        .head(2)
        .groupby("PrimaryExitReason")["SelectedAction"]
        .apply(list)
        .to_dict()
    )
else:
    exit_merged = pd.DataFrame()
    failed_action_map = {}

# ---------------- SIDEBAR NAVIGATION ----------------
# Session Time
elapsed_time = time.time() - st.session_state.login_time
remaining_time = max(0, SESSION_TIMEOUT - elapsed_time)
remaining_minutes = int(remaining_time // 60)

st.sidebar.success(f"Logged in as {user['username']} ({user['role']})")
st.sidebar.caption(f"🕒 Last login: {st.session_state.get('login_time_str', 'N/A')}")
st.sidebar.caption(f"⏳ Session expires in: {remaining_minutes} minutes")



if st.sidebar.button("🚪 Logout"):
    log_logout(st.session_state.user["username"])
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# CHRO Controls
if role == "CHRO":
    st.sidebar.markdown("### ⚙️ Risk Algorithm Tuning")
    st.sidebar.caption("Simulation mode — no data saved until applied")

    with st.sidebar.expander("Adjust Risk Weights"):
        new_weights = {
            "stress": st.slider("Stress Impact", 0.0, 1.0, CURRENT_WEIGHTS["stress"], 0.05),
            "js": st.slider("Job Satisfaction", 0.0, 1.0, CURRENT_WEIGHTS["js"], 0.05),
            "wl": st.slider("Work-Life Balance", 0.0, 1.0, CURRENT_WEIGHTS["wl"], 0.05),
            "ms": st.slider("Manager Support", 0.0, 1.0, CURRENT_WEIGHTS["ms"], 0.05),
            "cg": st.slider("Career Growth", 0.0, 1.0, CURRENT_WEIGHTS["cg"], 0.05)
        }

        total = sum(new_weights.values())
        if not 0.95 <= total <= 1.05:
            st.warning(f"Total weight = {round(total,2)} (ideal = 1.0)")

    if st.sidebar.button("🔎 Preview Impact", key="chro_preview_model"):
        sim_df = employee_df_full.copy()
        # Preview columns (NON-DESTRUCTIVE)
        sim_df["PreviewRisk"] = sim_df.apply(
            lambda r: calculate_attrition_risk(
                r["JobSatisfaction"],
                r["WorkLifeBalance"],
                r["ManagerSupport"],
                r["CareerGrowth"],
                r["StressLevel"],
                weights=new_weights
            ),
            axis=1
        )
        sim_df["PreviewBand"] = sim_df["PreviewRisk"].apply(risk_band)
        sim_df["RiskDelta"] = sim_df["PreviewRisk"] - sim_df["AttritionRisk"]
        sim_df["BandChanged"] = sim_df["RiskBand"] != sim_df["PreviewBand"]
        st.session_state.preview_df = sim_df

    if st.sidebar.button("💾 Save & Apply Model", key="chro_save_model"):
        if "preview_df" not in st.session_state:
            st.error("Please preview the model before applying.")
            st.stop()

        with open(RISK_CONFIG_FILE, "w") as f:
            json.dump(new_weights, f)

        CURRENT_WEIGHTS = new_weights

        # Apply preview as production
        employee_df_full["AttritionRisk"] = st.session_state.preview_df["PreviewRisk"]
        employee_df_full["RiskBand"] = st.session_state.preview_df["PreviewBand"]

        employee_df_full.to_csv(EMPLOYEE_FILE, index=False)
        st.success("New risk algorithm applied organization-wide")
        st.rerun()
if role == "CHRO" and "preview_df" in st.session_state:
    if st.sidebar.button("🧹 Clear Preview", key="clear_preview"):
        del st.session_state["preview_df"]
        st.rerun()

# ---------------- CSS STYLING ----------------
st.markdown("""
<style>
 /* ---- Main background ---- */
.stApp { background-color: #020617; color: #e5e7eb; }
 /* ---- Tabs container ---- */
div[data-testid="stTabs"] { background-color: #020617; }
 /* ---- Individual tabs ---- */
button[data-baseweb="tab"] {
    background-color: #020617; color: #94a3b8; border-radius: 12px 12px 0 0;
    font-weight: 600; padding: 12px 18px; border: 1px solid #1e293b; margin-right: 6px;
}
 /* ---- Active tab ---- */
button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #0f172a; color: #e5e7eb; border-bottom: 2px solid #38bdf8;
}
 /* ---- Tab content panel ---- */
div[data-testid="stTabsContent"] {
    background-color: #0f172a; border-radius: 0 16px 16px 16px;
    padding: 24px; border: 1px solid #1e293b; box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}
 /* ---- Section cards ---- */
.section-card {
    background-color: #020617; border: 1px solid #1e293b; border-radius: 16px;
    padding: 22px; margin-bottom: 24px;
}
 /* ---- Dataframe polish ---- */
div[data-testid="stDataFrame"] {
    border-radius: 14px; border: 1px solid #1e293b; overflow: hidden;
}
 /* ---- Chart container spacing ---- */
div[data-testid="stPlotlyChart"] {
    background-color: #020617; border: 1px solid #1e293b;
    border-radius: 16px; padding: 16px; margin-bottom: 28px;
}
 /* ---- Header container ---- */
.exec-header {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(2, 6, 23, 0.95));
    border: 1px solid #1e293b; border-radius: 18px; padding: 20px 26px; margin-bottom: 26px;
}
.exec-title { font-size: 1.6rem; font-weight: 800; color: #e5e7eb; margin-bottom: 4px; }
.exec-subtitle { font-size: 0.85rem; color: #94a3b8; }
.exec-user { font-size: 0.8rem; color: #38bdf8; margin-top: 6px; }

 /* ---- KPI Cards ---- */
div[data-testid="stMetric"] { background: linear-gradient(135deg, #0f172a, #020617); }
div[data-testid="stMetric"]:has(label:contains("High")) { background: linear-gradient(135deg, #7f1d1d, #450a0a); }
div[data-testid="stMetric"]:has(label:contains("Medium")) { background: linear-gradient(135deg, #78350f, #451a03); }
div[data-testid="stMetric"]:has(label:contains("Low")) { background: linear-gradient(135deg, #14532d, #052e16); }
div[data-testid="stMetric"]:has(label:contains("Cost")) { background: linear-gradient(135deg, #4c0519, #1f0208); }
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER & SIMULATION VIEW ----------------
st.markdown('<div class="exec-header">', unsafe_allow_html=True)
col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image("https://raw.githubusercontent.com/Wewake257/HR-Attrition-Intelligence-/main/orgaknow_logo.jpeg", width=90)
with col_title:
    st.markdown(f"""
    <div class="exec-title">OrgaKnow – Retention Intelligence</div>
    <div class="exec-subtitle">Enterprise Workforce Risk Intelligence Platform</div>
    <div class="exec-user">Logged in as: {user['username']} · Role: {user['role']} · Scope: {user['department']}</div>
    """, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# If CHRO Simulation is active, show the preview dashboard above tabs
if role == "CHRO" and "preview_df" in st.session_state:
    st.markdown("## 🔍 Risk Algorithm Preview (Simulation)")
    st.caption("Comparing current production vs tuned algorithm")

    preview_df = st.session_state.preview_df

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Employees Changed Band", preview_df["BandChanged"].sum())
    col2.metric("Avg Risk Change (%)", round(preview_df["RiskDelta"].mean(), 2))
    col3.metric("Risk Increased >5%", (preview_df["RiskDelta"] > 5).sum())
    col4.metric("Risk Decreased >5%", (preview_df["RiskDelta"] < -5).sum())

    st.markdown("### Employee-Level Comparison")
    st.dataframe(
        preview_df[[
            "EmployeeID", "Name", "Department",
            "AttritionRisk", "RiskBand",
            "PreviewRisk", "PreviewBand",
            "RiskDelta", "BandChanged"
        ]].sort_values("RiskDelta", ascending=False),
        use_container_width=True
    )
    
    flow_df = preview_df.groupby(
        ["RiskBand", "PreviewBand"]
    ).size().reset_index(name="Count")

    fig = px.sunburst(
        flow_df,
        path=["RiskBand", "PreviewBand"],
        values="Count",
        title="Risk Band Movement (Current → Preview)"
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

# ---------------- TABS ----------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Employee Entry & Risk Prediction",
    "Executive Overview",
    "Prescriptive Actions",
    "Reports & Downloads",
    "Action Effectiveness",
    "Outcome Tracking",
    "Exit Intelligence"
])

# =================================================
# TAB 1 — DATA ENTRY + CSV UPLOAD
# =================================================
with tab1:
    st.markdown("### 1. Upload Employee Master (Bulk Scoring)")

    if role == "CHRO":
        uploaded_file = st.file_uploader("Upload Employee CSV", type=["csv"])
    else:
        st.info("Only CHRO can upload bulk employee data.")
        uploaded_file = None

    if uploaded_file:
        upload_df = pd.read_csv(uploaded_file)
        required_cols = [
            "EmployeeID", "Name", "Department", "Role", "Tenure",
            "JobSatisfaction", "WorkLifeBalance",
            "ManagerSupport", "CareerGrowth", "StressLevel"
        ]

        if all(col in upload_df.columns for col in required_cols):
            upload_df["AttritionRisk"] = upload_df.apply(
                lambda r: calculate_attrition_risk(
                    r["JobSatisfaction"],
                    r["WorkLifeBalance"],
                    r["ManagerSupport"],
                    r["CareerGrowth"],
                    r["StressLevel"]
                ), axis=1
            )
            upload_df["RiskBand"] = upload_df["AttritionRisk"].apply(risk_band)

            employee_df_full = pd.concat([employee_df_full, upload_df], ignore_index=True)
            employee_df_full.to_csv(EMPLOYEE_FILE, index=False)

            # Refresh view
            employee_df_view = filter_employee_data(
                employee_df_full,
                st.session_state.user["role"],
                st.session_state.user["department"]
            )
            st.success("File uploaded, scored, and saved successfully.")
            st.dataframe(upload_df, use_container_width=True)
        else:
            st.error("Uploaded file does not match required format.")

    st.markdown("---")
    st.markdown("### 2. Manual Employee Entry (Single Record)")

    col1, col2, col3 = st.columns(3)
    with col1:
        emp_id = st.text_input("Employee ID")
        name = st.text_input("Employee Name")
    with col2:
        department = st.selectbox("Department", ["HR","Sales","IT","Finance","Operations","Marketing"])
    with col3:
        emp_role = st.selectbox("Role Level", ["Executive","Manager","Senior Staff","Staff","Entry Level"])

    tenure = st.select_slider("Tenure (Years)", [0,1,2,3,4,5,"5+"])

    st.caption("Scale: 1 = Very Low | 5 = Very High")
    js = st.select_slider("Job Satisfaction", [1,2,3,4,5])
    wl = st.select_slider("Work-Life Balance", [1,2,3,4,5])
    ms = st.select_slider("Manager Support", [1,2,3,4,5])
    cg = st.select_slider("Career Growth", [1,2,3,4,5])
    stress = st.select_slider("Stress Level", [1,2,3,4,5])

    if st.button("Save & Predict Risk"):
        risk = calculate_attrition_risk(js, wl, ms, cg, stress)
        new_row = {
            "EmployeeID": emp_id, "Name": name, "Department": department,
            "Role": emp_role, "Tenure": tenure,
            "JobSatisfaction": js, "WorkLifeBalance": wl,
            "ManagerSupport": ms, "CareerGrowth": cg,
            "StressLevel": stress, "AttritionRisk": risk,
            "RiskBand": risk_band(risk)
        }

        if emp_id in employee_df_full["EmployeeID"].astype(str).values:
            st.error("Employee ID already exists. Duplicate entries are not allowed.")
        else:
            employee_df_full = pd.concat(
                [employee_df_full, pd.DataFrame([new_row])],
                ignore_index=True
            )
            employee_df_full.to_csv(EMPLOYEE_FILE, index=False)
            st.success(f"Predicted Attrition Risk: {risk}%")

    st.markdown("### Stored Employee Data")
    st.dataframe(
        employee_df_view.style.apply(style_risk_rows, axis=1),
        use_container_width=True
    )

    st.download_button(
        "Download Employee Data (CSV)",
        employee_df_view.to_csv(index=False),
        "orgaknow_employee_attrition_data.csv",
        "text/csv"
    )
    
    # Data Management Controls
    st.markdown("## Data Management Controls")
    st.caption("Administrative controls for resetting and replacing employee data")
    col_reset1, col_reset2 = st.columns(2)

    # OPTION 1 — ERASE ALL DATA
    with col_reset1:
        st.markdown("### ⚠️ Erase All Employee Data")
        confirm_delete = st.checkbox("I understand this will permanently delete all employee data")
        guard(["CHRO"])
        if st.button("Erase Employee Master Data", type="primary"):
            if not confirm_delete:
                st.warning("Please confirm before deleting data.")
            else:
                if os.path.exists(EMPLOYEE_FILE):
                    os.remove(EMPLOYEE_FILE)
                employee_df_full = pd.DataFrame(columns=[
                    "EmployeeID", "Name", "Department", "Role", "Tenure",
                    "JobSatisfaction", "WorkLifeBalance", "ManagerSupport",
                    "CareerGrowth", "StressLevel", "AttritionRisk", "RiskBand"
                ])
                employee_df_full.to_csv(EMPLOYEE_FILE, index=False)
                st.success("All employee data erased successfully.")
                st.rerun()

    # OPTION 2 — REPLACE ON UPLOAD
    with col_reset2:
        st.markdown("### 🔄 Upload Fresh Data")
        replace_existing = st.checkbox("Replace existing employee data with uploaded file")

# =================================================
# TAB 2 — EXECUTIVE DASHBOARD
# =================================================
with tab2:
    st.markdown("## CHRO Executive Dashboard")
    st.caption("Workforce Attrition Risk · Financial Impact · Risk Drivers")

    if employee_df_full.empty:
        st.warning("No employee data available.")
    else:
        total_emp = len(employee_df_full)
        high_df = employee_df_full[employee_df_full["RiskBand"] == "High"]
        med_df = employee_df_full[employee_df_full["RiskBand"] == "Medium"]
        low_df = employee_df_full[employee_df_full["RiskBand"] == "Low"]

        high_cnt = len(high_df)
        med_cnt = len(med_df)
        low_cnt = len(low_df)

        high_pct = round((high_cnt / total_emp) * 100, 1)
        expected_leavers = round(employee_df_full["AttritionRisk"].sum() / 100, 2)
        est_cost = int(expected_leavers * 500000)

        avg_risk = round(employee_df_full["AttritionRisk"].mean(), 2)
        risk_std = round(employee_df_full["AttritionRisk"].std(), 2)

        critical_roles = employee_df_full[employee_df_full["Role"].isin(["Executive", "Manager"])]
        critical_high = len(critical_roles[critical_roles["RiskBand"] == "High"])

        dept_avg = employee_df_full.groupby("Department")["AttritionRisk"].mean()
        top_risk_dept = dept_avg.idxmax()
        low_risk_dept = dept_avg.idxmin()

        col1, col2, col3, col4 = st.columns(4)
        k1, k2, k3, k4 = st.columns(4)

        with k1: kpi_card("Total Employees", total_emp)
        with k2: kpi_card("High Risk Employees", high_cnt, tone="high")
        with k3: kpi_card("Medium Risk Employees", med_cnt, tone="medium")
        with k4: kpi_card("Low Risk Employees", low_cnt, tone="low")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("% Workforce High Risk", f"{high_pct}%")
        col6.metric("Expected Leavers", expected_leavers)
        kpi_card("Estimated Attrition Cost", f"${est_cost:,}", tone="high")
        col8.metric("Average Attrition Risk", f"{avg_risk}%")

        col9, col10, col11, col12 = st.columns(4)
        col9.metric("High Risk Critical Roles", critical_high)
        col10.metric("Highest Risk Dept", top_risk_dept)
        col11.metric("Lowest Risk Dept", low_risk_dept)
        col12.metric("Risk Volatility Index", risk_std)

        st.markdown("---")

        # ---- Chart 1 — Risk Distribution
        fig1 = px.pie(employee_df_full, names="RiskBand", title="Workforce Risk Distribution")
        st.plotly_chart(fig1, use_container_width=True)

        # ---- Chart 2 — Department vs Avg Risk
        dept_df = dept_avg.reset_index()
        fig2 = px.bar(dept_df, x="Department", y="AttritionRisk", title="Average Attrition Risk by Department", text_auto=True)
        fig2.update_traces(textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)

        # ---- Chart 3 — Role vs Avg Risk
        role_df = employee_df_full.groupby("Role")["AttritionRisk"].mean().reset_index()
        fig3 = px.bar(role_df, x="Role", y="AttritionRisk", title="Average Attrition Risk by Role Level", text_auto=True)
        fig3.update_traces(textposition="outside")
        st.plotly_chart(fig3, use_container_width=True)

        # ---- Chart 4 — Risk Pyramid
        pyramid_df = pd.DataFrame({
            "RiskBand": ["Low", "Medium", "High"],
            "Headcount": [low_cnt, med_cnt, high_cnt]
        })
        fig4 = px.bar(pyramid_df, x="RiskBand", y="Headcount", title="Attrition Risk Pyramid", text_auto=True)
        fig4.update_traces(textposition="outside")
        st.plotly_chart(fig4, use_container_width=True)

        # ---- Chart 5 — Job Satisfaction vs Risk
        fig5 = px.scatter(employee_df_full, x="JobSatisfaction", y="AttritionRisk", color="RiskBand", title="Job Satisfaction vs Attrition Risk")
        st.plotly_chart(fig5, use_container_width=True)

        # ---- Chart 6 — Stress vs Risk
        fig6 = px.box(employee_df_full, x="StressLevel", y="AttritionRisk", title="Stress Level vs Attrition Risk")
        st.plotly_chart(fig6, use_container_width=True)

        # ---- Chart 7 — Heatmap
        heatmap_df = employee_df_full.pivot_table(
            values="AttritionRisk", index="Department", columns="Role", aggfunc="mean"
        )
        fig7 = px.imshow(heatmap_df, title="Attrition Risk Heatmap: Department × Role", aspect="auto")
        st.plotly_chart(fig7, use_container_width=True)

        # ---- Chart 8 — Treemap
        treemap_df = employee_df_full.groupby(["Department", "RiskBand"]).size().reset_index(name="Headcount")
        fig8 = px.treemap(treemap_df, path=["Department", "RiskBand"], values="Headcount", title="Workforce Risk Composition Tree Map")
        fig8.update_traces(textinfo="label+value")
        st.plotly_chart(fig8, use_container_width=True)

# =================================================
# TAB 3 — PRESCRIPTIVE ACTIONS
# =================================================
with tab3:
    st.markdown("## Prescriptive Actions Engine")
    st.caption("From Risk Identification → Manager Action → Retention Outcome")

    # Simulated Role Selection
    role_view = st.selectbox("View As", ["CHRO", "HRBP", "Manager"])
    manager_name = st.text_input("Manager Name (for Manager / HRBP view)", value="Manager_A")

    # Data Scope Logic
    scoped_df = employee_df_view.copy()
    if role_view == "Manager":
        scoped_df = scoped_df[scoped_df["Name"].notna()] # placeholder for team logic
    
    # Focus on Medium + High Risk
    scoped_df = scoped_df[scoped_df["RiskBand"].isin(["High", "Medium"])]

    st.markdown("### At-Risk Employees Requiring Action")
    st.dataframe(
        scoped_df[["EmployeeID", "Name", "Department", "Role", "AttritionRisk", "RiskBand"]],
        use_container_width=True
    )

    st.markdown("---")
    st.markdown("### Action Planning for Selected Employee")

    emp_id = st.selectbox(
        "Select Employee ID",
        scoped_df["EmployeeID"].unique() if not scoped_df.empty else []
    )
    selected_emp = scoped_df[scoped_df["EmployeeID"] == emp_id]

    if not selected_emp.empty:
        emp = selected_emp.iloc[0]
        st.info(f"**{emp['Name']}** | Dept: {emp['Department']} | Risk: {emp['AttritionRisk']}% ({emp['RiskBand']})")

        # SMART ACTION NUDGE
        available_actions = [
            "Career Path Discussion", "Compensation Review", "Manager Coaching / 1:1",
            "Internal Role Movement", "Workload Rebalancing", "Training / Upskilling",
            "Engagement Survey Follow-up", "No Action – Monitor"
        ]

        likely_exit_reason = None
        dept_col = "Department_Employee" if "Department_Employee" in exit_merged.columns else "Department"
        role_col = "Role_Employee" if "Role_Employee" in exit_merged.columns else "Role"

        if not exit_merged.empty:
            similar_exits = exit_merged[exit_merged[role_col] == emp["Role"]]
            if dept_col in exit_merged.columns:
                similar_exits = similar_exits[similar_exits[dept_col] == emp["Department"]]
            
            if not similar_exits.empty:
                likely_exit_reason = similar_exits["PrimaryExitReason"].value_counts().idxmax()

        # Remove historically failed actions
        if likely_exit_reason and likely_exit_reason in failed_action_map:
            avoid_actions = failed_action_map[likely_exit_reason]
            available_actions = [a for a in available_actions if a not in avoid_actions]

        recommended_action = st.selectbox("Recommended Action", available_actions)
        if likely_exit_reason:
            st.caption(
                f"Based on past exits in this role/department, **{likely_exit_reason}** is a common attrition driver. "
                f"Historically ineffective actions are deprioritized."
            )

        action_status = st.selectbox("Action Status", ["Planned", "In Progress", "Completed"])
        manager_comment = st.text_area("Manager / HRBP Comment", placeholder="Describe the action taken or planned...")

        if st.button("Save Action Decision"):
            guard(["CHRO", "HRBP", "Manager"])
            if emp["Department"] != dept and role != "CHRO":
                st.error("You can only act within your department.")
                st.stop()

            new_action = {
                "EmployeeID": emp["EmployeeID"],
                "EmployeeName": emp["Name"],
                "Department": emp["Department"],
                "Manager": manager_name,
                "RiskScore": emp["AttritionRisk"],
                "RiskBand": emp["RiskBand"],
                "SelectedAction": recommended_action,
                "ActionStatus": action_status,
                "ManagerComment": manager_comment,
                "OutcomeStatus": "Pending",
                "OutcomeDate": ""
            }

            actions_df = pd.concat([actions_df, pd.DataFrame([new_action])], ignore_index=True)
            actions_df.to_csv(ACTIONS_FILE, index=False)
            st.success("Action recorded successfully.")

    # ACTION MONITORING DASHBOARD
    st.markdown("### Action Monitoring & Effectiveness")

    if actions_df.empty:
        st.warning("No actions recorded yet.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Actions Logged", len(actions_df))
        col2.metric("High Risk Covered", len(actions_df[actions_df["RiskBand"] == "High"]))
        col3.metric("Actions In Progress", len(actions_df[actions_df["ActionStatus"] == "In Progress"]))
        col4.metric("Completed Actions", len(actions_df[actions_df["ActionStatus"] == "Completed"]))

        fig1 = px.pie(actions_df, names="ActionStatus", title="Action Status Distribution")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(actions_df, x="SelectedAction", title="Types of Retention Actions Taken")
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.histogram(actions_df, x="RiskScore", color="ActionStatus", title="Risk Score Coverage by Action Status")
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### Detailed Action Log")
        st.dataframe(actions_df, use_container_width=True)

# =================================================
# TAB 4 — REPORTS
# =================================================
with tab4:
    st.markdown("## Reports & Downloads")
    st.caption("Executive-ready reports generated from live retention data")

    if employee_df_full.empty:
        st.warning("No employee data available to generate reports.")
    else:
        # EXEC SUMMARY
        total_emp = len(employee_df_full)
        high = len(employee_df_full[employee_df_full["RiskBand"] == "High"])
        medium = len(employee_df_full[employee_df_full["RiskBand"] == "Medium"])
        low = len(employee_df_full[employee_df_full["RiskBand"] == "Low"])
        expected_leavers = round(employee_df_full["AttritionRisk"].sum() / 100, 2)
        est_cost = int(expected_leavers * 500000)

        exec_summary = pd.DataFrame({
            "Metric": ["Total Employees", "High Risk Employees", "Medium Risk Employees", "Low Risk Employees", "Expected Leavers", "Estimated Attrition Cost ($)"],
            "Value": [total_emp, high, medium, low, expected_leavers, est_cost]
        })

        high_risk_emps = employee_df_full[employee_df_full["RiskBand"] == "High"].sort_values("AttritionRisk", ascending=False)
        action_summary = actions_df if not actions_df.empty else pd.DataFrame({"Info": ["No actions logged yet"]})

        segment_stats = employee_df_full.groupby("Department").agg(
            Headcount=("EmployeeID", "count"),
            Avg_Risk=("AttritionRisk", "mean"),
            High_Risk_Count=("RiskBand", lambda x: (x == "High").sum())
        ).reset_index()

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            exec_summary.to_excel(writer, sheet_name="Executive Summary", index=False)
            high_risk_emps.to_excel(writer, sheet_name="High Risk Employees", index=False)
            segment_stats.to_excel(writer, sheet_name="Department Risk Stats", index=False)
            action_summary.to_excel(writer, sheet_name="Retention Actions Log", index=False)
        output.seek(0)

        guard(["CHRO", "HRBP"])
        st.download_button(
            label="Download Executive & HRBP Report (Excel)",
            data=output,
            file_name="OrgaKnow_Retention_Intelligence_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("---")
        st.markdown("### What This Report Includes")
        st.markdown("""
        - Executive Summary KPIs
        - Prioritized High-Risk Employees
        - Department-wise Risk Statistics
        - Manager / HRBP Action Tracking
        """)
        st.success("Report ready for CHRO / HRBP review.")

# =================================================
# TAB 5 — ACTION EFFECTIVENESS
# =================================================
with tab5:
    st.markdown("## Action Effectiveness Analytics")
    st.caption("Evaluating which retention actions reduce attrition risk")

    if actions_df.empty or employee_df_full.empty:
        st.warning("Insufficient data to evaluate action effectiveness.")
    else:
        merged_df = actions_df.merge(
            employee_df_full[["EmployeeID", "AttritionRisk"]],
            on="EmployeeID", how="left", suffixes=("_AtAction", "_Current")
        )
        merged_df.rename(columns={"RiskScore": "Risk_At_Action", "AttritionRisk": "Risk_Current"}, inplace=True)
        merged_df["Risk_Change"] = merged_df["Risk_At_Action"] - merged_df["Risk_Current"]
        merged_df["RiskMovement"] = merged_df["Risk_Change"].apply(risk_arrow)

        total_actions = len(merged_df)
        improved_cases = len(merged_df[merged_df["Risk_Change"] > 0])
        worsened_cases = len(merged_df[merged_df["Risk_Change"] < 0])
        avg_risk_reduction = round(merged_df["Risk_Change"].mean(), 2)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Actions Evaluated", total_actions)
        col2.metric("Risk Reduced Cases", improved_cases)
        col3.metric("Risk Increased Cases", worsened_cases)
        col4.metric("Avg Risk Change (%)", avg_risk_reduction)
        st.markdown("---")

        action_effect = merged_df.groupby("SelectedAction")["Risk_Change"].mean().reset_index()
        fig1 = px.bar(action_effect, x="SelectedAction", y="Risk_Change", title="Average Risk Reduction by Action Type")
        st.plotly_chart(fig1, use_container_width=True)

        merged_df["ActionSuccess"] = merged_df["Risk_Change"].apply(lambda x: "Effective" if x > 0 else "Not Effective")
        fig2 = px.histogram(merged_df, x="SelectedAction", color="ActionSuccess", title="Action Effectiveness Distribution")
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.box(merged_df, x="SelectedAction", y="Risk_Change", title="Risk Change Distribution by Action")
        st.plotly_chart(fig3, use_container_width=True)

        high_risk_actions = merged_df[merged_df["RiskBand"] == "High"]
        if not high_risk_actions.empty:
            fig4 = px.bar(high_risk_actions.groupby("SelectedAction")["Risk_Change"].mean().reset_index(),
                          x="SelectedAction", y="Risk_Change", title="Action Effectiveness for High-Risk Employees")
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### Drill-Down: Manager View")
        manager_filter = st.selectbox("Select Manager", merged_df["Manager"].unique())
        mgr_df = merged_df[merged_df["Manager"] == manager_filter]

        fig5 = px.scatter(mgr_df, x="Risk_At_Action", y="Risk_Current", color="SelectedAction", title=f"Risk Movement for {manager_filter}'s Team")
        st.plotly_chart(fig5, use_container_width=True)

        st.markdown("---")
        st.markdown("### Action Effectiveness Table")
        st.dataframe(
            merged_df[[
                "EmployeeID", "EmployeeName", "SelectedAction",
                "Risk_At_Action", "Risk_Current", "Risk_Change", "ActionStatus"
            ]], use_container_width=True
        )

# =================================================
# TAB 6 — OUTCOME TRACKING
# =================================================
with tab6:
    st.markdown("## Outcome Tracking")
    st.caption("Tracking retention outcomes to measure real business impact")

    if actions_df.empty:
        st.warning("No action records available for outcome tracking.")
    else:
        st.markdown("### Update Employee Outcome")
        emp_id = st.selectbox("Select Employee ID", actions_df["EmployeeID"].unique(), key="outcome_emp_select")
        emp_action = actions_df[actions_df["EmployeeID"] == emp_id].iloc[-1]

        st.info(f"**{emp_action['EmployeeName']}** | Risk at Action: {emp_action['RiskScore']}% | Action: {emp_action['SelectedAction']}")
        outcome = st.selectbox("Outcome Status", ["Pending", "Stayed", "Left"])
        outcome_date = st.date_input("Outcome Date")
        
        guard(["CHRO", "HRBP"])
        if st.button("Save Outcome"):
            idx = actions_df[actions_df["EmployeeID"] == emp_id].index[-1]
            actions_df.loc[idx, "OutcomeStatus"] = outcome
            actions_df.loc[idx, "OutcomeDate"] = str(outcome_date)
            actions_df.to_csv(ACTIONS_FILE, index=False)
            st.success("Outcome updated successfully.")

        st.markdown("---")

        total_tracked = len(actions_df)
        stayed = len(actions_df[actions_df["OutcomeStatus"] == "Stayed"])
        left = len(actions_df[actions_df["OutcomeStatus"] == "Left"])
        retention_rate = round((stayed / (stayed + left)) * 100, 1) if (stayed + left) > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Employees Tracked", total_tracked)
        col2.metric("Retained (Stayed)", stayed)
        col3.metric("Attrited (Left)", left)
        col4.metric("Retention Success Rate", f"{retention_rate}%")

        st.markdown("---")
        fig1 = px.pie(actions_df, names="OutcomeStatus", title="Retention Outcomes Distribution")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.histogram(actions_df, x="SelectedAction", color="OutcomeStatus", title="Outcome by Action Type")
        st.plotly_chart(fig2, use_container_width=True)

        high_risk_outcomes = actions_df[actions_df["RiskBand"] == "High"]
        if not high_risk_outcomes.empty:
            fig3 = px.pie(high_risk_outcomes, names="OutcomeStatus", title="High-Risk Employee Outcomes")
            st.plotly_chart(fig3, use_container_width=True)

        fig4 = px.box(actions_df, x="OutcomeStatus", y="RiskScore", title="Risk Score vs Outcome")
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")
        st.markdown("### Outcome Tracking Log")
        st.dataframe(actions_df[["EmployeeID", "EmployeeName", "SelectedAction", "RiskScore", "OutcomeStatus", "OutcomeDate", "Manager"]], use_container_width=True)

st.markdown("---")
st.caption("OrgaKnow Retention Intelligence · Decision-support analytics. Predictions are probabilistic and should be combined with HR judgment.")

# =================================================
# TAB 7 — EXIT INTELLIGENCE
# =================================================
with tab7:
    # Debug info
    # st.write("EXIT MERGED COLUMNS:", exit_merged.columns.tolist()) 

    # Filter for employees marked as Left in Outcome Tracking
    left_employee_ids = actions_df[actions_df["OutcomeStatus"] == "Left"]["EmployeeID"].unique() if not actions_df.empty else []

    st.markdown("## Exit Intelligence")
    st.caption("Structured learning from employee exits to improve future retention decisions")

    guard(["CHRO", "HRBP"])

    st.markdown("### Record Exit Intelligence")
    st.markdown("### Bulk Upload Exit Data (Smart Import)")
    exit_upload = st.file_uploader("Upload Exit Data CSV", type=["csv"])
    
    if exit_upload:
        raw_df = pd.read_csv(exit_upload)
        st.write("Preview of uploaded data:", raw_df.head(3))

        required_fields = ["EmployeeID", "ExitDate", "ExitType", "PrimaryExitReason", "ActionTaken"]
        column_mapping = {}
        
        st.markdown("#### Map Your Columns")
        st.caption("We tried to match your columns to ours. Please confirm.")
        
        cols = st.columns(len(required_fields))
        for i, field in enumerate(required_fields):
            matches = difflib.get_close_matches(field, raw_df.columns, n=1, cutoff=0.4)
            default_index = list(raw_df.columns).index(matches[0]) if matches else 0
            with cols[i % 3]: 
                selected_col = st.selectbox(f"Map to '{field}'", raw_df.columns, index=default_index, key=f"map_{field}")
                column_mapping[field] = selected_col

        if st.button("Import & Standardize Data"):
            standardized_df = pd.DataFrame()
            for system_col, user_col in column_mapping.items():
                standardized_df[system_col] = raw_df[user_col]
        
            standardized_df["SecondaryExitReason"] = "None"
            standardized_df["ActionHelped"] = "Not Applicable"
            standardized_df["HRComment"] = "Bulk Uploaded"

            # Data Validation
            standardized_df["EmployeeID"] = standardized_df["EmployeeID"].astype(str)
            valid_ids = employee_df_full["EmployeeID"].astype(str).unique()
            invalid_rows = standardized_df[~standardized_df["EmployeeID"].isin(valid_ids)]

            if not invalid_rows.empty:
                st.warning(f"⚠️ {len(invalid_rows)} records have Employee IDs that don't exist in the Master Database. They were skipped.")
                standardized_df = standardized_df[standardized_df["EmployeeID"].isin(valid_ids)]
        
            exit_df = pd.concat([exit_df, standardized_df], ignore_index=True)
            exit_df.to_csv(EXIT_FILE, index=False)
            st.success(f"Successfully imported {len(standardized_df)} exit records!")
            st.rerun()

            standardized_df["ExitDate"] = pd.to_datetime(standardized_df["ExitDate"], errors='coerce')
            if standardized_df["ExitDate"].isnull().any():
                st.error("Some dates could not be read. Please ensure Date format is consistent.")
                st.stop()

    # Manual Exit Entry
    if len(left_employee_ids) == 0:
        st.info("No employees marked as 'Left' yet.")
    else:
        emp_id = st.selectbox("Select Exited Employee", left_employee_ids)
        exit_date = st.date_input("Exit Date", key="manual_exit_date")
        exit_type = st.selectbox("Exit Type", ["Voluntary", "Involuntary", "Contract End"])
        
        primary_reason = st.selectbox("Primary Exit Reason", [
            "Compensation", "Career Growth", "Manager Relationship",
            "Workload / Burnout", "Role Mismatch", "Work Culture",
            "External Opportunity", "Personal Reasons"
        ])
        
        secondary_reason = st.selectbox("Secondary Exit Reason (Optional)", ["None"] + [
            "Compensation", "Career Growth", "Manager Relationship",
            "Workload / Burnout", "Role Mismatch", "Work Culture",
            "External Opportunity", "Personal Reasons"
        ])

        action_taken = st.selectbox("Was any retention action taken?", ["Yes", "No"])
        action_helped = st.selectbox("Did the action help?", ["Yes", "Partially", "No", "Not Applicable"])
        hr_comment = st.text_area("HR Comment (Optional)", placeholder="Neutral summary from FnF discussion")

        if st.button("Save Exit Intelligence"):
            new_exit = {
                "EmployeeID": emp_id,
                "ExitDate": str(exit_date),
                "ExitType": exit_type,
                "PrimaryExitReason": primary_reason,
                "SecondaryExitReason": secondary_reason,
                "ActionTaken": action_taken,
                "ActionHelped": action_helped,
                "HRComment": hr_comment
            }
            exit_df = pd.concat([exit_df, pd.DataFrame([new_exit])], ignore_index=True)
            exit_df.to_csv(EXIT_FILE, index=False)
            st.success("Exit intelligence saved successfully.")

    st.markdown("---")
    st.markdown("### Exit Intelligence Insights")

    if exit_df.empty:
        st.info("No exit intelligence data available yet.")
    else:
        # Re-merge to capture updates
        exit_merged = exit_df.merge(
            actions_df, on="EmployeeID", how="left"
        ).merge(
            employee_df_full, on="EmployeeID", how="left", suffixes=("_Action", "_Employee")
        )

        st.markdown("#### 1. Why Employees Leave")
        
        ROLE_COL = "Role_Employee" if "Role_Employee" in exit_merged.columns else "Role"
        DEPT_COL = "Department_Employee" if "Department_Employee" in exit_merged.columns else "Department"

        reason_counts = exit_merged["PrimaryExitReason"].value_counts().reset_index()
        reason_counts.columns = ["Exit Reason", "Count"]

        fig1 = px.pie(reason_counts, names="Exit Reason", values="Count", title="Primary Reasons for Employee Attrition")
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("#### 2. Exit Reasons by Department")
        if DEPT_COL in exit_merged.columns:
            dept_reason = exit_merged.groupby([DEPT_COL, "PrimaryExitReason"]).size().reset_index(name="Count")
            fig2 = px.bar(dept_reason, x=DEPT_COL, y="Count", color="PrimaryExitReason", title="Exit Reasons by Department")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 3. Action Failure Analysis")
        action_failure = exit_merged[exit_merged["ActionTaken"] == "Yes"]
        if not action_failure.empty:
            failure_summary = action_failure.groupby(["SelectedAction", "PrimaryExitReason"]).size().reset_index(name="Count")
            fig3 = px.bar(failure_summary, x="SelectedAction", y="Count", color="PrimaryExitReason", title="Failed Retention Actions by Exit Reason")
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("#### 4. Risk Blind Spot Analysis")
        # Ensure RiskScore is available (it comes from actions_df merge)
        if "RiskScore" in exit_merged.columns:
            exit_merged["RiskCategoryAtExit"] = exit_merged["RiskScore"].apply(
                lambda x: "High Risk Exit" if pd.notnull(x) and x >= 70
                else "Medium Risk Exit" if pd.notnull(x) and x >= 40
                else "Low Risk Exit" if pd.notnull(x) else "Unknown"
            )
            blindspot_counts = exit_merged["RiskCategoryAtExit"].value_counts().reset_index()
            blindspot_counts.columns = ["Risk Category", "Count"]

            fig4 = px.bar(blindspot_counts, x="Risk Category", y="Count", title="Attrition by Risk Category at Exit")
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("#### 5. Executive Learning Summary")
        if not reason_counts.empty:
            top_reason = reason_counts.iloc[0]["Exit Reason"]
            st.info(f"""
            **Key Attrition Insights**
            - Most common exit reason: **{top_reason}**
            - These insights should guide future retention strategy and policy changes.
            """)

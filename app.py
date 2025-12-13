import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Skills-First Tech Gaps", layout="wide")

# -------------------------
# Load data
# -------------------------
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    empleados = pd.read_csv(DATA_DIR / "01_Empleados.csv")
    skills_req = pd.read_csv(DATA_DIR / "02_Skills_Requeridas.csv")
    skills_act = pd.read_csv(DATA_DIR / "03_Skills_Actuales.csv")

    df = skills_act.merge(
        empleados[["employee_id", "nombre", "area", "rol", "seniority"]],
        on="employee_id",
        how="left"
    ).merge(
        skills_req,
        on=["rol", "skill"],
        how="left"
    )

    df["nivel_actual"] = pd.to_numeric(df["nivel_actual"], errors="coerce")
    df["nivel_requerido"] = pd.to_numeric(df["nivel_requerido"], errors="coerce")
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce")

    df["gap"] = df["nivel_requerido"] - df["nivel_actual"]
    df["gap_pos"] = df["gap"].clip(lower=0)
    df["gap_ponderado"] = df["gap_pos"] * df["peso"]

    df["tiene_gap"] = df["gap_pos"] > 0
    df["skill_critica"] = df["peso"] == 3

    return empleados, df

empleados, df = load_data()

# -------------------------
# Outputs
# -------------------------
def build_outputs(df_):
    gap_por_skill = (
        df_.groupby(["skill", "categoria_skill"], as_index=False)
           .agg(
               empleados_afectados=("tiene_gap", "sum"),
               empleados_total=("employee_id", "nunique"),
               gap_ponderado_total=("gap_ponderado", "sum")
           )
    ).sort_values("gap_ponderado_total", ascending=False)

    gap_por_persona = (
        df_.groupby(["employee_id","nombre","rol","area"], as_index=False)
           .agg(
               gap_ponderado_total=("gap_ponderado","sum")
           )
    ).sort_values("gap_ponderado_total", ascending=False)

    gap_por_rol = (
        df_.groupby(["rol"], as_index=False)
           .agg(
               gap_ponderado_promedio=("gap_ponderado","mean")
           )
    ).sort_values("gap_ponderado_promedio", ascending=False)

    return gap_por_skill, gap_por_persona, gap_por_rol

gap_skill, gap_persona, gap_rol = build_outputs(df)

# -------------------------
# UI
# -------------------------
st.title("Skills-First – Tech Gaps")

tab1, tab2, tab3 = st.tabs(["Overview", "Por rol", "Por persona"])

with tab1:
    st.subheader("Top 3 skills con mayor gap ponderado")
    st.dataframe(gap_skill.head(3), use_container_width=True)

with tab2:
    st.subheader("Top roles con mayor gap")
    st.dataframe(gap_rol, use_container_width=True)

with tab3:
    st.subheader("Gap por persona")
    st.dataframe(gap_persona, use_container_width=True)

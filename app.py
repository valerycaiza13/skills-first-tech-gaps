import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Skills-First Tech Gaps", layout="wide")

DATA_DIR = Path(__file__).parent  # CSV al mismo nivel que app.py

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

    # tipos numéricos
    df["nivel_actual"] = pd.to_numeric(df["nivel_actual"], errors="coerce")
    df["nivel_requerido"] = pd.to_numeric(df["nivel_requerido"], errors="coerce")
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce")

    # GAP simple (sin ponderación)
    df["gap"] = df["nivel_requerido"] - df["nivel_actual"]
    df["gap_pos"] = df["gap"].clip(lower=0)

    df["tiene_gap"] = df["gap_pos"] > 0
    df["skill_critica"] = df["peso"] == 3

    return empleados, skills_req, skills_act, df

empleados, skills_req, skills_act, df = load_data()

# -------------------------
# Helpers (outputs)
# -------------------------
def gap_por_skill(df_):
    out = (
        df_.groupby(["skill", "categoria_skill"], as_index=False)
           .agg(
               empleados_total=("employee_id", "nunique"),
               empleados_con_gap=("tiene_gap", "sum"),
               gap_promedio=("gap_pos", "mean"),
               gap_total=("gap_pos", "sum"),
               peso=("peso", "max")  # peso está definido por rol-skill, aquí solo para referencia
           )
    )
    out["pct_empleados_con_gap"] = (out["empleados_con_gap"] / out["empleados_total"]) * 100
    out = out.sort_values(["gap_total", "pct_empleados_con_gap"], ascending=False)
    return out

def gap_por_persona(df_):
    out = (
        df_.groupby(["employee_id","nombre","area","rol"], as_index=False)
           .agg(
               skills_evaluadas=("skill","count"),
               skills_con_gap=("tiene_gap","sum"),
               gap_total=("gap_pos","sum"),
               gap_promedio=("gap_pos","mean")
           )
    )
    out["pct_skills_con_gap"] = (out["skills_con_gap"] / out["skills_evaluadas"]) * 100
    out = out.sort_values(["gap_total","pct_skills_con_gap"], ascending=False)
    return out

def gap_por_rol_area(df_):
    out = (
        df_.groupby(["area","rol"], as_index=False)
           .agg(
               empleados=("employee_id","nunique"),
               gap_promedio=("gap_pos","mean"),
               gap_total=("gap_pos","sum"),
               pct_empleados_con_gap=("tiene_gap","mean")
           )
    )
    out["pct_empleados_con_gap"] = out["pct_empleados_con_gap"] * 100
    out = out.sort_values(["gap_promedio","gap_total"], ascending=False)
    return out

def kpis_agregados(df_, gap_persona_df, gap_skill_df, gap_rol_area_df):
    empleados_total = gap_persona_df["employee_id"].nunique()
    empleados_con_brecha = (gap_persona_df["skills_con_gap"] > 0).sum()
    pct_empleados_con_brechas = (empleados_con_brecha / empleados_total) * 100

    top_roles = gap_rol_area_df.sort_values("gap_promedio", ascending=False).head(5)
    top3_skills = gap_skill_df.sort_values("gap_total", ascending=False).head(3)

    return empleados_total, empleados_con_brecha, pct_empleados_con_brechas, top_roles, top3_skills

def skills_criticas_en_riesgo(df_, gap_skill_df, threshold_pct=30):
    # Definición simple y defendible:
    # skill crítica si peso=3 y además afecta al >= threshold_pct de empleados evaluados para esa skill
    crit = gap_skill_df[(gap_skill_df["pct_empleados_con_gap"] >= threshold_pct) & (gap_skill_df["peso"] == 3) & (gap_skill_df["gap_total"] > 0)]
    return crit.sort_values(["gap_total","pct_empleados_con_gap"], ascending=False)

def recomendar_formacion(df_emp):
    # Recomendaciones simples basadas en gaps (sin ponderación)
    # Devuelve top 3 skills con mayor gap para esa persona
    df_emp = df_emp.copy()
    df_emp = df_emp[df_emp["gap_pos"] > 0].sort_values("gap_pos", ascending=False).head(3)

    recs = []
    for _, r in df_emp.iterrows():
        if r["peso"] == 3 and r["gap_pos"] >= 2:
            accion = "Upskilling prioritario: curso + práctica guiada (4–6 semanas)"
        elif r["peso"] == 3:
            accion = "Upskilling focalizado: workshop interno + ejercicios (2–3 semanas)"
        elif r["categoria_skill"] == "Tools & Collaboration":
            accion = "Refuerzo rápido: workshop interno + checklist"
        elif r["categoria_skill"] == "Security & Systems":
            accion = "Microlearning + casos prácticos + repaso de política interna"
        else:
            accion = "Curso corto + práctica aplicada en tareas del rol"

        recs.append({
            "skill": r["skill"],
            "gap": float(r["gap_pos"]),
            "peso": int(r["peso"]) if pd.notna(r["peso"]) else None,
            "recomendacion": accion
        })

    return pd.DataFrame(recs)

# -------------------------
# UI
# -------------------------
st.title("Skills-First – Tech Gaps (versión completa)")

with st.sidebar:
    st.header("Filtros")
    area_sel = st.selectbox("Área", ["Todas"] + sorted(df["area"].dropna().unique().tolist()))
    rol_sel = st.selectbox("Rol", ["Todos"] + sorted(df["rol"].dropna().unique().tolist()))
    threshold_pct = st.slider("Umbral 'críticas en riesgo' (% empleados con gap)", 10, 70, 30, 5)

df_f = df.copy()
if area_sel != "Todas":
    df_f = df_f[df_f["area"] == area_sel]
if rol_sel != "Todos":
    df_f = df_f[df_f["rol"] == rol_sel]

# Outputs base
skill_df = gap_por_skill(df_f)
persona_df = gap_por_persona(df_f)
rol_area_df = gap_por_rol_area(df_f)

# KPIs
empleados_total, empleados_con_brecha, pct_empleados_con_brechas, top_roles, top3_skills = kpis_agregados(df_f, persona_df, skill_df, rol_area_df)

# Skills críticas en riesgo
criticas_df = skills_criticas_en_riesgo(df_f, skill_df, threshold_pct=threshold_pct)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Overview (KPIs)", "Gap por skill", "Gap por rol/área", "Gap por persona + Recos"])

with tab1:
    st.subheader("Indicadores agregados")
    c1, c2, c3 = st.columns(3)
    c1.metric("% empleados con brechas", f"{pct_empleados_con_brechas:.1f}%")
    c2.metric("Empleados con brechas", int(empleados_con_brecha))
    c3.metric("Empleados evaluados", int(empleados_total))

    st.markdown("### Top roles con mayor gap (promedio)")
    st.dataframe(top_roles, use_container_width=True)

    st.markdown("### Top 3 skills con mayor gap (total)")
    st.dataframe(top3_skills[["skill","categoria_skill","gap_total","pct_empleados_con_gap","peso"]], use_container_width=True)

    st.markdown("### Skills críticas en riesgo (peso=3 + umbral)")
    if len(criticas_df) == 0:
        st.info("No se detectaron skills críticas en riesgo con el umbral actual.")
    else:
        st.dataframe(criticas_df[["skill","categoria_skill","gap_total","pct_empleados_con_gap","peso"]], use_container_width=True)

with tab2:
    st.subheader("Gap por skill")
    st.caption("Gap = nivel requerido - nivel actual (solo si es positivo). No se usa ponderación.")
    st.dataframe(skill_df, use_container_width=True)

with tab3:
    st.subheader("Gap por rol y por área")
    st.dataframe(rol_area_df, use_container_width=True)

with tab4:
    st.subheader("Gap por persona")
    st.dataframe(persona_df, use_container_width=True)

    st.markdown("### Ver detalle + recomendaciones por empleado")
    emp_list = empleados[["employee_id","nombre","rol","area"]].copy()
    if area_sel != "Todas":
        emp_list = emp_list[emp_list["area"] == area_sel]
    if rol_sel != "Todos":
        emp_list = emp_list[emp_list["rol"] == rol_sel]

    if len(emp_list) == 0:
        st.warning("No hay empleados para los filtros seleccionados.")
    else:
        emp_list["label"] = emp_list["employee_id"] + " - " + emp_list["nombre"] + " (" + emp_list["rol"] + ")"
        emp_label = st.selectbox("Empleado", emp_list["label"].tolist())
        emp_id = emp_list.loc[emp_list["label"] == emp_label, "employee_id"].iloc[0]

        df_emp = df_f[df_f["employee_id"] == emp_id].copy().sort_values("gap_pos", ascending=False)

        st.markdown("#### Detalle de skills")
        st.dataframe(df_emp[[
            "skill","categoria_skill","nivel_actual","nivel_requerido","peso","gap_pos"
        ]], use_container_width=True)

        st.markdown("#### Recomendaciones (Top 3 gaps)")
        recs_df = recomendar_formacion(df_emp)
        if len(recs_df) == 0:
            st.success("Este empleado no presenta brechas para las skills evaluadas.")
        else:
            st.dataframe(recs_df, use_container_width=True)



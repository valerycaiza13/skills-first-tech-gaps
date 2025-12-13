import pandas as pd
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

    # numeric
    df["nivel_actual"] = pd.to_numeric(df["nivel_actual"], errors="coerce")
    df["nivel_requerido"] = pd.to_numeric(df["nivel_requerido"], errors="coerce")
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce")

    # gap simple
    df["gap"] = df["nivel_requerido"] - df["nivel_actual"]
    df["gap_pos"] = df["gap"].clip(lower=0)
    df["tiene_gap"] = df["gap_pos"] > 0

    # "critica" solo como etiqueta (no multiplicamos nada)
    df["skill_critica"] = df["peso"] == 3

    return empleados, skills_req, skills_act, df

empleados, skills_req, skills_act, df = load_data()

# -------------------------
# Outputs
# -------------------------
def resumen_headcount(empleados_df):
    total = empleados_df["employee_id"].nunique()
    por_area = empleados_df.groupby("area")["employee_id"].nunique().reset_index(name="empleados")
    por_rol = empleados_df.groupby(["area","rol"])["employee_id"].nunique().reset_index(name="empleados")
    return total, por_area, por_rol

def gap_por_skill(df_):
    out = (
        df_.groupby(["skill","categoria_skill"], as_index=False)
           .agg(
               empleados_total=("employee_id","nunique"),
               empleados_afectados=("tiene_gap","sum"),
               peso=("peso","max")
           )
    )
    out["pct_empleados_afectados"] = (out["empleados_afectados"] / out["empleados_total"]) * 100
    out = out.sort_values(["pct_empleados_afectados","empleados_afectados"], ascending=False)
    return out

def gap_por_rol_area(df_):
    # Primero: a nivel PERSONA → si tiene al menos 1 gap
    persona_gap = (
        df_.groupby(["area","rol","employee_id"], as_index=False)
           .agg(tiene_gap=("tiene_gap","any"))
    )

    # Luego: agregamos por rol y área
    out = (
        persona_gap.groupby(["area","rol"], as_index=False)
                   .agg(
                       empleados=("employee_id","nunique"),
                       empleados_afectados=("tiene_gap","sum")
                   )
    )

    out["pct_empleados_afectados"] = (out["empleados_afectados"] / out["empleados"]) * 100
    out = out.sort_values("pct_empleados_afectados", ascending=False)

    return out


def gap_por_persona(df_):
    out = (
        df_.groupby(["employee_id","nombre","area","rol"], as_index=False)
           .agg(
               skills_evaluadas=("skill","count"),
               skills_con_gap=("tiene_gap","sum")
           )
    )
    out["pct_skills_con_gap"] = (out["skills_con_gap"] / out["skills_evaluadas"]) * 100
    out = out.sort_values(["skills_con_gap","pct_skills_con_gap"], ascending=False)
    return out

def skills_criticas_en_riesgo(df_, gap_skill_df, threshold_pct=30):
    # crítica = peso 3, en riesgo = >= threshold_pct afectados
    crit = gap_skill_df[(gap_skill_df["peso"] == 3) & (gap_skill_df["pct_empleados_afectados"] >= threshold_pct)]
    return crit.sort_values(["pct_empleados_afectados","empleados_afectados"], ascending=False)

def recomendar(df_emp):
    # recomendación simple: top 3 gaps (sin ponderación)
    df_emp = df_emp[df_emp["gap_pos"] > 0].sort_values("gap_pos", ascending=False).head(3).copy()
    if df_emp.empty:
        return pd.DataFrame(columns=["skill","nivel_actual","nivel_requerido","gap","recomendacion"])

    recs = []
    for _, r in df_emp.iterrows():
        if r["peso"] == 3 and r["gap_pos"] >= 2:
            accion = "Upskilling prioritario: curso + práctica guiada (4–6 semanas)"
        elif r["peso"] == 3:
            accion = "Upskilling focalizado: workshop interno + ejercicios (2–3 semanas)"
        else:
            accion = "Curso corto + práctica aplicada en tareas del rol"

        recs.append({
            "skill": r["skill"],
            "nivel_actual": r["nivel_actual"],
            "nivel_requerido": r["nivel_requerido"],
            "gap": r["gap_pos"],
            "recomendacion": accion
        })

    return pd.DataFrame(recs)

# -------------------------
# UI
# -------------------------
st.title("Skills-First–Tech Gaps")

with st.sidebar:
    st.header("Filtros")
    area_sel = st.selectbox("Área", ["Todas"] + sorted(df["area"].dropna().unique().tolist()))
    rol_sel = st.selectbox("Rol", ["Todos"] + sorted(df["rol"].dropna().unique().tolist()))
    threshold_pct = st.slider("Umbral 'skills críticas en riesgo' (% afectados)", 10, 70, 30, 5)

df_f = df.copy()
if area_sel != "Todas":
    df_f = df_f[df_f["area"] == area_sel]
if rol_sel != "Todos":
    df_f = df_f[df_f["rol"] == rol_sel]

total_emp, por_area, por_rol = resumen_headcount(empleados)
skill_df = gap_por_skill(df_f)
rol_area_df = gap_por_rol_area(df_f)
persona_df = gap_por_persona(df_f)
criticas_df = skills_criticas_en_riesgo(df_f, skill_df, threshold_pct=threshold_pct)

# KPIs simples
empleados_afectados_total = (persona_df["skills_con_gap"] > 0).sum()
pct_empleados_afectados_total = (empleados_afectados_total / persona_df["employee_id"].nunique()) * 100

tab1, tab2, tab3, tab4 = st.tabs(["Resumen", "Gap por skill", "Gap por rol/área", "Por persona"])
def skills_evaluadas_por_area(empleados_df, skills_req_df):
    """
    Devuelve las skills evaluadas por área,
    en base a los roles que existen en cada área.
    """
    roles_por_area = empleados_df.groupby("area")["rol"].unique().to_dict()

    filas = []
    for area, roles in roles_por_area.items():
        df_area = skills_req_df[skills_req_df["rol"].isin(roles)].copy()
        if df_area.empty:
            continue

        df_area = (
            df_area.groupby(["skill", "categoria_skill"], as_index=False)
                   .agg(peso=("peso", "max"))
        )
        df_area["area"] = area
        filas.append(df_area)

    if not filas:
        return pd.DataFrame(columns=["area", "skill", "categoria_skill", "peso"])

    out = pd.concat(filas, ignore_index=True)
    out = out.sort_values(["area", "peso", "skill"], ascending=[True, False, True])
    return out
with tab1:
    st.subheader("Resumen")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total empleados", int(total_emp))
    c2.metric("Empleados afectados (>=1 gap)", int(empleados_afectados_total))
    c3.metric("% empleados afectados", f"{pct_empleados_afectados_total:.1f}%")

    st.markdown("### Empleados por área")
    st.dataframe(por_area, use_container_width=True)

    st.markdown("### Empleados por rol (dentro de cada área)")
    st.dataframe(por_rol, use_container_width=True)

    st.markdown("### Skills evaluadas por área")
    st.caption(
        "Listado de skills técnicas consideradas en la evaluación, "
        "según los roles existentes en cada área."
    )

    skills_area_df = skills_evaluadas_por_area(empleados, skills_req)

    area_focus_skills = st.selectbox(
        "Selecciona un área para ver las skills evaluadas:",
        ["Todas"] + sorted(skills_area_df["area"].unique().tolist()),
        key="skills_area_select"
    )

    if area_focus_skills != "Todas":
        st.dataframe(
            skills_area_df[skills_area_df["area"] == area_focus_skills],
            use_container_width=True
        )
    else:
        st.dataframe(skills_area_df, use_container_width=True)

    # 👇 Esto se muestra SIEMPRE en tab1 (no depende del if/else)
    st.info(
        "🔎 **Interpretación del peso de las skills**\n\n"
        "- **3** → Muy importante / crítica para el rol\n"
        "- **2** → Importante\n"
        "- **1** → Básica o de apoyo"
    )

    st.markdown("### Skills críticas en riesgo (peso = 3 → muy importantes para el rol)")
    if len(criticas_df) == 0:
        st.info("No se detectaron skills críticas en riesgo con el umbral actual.")
    else:
        st.dataframe(
            criticas_df[["skill","categoria_skill","empleados_afectados","empleados_total","pct_empleados_afectados","peso"]],
            use_container_width=True
        )

with tab2:
    st.subheader("Gap por skill")
    st.caption("Aquí vemos cuántas personas NO cumplen el nivel requerido por skill (según su rol).")
    st.dataframe(
        skill_df[["skill","categoria_skill","empleados_afectados","empleados_total","pct_empleados_afectados","peso"]],
        use_container_width=True
    )

with tab3:
    st.subheader("Gap por rol y por área")
    st.dataframe(
        rol_area_df[["area","rol","empleados_afectados","empleados","pct_empleados_afectados"]],
        use_container_width=True
    )

with tab4:
    st.subheader("Gap por persona")
    st.dataframe(persona_df, use_container_width=True)

    st.markdown("### Selecciona un empleado para ver: nivel actual vs requerido + gap")
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

        df_emp = df_f[df_f["employee_id"] == emp_id].copy()
        df_emp = df_emp.sort_values("gap_pos", ascending=False)

        st.markdown("#### Detalle (nivel actual, requerido, gap)")
        st.dataframe(
            df_emp[["skill","categoria_skill","nivel_actual","nivel_requerido","gap_pos","peso"]],
            use_container_width=True
        )

        st.markdown("#### Recomendaciones (Top 3 gaps)")
        rec_df = recomendar(df_emp)
        if rec_df.empty:
            st.success("Este empleado no presenta brechas para las skills evaluadas.")
        else:
            st.dataframe(rec_df, use_container_width=True)
















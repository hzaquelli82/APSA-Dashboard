import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh


st.set_page_config(
    page_title="Control de Producción",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.logo('images/Logo_Inst.png', size='large')

count = st_autorefresh(interval=60000, limit=None, key="counter_autorefresh")


def format_timedelta_hh_mm_ss(td) -> str:
    if pd.isna(td):
        return ""
    if isinstance(td, pd.Timedelta):
        total_seconds = int(td.total_seconds())
    elif isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
    else:
        return str(td)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def conectar_mysql():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

@st.cache_data(ttl=60)
def obtener_df(fecha_actual_param, hora_referencia):
    fecha_ayer_param = (fecha_actual_param - timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_str = fecha_actual_param.strftime("%Y-%m-%d")
    
    db = conectar_mysql()
    cur = db.cursor()

    try:
        cur.execute('''
            SELECT                 
                tareaseje.NroID,
                tareaseje.Fecha AS Fecha,
                tareaseje.Hora AS Hora,
                formulas.NroID AS IDF,
                formulas.Nombre AS Nombre,
                tareaseje.Set AS Programado,
                (SELECT SUM(dcaptura.Valor) FROM dbp8100.dcaptura WHERE dcaptura.IDT = tareaseje.NroID) AS Dosificado,
                tareaseje.Tiempo AS Tiempo
            FROM 
                dbp8100.tareaseje AS tareaseje
            JOIN 
                dbp8100.formulas AS formulas ON formulas.NroID = tareaseje.IDF
            WHERE
                (tareaseje.Fecha = %s AND tareaseje.Hora >= '22:00:00') OR 
                (tareaseje.Fecha > %s AND tareaseje.Fecha <= %s AND tareaseje.Hora < '22:00:00')
            GROUP BY
                tareaseje.NroID
        ''', (fecha_ayer_param, fecha_ayer_param, fecha_str))
        
        resultados = cur.fetchall()
        columnas = [desc[0] for desc in cur.description]
        df = pd.DataFrame(resultados, columns=columnas)
    finally:
        cur.close()
        db.close()

    if df.empty:
        return df

    # Convertir a objetos TimeDelta
    df['Hora'] = pd.to_timedelta(df['Hora'].astype(str))
    df['Tiempo'] = pd.to_timedelta(df['Tiempo'].astype(str))

    # Corregir los tiempos 0
    mask = df['Tiempo'] == pd.Timedelta(0)
    df.loc[mask, 'Tiempo'] = df['Hora'].shift(-1) - df.loc[mask, 'Hora']

    if pd.isna(df.loc[df.index[-1], 'Tiempo']):
        df.loc[df.index[-1], 'Tiempo'] = hora_referencia - df.loc[df.index[-1], 'Hora']

    segundos_tiempo = df['Tiempo'].dt.total_seconds().replace(0, pd.NA)
    df['Rendimiento'] = (df['Dosificado'] / (segundos_tiempo / 3600)) / 1000

    return df

# Sidebar Date Picker
default_date = datetime.now()
selected_date = st.sidebar.date_input("Seleccione una fecha:", default_date)
fecha_actual = datetime.combine(selected_date, datetime.min.time())

# Determinar hora de referencia
es_hoy = selected_date == datetime.now().date()
hora_actual = pd.to_timedelta(datetime.now().strftime('%H:%M:%S')) if es_hoy else pd.to_timedelta('22:00:00')

if st.sidebar.button("Actualizar"):
    st.cache_data.clear()

df = obtener_df(fecha_actual, hora_actual)

st.markdown(
    """
    <style>
    .big-font {
        font-size: 40px !important;
        color: blue;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<p class="big-font">Control de Producción</p>', unsafe_allow_html=True)

if df.empty:
    st.warning("⚠️ No se encontraron registros de producción para la fecha seleccionada.")
else:
    # Productos elaborados para el selector
    productos_elab = sorted(df['Nombre'].dropna().unique().tolist())
    selected_prod = st.sidebar.multiselect("Seleccione un producto:", productos_elab)

    # Filtrar df según selección de producto
    df_filtrado = df[df['Nombre'].isin(selected_prod)] if selected_prod else df

    # Agrupar producción por nombre de producto
    df_agrupado = df_filtrado.groupby('Nombre', as_index=False)['Dosificado'].sum()
    df_agrupado['Dosificado_Tn'] = df_agrupado['Dosificado'] / 1000

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agrupado['Nombre'], 
        y=df_agrupado['Dosificado_Tn'], 
        name="Producción (Tn)",
        text=df_agrupado['Dosificado_Tn'].round(2),
        textposition='auto'
    ))

    fig.update_layout(
        title="Productos Elaborados (Toneladas)",
        xaxis_title="Producto",
        yaxis_title="Dosificado (Tn)",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)

    # Formatear la tabla de datos crudos
    df_display = df_filtrado.copy()
    df_display['Hora'] = df_display['Hora'].apply(format_timedelta_hh_mm_ss)
    df_display['Tiempo'] = df_display['Tiempo'].apply(format_timedelta_hh_mm_ss)
    df_display['Rendimiento (Tn/h)'] = df_display['Rendimiento'].round(2)

    st.subheader("Detalle de Tareas Ejecutadas")
    st.dataframe(df_display, use_container_width=True)

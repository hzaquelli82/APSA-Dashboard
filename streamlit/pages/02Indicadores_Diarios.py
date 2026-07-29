import streamlit as st
import mysql.connector
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_echarts import st_echarts
from streamlit_autorefresh import st_autorefresh


st.set_page_config(
    page_title="Control de Producción",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.logo('images/Logo_Inst.png', size='large')

# Inyectar script Javascript/HTML para forzar autorefresh cada 300 segundos (5 minutos)
st.markdown(
    """
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 300000);
    </script>
    """,
    unsafe_allow_html=True
)

count = st_autorefresh(interval=60000, limit=None, key="counter_autorefresh")

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

    # Asegurar tipos datetime/timedelta
    df['Hora'] = pd.to_timedelta(df['Hora'].astype(str))
    df['Tiempo'] = pd.to_timedelta(df['Tiempo'].astype(str))

    # Corregir tiempo 0
    mask = df['Tiempo'] == pd.Timedelta(0)
    df.loc[mask, 'Tiempo'] = df['Hora'].shift(-1) - df.loc[mask, 'Hora']

    if pd.isna(df.loc[df.index[-1], 'Tiempo']):
        df.loc[df.index[-1], 'Tiempo'] = hora_referencia - df.loc[df.index[-1], 'Hora']

    # Rendimiento en Toneladas por Hora
    segundos_tiempo = df['Tiempo'].dt.total_seconds().replace(0, pd.NA)
    df['Rendimiento'] = (df['Dosificado'] / (segundos_tiempo / 3600)) / 1000

    return df

def custom_metric(label, value, color="#f0f2f6"):
    st.markdown(f"""
        <div style="border: 2px solid #ddd; border-radius: 15px; padding: 20px; background-color: {color}; text-align: center; margin: 10px 0;">
            <div style="font-size: 20px; font-weight: 600; color: #555;">{label}</div>
            <div style="font-size: 40px; font-weight: bold; margin: 10px 0;">{value}</div>
        </div>
    """, unsafe_allow_html=True)

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
    .big-font { font-size: 40px !important; color: blue; }
    .medium-font { font-size: 25px !important; text-align: center; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<p class="big-font">Indicadores Diarios</p>', unsafe_allow_html=True)

if df.empty:
    st.warning("⚠️ No se encontraron registros de producción para la fecha seleccionada.")
else:
    tn_total = df['Dosificado'].sum() / 1000
    primera_fecha = df.loc[df.index[0], 'Fecha'].strftime("%Y-%m-%d")
    
    if primera_fecha != fecha_actual.strftime("%Y-%m-%d"):
        primera_hora = (df.loc[df.index[0], 'Hora'].total_seconds() / 3600) - 24.00
    else:
        primera_hora = df.loc[df.index[0], 'Hora'].total_seconds() / 3600

    hs_total = (hora_actual.total_seconds() / 3600) - primera_hora
    rendimiento_gral = (tn_total / hs_total) if hs_total > 0 else 0

    col0, col1, col2 = st.columns([2, 3, 2], gap='large', vertical_alignment='top')

    with col0:
        custom_metric("Producción Total (tn)", round(tn_total, 2))

    with col1:
        st.markdown('<div class="medium-font">Rendimiento General (tn/h)</div>', unsafe_allow_html=True)
        options = {
            "series": [
                {
                    "type": "gauge",
                    "startAngle": 180,
                    "endAngle": 0,
                    "radius": "100%",
                    "center": ["50%", "75%"],
                    "min": 0,
                    "max": 8,
                    "splitNumber": 4,
                    "itemStyle": {
                        "color": "#60FD68" if rendimiento_gral >= 6 else "#FF9800" if rendimiento_gral >= 4 else "#F44336"
                    },
                    "progress": {"show": True, "width": 30},
                    "pointer": {"show": False},
                    "axisLine": {"lineStyle": {"width": 30}},
                    "axisTick": {
                        "distance": -45,
                        "splitNumber": 5,
                        "lineStyle": {"width": 2, "color": "#999"}
                    },
                    "splitLine": {
                        "distance": -52,
                        "length": 14,
                        "lineStyle": {"width": 3, "color": "#999"}
                    },
                    "axisLabel": {"distance": -20, "color": "#999", "fontSize": 12},
                    "anchor": {"show": False},
                    "title": {"show": False},
                    "detail": {
                        "valueAnimation": True,
                        "fontSize": 30,
                        "offsetCenter": [0, "-10%"],
                        "formatter": "{value}tn/h",
                        "color": "inherit"
                    },
                    "data": [{"value": round(rendimiento_gral, 2)}]
                }
            ]
        }
        st_echarts(options=options, height="300px")
        
    with col2:
        custom_metric("Horas de Producción (Hs)", round(hs_total, 2))

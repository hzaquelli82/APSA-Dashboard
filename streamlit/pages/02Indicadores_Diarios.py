import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_echarts import st_echarts

st.set_page_config(
    page_title="Control de Producción",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.logo('images/Logo_Inst.png', size='large')

def conectar_mysql():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def obtener_df(fecha_actual_param):
    fecha_ayer_param = (fecha_actual_param - timedelta(days=1)).strftime("%Y-%m-%d")

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
                ''', (fecha_ayer_param, fecha_ayer_param, fecha_actual_param.strftime("%Y-%m-%d")))
    resultados = cur.fetchall()
    columnas = [desc[0] for desc in cur.description]
    df = pd.DataFrame(resultados, columns=columnas)

    # Correct time 0
    mask = df['Tiempo'] == pd.Timedelta(0)
    df.loc[mask, 'Tiempo'] = df['Hora'].shift(-1) - df.loc[mask, 'Hora']
    valor = df.loc[df.index[-1], 'Tiempo']
    if pd.isna(valor):
        df.loc[df.index[-1], 'Tiempo'] = hora_actual - df.loc[df.index[-1], 'Hora']

    df['Rendimiento'] = (df['Dosificado'] / (df['Tiempo'].astype('int64')/3.6e12))/1000
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
fecha_ayer = fecha_actual - timedelta(days=1)
hora_actual = pd.to_timedelta(datetime.now().strftime('%H:%M:%S'))


db = conectar_mysql()
cur = db.cursor()

if st.sidebar.button("Actualizar"):
    df = obtener_df(fecha_actual)

else:
    df = obtener_df(fecha_actual)


tn_total = df['Dosificado'].sum()/1000
primera_fecha = (df.loc[df.index[0], 'Fecha'].strftime("%Y-%m-%d"))
if primera_fecha != fecha_actual.strftime("%Y-%m-%d"):
    primera_hora = (df.loc[df.index[0], 'Hora'].seconds / 3600) - 24.00
else:
    primera_hora = df.loc[df.index[0], 'Hora'].seconds / 3600

ultima_hora = df.loc[df.index[-1], 'Tiempo']

if pd.isna(ultima_hora):
    hs_total = (hora_actual.total_seconds() / 3600) - primera_hora
else:
    hs_total = df['Tiempo'].astype('int64').sum() / 3.6e12


rendimiento_gral = (tn_total / hs_total)


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

st.markdown('<p class="big-font">Indicadores Diarios</p>', unsafe_allow_html=True)


col0, col1, col2 = st.columns([2, 3, 2], gap='large',vertical_alignment='top')

with col0:
    custom_metric("Producción Total (tn)", tn_total.round(2))
    # st.metric(label="Producción Total (tn)", value=tn_total.round(2),)

with col1:
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
                "progress": {
                    "show": True,
                    "width": 30
                },
                "pointer": {
                    "show": False
                },
                "axisLine": {
                    "lineStyle": {
                        "width": 30
                    }
                },
                "axisTick": {
                    "distance": -45,
                    "splitNumber": 5,
                    "lineStyle": {
                        "width": 2,
                        "color": "#999"
                    }
                },
                "splitLine": {
                    "distance": -52,
                    "length": 14,
                    "lineStyle": {
                        "width": 3,
                        "color": "#999"
                    }
                },
                "axisLabel": {
                    "distance": -20,
                    "color": "#999",
                    "fontSize": 12
                },
                "anchor": {
                    "show": False
                },
                "title": {
                    "show": False
                },
                "detail": {
                    "valueAnimation": True,
                    "fontSize": 30,
                    "offsetCenter": [0, "-10%"],
                    "formatter": "{value}tn/h",
                    "color": "inherit"
                },
                "data": [
                    {
                        "value": rendimiento_gral.round(2),
                    }
                ]
            }
        ]
    }

    st_echarts(options=options, height="300px")
    
with col2:
    custom_metric("Horas de Producción (Hs)", hs_total.round(2))
    
    st.write(primera_hora)
    st.write(hora_actual)
    # st.write(ultima_hora - primera_hora)
    # st.metric(label="Horas de Producción (Hs)", value=hs_total.round(2))
    
st.write(type(primera_hora))
st.write(type(fecha_actual))

cur.close()
db.close()

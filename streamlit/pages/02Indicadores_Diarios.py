import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Control de Producción",
    page_icon="🌟",
    layout="wide",  # O "centered" para un diseño más compacto
    initial_sidebar_state="expanded"  # O "collapsed"
)
st.logo('images/Logo_Inst.png', size='large')

def conectar_mysql():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def obtener_df():
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
                    Fecha = %s
                GROUP BY
                    tareaseje.NroID
                ''', (fecha_actual,))
    resultados = cur.fetchall()
    # Obtener los nombres de las columnas
    columnas = [desc[0] for desc in cur.description]

    # Crear un DataFrame de pandas
    df = pd.DataFrame(resultados, columns=columnas)

    # Cerrar el cursor y la conexión
    cur.close()
    db.close()

    #Corregir los tiempos 0
    # Identificar filas con tiempo 0
    mask = df['Tiempo'] == pd.Timedelta(0)

    # Calcular la diferencia de hora con la siguiente fila
    df.loc[mask, 'Tiempo'] = df['Hora'].shift(-1) - df.loc[mask, 'Hora']

    # Para la última fila, calcular diferencia con la hora actual
    valor = df.loc[df.index[-1], 'Tiempo']
    # print(valor)
    if pd.isna(valor):
        df.loc[df.index[-1], 'Tiempo'] = hora_actual - df.loc[df.index[-1], 'Hora']

    df['Rendimiento'] = (df['Dosificado'] / (df['Tiempo'].astype('int64')/3.6e12))/1000

    return df

if st.sidebar.button("Actualizar"):
    db = conectar_mysql()
    cur = db.cursor()

    #Obtener  hora
    fecha_actual = datetime.now()
    fecha_actual = fecha_actual.strftime("%Y-%m-%d")
    hora_actual = pd.to_timedelta(datetime.now().strftime('%H:%M:%S'))


    df = obtener_df()
    

#Conectar base de datos
db = conectar_mysql()
cur = db.cursor()

#Obtener fecha y hora
fecha_actual = datetime.now()
fecha_actual = fecha_actual.strftime("%Y-%m-%d")
hora_actual = pd.to_timedelta(datetime.now().strftime('%H:%M:%S'))


df = obtener_df()

#Toneladas elaboradas
tn_total = df['Dosificado'].sum()/1000

# Horas totales
hs_total = df['Tiempo'].astype('int64').sum() / 3.6e12

#Rendimiento promedio
rendimiento_gral = (tn_total / hs_total)


#Formateo y gráficos


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


# Crear columnas con diferentes proporciones
col0, col1, col2 = st.columns([2, 3, 2], gap='large',vertical_alignment='top')

# Mostrar métricas dentro de cada columna
with col0:
    # st.metric(label='Producción Total (tn)', value=tn_total, border=True)
    fig = go.Figure(go.Indicator(
        mode="number",
        value=tn_total,
        title={
            'text': "Producción Total (tn)",
            'font': {'size': 14},  # Ajusta el tamaño de la fuente
            'align': "center"  # Alineación del texto
        },
        ))

    st.plotly_chart(fig)
with col1:
    # Definir color según el valor
    if rendimiento_gral < 4:
        color = "red"
    elif 4 <= rendimiento_gral < 6:
        color = "orange"
    else:
        color = "green"

    # Crear el gauge con cambio de color
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rendimiento_gral,
        title={
            'text': "Rendimiento Gral (tn/h)",
            'font': {'size': 16},  # Ajusta el tamaño de la fuente
            'align': "center"  # Alineación del texto
        },
        gauge={
            'axis': {'range': [0, 8]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 4], 'color': "lightcoral"},
                {'range': [4, 6], 'color': "gold"},
                {'range': [6, 8], 'color': "lightgreen"}
            ]
        }
    ))

    st.plotly_chart(fig, use_container_width=True)

with col2:
    # st.metric(label='Horas de Producción (hs)', value=hs_total, border=True)
    fig = go.Figure(go.Indicator(
        mode="number",
        value=hs_total,
        title={
            'text': "Horas de Producción (Hs)",
            'font': {'size': 14},  # Ajusta el tamaño de la fuente
            'align': "center"  # Alineación del texto
        },
        ))
    st.plotly_chart(fig)


import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
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
                    (tareaseje.Fecha = %s AND tareaseje.Hora >= '23:00:00') OR 
                    (tareaseje.Fecha > %s AND tareaseje.Fecha <= %s AND tareaseje.Hora < '23:00:00')
                GROUP BY
                    tareaseje.NroID
                ''',(fecha_ayer_param, fecha_ayer_param, fecha_actual_param.strftime("%Y-%m-%d")),)
    resultados = cur.fetchall()
    # Obtener los nombres de las columnas
    columnas = [desc[0] for desc in cur.description]

    # Crear un DataFrame de pandas
    df = pd.DataFrame(resultados, columns=columnas)

    #Cerrar el cursor y la conexión
    
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

# Sidebar Date Picker
default_date = datetime.now()
selected_date = st.sidebar.date_input("Seleccione una fecha:", default_date)

# Convert the selected date to a datetime object (at midnight)
fecha_actual = datetime.combine(selected_date, datetime.min.time())

# Conectar base de datos
db = conectar_mysql()
cur = db.cursor()

#Obtener  hora
hora_actual = pd.to_timedelta(datetime.now().strftime('%H:%M:%S'))

if st.sidebar.button("Actualizar"):
    df = obtener_df(fecha_actual)

else:
    df = obtener_df(fecha_actual)
    

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


fig = make_subplots(rows=2, cols=1, 
                    subplot_titles=("Productos Elaborados", "Rendimientos"),
                    vertical_spacing=0.5)

#Productos elaborados
fig.add_trace(go.Bar(x=df['Nombre'], y=df['Dosificado'], name="Barras"),
              row=1, col=1)
hora = df['Hora'].astype('int64')/3.6e12
fig.add_trace(go.Scatter(x=hora, y=df['Rendimiento'], mode='lines+markers', name="Líneas"),
              row=2, col=1)
# Ajustar el dominio de los ejes y la altura de cada gráfico
fig.update_layout(
    height=600,  # Altura total de la figura
    yaxis=dict(domain=[0.4, 1]),  # Dominio del primer gráfico (70%)
    yaxis2=dict(domain=[0, 0.3])   # Dominio del segundo gráfico (30%)
)

st.plotly_chart(fig)

cur.close()
db.close()

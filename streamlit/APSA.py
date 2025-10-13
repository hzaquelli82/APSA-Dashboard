import streamlit as st



st.set_page_config(
    page_title="Control de Producción",
    page_icon="🌟",
    layout="wide",  # O "centered" para un diseño más compacto
    initial_sidebar_state="expanded"  # O "collapsed"
)


st.markdown(
    """
    <style>
    .big-font {
        font-size: 60px !important;
        color: gray;
        text-align: center;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<p class="big-font">GESTIÓN DE PRODUCCIÓN</p>', unsafe_allow_html=True)

# Barra lateral para la navegación
st.sidebar.title("Navegación")

st.image('images/logo.png')


import streamlit as st
from painel import render_painel
from rt import render_roteirizar
from agregado import render_agregado

# Configuração da página
st.set_page_config(
    page_title="Menu Principal",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar como menu de navegação
st.sidebar.markdown("### 📋 Menu")
page = st.sidebar.radio("Navegação", ["Painel de Coletas", "Roteirizador", "Relatório de Agregados"])

# Exibir a página selecionada
if page == "Painel de Coletas":
    render_painel()
elif page == "Roteirizador":
    render_roteirizar()
elif page == "Relatório de Agregados":
    render_agregado()

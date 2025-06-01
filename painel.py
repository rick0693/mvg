import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# Configurar o cliente Supabase
@st.cache_resource
def init_supabase():
    url = "https://glyhzstmzwniflatcjra.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdseWh6c3RtenduaWZsYXRjanJhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDYxMjU5NTMsImV4cCI6MjA2MTcwMTk1M30.Ggj_d_ysVv6WmBWKItz-vBFbZpoWfFWRm020v3Rk9HU"
    return create_client(url, key)

supabase = init_supabase()

# Dicionário de motoristas e placas
motorista_placa_dict = {
    "AELSON LUIS CARDOSO": "KKK0282",
    "ANDERSON RESSTEL": "MQM0736",
    "ANSELMO SILVA DE JESUS": "SFX2B90",
    "ANTONIO MARCOS BRITO": "HJF7346",
    "CLAUDIO CESCONETO": "MQY3A78",
    "EDIMAR ANACLETO DE SOUZA": "MQL8B02",
    "EDMILSON MORAES LEMOS": "OXJ0900",
    "ELIO JOSE DE MATOS": "KQT0A86",
    "FAGNER ALOISIO DA SILVA": "HBN8827",
    "HELIO BELCAVELLO": "MPP6D08",
    "IVAN CARDOZO PEREIRA": "MRX5H14",
    "JEAN CARLOS DE SOUZA": "JNZ5D41",
    "JOSE MARIA ALMEIDA": "GYB7065",
    "JOSUE CHAGAS COIMBRA": "GYB7065",
    "JUSTINO DOS SANTOS": "PVB4550",
    "MARCELO ROSSI": "DJC2A49",
    "MARCIO ALEXANDRO": "MRA3G30",
    "RAFAEL PATROCINO SENNA": "PPQ8G36"
}

# Funções do banco de dados
@st.cache_data(ttl=30)
def carregar_coletas():
    response = supabase.table('Coletas').select('*').execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y')
        df = df.rename(columns={'created_at': 'Data de solicitação'})
        df['Motorista'] = df.apply(
            lambda row: f"{row['Motorista']} ({row['Placa']})" if row['Motorista'] and row['Placa'] else "",
            axis=1
        )
        df = df.drop(columns=['id', 'Placa'])
    return df

@st.cache_data(ttl=60)
def carregar_clientes():
    response = supabase.table('Pontos de coleta').select('*').execute()
    return pd.DataFrame(response.data)

def salvar_coleta(data):
    response = supabase.table('Coletas').insert(data).execute()
    return response

def atualizar_coleta(id, data):
    response = supabase.table('Coletas').update(data).eq('id', id).execute()
    return response

def is_dia_util():
    hoje = datetime.now().weekday()
    return hoje < 5

def coleta_ja_cadastrada(cnpj, data_atual):
    response = supabase.table('Coletas').select('*').eq('CNPJ', cnpj).execute()
    coletas = pd.DataFrame(response.data)
    if not coletas.empty:
        coletas['created_at'] = pd.to_datetime(coletas['created_at']).dt.strftime('%d/%m/%Y')
        return not coletas[coletas['created_at'] == data_atual].empty
    return False

def cadastrar_coletas_automaticas():
    if is_dia_util():
        clientes_df = carregar_clientes()
        clientes_automaticos = clientes_df[clientes_df["Regularidade"] == "Automatica"]
        data_atual = datetime.now().strftime('%d/%m/%Y')

        for _, cliente in clientes_automaticos.iterrows():
            cnpj = cliente["CNPJ"]
            if not coleta_ja_cadastrada(cnpj, data_atual):
                data = {
                    "Nome do cliente": cliente["Nome do cliente"],
                    "CNPJ": cnpj,
                    "Motorista": "",
                    "Cidade": cliente["Remetente_Cidade"],
                    "Contato": "",
                    "Bairro": cliente["Remetente_Bairro"],
                    "Peso": "",
                    "Status": "Pendente",
                    "Observação": "Cadastro automático"
                }
                response = salvar_coleta(data)

def render_painel():

    # CSS personalizado - Tema Dark
    st.markdown("""
    <style>
        /* Dark theme base */
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }

        .main {
            padding-top: 1rem;
            background-color: #0e1117;
        }

        /* Sidebar dark */
        .css-1d391kg {
            background-color: #1e2530;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
            background-color: #1e2530;
            padding: 1rem;
            border-radius: 10px;
        }

        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 0 2rem;
            border-radius: 10px;
            background-color: #262730;
            border: 2px solid #333;
            color: #fafafa;
        }

        .stTabs [aria-selected="true"] {
            background-color: #00d4aa;
            color: #000;
            border-color: #00d4aa;
        }

        /* Form container */
        .form-container {
            background-color: #1e2530;
            padding: 2rem;
            border-radius: 15px;
            margin: 1rem 0;
            border: 1px solid #333;
        }

        /* Header styling */
        .header-title {
            text-align: center;
            color: #00d4aa;
            margin-bottom: 2rem;
            padding: 1rem;
            font-size: 2.5rem;
            font-weight: bold;
            text-shadow: 0 0 20px rgba(0, 212, 170, 0.5);
        }

        /* Metrics styling */
        .metric-card {
            background: linear-gradient(135deg, #1e2530 0%, #262730 100%);
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid #333;
            color: #fafafa;
            text-align: center;
            margin: 0.5rem 0;
        }

        /* Success/Error messages */
        .success-message {
            background-color: #1e4d3a;
            color: #4ade80;
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid #16a34a;
            margin: 1rem 0;
        }

        .error-message {
            background-color: #4d1e1e;
            color: #f87171;
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid #dc2626;
            margin: 1rem 0;
        }

        /* Input fields dark theme */
        .stSelectbox > div > div {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #333;
        }

        .stTextInput > div > div > input {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #333;
        }

        .stTextArea > div > div > textarea {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #333;
        }

        /* Buttons */
        .stButton > button {
            background-color: #00d4aa;
            color: #000;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .stButton > button:hover {
            background-color: #00b894;
            box-shadow: 0 5px 15px rgba(0, 212, 170, 0.3);
        }

        /* DataEditor styling for status colors */
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(9) {
            font-weight: bold;
        }

        /* Status colors in DataFrame */
        div[data-testid="stDataFrame"] table tbody tr:has(td:nth-child(9):contains("Coletado")) td:nth-child(9) {
            color: #4ade80 !important;
            background-color: rgba(74, 222, 128, 0.1) !important;
        }

        div[data-testid="stDataFrame"] table tbody tr:has(td:nth-child(9):contains("Pendente")) td:nth-child(9) {
            color: #f87171 !important;
            background-color: rgba(248, 113, 113, 0.1) !important;
        }

        div[data-testid="stDataFrame"] table tbody tr:has(td:nth-child(9):contains("Cancelado")) td:nth-child(9) {
            color: #fbbf24 !important;
            background-color: rgba(251, 191, 36, 0.1) !important;
        }

        /* DataEditor dark theme */
        div[data-testid="stDataFrame"] {
            background-color: #1e2530;
            border-radius: 10px;
            border: 1px solid #333;
        }

        div[data-testid="stDataFrame"] table {
            background-color: #1e2530;
            color: #fafafa;
        }

        div[data-testid="stDataFrame"] table thead th {
            background-color: #262730;
            color: #00d4aa;
            border-bottom: 2px solid #333;
        }

        div[data-testid="stDataFrame"] table tbody tr {
            background-color: #1e2530;
            border-bottom: 1px solid #333;
        }

        div[data-testid="stDataFrame"] table tbody tr:hover {
            background-color: #262730;
        }

        /* Multiselect dark theme */
        .stMultiSelect > div > div {
            background-color: #262730;
            border: 1px solid #333;
        }

        /* Date input dark theme */
        .stDateInput > div > div > input {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #333;
        }

        /* Metrics styling */
        div[data-testid="metric-container"] {
            background-color: #1e2530;
            border: 1px solid #333;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }

        div[data-testid="metric-container"] > div {
            color: #fafafa;
        }

        div[data-testid="metric-container"] label {
            color: #00d4aa !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Inicializar session state
    if 'refresh_data' not in st.session_state:
        st.session_state.refresh_data = False
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    if 'success_message' not in st.session_state:
        st.session_state.success_message = ""
    if 'error_message' not in st.session_state:
        st.session_state.error_message = ""

    # Header principal
    st.markdown('<h1 class="header-title">🚛 Painel de Coletas</h1>', unsafe_allow_html=True)

    # Métricas na página principal
    st.markdown("### 📊 Estatísticas")
    df_stats = carregar_coletas()
    if not df_stats.empty:
        total_coletas = len(df_stats)
        coletados = len(df_stats[df_stats['Status'] == 'Coletado'])
        pendentes = len(df_stats[df_stats['Status'] == 'Pendente'])
        cancelados = len(df_stats[df_stats['Status'] == 'Cancelado'])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total", total_coletas, delta=None)
        with col2:
            st.metric("✅ Coletados", coletados, delta=f"{(coletados/total_coletas*100):.1f}%")
        with col3:
            st.metric("⏳ Pendentes", pendentes, delta=f"{(pendentes/total_coletas*100):.1f}%")
        with col4:
            st.metric("❌ Cancelados", cancelados, delta=f"{(cancelados/total_coletas*100):.1f}%")

    # Tabs principais
    tab1, tab2 = st.tabs(["📝 Cadastro", "📋 Visualização"])

    with tab1:
        st.markdown("### Cadastro de Coletas")

        clientes_df = carregar_clientes()

        if not clientes_df.empty:
            with st.container():

                clientes_options = clientes_df.apply(
                    lambda row: f"{row['Nome do cliente']} - CNPJ: {row['CNPJ']} - Cidade: {row['Remetente_Cidade']}",
                    axis=1
                ).tolist()

                cliente_selecionado = st.selectbox(
                    "🏢 Selecione o Cliente",
                    clientes_options,
                    key="cliente_select"
                )

                cliente_info = clientes_df.iloc[clientes_options.index(cliente_selecionado)]

                with st.form("cadastro_form", clear_on_submit=True):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        nome_cliente = st.text_input("👤 Nome do Cliente", value=cliente_info["Nome do cliente"])
                    with col2:
                        cnpj = st.text_input("🏪 CNPJ", value=cliente_info["CNPJ"])
                    with col3:
                        motorista_options = [f"{motorista} ({placa})" for motorista, placa in motorista_placa_dict.items()]
                        motorista_selecionado = st.selectbox("🚛 Motorista", motorista_options)
                        motorista = motorista_selecionado.split(" (")[0]
                        placa = motorista_placa_dict[motorista]
                    with col4:
                        cidade = st.text_input("🏙️ Cidade", value=cliente_info["Remetente_Cidade"])

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        contato = st.text_input("📞 Contato", value="")
                    with col2:
                        bairro = st.text_input("📍 Bairro", value=cliente_info["Remetente_Bairro"])
                    with col3:
                        peso = st.text_input("⚖️ Peso", value="")
                    with col4:
                        status = st.selectbox("📊 Status", ["Coletado", "Pendente", "Cancelado"])

                    observacao = st.text_area("📝 Observação", value="")

                    submit_button = st.form_submit_button("💾 Salvar", use_container_width=True)

                    if submit_button:
                        data = {
                            "Nome do cliente": nome_cliente,
                            "CNPJ": cnpj,
                            "Motorista": motorista,
                            "Placa": placa,
                            "Cidade": cidade,
                            "Contato": contato,
                            "Bairro": bairro,
                            "Peso": peso,
                            "Status": status,
                            "Observação": observacao
                        }
                        response = salvar_coleta(data)
                        if hasattr(response, 'data'):
                            st.success("✅ Dados salvos com sucesso!")
                            st.cache_data.clear()
                        else:
                            st.error("❌ Erro ao salvar os dados.")

                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ Nenhum cliente cadastrado.")


    with tab2:
        st.markdown("### Visualização de Coletas")

        # Filtros
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            filtro_status = st.multiselect(
                "Filtrar por Status",
                ["Coletado", "Pendente", "Cancelado"],
                default=["Coletado", "Pendente", "Cancelado"]
            )
        with col2:
            filtro_data = st.date_input("Filtrar por Data", value=None)
        with col3:
            if st.button("🔄 Atualizar"):
                st.cache_data.clear()  # Limpa o cache para forçar a recarga dos dados
                df = carregar_coletas()  # Recarrega os dados

        df = carregar_coletas()  # Carrega os dados novamente para garantir que estão atualizados

        if not df.empty:
            # Aplicar filtros
            if filtro_status:
                df = df[df['Status'].isin(filtro_status)]

            if filtro_data:
                data_filtro = filtro_data.strftime('%d/%m/%Y')
                df = df[df['Data de solicitação'] == data_filtro]

            motoristas_options = [f"{motorista} ({placa})" for motorista, placa in motorista_placa_dict.items()]
            motoristas_options.append("")
            status_options = ["Coletado", "Pendente", "Cancelado"]

            # Função para aplicar cores ao status
            def format_status(val):
                if val == "Coletado":
                    return f'<span style="color: #4ade80; font-weight: bold; background-color: rgba(74, 222, 128, 0.1); padding: 4px 8px; border-radius: 4px;">{val}</span>'
                elif val == "Pendente":
                    return f'<span style="color: #f87171; font-weight: bold; background-color: rgba(248, 113, 113, 0.1); padding: 4px 8px; border-radius: 4px;">{val}</span>'
                elif val == "Cancelado":
                    return f'<span style="color: #fbbf24; font-weight: bold; background-color: rgba(251, 191, 36, 0.1); padding: 4px 8px; border-radius: 4px;">{val}</span>'
                return val

            edited_df = st.data_editor(
                df,
                column_config={
                    "Data de solicitação": st.column_config.TextColumn("📅 Data", disabled=True, width="small"),
                    "Nome do cliente": st.column_config.TextColumn("👤 Cliente", disabled=True, width="medium"),
                    "CNPJ": st.column_config.TextColumn("🏪 CNPJ", disabled=True, width="small"),
                    "Cidade": st.column_config.TextColumn("🏙️ Cidade", disabled=True, width="small"),
                    "Bairro": st.column_config.TextColumn("📍 Bairro", disabled=True, width="small"),
                    "Motorista": st.column_config.SelectboxColumn("🚛 Motorista", options=motoristas_options, width="medium"),
                    "Contato": st.column_config.TextColumn("📞 Contato", width="small"),
                    "Peso": st.column_config.TextColumn("⚖️ Peso", width="small"),
                    "Status": st.column_config.SelectboxColumn("📊 Status", options=status_options, width="small"),
                    "Observação": st.column_config.TextColumn("📝 Observação", width="large"),
                },
                disabled=["Data de solicitação", "Nome do cliente", "CNPJ", "Cidade", "Bairro"],
                use_container_width=True,
                hide_index=True,
                key="data_editor"
            )

            if st.button("💾 Salvar Alterações", use_container_width=True):
                response = supabase.table('Coletas').select('*').execute()
                original_df = pd.DataFrame(response.data)
                original_df['created_at'] = pd.to_datetime(original_df['created_at']).dt.strftime('%d/%m/%Y')
                original_df = original_df.rename(columns={'created_at': 'Data de solicitação'})
                original_df['Motorista'] = original_df.apply(
                    lambda row: f"{row['Motorista']} ({row['Placa']})" if row['Motorista'] and row['Placa'] else "",
                    axis=1
                )
                original_df = original_df.drop(columns=['id', 'Placa'])

                original_df = original_df.fillna("")
                edited_df = edited_df.fillna("")

                editable_columns = ["Motorista", "Contato", "Peso", "Status", "Observação"]
                changed_rows = edited_df[edited_df[editable_columns].ne(original_df[editable_columns]).any(axis=1)]

                if not changed_rows.empty:
                    response_df = pd.DataFrame(response.data)
                    alteracoes_salvas = 0

                    for i, row in changed_rows.iterrows():
                        matching_row = response_df[
                            (response_df['CNPJ'] == row['CNPJ']) &
                            (pd.to_datetime(response_df['created_at']).dt.strftime('%d/%m/%Y') == row['Data de solicitação'])
                        ]
                        if not matching_row.empty:
                            id_coleta = matching_row.iloc[0]['id']
                            motorista_selecionado = row['Motorista'] if pd.notna(row['Motorista']) else ""
                            motorista = motorista_selecionado.split(" (")[0] if motorista_selecionado else ""
                            placa = motorista_placa_dict.get(motorista, "")

                            data = {
                                "Nome do cliente": row["Nome do cliente"],
                                "CNPJ": row["CNPJ"],
                                "Motorista": motorista,
                                "Placa": placa,
                                "Cidade": row["Cidade"],
                                "Contato": row["Contato"],
                                "Bairro": row["Bairro"],
                                "Peso": row["Peso"],
                                "Status": row["Status"],
                                "Observação": row["Observação"]
                            }
                            response = atualizar_coleta(id_coleta, data)
                            if hasattr(response, 'data'):
                                alteracoes_salvas += 1

                    if alteracoes_salvas > 0:
                        st.success(f"✅ {alteracoes_salvas} alteração(ões) salva(s) com sucesso!")
                        st.cache_data.clear()
                    else:
                        st.error("❌ Erro ao salvar algumas alterações.")
                else:
                    st.info("ℹ️ Nenhuma alteração detectada.")
        else:
            st.warning("⚠️ Nenhuma coleta cadastrada.")



    # Executar cadastro automático
    cadastrar_coletas_automaticas()

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; padding: 1rem;'>"
        "Sistema de Gerenciamento de Coletas | Desenvolvido com ❤️ usando Streamlit"
        "</div>",
        unsafe_allow_html=True
    )

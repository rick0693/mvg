import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import requests
import json
import unicodedata
import hashlib
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Configuração da API do Google Maps
API_KEY = "AIzaSyBBLM5OcS_gLh7okPCtBoDi9VDYygVSLqE"
ORIGEM_FIXA = "R. Nove, 384 - Arlindo Angelo Villaschi, Viana - ES, 29136-176"
MAX_WAYPOINTS = 23  # Máximo de endereços intermediários (25 - origem - destino)

# Função principal para renderizar a aba de roteirização
def render_roteirizar():
    # Configuração da página
    st.title("Roteirizador - Visualização e Edição de Rotas")

    # Aplicar tema escuro
    st.markdown("""
    <style>
    .main {
        background-color: #1E1E1E;
        color: white;
    }
    .st-bw {
        background-color: #333333;
    }
    .st-df {
        background-color: #333333;
    }
    .st-dg {
        background-color: #333333;
    }
    .stTextInput, .stSelectbox, .stMultiSelect, .stDateInput {
        background-color: #333333;
        color: white;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
    }
    .stDataFrame {
        background-color: #333333;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

    # Inicializar o session_state com valores padrão
    if 'df_filtered' not in st.session_state:
        st.session_state.df_filtered = None
    if 'selected_routes' not in st.session_state:
        st.session_state.selected_routes = []
    if 'summary_df' not in st.session_state:
        st.session_state.summary_df = None
    if 'filter_applied' not in st.session_state:
        st.session_state.filter_applied = False
    if 'selected_uf' not in st.session_state:
        st.session_state.selected_uf = []
    if 'selected_cidade' not in st.session_state:
        st.session_state.selected_cidade = []
    if 'selected_situacao' not in st.session_state:
        st.session_state.selected_situacao = []
    if 'selected_rota' not in st.session_state:
        st.session_state.selected_rota = []
    if 'data_emissao_min' not in st.session_state:
        st.session_state.data_emissao_min = datetime.now() - timedelta(days=7)
    if 'data_emissao_max' not in st.session_state:
        st.session_state.data_emissao_max = datetime.now()
    if 'df_concat_ordered' not in st.session_state:
        st.session_state.df_concat_ordered = None

    # Função para normalizar nomes de rotas
    def normalize_route_name(name):
        """Remove espaços extras, substitui hífens por espaços e normaliza o nome da rota."""
        if pd.isna(name):
            return name
        return ' '.join(name.replace('-', ' ').strip().split())

    # Função para normalizar CEP
    def normalize_cep(cep):
        """Remove hífen e garante que o CEP tenha 8 dígitos."""
        if pd.isna(cep):
            return None
        cep = str(cep).replace('-', '').strip()
        return cep.zfill(8)

    # Função para normalizar texto: maiúsculas e sem acentos
    def normalize_text(text):
        if not isinstance(text, str):
            return text
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        text = text.upper().strip()
        corrections = {
            "COLINA DE LARANJEIRA": "COLINA LARANJEIRAS",
            "COLINA LARANJEIRAS": "COLINA LARANJEIRAS",
            "CACHOEIRO ITAPEMIRIM": "CACHOEIRO DE ITAPEMIRIM",
            "ITAPOA": "ITAPUÃ",
            "ITAPARICA": "PRAIA DE ITAPARICA",
            "VILA BETHANIA": "VILA BETÂNIA",
            "ARACRUZ (GUARANA)": "ARACRUZ",
            "NOVA BETANIA": "NOVA BETHANIA",
            "VIEIRA MACHADO": "VIEIRA MACHADO",
            "MORADA LARANJEI": "MORADA DE LARANJEIRAS",
            "ENSEADA JACARAIPE": "ENSEADA DE JACARAIPE",
            "PLANICIE DA SERRA": "PLANICIE DA SERRA",
            "NOVA CARAPINA 2": "NOVA CARAPINA II",
            "SERRA DOURADA": "SERRA DOURADA",
            "PQ RES.MESTRE A": "PARQUE RESIDENCIAL MESTRE ALVARO",
            "SERRA DOURAD II": 'SERRA DOURADA II',
            "ENSEAD DO SUA": "ENSEADA DO SUA",
            "SANTA MARGARIDA (BARREIRO)": "SANTA MARGARIDA",
            "JARD MARILANDIA": "JARDIM MARILANDIA",
            "ROSARIO FATIMA": "ROSARIO DE FATIMA",
            "JD. LIMOEIRA": "JARDIM LIMOEIRO",
            "VILA FERREIRA": "VALE ENCANTADO",
            "MORADA DE LARAN": "MORADA DE LARANJEIRAS",
            "ROSARIO DE FATIMA": "ROSARIO DE FATIMA",
            "N S FATIMA": "DE FATIMA",
            "RIVIERA BARRA": "RIVIERA DA BARRA",
            "EST MONAZITICA": "ESTANCIA MONAZITICA",
            "CACHOEIRO ITAPEMIRIM": "CACHOEIRO DE ITAPEMIRIM",
            "CAMARA": "CAMARA"
        }
        return corrections.get(text, text)

    # Função para corrigir bairros e associar rotas usando o JSON
    def corrigir_bairros_com_json(df, json_path='dicionarios.json'):
        """Corrige a coluna Bairro e associa Rota com base no CEP e no JSON."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            def find_bairro_and_route_by_cep(cep, cidade):
                cep = normalize_cep(cep)
                if not cep:
                    return None, None
                for key, value in json_data.items():
                    ceps = value.get('Cep', '').replace(' ', '').split(',')
                    if cep in ceps:
                        return value.get('Bairro'), value.get('Rota', normalize_route_name(cidade))
                return None, normalize_route_name(cidade)

            df[['Bairro', 'vazio2']] = df.apply(
                lambda row: pd.Series(find_bairro_and_route_by_cep(row['Entrega_CEP'], row['Destino_Cidade'])),
                axis=1
            )
            df['Bairro'] = df['Bairro'].fillna(df['Entrega_Bairro']).fillna('Desconhecido')
            df['vazio2'] = df['vazio2'].fillna(normalize_route_name(df['Destino_Cidade']))
            return df
        except FileNotFoundError:
            st.error(f"Arquivo {json_path} não encontrado.")
            return df
        except json.JSONDecodeError:
            st.error(f"Erro ao ler o arquivo JSON {json_path}.")
            return df
        except Exception:
            return df

    # Dicionário de parâmetros por rota com nomes normalizados
    route_params = {
        normalize_route_name("CACHOEIRO - SUL"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("CARIACICA - CAMPO GRANDE"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("CARIACICA - CARIACICA SEDE"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("CARIACICA - JARDIM AMERICA"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("CASTELO 262 - SUL"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("COLATINA - NORTE"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("GUARAPARI - SUL"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("LINHARES - NORTE"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("ROTA DESCONHECIDA"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SAO MATHEUS - NORTE"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SERRA - CIVIT1"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SERRA - CIVIT2"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SERRA - PRAIA"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SERRA - REGIAO 4"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("SERRA - REGIAO 5"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VILA VELHA - REGIAO ARIBIRI"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VILA VELHA - REGIAO BARRA DO JUCU"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VILA VELHA - REGIAO CENTRO"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VILA VELHA - REGIAO COBILANDIA"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VILA VELHA - REGIAO NOVO MEXICO"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VITORIA - REGIAO CENTRO"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000},
        normalize_route_name("VITORIA - REGIAO PRAIA"): {"FRETE_MINIMO": 4000.00, "PESO_LIMITE": 4000}
    }

    # Função para conectar ao banco e carregar dados
    def load_data():
        try:
            # Conectar ao banco
            conn = sqlite3.connect('ctrc_database.db')
            # Modificar a query para incluir situacao_resumida
            query = """
            SELECT CTRC_Identificador, Destino_UF, Destino_Cidade, Entrega_Bairro,
                Entrega_CEP, Tipo_Operação, Código_Situação, Descrição_Situação,
                Unidade_Emissor, datetime(Emissão_Data_Hora) AS Data_Emissao,
                Previsão_Entrega, Valor_Frete_RRS, Valor_Nota_Fiscal_RRS,
                Peso_Cálculo_Kg, Entrega_Nome, Remetente_Nome, rota, situacao_resumida
            FROM ctrc_data_vna
            WHERE Código_Situação NOT IN ('1-ENTREGUE', '36-MERCADORIA', '93-CTRC',
                                        '99-CTRC', '5-DEST', '7-CANCELAMENTO',
                                        '37-ENTREGA', '14-MERCADORIA', '50-FALTA',
                                        '94-CTRC')
            UNION
            SELECT CTRC_Identificador, Destino_UF, Destino_Cidade, Entrega_Bairro,
                Entrega_CEP, Tipo_Operação, Código_Situação, Descrição_Situação,
                Unidade_Emissor, datetime(Emissão_Data_Hora) AS Data_Emissao,
                Previsão_Entrega, Valor_Frete_RRS, Valor_Nota_Fiscal_RRS,
                Peso_Cálculo_Kg, Entrega_Nome, Remetente_Nome, rota, situacao_resumida
            FROM ctrc_data_bhz
            WHERE Código_Situação NOT IN ('1-ENTREGUE', '36-MERCADORIA', '93-CTRC',
                                        '99-CTRC', '5-DEST', '7-CANCELAMENTO',
                                        '37-ENTREGA', '14-MERCADORIA', '50-FALTA',
                                        '94-CTRC')
            """
            df = pd.read_sql_query(query, conn)
            conn.close()

            # Converter a coluna Data_Emissao para datetime
            df['Data_Emissao'] = pd.to_datetime(df['Data_Emissao'], errors='coerce')

            required_columns = ['Entrega_Nome', 'Remetente_Nome', 'Entrega_Bairro', 'Descrição_Situação', 'situacao_resumida']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.error(f"Colunas ausentes no DataFrame: {missing_columns}. Verifique a query ou o banco de dados.")
                return pd.DataFrame()

            # Verificar se a coluna 'Entrega_UF' existe, caso contrário, usar 'Destino_UF'
            if 'Entrega_UF' not in df.columns:
                df['Entrega_UF'] = df['Destino_UF']

            df = corrigir_bairros_com_json(df)
            df['Tipo_Operação'] = df['Tipo_Operação'].str.upper().str.strip()

            return df
        except sqlite3.Error as e:
            st.error(f"Erro ao carregar dados do banco: {e}")
            return pd.DataFrame()

    # Função para criar DataFrame de resumo
    def create_summary_df(df_filtered):
        if df_filtered.empty:
            return pd.DataFrame()

        try:
            df_filtered['Valor_Frete_RRS'] = pd.to_numeric(df_filtered['Valor_Frete_RRS'], errors='coerce').fillna(0)
            df_filtered['Valor_Nota_Fiscal_RRS'] = pd.to_numeric(df_filtered['Valor_Nota_Fiscal_RRS'], errors='coerce').fillna(0)
            df_filtered['Peso_Cálculo_Kg'] = pd.to_numeric(df_filtered['Peso_Cálculo_Kg'], errors='coerce').fillna(0)

            df_filtered['Previsão_Entrega_dt'] = pd.to_datetime(df_filtered['Previsão_Entrega'], errors='coerce')
            current_date = pd.to_datetime(datetime.now().date())

            df_filtered['No Prazo'] = (df_filtered['Previsão_Entrega_dt'] >= current_date) & df_filtered['Previsão_Entrega_dt'].notna()
            df_filtered['Fora do Prazo'] = (df_filtered['Previsão_Entrega_dt'] < current_date) & df_filtered['Previsão_Entrega_dt'].notna()

            summary = df_filtered.groupby('rota').agg({
                'CTRC_Identificador': 'count',
                'Valor_Frete_RRS': 'sum',
                'Valor_Nota_Fiscal_RRS': 'sum',
                'Destino_Cidade': 'nunique',
                'No Prazo': 'sum',
                'Fora do Prazo': 'sum',
                'Peso_Cálculo_Kg': 'sum'
            }).reset_index()

            summary.columns = ['Nome da Rota', 'Tot. Entregas', 'Total do Frete', 'Total da NF',
                              'Quantidade de Cidades', 'Ent. no Prazo', 'Ent. Fora do Prazo', 'Peso Total (Kg)']

            missing_routes = [route for route in summary['Nome da Rota'] if route not in route_params]
            if missing_routes:
                st.warning(f"Rotas não encontradas em route_params: {missing_routes}")

            summary['Progresso Frete'] = summary.apply(
                lambda row: (row['Total do Frete'] / route_params.get(row['Nome da Rota'], {'FRETE_MINIMO': 4000})['FRETE_MINIMO']) * 100,
                axis=1
            )
            summary['Progresso Peso'] = summary.apply(
                lambda row: (row['Peso Total (Kg)'] / route_params.get(row['Nome da Rota'], {'PESO_LIMITE': 4000})['PESO_LIMITE']) * 100,
                axis=1
            )

            summary['Total do Frete'] = summary['Total do Frete'].apply(lambda x: f"R$ {x:,.2f}")
            summary['Total da NF'] = summary['Total da NF'].apply(lambda x: f"R$ {x:,.2f}")
            summary['Peso Total (Kg)'] = summary['Peso Total (Kg)'].apply(lambda x: f"{x:,.2f}")

            return summary
        except Exception as e:
            st.error(f"Erro ao criar resumo: {e}")
            return pd.DataFrame()

    # Função para exportar DataFrame para XLSX
    def export_to_xlsx(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        return output.getvalue()

    # Função para exportar DataFrame para PDF
    def export_to_pdf(df):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        data = [df.columns.to_list()] + df.values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), '#333333'),
            ('TEXTCOLOR', (0, 0), (-1, 0), 'white'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), '#EEEEEE'),
            ('TEXTCOLOR', (0, 1), (-1, -1), 'black'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, '#CCCCCC'),
        ]))
        elements.append(table)
        doc.build(elements)
        return buffer.getvalue()

    # Função auxiliar para chamar a API do Google Maps Routes
    def roteirizar_subgrupo(enderecos, api_key, origem, trecho_inicial, endereco_cep_map=None):
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        # Inicializar lista de endereços a tentar
        tentativas = []
        for endereco in enderecos[1:]:  # Excluir origem, que é fixa
            tentativas_endereco = [{'endereco': endereco, 'tipo': 'original'}]
            if endereco_cep_map and endereco in endereco_cep_map:
                cep = endereco_cep_map[endereco]
                if cep:
                    tentativas_endereco.append({'endereco': cep, 'tipo': 'cep'})
                cidade_uf = ', '.join(endereco.split(', ')[1:])  # Extrair cidade e UF
                tentativas_endereco.append({'endereco': cidade_uf, 'tipo': 'cidade'})
            tentativas.append(tentativas_endereco)

        # Endereços finais usados após tentativas
        enderecos_finais = [origem]  # Começa com a origem
        enderecos_usados = [{'endereco': origem, 'tipo': 'origem'}]

        # Tentar cada endereço com fallback
        for i, tentativas_endereco in enumerate(tentativas):
            sucesso = False
            for tentativa in tentativas_endereco:
                endereco_atual = tentativa['endereco']
                tipo = tentativa['tipo']

                # Preparar payload com o endereço atual
                payload = {
                    "origin": {"address": origem},
                    "destination": {"address": origem},
                    "intermediates": [{"address": addr['endereco']} for addr in enderecos_usados[1:] + [{'endereco': endereco_atual}]],
                    "travelMode": "DRIVE",
                    "routingPreference": "TRAFFIC_AWARE",
                    "optimizeWaypointOrder": True,
                    "languageCode": "pt-BR",
                    "units": "METRIC"
                }
                headers = {
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': api_key,
                    'X-Goog-FieldMask': 'routes.legs,routes.duration,routes.distanceMeters,routes.optimizedIntermediateWaypointIndex'
                }

                try:
                    response = requests.post(url, headers=headers, data=json.dumps(payload))
                    response.raise_for_status()
                    results = response.json()

                    if 'routes' in results and len(results['routes']) > 0:
                        route = results['routes'][0]
                        legs = route.get('legs', [])
                        distancia_total = sum(leg.get('distanceMeters', 0) for leg in legs) / 1000
                        duracao_total = sum(int(leg.get('duration', '0s').replace('s', '')) for leg in legs) / 60

                        if distancia_total > 0 and duracao_total > 0:
                            enderecos_finais.append(endereco_atual)
                            enderecos_usados.append({'endereco': endereco_atual, 'tipo': tipo})
                            if tipo != 'original':
                                st.info(f"Trecho {trecho_inicial + i}: Endereço '{tentativas_endereco[0]['endereco']}' ajustado para {tipo.upper()}: {endereco_atual}")
                            sucesso = True
                            break
                except requests.exceptions.RequestException as e:
                    st.warning(f"Erro ao tentar {tipo} '{endereco_atual}' para trecho {trecho_inicial + i}: {e}")

            if not sucesso:
                st.warning(f"Trecho {trecho_inicial + i} com distância e duração nulas. Nenhum endereço válido encontrado para: {tentativas_endereco[0]['endereco']}")
                enderecos_finais.append(tentativas_endereco[0]['endereco'])  # Manter original para não quebrar a ordem
                enderecos_usados.append({'endereco': tentativas_endereco[0]['endereco'], 'tipo': 'original'})

        # Chamar a API com os endereços finais
        payload = {
            "origin": {"address": origem},
            "destination": {"address": origem},
            "intermediates": [{"address": addr} for addr in enderecos_finais[1:]],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "optimizeWaypointOrder": True,
            "languageCode": "pt-BR",
            "units": "METRIC"
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': 'routes.legs,routes.duration,routes.distanceMeters,routes.optimizedIntermediateWaypointIndex'
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            results = response.json()

            if 'routes' in results and len(results['routes']) > 0:
                route = results['routes'][0]
                optimized_order_indices = route.get('optimizedIntermediateWaypointIndex', [])

                ordem_otimizada_enderecos = [origem]
                for index in optimized_order_indices:
                    ordem_otimizada_enderecos.append(enderecos_finais[index + 1])
                ordem_otimizada_enderecos.append(origem)

                legs = route.get('legs', [])
                trechos_info = []
                acumulado_distancia_km = 0
                acumulado_duracao_minutos = 0

                for i, leg in enumerate(legs):
                    distancia_meters = leg.get('distanceMeters', 0)
                    distancia_km = distancia_meters / 1000
                    duracao_segundos = int(leg.get('duration', '0s').replace('s', ''))
                    duracao_minutos = duracao_segundos / 60

                    acumulado_distancia_km += distancia_km
                    acumulado_duracao_minutos += duracao_minutos

                    trechos_info.append({
                        'trecho': trecho_inicial + i,
                        'distancia_km': acumulado_distancia_km,
                        'duracao_minutos': acumulado_duracao_minutos,
                        'endereco_destino': ordem_otimizada_enderecos[i + 1]
                    })

                total_duration_seconds = int(route.get('duration', '0s').replace('s', ''))
                total_distance_meters = route.get('distanceMeters', 0)

                return {
                    'ordem_enderecos': ordem_otimizada_enderecos,
                    'duracao_minutos': total_duration_seconds / 60,
                    'distancia_km': total_distance_meters / 1000,
                    'trechos_info': trechos_info
                }
            else:
                st.error("Nenhuma rota encontrada na resposta da API.")
                return None
        except requests.exceptions.RequestException as e:
            st.error(f"Erro ao chamar a API: {e}")
            return None

    # Função para roteirizar entregas, lidando com mais de 25 waypoints
    def roteirizar_entregas(enderecos, api_key, origem, df_concat_display):
        num_intermediarios = len(enderecos) - 1
        # Criar mapeamento de endereços para CEPs
        endereco_cep_map = {}
        for endereco in enderecos[1:]:  # Excluir origem
            cep = df_concat_display[df_concat_display['Bairro'] + ', ' + df_concat_display['Cidade de Entrega'] + ' - ' + df_concat_display['UF de Entrega'] == endereco]['CEP de Entrega'].iloc[0] if not df_concat_display[df_concat_display['Bairro'] + ', ' + df_concat_display['Cidade de Entrega'] + ' - ' + df_concat_display['UF de Entrega'] == endereco].empty else None
            endereco_cep_map[endereco] = normalize_cep(cep)

        if num_intermediarios <= MAX_WAYPOINTS:
            resultado = roteirizar_subgrupo(enderecos, api_key, origem, trecho_inicial=1, endereco_cep_map=endereco_cep_map)
            if resultado:
                return resultado
            return None

        sub_rotas = []
        for i in range(0, num_intermediarios, MAX_WAYPOINTS):
            sub_enderecos = [origem] + enderecos[1:][i:i + MAX_WAYPOINTS]
            sub_rotas.append(sub_enderecos)

        st.info(f"Rota dividida em {len(sub_rotas)} sub-rotas devido ao limite de {MAX_WAYPOINTS + 2} waypoints por chamada.")

        ordem_enderecos_completa = []
        trechos_info_completa = []
        total_duracao_minutos = 0
        total_distancia_km = 0
        trecho_atual = 1
        ultimo_acumulado_distancia = 0
        ultimo_acumulado_duracao = 0

        for i, sub_enderecos in enumerate(sub_rotas):
            resultado = roteirizar_subgrupo(sub_enderecos, api_key, origem, trecho_inicial=trecho_atual, endereco_cep_map=endereco_cep_map)
            if not resultado:
                st.error(f"Falha ao roteirizar sub-rota {i+1}.")
                return None

            if i < len(sub_rotas) - 1:
                ordem_enderecos_completa.extend(resultado['ordem_enderecos'][:-1])
            else:
                ordem_enderecos_completa.extend(resultado['ordem_enderecos'])

            for trecho in resultado['trechos_info']:
                trechos_info_completa.append({
                    'trecho': trecho['trecho'],
                    'distancia_km': trecho['distancia_km'] + ultimo_acumulado_distancia,
                    'duracao_minutos': trecho['duracao_minutos'] + ultimo_acumulado_duracao,
                    'endereco_destino': trecho['endereco_destino']
                })

            total_duracao_minutos += resultado['duracao_minutos']
            total_distancia_km += resultado['distancia_km']
            trecho_atual += len(resultado['trechos_info'])
            ultimo_acumulado_distancia += resultado['distancia_km']
            ultimo_acumulado_duracao += resultado['duracao_minutos']

        return {
            'ordem_enderecos': ordem_enderecos_completa,
            'duracao_minutos': total_duracao_minutos,
            'distancia_km': total_distancia_km,
            'trechos_info': trechos_info_completa
        }

    # Função para criar link do Google Maps
    def criar_link_google_maps(ordem_enderecos):
        """Cria um link do Google Maps com a rota otimizada, incluindo todos os endereços."""
        base_url = "https://www.google.com.br/maps/dir/"
        enderecos_formatados = []
        for endereco in ordem_enderecos:
            # Verificar se o endereço é um CEP (8 dígitos numéricos)
            if endereco.replace('-', '').isdigit() and len(endereco.replace('-', '')) == 8:
                endereco_formatado = endereco
            else:
                try:
                    bairro_cidade_uf = endereco.split(', ')
                    if len(bairro_cidade_uf) == 2:
                        bairro = normalize_text(bairro_cidade_uf[0])
                        cidade_uf = bairro_cidade_uf[1].split(' - ')
                        cidade = normalize_text(cidade_uf[0])
                        uf = cidade_uf[1]
                        endereco_formatado = f"{bairro}, {cidade}, {uf}"
                    elif len(bairro_cidade_uf) == 1:
                        # Caso seja apenas cidade, UF
                        cidade_uf = bairro_cidade_uf[0].split(' - ')
                        cidade = normalize_text(cidade_uf[0])
                        uf = cidade_uf[1]
                        endereco_formatado = f"{cidade}, {uf}"
                    else:
                        endereco_formatado = endereco
                except:
                    endereco_formatado = endereco
            enderecos_formatados.append(endereco_formatado.replace(' ', '+'))

        link = base_url + '/'.join(enderecos_formatados)
        return link

    # Função para aplicar filtros
    def apply_filters(df):
        df_filtered = df.copy()
        # Normalizar a coluna de situação
        df_filtered['Tipo_Operação'] = df_filtered['Tipo_Operação'].str.upper().str.strip()

        if st.session_state.selected_uf:
            uf_column = 'Entrega_UF' if 'Entrega_UF' in df_filtered.columns else 'Destino_UF'
            df_filtered = df_filtered[df_filtered[uf_column].isin(st.session_state.selected_uf)]
        if st.session_state.selected_cidade:
            df_filtered = df_filtered[df_filtered['Destino_Cidade'].isin(st.session_state.selected_cidade)]
        if st.session_state.selected_rota:
            df_filtered = df_filtered[df_filtered['rota'].isin(st.session_state.selected_rota)]
        if st.session_state.data_emissao_min:
            df_filtered = df_filtered[df_filtered['Data_Emissao'] >= pd.to_datetime(st.session_state.data_emissao_min)]
        if st.session_state.data_emissao_max:
            # Adicionar 1 dia ao filtro de data máxima para incluir o dia inteiro
            df_filtered = df_filtered[df_filtered['Data_Emissao'] <= pd.to_datetime(st.session_state.data_emissao_max) + pd.Timedelta(days=1)]

        # Filtrar dados onde situacao_resumida não é "ROTA DE ENTREGA"
        df_filtered = df_filtered[df_filtered['situacao_resumida'] != 'EM ROTA DE ENTREGA']

        # Zerar valores de peso, valor de frete e valor de NF quando situacao_resumida for "CANHOTO RETIDO"
        canhoto_retido_mask = df_filtered['situacao_resumida'] == 'CANHOTO RETIDO'
        df_filtered.loc[canhoto_retido_mask, 'Valor_Frete_RRS'] = 0
        df_filtered.loc[canhoto_retido_mask, 'Peso_Cálculo_Kg'] = 0
        df_filtered.loc[canhoto_retido_mask, 'Valor_Nota_Fiscal_RRS'] = 0

        st.session_state.df_filtered = df_filtered
        st.session_state.filter_applied = True
        st.session_state.selected_routes = []
        st.session_state.df_concat_ordered = None

        if not df_filtered.empty:
            st.session_state.summary_df = create_summary_df(df_filtered)
        else:
            st.warning("Nenhum dado encontrado com os filtros selecionados.")

        st.rerun()

    # Função para lidar com o callback de seleção
    def handle_checkbox_click(summary_df):
        selected_rows = summary_df[summary_df["Selecionar"] == True]
        new_selected_routes = list(selected_rows["Nome da Rota"])
        if new_selected_routes != st.session_state.selected_routes:
            st.session_state.selected_routes = new_selected_routes
            st.session_state.df_concat_ordered = None
            st.rerun()

    # Carregar dados com spinner
    with st.spinner("Carregando dados..."):
        df = load_data()

    # Filtros na barra lateral
    with st.expander("Filtros", expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            uf_column = 'Entrega_UF' if 'Entrega_UF' in df.columns else 'Destino_UF'
            uf_options = sorted(df[uf_column].dropna().unique().tolist())
            st.session_state.selected_uf = st.multiselect(
                "UF de Entrega", uf_options, default=st.session_state.selected_uf, key="uf_filter"
            )
        with col2:
            cidade_column = 'Destino_Cidade'
            cidade_options = sorted(
                df[df[uf_column].isin(st.session_state.selected_uf)][cidade_column].dropna().unique().tolist()
                if st.session_state.selected_uf else df[cidade_column].dropna().unique().tolist()
            )
            st.session_state.selected_cidade = st.multiselect(
                "Cidade de Entrega", cidade_options, default=st.session_state.selected_cidade, key="cidade_filter"
            )
        with col3:
            rota_options = sorted(df['rota'].dropna().unique().tolist())
            st.session_state.selected_rota = st.multiselect(
                "Rota", rota_options, default=st.session_state.selected_rota, key="rota_filter"
            )
        with col4:
            st.session_state.data_emissao_min = st.date_input(
                "Data de Emissão (Início)", value=st.session_state.data_emissao_min, key="data_emissao_min_filter"
            )
        with col5:
            st.session_state.data_emissao_max = st.date_input(
                "Data de Emissão (Fim)", value=st.session_state.data_emissao_max, key="data_emissao_max_filter"
            )

        if st.button("Filtrar"):
            with st.spinner("Aplicando filtros..."):
                apply_filters(df)

    # Exibir resultados se os filtros foram aplicados
    if st.session_state.filter_applied and st.session_state.df_filtered is not None:
        df_filtered = st.session_state.df_filtered

        if not df_filtered.empty and st.session_state.summary_df is not None:
            st.subheader("Resumo por Rota")

            display_summary = st.session_state.summary_df.copy()
            display_summary["Selecionar"] = display_summary["Nome da Rota"].isin(st.session_state.selected_routes)

            routes_hash = hashlib.md5(json.dumps(st.session_state.selected_routes, sort_keys=True).encode()).hexdigest()
            summary_editor_key = f"summary_editor_{routes_hash}"

            edited_summary = st.data_editor(
                display_summary,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn(
                        "Selecionar",
                        help="Selecione uma ou mais rotas para visualizar detalhes",
                        default=False
                    ),
                    "Nome da Rota": st.column_config.TextColumn("Nome da Rota", disabled=True),
                    "Tot. Entregas": st.column_config.NumberColumn("Tot. Entregas", disabled=True),
                    "Total do Frete": st.column_config.TextColumn("Total do Frete", disabled=True),
                    "Total da NF": st.column_config.TextColumn("Total da NF", disabled=True),
                    "Quantidade de Cidades": st.column_config.NumberColumn("Quantidade de Cidades", disabled=True),
                    "Ent. no Prazo": st.column_config.NumberColumn("Ent. no Prazo", disabled=True),
                    "Ent. Fora do Prazo": st.column_config.NumberColumn("Ent. Fora do Prazo", disabled=True),
                    "Peso Total (Kg)": st.column_config.TextColumn("Peso Total (Kg)", disabled=True),
                    "Progresso Frete": st.column_config.NumberColumn(
                        "Progresso Frete (%)",
                        help="Porcentagem em relação ao frete mínimo",
                        format="%.0f%%",
                        disabled=True
                    ),
                    "Progresso Peso": st.column_config.NumberColumn(
                        "Progresso Peso (%)",
                        help="Porcentagem em relação ao peso limite",
                        format="%.0f%%",
                        disabled=True
                    )
                },
                use_container_width=True,
                hide_index=True,
                disabled=["Nome da Rota", "Tot. Entregas", "Total do Frete", "Total da NF",
                          "Quantidade de Cidades", "Ent. no Prazo", "Ent. Fora do Prazo",
                          "Peso Total (Kg)", "Progresso Frete", "Progresso Peso"],
                num_rows="fixed",
                key=summary_editor_key
            )

            if summary_editor_key in st.session_state and st.session_state[summary_editor_key] is not None:
                handle_checkbox_click(edited_summary)

            if st.session_state.selected_routes:
                st.subheader("Dados Concatenados das Rotas Selecionadas")

                df_concat = pd.concat([df_filtered[df_filtered['rota'] == route] for route in st.session_state.selected_routes])

                df_concat_display = df_concat[[
    'CTRC_Identificador', 'Tipo_Operação', 'situacao_resumida', 'Descrição_Situação', 'rota', 'Remetente_Nome',
    'Entrega_Nome', 'Entrega_UF', 'Destino_Cidade', 'Entrega_Bairro',
    'Entrega_CEP', 'Valor_Nota_Fiscal_RRS', 'Valor_Frete_RRS',
    'Peso_Cálculo_Kg'
                ]].copy()

                canhoto_retido_mask = df_concat_display['Tipo_Operação'] == 'CANHOTO RETIDO'
                canhoto_retido_mask = df_concat_display['Tipo_Operação'] == 'CANHOTO RETIDO'
                df_concat_display.loc[canhoto_retido_mask, 'Valor_Frete_RRS'] = 0
                df_concat_display.loc[canhoto_retido_mask, 'Peso_Cálculo_Kg'] = 0
                df_concat_display.loc[canhoto_retido_mask, 'Valor_Nota_Fiscal_RRS'] = 0

                df_concat_display['Entrega_Bairro'] = df_concat_display['Entrega_Bairro'].str.strip().replace('', pd.NA)
                df_concat_display['Entrega_Bairro'] = df_concat_display['Entrega_Bairro'].fillna('Desconhecido')

                df_concat_display = corrigir_bairros_com_json(df_concat_display)
                df_concat_display = df_concat_display.drop(columns=['Bairro', 'vazio2'], errors='ignore')  # Remover colunas extras
                df_concat_display = df_concat_display.sort_values('Entrega_CEP')

                df_concat_display.columns = [
    'Serie/Numero CTRC', 'Tipo_Operação', 'Situação Resumida', 'Descrição da Situação', 'Rota (rota)', 'Cliente Remetente',
    'Cliente Recebedor', 'UF de Entrega', 'Cidade de Entrega', 'Bairro',
    'CEP de Entrega', 'Valor da NF', 'Valor do Frete', 'Peso (Kg)'
                ]

                if st.button("Roteirizar Entregas"):
                    with st.spinner("Roteirizando entregas..."):
                        # Criar coluna temporária para a API
                        df_concat_display['Endereco_temp'] = df_concat_display.apply(
                            lambda row: f"{normalize_text(row['Bairro'])}, {normalize_text(row['Cidade de Entrega'])} - {row['UF de Entrega']}",
                            axis=1
                        )

                        enderecos_unicos = df_concat_display['Endereco_temp'].drop_duplicates().tolist()

                        if len(enderecos_unicos) < 1:
                            st.warning("É necessário pelo menos um endereço único para roteirizar.")
                        else:
                            enderecos_para_api = [ORIGEM_FIXA] + enderecos_unicos

                            resultado = roteirizar_entregas(enderecos_para_api, API_KEY, ORIGEM_FIXA, df_concat_display)

                            if resultado:
                                st.success(f"Rota otimizada encontrada!")
                                st.write(f"Duração Total Estimada: {resultado['duracao_minutos']:.2f} minutos")
                                st.write(f"Distância Total Estimada: {resultado['distancia_km']:.2f} km")

                                link_maps = criar_link_google_maps(resultado['ordem_enderecos'])
                                st.markdown(f"[Ver Rota no Google Maps]({link_maps})")

                                ordem_enderecos = resultado['ordem_enderecos']
                                ordem_dict = {addr: idx for idx, addr in enumerate(ordem_enderecos)}

                                df_concat_display['Ordem'] = df_concat_display['Endereco_temp'].map(ordem_dict)
                                df_concat_display['Ordem'] = df_concat_display['Ordem'].fillna(len(ordem_enderecos))

                                trechos_dict = {info['endereco_destino']: f"Trecho {info['trecho']}: {info['distancia_km']:.2f} km, {info['duracao_minutos']:.2f} min"
                                                for info in resultado['trechos_info']}
                                df_concat_display['Info Rota'] = df_concat_display['Endereco_temp'].map(trechos_dict)
                                df_concat_display['Info Rota'] = df_concat_display['Info Rota'].fillna('Retorno à Origem')

                                df_concat_ordered = df_concat_display.sort_values('Ordem').drop(columns=['Ordem', 'Endereco_temp'])

                                st.session_state.df_concat_ordered = df_concat_ordered

                # Exibir o DataFrame
                rota_options = sorted(df['rota'].dropna().unique().tolist())
                if st.session_state.df_concat_ordered is not None:
                    edited_concat = st.data_editor(
                        st.session_state.df_concat_ordered,
                        column_config={
                            'Serie/Numero CTRC': st.column_config.TextColumn("Serie/Numero CTRC", disabled=True),
                            'Situação Resumida': st.column_config.TextColumn("Situação Resumida", disabled=True),
                            'Descrição da Situação': st.column_config.TextColumn("Descrição da Situação", disabled=True),
                            'Rota (rota)': st.column_config.SelectboxColumn(
                                "Rota (rota)",
                                options=rota_options,
                                help="Selecione a rota",
                                required=True
                            ),
                            'Cliente Remetente': st.column_config.TextColumn("Cliente Remetente", disabled=True),
                            'Cliente Recebedor': st.column_config.TextColumn("Cliente Recebedor", disabled=True),
                            'UF de Entrega': st.column_config.TextColumn("UF de Entrega", disabled=True),
                            'Cidade de Entrega': st.column_config.TextColumn("Cidade de Entrega", disabled=True),
                            'Bairro': st.column_config.TextColumn("Bairro", disabled=True),
                            'CEP de Entrega': st.column_config.TextColumn("CEP de Entrega", disabled=True),
                            'Valor da NF': st.column_config.NumberColumn(
                                "Valor da NF",
                                disabled=True,
                                format="R$ %.2f"
                            ),
                            'Valor do Frete': st.column_config.NumberColumn(
                                "Valor do Frete",
                                disabled=True,
                                format="R$ %.2f"
                            ),
                            'Peso (Kg)': st.column_config.NumberColumn("Peso (Kg)", disabled=True, format="%.2f"),
                            'Info Rota': st.column_config.TextColumn("Info Rota", disabled=True)
                        },
                        use_container_width=True,
                        hide_index=True,
                        disabled=['Serie/Numero CTRC', 'Situação Resumida', 'Descrição da Situação',
                                  'Cliente Remetente', 'Cliente Recebedor', 'UF de Entrega',
                                  'Cidade de Entrega', 'Bairro', 'CEP de Entrega',
                                  'Valor da NF', 'Valor do Frete', 'Peso (Kg)', 'Info Rota'],
                        num_rows="fixed",
                        key=f"concat_editor_ordered_{routes_hash}"
                    )
                    if edited_concat is not None:
                        st.session_state.df_concat_ordered = edited_concat

                    # Botões de exportação
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Exportar para XLSX"):
                            xlsx_data = export_to_xlsx(st.session_state.df_concat_ordered)
                            st.download_button(
                                label="Baixar XLSX",
                                data=xlsx_data,
                                file_name="roteirizador_export.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    with col2:
                        if st.button("Exportar para PDF"):
                            pdf_data = export_to_pdf(st.session_state.df_concat_ordered)
                            st.download_button(
                                label="Baixar PDF",
                                data=pdf_data,
                                file_name="roteirizador_export.pdf",
                                mime="application/pdf"
                            )
                else:
                    edited_concat = st.data_editor(
                        df_concat_display,
                        column_config={
                            'Serie/Numero CTRC': st.column_config.TextColumn("Serie/Numero CTRC", disabled=True),
                            'Situação Resumida': st.column_config.TextColumn("Situação Resumida", disabled=True),
                            'Descrição da Situação': st.column_config.TextColumn("Descrição da Situação", disabled=True),
                            'Rota (rota)': st.column_config.SelectboxColumn(
                                "Rota (rota)",
                                options=rota_options,
                                help="Selecione a rota",
                                required=True
                            ),
                            'Cliente Remetente': st.column_config.TextColumn("Cliente Remetente", disabled=True),
                            'Cliente Recebedor': st.column_config.TextColumn("Cliente Recebedor", disabled=True),
                            'UF de Entrega': st.column_config.TextColumn("UF de Entrega", disabled=True),
                            'Cidade de Entrega': st.column_config.TextColumn("Cidade de Entrega", disabled=True),
                            'Bairro': st.column_config.TextColumn("Bairro", disabled=True),
                            'CEP de Entrega': st.column_config.TextColumn("CEP de Entrega", disabled=True),
                            'Valor da NF': st.column_config.NumberColumn(
                                "Valor da NF",
                                disabled=True,
                                format="R$ %.2f"
                            ),
                            'Valor do Frete': st.column_config.NumberColumn(
                                "Valor do Frete",
                                disabled=True,
                                format="R$ %.2f"
                            ),
                            'Peso (Kg)': st.column_config.NumberColumn("Peso (Kg)", disabled=True, format="%.2f")
                        },
                        use_container_width=True,
                        hide_index=True,
                        disabled=['Serie/Numero CTRC', 'Situação Resumida', 'Descrição da Situação',
                                  'Cliente Remetente', 'Cliente Recebedor', 'UF de Entrega',
                                  'Cidade de Entrega', 'Bairro', 'CEP de Entrega',
                                  'Valor da NF', 'Valor do Frete', 'Peso (Kg)'],
                        num_rows="fixed",
                        key=f"concat_editor_{routes_hash}"
                    )
                    if edited_concat is not None:
                        df_concat_display = edited_concat
    else:
        st.info("Selecione os filtros desejados e clique em 'Filtrar' para visualizar os dados.")

if __name__ == "__main__":
    render_roteirizar()

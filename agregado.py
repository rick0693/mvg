import streamlit as st
import pandas as pd
import sqlite3
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

# --- Função para conectar ao banco de dados e recuperar os dados ---
def get_data_from_db(db_file: str, table_names: list) -> Optional[pd.DataFrame]:
    try:
        conn = sqlite3.connect(db_file)
        dfs = []
        for table_name in table_names:
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql_query(query, conn)
            dfs.append(df)
        combined_df = pd.concat(dfs, ignore_index=True)
        return combined_df
    except sqlite3.Error as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def generate_report(df: pd.DataFrame, motoristas_dict: Dict[str, Dict[str, Any]], date_start: str, date_end: str, placas: list, tipo: str) -> Optional[Tuple[pd.DataFrame, Dict[str, Any]]]:
    required_columns = ['Veículo_Coleta', 'Placa_Entrega', 'Valor_Frete_RRS', 'CTRC_Identificador', 'Número_Nota_Fiscal', 'Remetente_Cidade', 'Destino_Cidade', 'ocorrencia_data_Entregue', 'ocorrencia_data_Data_de_Emissão_CTRC', 'ocorrencia_data_Saída_para_Entrega', 'ocorrencia_data_Tentativas_de_Entrega']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"Colunas faltando no DataFrame: {missing_columns}")
        return None

    df = df.copy()
    df['Veículo_Coleta'] = df['Veículo_Coleta'].replace('JMZ1I88', 'JMZ1888')
    df['Placa_Entrega'] = df['Placa_Entrega'].replace('JMZ1I88', 'JMZ1888')

    # Conversão de datas com formato explícito
    df['ocorrencia_data_Data_de_Emissão_CTRC'] = pd.to_datetime(df['ocorrencia_data_Data_de_Emissão_CTRC'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['ocorrencia_data_Entregue'] = pd.to_datetime(df['ocorrencia_data_Entregue'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['ocorrencia_data_Saída_para_Entrega'] = pd.to_datetime(df['ocorrencia_data_Saída_para_Entrega'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

    # Ajustar a data de emissão para o dia anterior se for antes das 6:00 da manhã (inalterado para coletas)
    df['ocorrencia_data_Data_de_Emissão_CTRC'] = df['ocorrencia_data_Data_de_Emissão_CTRC'].apply(
        lambda x: x - timedelta(days=1) if pd.notna(x) and x.hour < 6 else x
    )

    # Ajustar a data de entrega para o dia anterior se for antes das 4:00 da manhã
    df['ocorrencia_data_Entregue'] = df['ocorrencia_data_Entregue'].apply(
        lambda x: x - timedelta(days=1) if pd.notna(x) and x.hour < 4 else x
    )

    # Ajuste do intervalo de datas para incluir o dia inteiro de date_end
    date_start = pd.to_datetime(date_start).replace(hour=0, minute=0, second=0)
    date_end = pd.to_datetime(date_end).replace(hour=23, minute=59, second=59)

    # Coletas (inalterado)
    coletas = df[df['Veículo_Coleta'].notna() & df['ocorrencia_data_Data_de_Emissão_CTRC'].notna()].copy()
    coletas = coletas[(coletas['ocorrencia_data_Data_de_Emissão_CTRC'] >= date_start) &
                      (coletas['ocorrencia_data_Data_de_Emissão_CTRC'] <= date_end)]
    coletas['PLACA'] = coletas['Veículo_Coleta']
    coletas['TIPO BAIXA'] = 'C'
    coletas['DATA BAIXA_DIA'] = coletas['ocorrencia_data_Data_de_Emissão_CTRC'].dt.date
    coletas['CIDADE ORIGEM'] = coletas['Remetente_Cidade']

    # Entregas (ajustado para considerar apenas entregas com ocorrencia_data_Entregue não nulo)
    entregas = df[df['Placa_Entrega'].notna() & df['ocorrencia_data_Entregue'].notna()].copy()
    entregas['DATA_ENTREGA'] = entregas.apply(
        lambda row: row['ocorrencia_data_Entregue'] if row['ocorrencia_data_Tentativas_de_Entrega'] > 1 else row['ocorrencia_data_Saída_para_Entrega'],
        axis=1
    )
    entregas = entregas[(entregas['DATA_ENTREGA'] >= date_start) &
                        (entregas['DATA_ENTREGA'] <= date_end)]
    entregas['PLACA'] = entregas['Placa_Entrega']
    entregas['TIPO BAIXA'] = 'E'
    entregas['DATA BAIXA_DIA'] = entregas['DATA_ENTREGA'].dt.date
    entregas['CIDADE ORIGEM'] = entregas['Destino_Cidade']

    df_filtered = pd.concat([coletas, entregas], ignore_index=True)
    if df_filtered.empty:
        return None

    placas_agregado = [info['placa'].replace('JMZ1I88', 'JMZ1888') for motorista, info in motoristas_dict.items() if info.get('tipo') == 'Agregado']
    if tipo == 'Agregado':
        df_filtered = df_filtered[df_filtered['PLACA'].isin(placas_agregado)]
    elif tipo == 'Casa':
        df_filtered = df_filtered[~df_filtered['PLACA'].isin(placas_agregado)]

    if placas:
        placas = ['JMZ1888' if placa == 'JMZ1I88' else placa for placa in placas]
        df_filtered = df_filtered[df_filtered['PLACA'].isin(placas)]

    if df_filtered.empty:
        return None

    df_filtered['VLR FRETE'] = pd.to_numeric(df_filtered['Valor_Frete_RRS'], errors='coerce')

    placa_to_motorista = {info['placa'].replace('JMZ1I88', 'JMZ1888'): motorista for motorista, info in motoristas_dict.items()}
    df_filtered['MOTORISTA'] = df_filtered['PLACA'].map(lambda x: placa_to_motorista.get(x, 'Desconhecido'))

    active_day_plates = set()
    for _, row in df_filtered.iterrows():
        if pd.notna(row['DATA BAIXA_DIA']):
            active_day_plates.add((row['DATA BAIXA_DIA'], row['PLACA']))

    base_df = pd.DataFrame(list(active_day_plates), columns=['DATA BAIXA_DIA', 'PLACA'])

    coletas_grouped = df_filtered[df_filtered['TIPO BAIXA'] == 'C'].groupby(['DATA BAIXA_DIA', 'PLACA']).agg({
        'VLR FRETE': 'sum',
        'CTRC_Identificador': 'count'
    }).rename(columns={
        'VLR FRETE': 'VLR FRETE COLETA',
        'CTRC_Identificador': 'TOTAL DE COLETAS'
    }).reset_index()

    entregas_grouped = df_filtered[df_filtered['TIPO BAIXA'] == 'E'].groupby(['DATA BAIXA_DIA', 'PLACA']).agg({
        'VLR FRETE': 'sum',
        'CTRC_Identificador': 'count'
    }).rename(columns={
        'VLR FRETE': 'VLR FRETE ENTREGA',
        'CTRC_Identificador': 'TOTAL DE ENTREGAS'
    }).reset_index()

    report_df = base_df.merge(coletas_grouped, on=['DATA BAIXA_DIA', 'PLACA'], how='left')
    report_df = report_df.merge(entregas_grouped, on=['DATA BAIXA_DIA', 'PLACA'], how='left').fillna(0)

    report_df['MOTORISTA'] = report_df['PLACA'].map(lambda x: placa_to_motorista.get(x, 'Desconhecido'))

    report_df['VALOR TOTAL'] = report_df['VLR FRETE COLETA'] + report_df['VLR FRETE ENTREGA']

    report_df['% DE COLETA'] = 0.0
    report_df['VALOR DA NF'] = 0.0
    report_df['%SALDO / TOTAL DE NFS_NUM'] = 0.0
    report_df['%SALDO / TOTAL DE NFS'] = 0.0
    report_df['VALOR FRETE'] = 0.0

    placa_to_info = {info['placa'].replace('JMZ1I88', 'JMZ1888'): (motorista, info['valor'], info.get('Adicional', 0.0)) for motorista, info in motoristas_dict.items()}

    for index, row in report_df.iterrows():
        df_dia_placa = df_filtered[(df_filtered['DATA BAIXA_DIA'] == row['DATA BAIXA_DIA']) & (df_filtered['PLACA'] == row['PLACA'])]
        placa = row['PLACA']
        valor_frete_total = 0.0
        coleta_valor_total = 0.0
        valor_frete_diario = 0.0

        if placa in placa_to_info:
            _, valor_diario, adicional = placa_to_info[placa]
            valor_frete_total = valor_diario
            valor_frete_diario = valor_diario
            coletas_dia = df_dia_placa[df_dia_placa['TIPO BAIXA'] == 'C'].shape[0]
            entregas_dia = df_dia_placa[df_dia_placa['TIPO BAIXA'] == 'E'].shape[0]
            coleta_valor_total = (coletas_dia + entregas_dia) * adicional

        report_df.at[index, '% DE COLETA'] = coleta_valor_total
        report_df.at[index, 'VALOR DA NF'] = valor_frete_total + coleta_valor_total
        report_df.at[index, 'VALOR FRETE'] = valor_frete_diario
        report_df.at[index, '%SALDO / TOTAL DE NFS_NUM'] = (
            (valor_frete_total + coleta_valor_total) / row['VALOR TOTAL'] * 100 if row['VALOR TOTAL'] > 0 else 0
        )
        report_df.at[index, '%SALDO / TOTAL DE NFS'] = (
            (valor_frete_total + coleta_valor_total) / row['VALOR TOTAL'] * 100 if row['VALOR TOTAL'] > 0 else 0
        )

    total_geral_nf = report_df['VALOR DA NF'].sum()
    total_coletas = report_df['TOTAL DE COLETAS'].sum()
    total_entregas = report_df['TOTAL DE ENTREGAS'].sum()
    total_frete_coleta = report_df['VLR FRETE COLETA'].sum()
    total_frete_entrega = report_df['VLR FRETE ENTREGA'].sum()
    total_valor_total = report_df['VALOR TOTAL'].sum()
    total_valor_frete = report_df['VALOR FRETE'].sum()
    percentual_saldo_nfs = (
        (total_geral_nf / total_valor_total * 100) if total_valor_total > 0 else 0
    )

    report_df['DATA_FORMATADA'] = pd.to_datetime(report_df['DATA BAIXA_DIA']).dt.strftime('%Y-%m-%d')

    for col in ['VLR FRETE COLETA', 'VLR FRETE ENTREGA', '% DE COLETA', 'VALOR TOTAL', 'VALOR DA NF', 'VALOR FRETE']:
        report_df[col + '_NUM'] = report_df[col]
        report_df[col] = report_df[col].map(lambda x: f'R$ {x:,.2f}')

    report_df['%SALDO / TOTAL DE NFS'] = report_df['%SALDO / TOTAL DE NFS'].map(lambda x: f'{x:.2f}%'.replace('.', ','))

    columns_order = [
        'DATA BAIXA_DIA', 'DATA_FORMATADA', 'MOTORISTA', 'PLACA', 'VALOR FRETE', 'VLR FRETE COLETA', 'VLR FRETE ENTREGA',
        'TOTAL DE COLETAS', 'TOTAL DE ENTREGAS', '% DE COLETA', 'VALOR TOTAL',
        'VALOR DA NF', '%SALDO / TOTAL DE NFS', '%SALDO / TOTAL DE NFS_NUM'
    ]
    columns_order.extend([col + '_NUM' for col in ['VLR FRETE COLETA', 'VLR FRETE ENTREGA', '% DE COLETA', 'VALOR TOTAL', 'VALOR DA NF', 'VALOR FRETE']])
    columns_order = [col for col in columns_order if col in report_df.columns]
    report_df = report_df[columns_order]

    return report_df, {
        'total_geral_nf': total_geral_nf,
        'total_coletas': total_coletas,
        'total_entregas': total_entregas,
        'total_frete_coleta': total_frete_coleta,
        'total_frete_entrega': total_frete_entrega,
        'total_valor_frete': total_valor_frete,
        'percentual_saldo_nfs': percentual_saldo_nfs
    }

# --- Função para gerar o extrato detalhado ---
def generate_detailed_extract(df: pd.DataFrame, motoristas_dict: Dict[str, Dict[str, Any]], date_start: str, date_end: str, placas: list, tipo: str) -> pd.DataFrame:
    df = df.copy()

    # Conversão de datas com formato explícito
    df['ocorrencia_data_Data_de_Emissão_CTRC'] = pd.to_datetime(df['ocorrencia_data_Data_de_Emissão_CTRC'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['ocorrencia_data_Entregue'] = pd.to_datetime(df['ocorrencia_data_Entregue'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['ocorrencia_data_Saída_para_Entrega'] = pd.to_datetime(df['ocorrencia_data_Saída_para_Entrega'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

    # Ajuste do intervalo de datas para incluir o dia inteiro de date_end
    date_start = pd.to_datetime(date_start).replace(hour=0, minute=0, second=0)
    date_end = pd.to_datetime(date_end).replace(hour=23, minute=59, second=59)

    coletas = df[df['Veículo_Coleta'].notna() & df['ocorrencia_data_Data_de_Emissão_CTRC'].notna()].copy()
    coletas = coletas[(coletas['ocorrencia_data_Data_de_Emissão_CTRC'] >= date_start) &
                      (coletas['ocorrencia_data_Data_de_Emissão_CTRC'] <= date_end)]
    coletas['PLACA'] = coletas['Veículo_Coleta']
    coletas['TIPO BAIXA'] = 'C'

    entregas = df[df['Placa_Entrega'].notna()].copy()
    entregas['DATA_ENTREGA'] = entregas.apply(
        lambda row: row['ocorrencia_data_Entregue'] if row['ocorrencia_data_Tentativas_de_Entrega'] > 1 else row['ocorrencia_data_Saída_para_Entrega'],
        axis=1
    )
    entregas = entregas[(entregas['DATA_ENTREGA'] >= date_start) &
                        (entregas['DATA_ENTREGA'] <= date_end)]
    entregas['PLACA'] = entregas['Placa_Entrega']
    entregas['TIPO BAIXA'] = 'E'

    df = pd.concat([coletas, entregas], ignore_index=True)
    if df.empty:
        return pd.DataFrame()

    df['Veículo_Coleta'] = df['Veículo_Coleta'].replace('JMZ1I88', 'JMZ1888')
    df['Placa_Entrega'] = df['Placa_Entrega'].replace('JMZ1I88', 'JMZ1888')

    placas_agregado = [info['placa'].replace('JMZ1I88', 'JMZ1888') for motorista, info in motoristas_dict.items() if info.get('tipo') == 'Agregado']
    if tipo == 'Agregado':
        df = df[df['PLACA'].isin(placas_agregado)]
    elif tipo == 'Casa':
        df = df[~df['PLACA'].isin(placas_agregado)]

    if placas:
        placas = ['JMZ1888' if placa == 'JMZ1I88' else placa for placa in placas]
        df = df[df['PLACA'].isin(placas)]

    placa_to_info = {info['placa'].replace('JMZ1I88', 'JMZ1888'): (motorista, info['valor']) for motorista, info in motoristas_dict.items()}
    df['MOTORISTA'] = df['PLACA'].map(lambda x: placa_to_info[x][0] if x in placa_to_info else 'Desconhecido')
    df['VALOR DO FRETE'] = df['PLACA'].map(
        lambda x: f'R$ {placa_to_info[x][1]:,.2f}' if x in placa_to_info else 'R$ 0,00'
    )

    # Concatenar Origem_Cidade e Origem_UF para a coluna Remetente_Cidade
    df['Remetente_Cidade'] = df['Origem_Cidade'].str.upper() + ' - ' + df['Origem_UF'].str.upper()

    # Adicionar colunas REMETENTE e DESTINATARIO
    df['REMETENTE'] = df['Remetente_Nome']
    df['DESTINATARIO'] = df['Entrega_Nome']

    columns_extract = [
        'MOTORISTA', 'VALOR DO FRETE', 'PLACA', 'TIPO BAIXA',
        'ocorrencia_data_Data_de_Emissão_CTRC', 'DATA_ENTREGA',
        'CTRC_Identificador', 'Número_Nota_Fiscal', 'Remetente_Cidade',
        'Destino_Cidade', 'Valor_Frete_RRS', 'REMETENTE', 'DESTINATARIO'
    ]
    available_columns = df.columns.tolist()
    columns_extract = [col for col in columns_extract if col in available_columns]
    extract_df = df[columns_extract].copy()

    if 'ocorrencia_data_Data_de_Emissão_CTRC' in extract_df.columns:
        extract_df['DATA_COLETA'] = extract_df['ocorrencia_data_Data_de_Emissão_CTRC'].dt.strftime('%Y-%m-%d %H:%M:%S')
    if 'DATA_ENTREGA' in extract_df.columns:
        extract_df['DATA_ENTREGA'] = extract_df['DATA_ENTREGA'].dt.strftime('%Y-%m-%d %H:%M:%S')
    extract_df = extract_df.drop(columns=['ocorrencia_data_Data_de_Emissão_CTRC'], errors='ignore')

    if 'Valor_Frete_RRS' in extract_df.columns:
        extract_df['Valor_Frete_RRS'] = extract_df['Valor_Frete_RRS'].map(
            lambda x: f'R$ {float(x):,.2f}' if pd.notnull(x) else 'R$ 0,00'
        )

    extract_df = extract_df.sort_values(['MOTORISTA', 'DATA_COLETA', 'DATA_ENTREGA'], na_position='last')

    return extract_df

# --- Função para estilizar o DataFrame ---
def style_dataframe(df):
    def highlight_values(val, column):
        try:
            if column == '%SALDO / TOTAL DE NFS':
                num_val = float(val.replace(',', '.').replace('%', ''))
                if 'DJC2A49' in df['PLACA'].values:
                    return 'color: #00dfc0; font-weight: bold; text-shadow: 0 0 5px rgba(0, 223, 192, 0.5);' if num_val < 28.0 else 'color: #ff4d9e; font-weight: bold; text-shadow: 0 0 5px rgba(255, 77, 158, 0.5);'
                return 'color: #00dfc0; font-weight: bold; text-shadow: 0 0 5px rgba(0, 223, 192, 0.5);' if num_val <= 9.9 else 'color: #ff4d9e; font-weight: bold; text-shadow: 0 0 5px rgba(255, 77, 158, 0.5);'
            return ''
        except:
            return ''

    styled_df = df.style
    if '%SALDO / TOTAL DE NFS' in df.columns:
        styled_df = styled_df.map(lambda x, col='%SALDO / TOTAL DE NFS': highlight_values(x, col), subset=['%SALDO / TOTAL DE NFS'])

    return styled_df

# --- Dicionário de motoristas ---
motoristas_dict = {
    'Marcelo Rossi': {'valor': 367.20, 'tipo': 'Agregado', 'placa': 'DJC2A49', 'Adicional': 1.72, 'filial': 'VNA'},
    'Ivan Cardoso': {'valor': 367.20, 'tipo': 'Agregado', 'placa': 'MRX5H14', 'Adicional': 1.70, 'filial': 'VNA'},
    'Rafael Patrocinio': {'valor': 265.00, 'tipo': 'Agregado', 'placa': 'PPO8G36', 'Adicional': 0.00, 'filial': 'VNA'},
    'Jose Maria de Almeida': {'valor': 367.20, 'tipo': 'Agregado', 'placa': 'PPO8G37', 'Adicional': 1.70, 'filial': 'VNA'},
    'Edimar Anacleto De Souza': {'valor': 448.00, 'tipo': 'Agregado', 'placa': 'GYB7065', 'Adicional': 0.0, 'filial': 'VNA'},
    'Aelson Luis Cardoso': {'valor': 550.00, 'tipo': 'Agregado', 'placa': 'MQL8B02', 'Adicional': 0.0, 'filial': 'VNA'},
    'Elio Jose de Matos': {'valor': 367.20, 'tipo': 'Agregado', 'placa': 'KQT0A86', 'Adicional': 1.70, 'filial': 'VNA'},
    'Anderson Resstel': {'valor': 450.00, 'tipo': 'Agregado', 'placa': 'MQM0736', 'Adicional': 1.50, 'filial': 'VNA'},
    'Deilson de Melo Gomes': {'valor': 550.00, 'tipo': 'Agregado', 'placa': 'MRI2E67', 'Adicional': 0.0, 'filial': 'VNA'},
    'Claudio Cesconeto Salles': {'valor': 550.00, 'tipo': 'Agregado', 'placa': 'MQY3A78', 'Adicional': 1.50, 'filial': 'VNA'},
    'Marcio Alexandre': {'valor': 550.00, 'tipo': 'Agregado', 'placa': 'MRA3G30', 'Adicional': 1.50, 'filial': 'VNA'},
    'Jean Carlos': {'valor': 367.20, 'tipo': 'Agregado', 'placa': 'JNZ5D41', 'Adicional': 1.72, 'filial': 'VNA'},
    'Helio Belcavelho': {'valor': 486.00, 'tipo': 'Agregado', 'placa': 'MPP6D08', 'Adicional': 1.72, 'filial': 'VNA'},
    'Jose Chagas Coimbra': {'valor': 370.00, 'tipo': 'Agregado', 'placa': 'JMZ1888', 'Adicional': 1.70, 'filial': 'VNA'},
    'Jose Chagas Coimbra_2': {'valor': 370.00, 'tipo': 'Agregado', 'placa': 'JMZ1I88', 'Adicional': 1.70, 'filial': 'VNA'}
}

# --- Função principal para renderizar o aplicativo ---
def render_agregado():
    st.markdown("""
    <div class="title-container main-content">
        <div class="main-title">Relatório de Coletas e Entregas</div>
        <div class="subtitle">Sistema de Gestão de Fretes</div>
        <div class="title-separator"></div>
    </div>
    """, unsafe_allow_html=True)

    try:
        st.markdown('<style>{}</style>'.format(open('styles.css').read()), unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo styles.css não encontrado. Certifique-se de que ele está no mesmo diretório do script.")

    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'report_df' not in st.session_state:
        st.session_state.report_df = None
    if 'metrics' not in st.session_state:
        st.session_state.metrics = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'date_start' not in st.session_state:
        st.session_state.date_start = None
    if 'date_end' not in st.session_state:
        st.session_state.date_end = None
    if 'tipo' not in st.session_state:
        st.session_state.tipo = None
    if 'placas' not in st.session_state:
        st.session_state.placas = None

    if st.session_state.df is None:
        db_file = 'ctrc_database.db'
        table_names = ['ctrc_data_vna', 'ctrc_data_mre', 'ctrc_data_bhz', 'ctrc_data_spa']
        st.session_state.df = get_data_from_db(db_file, table_names)

    df = st.session_state.df

    default_min_date = datetime(2024, 1, 1).date()
    default_max_date = datetime(2025, 12, 31).date()

    if df is not None and not df.empty:
        date_column = 'ocorrencia_data_Entregue'
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], format='%Y-%m-%d %H:%M:%S', errors='coerce')
            minmax = df[date_column].agg(['min', 'max'])
            min_date = minmax['min'].to_pydatetime().date() if not df[date_column].isna().all() else default_min_date
            max_date = minmax['max'].to_pydatetime().date() if not df[date_column].isna().all() else default_max_date
        else:
            min_date = default_min_date
            max_date = default_max_date
    else:
        min_date = default_min_date
        max_date = default_max_date

    st.markdown("""
    <div class="section-header main-content">
        <div class="section-title">Métricas Gerais</div>
        <div class="section-header-line"></div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Filtros", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            date_start = st.date_input('Data Início', value=min_date, min_value=min_date, max_value=max_date, key="date_start_input")
        with col2:
            date_end = st.date_input('Data Fim', value=max_date, min_value=min_date, max_value=max_date, key="date_end_input")

        tipo = st.selectbox('Tipo', options=['Todos', 'Agregado', 'Casa'], key="tipo_select")
        placas_agregado = []
        for motorista, info in motoristas_dict.items():
            if 'tipo' not in info:
                st.warning(f"Chave 'tipo' ausente para o motorista {motorista}. Ignorando entrada.")
                continue
            if info['tipo'] == 'Agregado':
                placas_agregado.append(info['placa'])
        placas_agregado = ['JMZ1888' if placa == 'JMZ1I88' else placa for placa in placas_agregado]
        if tipo == 'Agregado':
            placa_options = list(set(placas_agregado))
        elif tipo == 'Casa' and df is not None and not df.empty:
            df_placas = df['Placa_Entrega'].replace('JMZ1I88', 'JMZ1888').dropna().unique()
            placa_options = list(set(df_placas) - set(placas_agregado))
        else:
            motoristas_placas = [info['placa'].replace('JMZ1I88', 'JMZ1888') for info in motoristas_dict.values()]
            df_placas = df['Placa_Entrega'].replace('JMZ1I88', 'JMZ1888').dropna().unique() if df is not None and not df.empty else []
            placa_options = list(set(motoristas_placas + list(df_placas)))

        placas = st.multiselect('Placas', options=placa_options, key="placas_multiselect")
        search_button = st.button("Buscar", key="search_button")

    placas_count = {placa: list(motoristas_dict.keys())[list(motoristas_dict.values()).index(info)]
                    for placa, info in [(info['placa'], info) for info in motoristas_dict.values()]}
    if len(placas_count) < len(motoristas_dict) and not (len(placas_count) == len(motoristas_dict) - 1 and 'JMZ1888' in placas_count and 'JMZ1I88' in placas_count):
        st.warning(f"Atenção: Placas duplicadas encontradas. A última entrada do dicionário será usada.")

    if search_button:
        st.session_state.date_start = date_start
        st.session_state.date_end = date_end
        st.session_state.tipo = tipo
        st.session_state.placas = placas
        st.session_state.data_loaded = True
        if df is not None and not df.empty:
            report_result = generate_report(df, motoristas_dict, date_start, date_end, placas, tipo)
            if report_result is not None:
                st.session_state.report_df, st.session_state.metrics = report_result
            else:
                st.session_state.report_df = None
                st.session_state.metrics = None
        else:
            st.session_state.report_df = None
            st.session_state.metrics = None
            st.info("Nenhum dado disponível para carregar.")

    if st.session_state.data_loaded and st.session_state.report_df is not None and st.session_state.metrics is not None:
        report_df = st.session_state.report_df
        metrics = st.session_state.metrics

        st.markdown("""
        <div class="section-header main-content">
            <div class="section-title">Métricas Gerais</div>
            <div class="section-header-line"></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="metrics-container">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        col4, col5, col6, col7 = st.columns([1, 1, 1, 1])

        with col1:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Total Geral NF</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"R$ {metrics['total_geral_nf']:,.2f}"),
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Total Coletas</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"{int(metrics['total_coletas'])}"),
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Total Entregas</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"{int(metrics['total_entregas'])}"),
                unsafe_allow_html=True
            )
        with col4:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Frete Coleta</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"R$ {metrics['total_frete_coleta']:,.2f}"),
                unsafe_allow_html=True
            )
        with col5:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Frete Entrega</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"R$ {metrics['total_frete_entrega']:,.2f}"),
                unsafe_allow_html=True
            )
        with col6:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">Valor Frete</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"R$ {metrics['total_valor_frete']:,.2f}"),
                unsafe_allow_html=True
            )
        with col7:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">% Saldo/NFs</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(f"{metrics['percentual_saldo_nfs']:.2f}%".replace('.', ',')),
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="section-header main-content">
            <div class="section-title">Relatório Consolidado</div>
            <div class="section-header-line"></div>
        </div>
        """, unsafe_allow_html=True)

        display_df = report_df.copy()
        display_df = display_df.rename(columns={'DATA_FORMATADA': 'DATA'})

        columns_to_display = [
            'DATA', 'MOTORISTA', 'PLACA', 'VALOR FRETE', 'VLR FRETE COLETA', 'VLR FRETE ENTREGA',
            'TOTAL DE COLETAS', 'TOTAL DE ENTREGAS', '% DE COLETA', 'VALOR TOTAL',
            'VALOR DA NF', '%SALDO / TOTAL DE NFS'
        ]
        columns_to_display = [col for col in columns_to_display if col in display_df.columns]
        display_df = display_df[columns_to_display]

        styled_df = style_dataframe(display_df)

        st.dataframe(styled_df, use_container_width=True)

        show_extract = st.toggle("Exibir Extrato Detalhado", value=False)
        if show_extract:
            st.markdown("""
            <div class="section-header main-content">
                <div class="section-title">Extrato Detalhado</div>
                <div class="section-header-line"></div>
            </div>
            """, unsafe_allow_html=True)
            extract_df = generate_detailed_extract(df, motoristas_dict, st.session_state.date_start, st.session_state.date_end, st.session_state.placas, st.session_state.tipo)
            columns_to_display_extract = [
                'MOTORISTA', 'VALOR DO FRETE', 'PLACA', 'TIPO BAIXA', 'DATA_COLETA',
                'DATA_ENTREGA', 'CTRC_Identificador', 'Número_Nota_Fiscal',
                'Remetente_Cidade', 'Destino_Cidade', 'Valor_Frete_RRS', 'REMETENTE', 'DESTINATARIO'
            ]
            columns_to_display_extract = [col for col in columns_to_display_extract if col in extract_df.columns]
            st.dataframe(extract_df[columns_to_display_extract], use_container_width=True)

    if st.session_state.data_loaded and (st.session_state.report_df is None or st.session_state.metrics is None):
        st.info("Nenhum dado encontrado para os filtros selecionados.")
    elif st.session_state.data_loaded and st.session_state.df is not None and st.session_state.df.empty:
        st.info("Nenhum dado encontrado para os filtros selecionados.")
    elif st.session_state.df is None and st.session_state.data_loaded:
        st.error("Erro ao carregar os dados do banco.")

    st.markdown("""
    <div class="footer main-content">
        Sistema de Gestão de Fretes | Desenvolvido com Streamlit | © 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    render_agregado()

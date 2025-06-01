from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
from datetime import datetime
from urllib.parse import urlparse
import requests
import jwt
import sqlite3
import pytz
import re
from data_extraction import extract_data_from_html, extract_nf_key, check_delivery_receipt, extract_tracking_info
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy

# Configura as opções para o modo headless
options = webdriver.ChromeOptions()
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")

# URL base do sistema
base_url = "https://sistema.ssw.inf.br"
login_url = f"{base_url}/bin/ssw0422"

# Nome do arquivo de configuração
config_file = "config.json"

# Intervalo de atualização em segundos (20 minutos * 60 segundos/minuto)
update_interval = 20 * 60

def get_token_and_save():
    print(f"\nIniciando busca do token em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Inicializa o driver do navegador (será fechado ao final da função)
    driver = webdriver.Chrome(options=options)

    try:
        # Navega até a página de login
        driver.get(login_url)

        # Espera até que a página de login esteja completamente carregada
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.ID, "frm")))
        wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        print("Página de login carregada.")

        # Localiza e preenche os campos de login
        dominio_input = wait.until(EC.presence_of_element_located((By.ID, "1")))
        cpf_input = wait.until(EC.presence_of_element_located((By.ID, "2")))
        usuario_input = wait.until(EC.presence_of_element_located((By.ID, "3")))
        senha_input = wait.until(EC.presence_of_element_located((By.ID, "4")))
        botao_login = wait.until(EC.element_to_be_clickable((By.ID, "5")))

        dominio_input.send_keys("rdm")
        cpf_input.send_keys("85842671581")
        usuario_input.send_keys("ricardos")
        senha_input.send_keys("RSS842")

        # Clica no botão de login
        botao_login.click()
        print("Login realizado.")

        # Espera um pouco para que os cookies sejam estabelecidos após o login
        time.sleep(5)

        # Obtém todos os cookies do navegador
        cookies = driver.get_cookies()
        print("\nCookies obtidos do navegador:")
        for cookie in cookies:
            print(f"{cookie['name']}={cookie['value']}")

        # Procura a chave e o token nos cookies
        chave = None
        token = None
        current_cookies = {}
        for cookie in cookies:
            current_cookies[cookie['name']] = cookie['value']
            if cookie['name'] == 'chave':
                chave = cookie['value']
            if cookie['name'] == 'token':
                token = cookie['value']

        print("\nInformações encontradas nos cookies:")
        if chave:
            print(f"Chave: {chave}")
        else:
            print("Chave não encontrada nos cookies.")

        if token:
            print(f"Token: {token}")
        else:
            print("Token não encontrado nos cookies.")

        # Carrega o arquivo de configuração existente ou cria um novo
        try:
            with open(config_file, "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config_data = {}
            print("Aviso: Arquivo config.json não encontrado ou corrompido. Criando um novo.")

        # Atualiza a seção de cookies e adiciona a data/hora da obtenção
        config_data['cookies'] = current_cookies
        config_data['last_token_retrieval'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if token:
            config_data['token_info'] = {
                'value': token,
                'retrieved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        # Salva as informações no arquivo config.json
        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=4)
        print(f"\nArquivo {config_file} atualizado com os novos cookies e data de obtenção.")

        return token is not None

    except Exception as e:
        print(f"Ocorreu um erro durante a obtenção do token: {e}")
        return False
    finally:
        # Fecha o navegador
        driver.quit()
        print("Navegador fechado.")

def refresh_token():
    print("Renovando token usando Selenium...")
    success = get_token_and_save()
    if success:
        print("Token renovado com sucesso.")
    else:
        print("Falha ao renovar token.")
    return success

# Carregar dicionários e configurações
def load_dictionarios():
    with open('dicionarios.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['situacao_resumida_rules'], data['corrections']

situacao_resumida_rules, corrections = load_dictionarios()

def load_config():
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config['cookies'], config['headers']

cookies, headers = load_config()

# Configurações de colunas necessárias
required_columns = [
    'Unidade Emissor', 'N° CTRC', 'CTRC_Identificador', 'Emissão Data/Hora', 'Tipo Operação', 'Sequência CTRC',
    'Número CT-e', 'Status', 'Situação Data/Hora', 'Código Situação', 'Descrição Situação', 'Usuário Inclusão',
    'Prazo Unidade Destinatária', 'Destino', 'Número Nota Fiscal', 'Quantidade Volumes',
    'Peso Cálculo (Kg)', 'Valor Nota Fiscal (R$)', 'Valor Frete (R$)', 'Tipo Cobrança', 'Situação Liquidação',
    'Remetente Nome', 'Remetente CNPJ', 'Remetente Endereço', 'Remetente Bairro', 'Remetente CEP',
    'Remetente Cidade', 'Destinatário Endereço', 'Destinatário Bairro', 'Destinatário CEP', 'Destinatário Cidade',
    'Destinatário UF', 'Domínio/Origem', 'Remetente UF', 'Remetente Telefone', 'Destinatário Nome',
    'Destinatário CNPJ', 'Entrega Nome', 'Entrega CNPJ', 'Entrega Endereço', 'Entrega Bairro', 'Entrega CEP',
    'Entrega Cidade', 'Entrega UF', 'Pagador Nome', 'Pagador CNPJ', 'Origem Código', 'Origem UF', 'Origem Cidade',
    'Destino Código', 'Destino UF', 'Destino Cidade', 'Veículo Coleta', 'Conferente Coleta', 'Romaneio Número',
    'Placa Entrega', 'Chave NF', 'Remessa Data/Hora', 'Comprovante de Entrega',
    'ocorrencia_data_Data de Emissão CTRC', 'ocorrencia_data_Saída de Unidade',
    'ocorrencia_data_Chegada em Unidade de Entrega', 'ocorrencia_data_Saída para Entrega',
    'ocorrencia_data_Entregue', 'ocorrencia_data_Tentativas de Entrega', 'Previsão Entrega', 'LEADTIME', 'situação_prazo',
    'tentativas_dados', 'situacao_resumida', 'ultima_verificacao', 'rota'
]

column_mapping = {col: col.replace('°', '_').replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_').replace('$', 'RS') for col in required_columns}

column_types = {
    'Unidade_Emissor': 'TEXT',
    'N_CTRC': 'TEXT',
    'CTRC_Identificador': 'TEXT UNIQUE',
    'Emissão_Data_Hora': 'TEXT',
    'Tipo_Operação': 'TEXT',
    'Sequência_CTRC': 'TEXT',
    'Número_CT-e': 'TEXT',
    'Status': 'TEXT',
    'Situação_Data_Hora': 'TEXT',
    'Código_Situação': 'TEXT',
    'Descrição_Situação': 'TEXT',
    'Usuário_Inclusão': 'TEXT',
    'Prazo_Unidade_Destinatária': 'TEXT',
    'Destino': 'TEXT',
    'Número_Nota_Fiscal': 'TEXT',
    'Quantidade_Volumes': 'INTEGER',
    'Peso_Cálculo_Kg': 'REAL',
    'Valor_Nota_Fiscal_RS': 'REAL',
    'Valor_Frete_RS': 'REAL',
    'Tipo_Cobrança': 'TEXT',
    'Situação_Liquidação': 'TEXT',
    'Remetente_Nome': 'TEXT',
    'Remetente_CNPJ': 'TEXT',
    'Remetente_Endereço': 'TEXT',
    'Remetente_Bairro': 'TEXT',
    'Remetente_CEP': 'TEXT',
    'Remetente_Cidade': 'TEXT',
    'Destinatário_Endereço': 'TEXT',
    'Destinatário_Bairro': 'TEXT',
    'Destinatário_CEP': 'TEXT',
    'Destinatário_Cidade': 'TEXT',
    'Destinatário_UF': 'TEXT',
    'Domínio_Origem': 'TEXT',
    'Remetente_UF': 'TEXT',
    'Remetente_Telefone': 'TEXT',
    'Destinatário_Nome': 'TEXT',
    'Destinatário_CNPJ': 'TEXT',
    'Entrega_Nome': 'TEXT',
    'Entrega_CNPJ': 'TEXT',
    'Entrega_Endereço': 'TEXT',
    'Entrega_Bairro': 'TEXT',
    'Entrega_CEP': 'TEXT',
    'Entrega_Cidade': 'TEXT',
    'Entrega_UF': 'TEXT',
    'Pagador_Nome': 'TEXT',
    'Pagador_CNPJ': 'TEXT',
    'Origem_Código': 'TEXT',
    'Origem_UF': 'TEXT',
    'Origem_Cidade': 'TEXT',
    'Destino_Código': 'TEXT',
    'Destino_UF': 'TEXT',
    'Destino_Cidade': 'TEXT',
    'Veículo_Coleta': 'TEXT',
    'Conferente_Coleta': 'TEXT',
    'Romaneio_Número': 'TEXT',
    'Placa_Entrega': 'TEXT',
    'Chave_NF': 'TEXT',
    'Remessa_Data_Hora': 'TEXT',
    'Comprovante_de_Entrega': 'TEXT',
    'ocorrencia_data_Data_de_Emissão_CTRC': 'TEXT',
    'ocorrencia_data_Saída_de_Unidade': 'TEXT',
    'ocorrencia_data_Chegada_em_Unidade_de_Entrega': 'TEXT',
    'ocorrencia_data_Saída_para_Entrega': 'TEXT',
    'ocorrencia_data_Entregue': 'TEXT',
    'ocorrencia_data_Tentativas_de_Entrega': 'INTEGER',
    'Previsão_Entrega': 'TEXT',
    'LEADTIME': 'REAL',
    'situação_prazo': 'TEXT',
    'tentativas_dados': 'INTEGER',
    'situacao_resumida': 'TEXT',
    'ultima_verificacao': 'TEXT',
    'rota': 'TEXT'
}

# Dicionário de intervalos de atualização
update_intervals = {
    "AGATD. TRANSF, DA UN VNA PARA UNIDADE DE BHZI": 60,
    "EM TRANSFERENCIA": 60,
    "CANHOTO RETIDO": 1440,
    "ENTREGA FINALIZADA": 0,
    "COMPLEMENTAR": 0,
    "OUTRO": 60,
    "Unidade de Muriae": 60,
    "Unidade de Belo Horizonte": 60,
    "Unidade de São Pedro da Aldeia": 60,
    "AGUARDANDO DEFINIÇÃO": 60,
    "Unidade de Viana": 60,
    "SETOR DE PENDÊNCIA": 60,
    "DISPONÍVEL PARA ENTREGA": 60,
    "AGUARDANDO TRATAMENTO": 60,
    "CANCELADO": 0,
    "EM ROTA DE ENTREGA": 60,
    "CANHOTO": 1440
}

# Funções auxiliares
def calculate_leadtime_and_situacao(row):
    required_keys = ['ocorrencia_data_Data_de_Emissão_CTRC', 'ocorrencia_data_Entregue', 'Previsão_Entrega']
    if all(key in row and row[key] for key in required_keys):
        try:
            data_entregue = datetime.strptime(row['ocorrencia_data_Entregue'], '%Y-%m-%d %H:%M:%S')
            data_emissao = datetime.strptime(row['ocorrencia_data_Data_de_Emissão_CTRC'], '%Y-%m-%d %H:%M:%S')
            data_previsao = datetime.strptime(row['Previsão_Entrega'], '%Y-%m-%d %H:%M:%S')

            leadtime = (data_entregue - data_emissao).total_seconds() / 86400
            situacao_prazo = 'ENTREGUE NO PRAZO' if data_entregue <= data_previsao else 'ENTREGUE FORA DO PRAZO'

            return int(leadtime), situacao_prazo
        except ValueError:
            return None, None
    return None, None

def calcular_leadtime_e_situacao_prazo(data_emissao, ocorrencia_data_entregue):
    result = {'LEADTIME': None, 'situação_prazo': None}
    if data_emissao and ocorrencia_data_entregue:
        try:
            data_emissao_dt = datetime.strptime(data_emissao, '%Y-%m-%d %H:%M:%S')
            ocorrencia_data_entregue_dt = datetime.strptime(ocorrencia_data_entregue, '%Y-%m-%d %H:%M:%S')
            result['LEADTIME'] = (ocorrencia_data_entregue_dt - data_emissao_dt).days
            result['situação_prazo'] = 'ENTREGUE NO PRAZO'
        except ValueError:
            pass
    return result

def extrair_inicio_descricao(descricao):
    if not descricao:
        return "SEM DADOS"
    descricao_upper = descricao.upper()
    for chave in situacao_resumida_rules:
        if descricao_upper.startswith(chave.upper()):
            return chave
    if descricao_upper.startswith("ENTREGA REALIZADA EM"):
        return "ENTREGA REALIZADA EM"
    return descricao.split()[0]

def is_token_expiring(token, threshold_seconds=300):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded['exp']
        current_timestamp = int(time.time())
        return exp_timestamp - current_timestamp < threshold_seconds
    except jwt.InvalidTokenError:
        return True

def create_table(table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        if 'ultima_verificacao' not in columns:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN ultima_verificacao TEXT')
        if 'rota' not in columns:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN rota TEXT')
        columns_sql = ', '.join([f'"{column_mapping[col]}" {column_types[col]}"' for col in required_columns])
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {columns_sql}
        )
        """
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao criar tabela {table_name}: {e}")

def get_last_ctrc(table_name, filial):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            conn.close()
            return filial['serie'], filial['start_number']
        query = f'SELECT "{column_mapping["N° CTRC"]}", "{column_mapping["Unidade Emissor"]}" FROM {table_name} ORDER BY CAST("{column_mapping["N° CTRC"]}" AS INTEGER) DESC LIMIT 1'
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[1], result[0]
        return filial['serie'], filial['start_number']
    except Exception as e:
        print(f"Erro ao obter último CTRC para {table_name}: {e}")
        return filial['serie'], filial['start_number']

def load_routes_data():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        routes_data = json.load(f)
    return routes_data

# Define cities to exclude from city-only fallback (customize as needed)
CITIES_EXCLUDED_FROM_CITY_ONLY_FALLBACK = set()

def create_route_mappings(routes_data):
    cep_to_route_map = {}
    uf_cidade_bairro_to_route_map = {}
    uf_cidade_to_route_map = {}

    for key_from_json, route_details in routes_data.items():
        route_name = route_details.get('Rota')

        if not route_name:
            parts = key_from_json.split('|')
            if len(parts) >= 4:
                route_name = parts[3].strip()
            else:
                continue

        uf_json = str(route_details.get('UF', '')).strip().upper()
        cidade_json = str(route_details.get('Cidade', '')).strip().upper()
        bairro_json = str(route_details.get('Bairro', '')).strip().upper()

        ceps_str = str(route_details.get('Cep', '')).replace(' ', '')
        if ceps_str:
            individual_ceps = ceps_str.split(',')
            for cep in individual_ceps:
                cleaned_cep = re.sub(r'[^0-9]', '', cep).strip()
                if cleaned_cep:
                    if cleaned_cep not in cep_to_route_map:
                        cep_to_route_map[cleaned_cep] = route_name

        if uf_json and cidade_json and bairro_json:
            composite_key_bairro = f"{uf_json}|{cidade_json}|{bairro_json}"
            if composite_key_bairro not in uf_cidade_bairro_to_route_map:
                uf_cidade_bairro_to_route_map[composite_key_bairro] = route_name

        if uf_json and cidade_json:
            if cidade_json not in CITIES_EXCLUDED_FROM_CITY_ONLY_FALLBACK:
                composite_key_cidade = f"{uf_json}|{cidade_json}"
                if composite_key_cidade not in uf_cidade_to_route_map:
                    uf_cidade_to_route_map[composite_key_cidade] = route_name

    return cep_to_route_map, uf_cidade_bairro_to_route_map, uf_cidade_to_route_map

def find_route(entrega_cep_db, destino_uf_db, destino_cidade_db, entrega_bairro_db, cep_to_route_map, uf_cidade_bairro_to_route_map, uf_cidade_to_route_map):
    found_route = None

    cleaned_uf_db = str(destino_uf_db).strip().upper() if destino_uf_db else ''
    cleaned_cidade_db = str(destino_cidade_db).strip().upper() if destino_cidade_db else ''
    cleaned_bairro_db = str(entrega_bairro_db).strip().upper() if entrega_bairro_db else ''

    if entrega_cep_db:
        cleaned_cep_db = re.sub(r'[^0-9]', '', entrega_cep_db).strip()
        if cleaned_cep_db:
            found_route = cep_to_route_map.get(cleaned_cep_db)

    if not found_route and cleaned_uf_db and cleaned_cidade_db and cleaned_bairro_db:
        composite_key_bairro_db = f"{cleaned_uf_db}|{cleaned_cidade_db}|{cleaned_bairro_db}"
        found_route = uf_cidade_bairro_to_route_map.get(composite_key_bairro_db)

    if not found_route and cleaned_uf_db and cleaned_cidade_db:
        if cleaned_cidade_db not in CITIES_EXCLUDED_FROM_CITY_ONLY_FALLBACK:
            composite_key_cidade_db = f"{cleaned_uf_db}|{cleaned_cidade_db}"
            found_route = uf_cidade_to_route_map.get(composite_key_cidade_db)

    return found_route

def insert_data(extracted_data, table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        columns = ', '.join([f'"{column_mapping[col]}"' for col in required_columns])
        placeholders = ', '.join(['?' for _ in required_columns])
        insert_sql = f'INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})'
        tz = pytz.timezone('America/Sao_Paulo')
        current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        extracted_data['ultima_verificacao'] = current_time

        for col in required_columns:
            if col not in extracted_data:
                extracted_data[col] = '' if 'Tentativas de Entrega' not in col else 0 if col == 'ocorrencia_data_Tentativas de Entrega' else None
            elif extracted_data[col] is None and col not in ['LEADTIME', 'situação_prazo', 'situacao_resumida', 'ultima_verificacao']:
                extracted_data[col] = '' if 'Tentativas de Entrega' not in col else 0 if col == 'ocorrencia_data_Tentativas de Entrega' else None
        values = [extracted_data.get(col, '' if 'Tentativas de Entrega' not in col else 0 if col == 'ocorrencia_data_Tentativas de Entrega' else None) for col in required_columns]
        cursor.execute(insert_sql, values)
        conn.commit()
        inserted_count = cursor.rowcount
        conn.close()
        return inserted_count
    except Exception as e:
        print(f"Erro ao inserir dados na tabela {table_name}: {e}")
        return 0

def process_ctrc(filial, ctrc_number, cookies, headers):
    local_cookies = deepcopy(cookies)
    data = {
        'act': 'P1',
        't_ser_ctrc': filial['serie'],
        't_nro_ctrc': str(ctrc_number),
        't_data_ini': '090224',
        't_data_fin': datetime.now().strftime('%d%m%y'),
        'data_ini_inf': '301299',
        'data_fin_inf': datetime.now().strftime('%d%m%y'),
        'seq_ctrc': '0',
        'local': '',
        'FAMILIA': '',
        'dummy': str(int(time.time() * 1000)),
    }
    attempt = 0
    max_attempts = 3
    extracted_data = None
    while attempt < max_attempts:
        try:
            response = requests.post('https://sistema.ssw.inf.br/bin/ssw0053', cookies=local_cookies, headers=headers, data=data)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            attempt += 1
            continue
        if "CTRC não encontrado" in response.text or not response.text.strip():
            return None, filial
        try:
            extracted_data = extract_data_from_html(response.text)
            if extracted_data is None:
                attempt += 1
                continue
        except Exception:
            attempt += 1
            continue
        seq_ctrc = extracted_data.get('Sequência CTRC', '')
        if seq_ctrc:
            try:
                chave_nf = extract_nf_key(local_cookies, headers, seq_ctrc)
                extracted_data['Chave NF'] = chave_nf if chave_nf else ''
            except Exception:
                extracted_data['Chave NF'] = ''
        if seq_ctrc:
            try:
                extracted_data['Comprovante de Entrega'] = check_delivery_receipt(local_cookies, headers, seq_ctrc) or 'NAO'
            except Exception:
                extracted_data['Comprovante de Entrega'] = 'NAO'
        try:
            tracking_info = extract_tracking_info(local_cookies, headers, seq_ctrc)
            if tracking_info:
                extracted_data.update(tracking_info)
            else:
                tracking_fields = [
                    'ocorrencia_data_Data de Emissão CTRC', 'ocorrencia_data_Saída de Unidade',
                    'ocorrencia_data_Chegada em Unidade de Entrega', 'ocorrencia_data_Saída para Entrega',
                    'ocorrencia_data_Entregue', 'ocorrencia_data_Tentativas de Entrega', 'Previsão Entrega'
                ]
                for field in tracking_fields:
                    extracted_data[field] = 0 if field == 'ocorrencia_data_Tentativas de Entrega' else ''
        except Exception:
            tracking_fields = [
                'ocorrencia_data_Data de Emissão CTRC', 'ocorrencia_data_Saída de Unidade',
                'ocorrencia_data_Chegada em Unidade de Entrega', 'ocorrencia_data_Saída para Entrega',
                'ocorrencia_data_Entregue', 'ocorrencia_data_Tentativas de Entrega', 'Previsão Entrega'
            ]
            for field in tracking_fields:
                extracted_data[field] = 0 if field == 'ocorrencia_data_Tentativas de Entrega' else ''
        break
    if extracted_data:
        if 'Unidade Emissor' in extracted_data and 'N° CTRC' in extracted_data:
            extracted_data['CTRC_Identificador'] = f"{extracted_data['Unidade Emissor']}{extracted_data['N° CTRC']}"
        else:
            return None, filial
        extracted_data['tentativas_dados'] = attempt + 1

        # Carregar os dados de rotas e criar os mapeamentos
        routes_data = load_routes_data()
        cep_to_route_map, uf_cidade_bairro_to_route_map, uf_cidade_to_route_map = create_route_mappings(routes_data)

        # Buscar a rota com base nos dados do registro
        entrega_cep_db = extracted_data.get('Entrega_CEP', '')
        destino_uf_db = extracted_data.get('Destino_UF', '')
        destino_cidade_db = extracted_data.get('Destino_Cidade', '')
        entrega_bairro_db = extracted_data.get('Entrega_Bairro', '')

        found_route = find_route(entrega_cep_db, destino_uf_db, destino_cidade_db, entrega_bairro_db, cep_to_route_map, uf_cidade_bairro_to_route_map, uf_cidade_to_route_map)

        if found_route:
            extracted_data['rota'] = found_route

    return extracted_data, filial

def check_and_fill_gaps(filial, cookies, headers):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = f'SELECT "{column_mapping["N° CTRC"]}" FROM {filial["table"]} ORDER BY CAST("{column_mapping["N° CTRC"]}" AS INTEGER)'
    cursor.execute(query)
    results = cursor.fetchall()
    processed_ctrcs = [int(result[0]) for result in results]
    if processed_ctrcs:
        processed_ctrcs.sort()
        gaps = []
        for i in range(1, len(processed_ctrcs)):
            if processed_ctrcs[i] - processed_ctrcs[i-1] > 1:
                gaps.extend(range(processed_ctrcs[i-1] + 1, processed_ctrcs[i]))
        for ctrc_number in gaps:
            extracted_data, _ = process_ctrc(filial, ctrc_number, cookies, headers)
            if extracted_data:
                insert_data(extracted_data, filial['table'])
    conn.close()

# Função auxiliar para depuração de datas
def debug_datetime_comparison(filial):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT "ultima_verificacao", datetime('now', 'localtime'), datetime('now', 'localtime', '-30 minutes')
            FROM {filial['table']}
            WHERE "situacao_resumida" NOT IN (
                SELECT key FROM (SELECT json_object() AS dict) AS temp,
                json_each(dict, '$') AS entry
                WHERE json_extract(entry.value, '$.value') = 0
            )
            LIMIT 1
        ''')
        result = cursor.fetchone()
        if result:
            ultima_verificacao, now_local, now_minus_30 = result
            print(f"Filial {filial['serie']}: ultima_verificacao={ultima_verificacao}, now_local={now_local}, now_minus_30={now_minus_30}")
        else:
            print(f"Filial {filial['serie']}: Nenhum registro encontrado para depuração de datas.")
        conn.close()
    except Exception as e:
        print(f"Erro ao depurar datas para {filial['serie']}: {e}")

# Função para validar e corrigir formatos inválidos de ultima_verificacao
def clean_invalid_ultima_verificacao(filial):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE {filial['table']}
            SET "ultima_verificacao" = NULL
            WHERE "ultima_verificacao" IS NOT NULL
            AND "ultima_verificacao" NOT LIKE '____-__-__ __:__:__'
        ''')
        conn.commit()
        print(f"Filial {filial['serie']}: {cursor.rowcount} registros com ultima_verificacao inválida corrigidos.")
        conn.close()
    except Exception as e:
        print(f"Erro ao corrigir ultima_verificacao para {filial['serie']}: {e}")

class ExistingDataHandler:
    def __init__(self, filiais, cookies, headers):
        self.filiais = filiais
        self.cookies = cookies
        self.headers = headers

    def update_existing_records(self):
        updated_total = 0
        tz = pytz.timezone('America/Sao_Paulo')

        for filial in self.filiais:
            try:
                clean_invalid_ultima_verificacao(filial)
                debug_datetime_comparison(filial)

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                query = f'''
                SELECT "N__CTRC", "Unidade_Emissor", "CTRC_Identificador", "situacao_resumida",
                    {', '.join([f'"{column_mapping[col]}"' for col in required_columns])}
                FROM {filial['table']}
                WHERE (
                    "situacao_resumida" IN (
                        SELECT key FROM (SELECT json_object(
                            {', '.join([f'"{k}", {v}' for k, v in update_intervals.items() if v != 0])}
                        ) AS dict) AS temp,
                        json_each(dict, '$') AS entry
                    )
                    OR "situacao_resumida" IS NULL
                    OR "situacao_resumida" = ''
                    OR "situacao_resumida" NOT IN (
                        SELECT key FROM (SELECT json_object(
                            {', '.join([f'"{k}", {v}' for k, v in update_intervals.items()])}
                        ) AS dict) AS temp,
                        json_each(dict, '$') AS entry
                    )
                )
                AND (
                    "ultima_verificacao" IS NULL
                    OR datetime("ultima_verificacao") < datetime('now', 'localtime', '-' || (
                        SELECT COALESCE((
                            SELECT value FROM (SELECT json_object(
                                {', '.join([f'"{k}", {v}' for k, v in update_intervals.items()])}
                            ) AS dict) AS temp,
                            json_each(dict, '$') AS entry
                            WHERE key = "situacao_resumida"
                        ), 30)  -- Intervalo padrão de 30 minutos para situações não listadas
                    ) || ' minutes')
                    OR "situacao_resumida" IS NULL
                    OR "situacao_resumida" = ''
                )
                '''
                cursor.execute(query)
                records = cursor.fetchall()
                conn.close()
                print(f"Filial {filial['serie']}: Encontrados {len(records)} registros para atualização.")

                updated_count = 0
                with ThreadPoolExecutor(max_workers=10) as executor:
                    tasks = {executor.submit(self.process_record, filial, record, tz): record for record in records}
                    for future in as_completed(tasks):
                        result = future.result()
                        if result:
                            updated_count += 1
                print(f"Filial {filial['serie']}: {updated_count} registros atualizados.")
                updated_total += updated_count
            except Exception as e:
                print(f"Erro ao atualizar registros existentes para {filial['serie']}: {e}")
                if 'conn' in locals():
                    try:
                        conn.close()
                    except:
                        pass
        return updated_total

    def process_record(self, filial, record, tz):
        try:
            ctrc_number, unidade_emissor, ctrc_identificador, situacao_resumida = record[:4]
            existing_data = dict(zip([column_mapping[col] for col in required_columns], record[4:]))

            extracted_data, _ = process_ctrc(filial, ctrc_number, self.cookies, self.headers)
            if extracted_data:
                current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                extracted_data['ultima_verificacao'] = current_time
                extracted_data['CTRC_Identificador'] = ctrc_identificador

                needs_update = False
                for key in required_columns:
                    if key != 'ultima_verificacao' and extracted_data.get(key) != existing_data.get(key):
                        needs_update = True
                        break

                # Atualizar se a coluna situacao_resumida estiver vazia, independentemente do tempo
                if not situacao_resumida or needs_update:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    columns = ', '.join([f'"{column_mapping[col]}" = ?' for col in required_columns if col != 'CTRC_Identificador'])
                    update_sql = f'''
                    UPDATE {filial['table']}
                    SET {columns}
                    WHERE "CTRC_Identificador" = ?
                    '''
                    values = [extracted_data.get(col, '' if 'Tentativas de Entrega' not in col else 0 if col == 'ocorrencia_data_Tentativas de Entrega' else None) for col in required_columns if col != 'CTRC_Identificador']
                    values.append(ctrc_identificador)
                    cursor.execute(update_sql, values)
                    conn.commit()

                    cursor.execute(f'''
                    SELECT "Descrição_Situação", "Previsão_Entrega", "ocorrencia_data_Entregue",
                           "Remetente_Bairro", "Destinatário_Bairro", "Entrega_Bairro",
                           "ocorrencia_data_Data_de_Emissão_CTRC", "situacao_resumida", "Status",
                           "Destino_Código"
                    FROM {filial['table']}
                    WHERE "CTRC_Identificador" = ?
                    ''', (ctrc_identificador,))
                    updated_record = cursor.fetchone()
                    if updated_record:
                        descricao_situacao, previsao_entrega, ocorrencia_data_entregue, remetente_bairro, destinatario_bairro, entrega_bairro, data_emissao, situacao_resumida_atual, status, destino_codigo = updated_record
                        remetente_bairro = corrections.get(remetente_bairro, remetente_bairro) if remetente_bairro else remetente_bairro
                        destinatario_bairro = corrections.get(destinatario_bairro, destinatario_bairro) if destinatario_bairro else destinatario_bairro
                        entrega_bairro = corrections.get(entrega_bairro, entrega_bairro) if entrega_bairro else entrega_bairro

                        if status == "CANCELADO":
                            situacao_resumida = "CANCELADO"
                            leadtime = 0
                            situacao_prazo = "CANCELADO"
                        else:
                            inicio_descricao = extrair_inicio_descricao(descricao_situacao)
                            if inicio_descricao == "CT-E AUTORIZADO COM":
                                situacao_resumida = "DISPONÍVEL PARA ENTREGA" if destino_codigo == "VNA" else f"AGATD. TRANSF, DA UN VNA PARA UNIDADE DE {destino_codigo}"
                            else:
                                situacao_resumida = situacao_resumida_rules.get(inicio_descricao, "OUTRO")
                            resultado = calcular_leadtime_e_situacao_prazo(data_emissao, ocorrencia_data_entregue)
                            leadtime = resultado['LEADTIME']
                            situacao_prazo = resultado['situação_prazo']

                        changes = {}
                        if leadtime != existing_data['LEADTIME']:
                            changes['LEADTIME'] = {'antes': existing_data['LEADTIME'], 'depois': leadtime}
                        if situacao_prazo != existing_data['situação_prazo']:
                            changes['situação_prazo'] = {'antes': existing_data['situação_prazo'], 'depois': situacao_prazo}
                        if situacao_resumida != existing_data['situacao_resumida']:
                            changes['situacao_resumida'] = {'antes': existing_data['situacao_resumida'], 'depois': situacao_resumida}
                        if remetente_bairro != existing_data['Remetente_Bairro']:
                            changes['Remetente_Bairro'] = {'antes': existing_data['Remetente_Bairro'], 'depois': remetente_bairro}
                        if destinatario_bairro != existing_data['Destinatário_Bairro']:
                            changes['Destinatário_Bairro'] = {'antes': existing_data['Destinatário_Bairro'], 'depois': destinatario_bairro}
                        if entrega_bairro != existing_data['Entrega_Bairro']:
                            changes['Entrega_Bairro'] = {'antes': existing_data['Entrega_Bairro'], 'depois': entrega_bairro}

                        cursor.execute(f'''
                        UPDATE {filial['table']}
                        SET "LEADTIME" = ?, "situação_prazo" = ?, "situacao_resumida" = ?,
                            "Remetente_Bairro" = ?, "Destinatário_Bairro" = ?, "Entrega_Bairro" = ?,
                            "ultima_verificacao" = ?
                        WHERE "CTRC_Identificador" = ?
                        ''', (
                            leadtime, situacao_prazo, situacao_resumida,
                            remetente_bairro, destinatario_bairro, entrega_bairro,
                            current_time, ctrc_identificador
                        ))
                        conn.commit()

                        if changes:
                            print(f"Filial {filial['serie']}: CTRC {unidade_emissor} {ctrc_number} atualizado com alterações: {changes}")
                        else:
                            print(f"Filial {filial['serie']}: CTRC {unidade_emissor} {ctrc_number} sem alterações.")
                        conn.close()
                        return True
                    conn.close()
            return False
        except Exception as e:
            print(f"Erro ao processar CTRC {unidade_emissor} {ctrc_number}: {e}")
            if 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
            return False

class NewDataHandler:
    def __init__(self, filiais, cookies, headers):
        self.filiais = filiais
        self.cookies = cookies
        self.headers = headers

    def process_new_data(self):
        new_data_found = False
        batch_size = 10  # Aumentar o tamanho do lote
        batch = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = {}
            for filial in self.filiais:
                # Processar múltiplos CTRCs de uma vez
                for i in range(batch_size):  # Processar 10 CTRCs de uma vez
                    tasks[executor.submit(process_ctrc, filial, filial['current_number'] + i, self.cookies, self.headers)] = filial

            for future in as_completed(tasks):
                result, filial = future.result()
                current_time = time.time()
                filial['last_attempt_time'] = current_time
                if result is not None:
                    new_data_found = True
                    tz = pytz.timezone('America/Sao_Paulo')
                    current_time_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                    result['ultima_verificacao'] = current_time_str
                    batch.append((result, filial['table']))
                    filial['consecutive_empty'] = 0
                    filial['pause_until'] = 0
                    print(f"Filial: {filial['serie']}, CTRC: {result.get('N° CTRC', 'N/A')}, Remetente: {result.get('Remetente Nome', 'N/A')}, NF: {result.get('Número Nota Fiscal', 'N/A')}")
                    filial['current_number'] += 1
                else:
                    print(f"Nenhum dado novo encontrado para a filial {filial['serie']} no CTRC {filial['current_number']}")
                    filial['consecutive_empty'] += 1
                    if filial['consecutive_empty'] >= MAX_NO_DATA_ATTEMPTS:
                        filial['pause_until'] = current_time + PAUSE_DURATION
                        print(f"Filial {filial['serie']} pausada até {datetime.fromtimestamp(filial['pause_until']).strftime('%Y-%m-%d %H:%M:%S')}.")

        # Inserir dados em lote
        if batch:
            self.insert_data_batch(batch)

        return new_data_found

    def insert_data_batch(self, batch):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for extracted_data, table_name in batch:
                columns = ', '.join([f'"{column_mapping[col]}"' for col in required_columns])
                placeholders = ', '.join(['?' for _ in required_columns])
                insert_sql = f'INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})'
                values = [extracted_data.get(col, '' if 'Tentativas de Entrega' not in col else 0 if col == 'ocorrencia_data_Tentativas de Entrega' else None) for col in required_columns]
                cursor.execute(insert_sql, values)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao inserir dados em lote: {e}")

# Ciclo contínuo
filiais = [
    {'serie': 'VNA', 'table': 'ctrc_data_vna', 'start_number': '767000', 'current_number': None, 'last_attempt_time': 0, 'active': True, 'pause_until': 0, 'consecutive_empty': 0},
    {'serie': 'BHZ', 'table': 'ctrc_data_bhz', 'start_number': '556600', 'current_number': None, 'last_attempt_time': 0, 'active': True, 'pause_until': 0, 'consecutive_empty': 0},
    {'serie': 'SPA', 'table': 'ctrc_data_spa', 'start_number': '18650', 'current_number': None, 'last_attempt_time': 0, 'active': True, 'pause_until': 0, 'consecutive_empty': 0},
    {'serie': 'MRE', 'table': 'ctrc_data_mre', 'start_number': '199388', 'current_number': None, 'last_attempt_time': 0, 'active': True, 'pause_until': 0, 'consecutive_empty': 0},
]

db_path = 'ctrc_database.db'
JSON_FILE = 'unique_routes_with_ceps.json'

for filial in filiais:
    create_table(filial['table'])

for filial in filiais:
    last_serie, last_number = get_last_ctrc(filial['table'], filial)
    filial['current_number'] = int(last_number) if last_number else int(filial['start_number'])
    check_and_fill_gaps(filial, cookies, headers)

existing_data_handler = ExistingDataHandler(filiais, cookies, headers)
new_data_handler = NewDataHandler(filiais, cookies, headers)

last_token_refresh_time = time.time()
PAUSE_DURATION = 600
MAX_NO_DATA_ATTEMPTS = 3
all_paused_message_printed = False

# Dicionário para controlar os intervalos de busca de novos dados
new_data_intervals = {
    'VNA': 60,  # 1 hora
    'BHZ': 60,  # 1 hora
    'SPA': 60,  # 1 hora
    'MRE': 60,  # 1 hora
}

last_new_data_check = {filial['serie']: 0 for filial in filiais}

while True:
    current_time = time.time()
    active_filiais = False
    if current_time - last_token_refresh_time >= 20 * 60:
        print("Renovando token...")
        if refresh_token():
            print("Token renovado com sucesso.")
        else:
            print("Falha ao renovar token.")
        last_token_refresh_time = current_time
    filiais_to_process = []
    for filial in filiais:
        if filial['active'] and current_time >= filial['pause_until']:
            filiais_to_process.append(filial)
            active_filiais = True
    if not active_filiais:
        if not all_paused_message_printed:
            print("Todas as filiais estão pausadas. Aguardando retomada...")
            all_paused_message_printed = True
        continue
    else:
        all_paused_message_printed = False

    # Primeiro, buscar novos dados
    new_data_found = new_data_handler.process_new_data()

    # Só atualizar os dados existentes se não houver novos dados encontrados
    if not new_data_found:
        existing_data_handler.update_existing_records()

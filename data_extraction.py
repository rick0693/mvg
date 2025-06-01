import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

import time
import json

# Funções de formatação
def format_cnpj(cnpj):
    return re.sub(r'\D', '', cnpj) if cnpj else ''





def format_phone(phone):
    phone = re.sub(r'\D', '', phone) if phone else ''
    return f"{phone[:2]} {phone[2:]}" if phone else ''

def format_date_time(date_time_str):
    if not date_time_str or len(date_time_str.split()) < 2:
        return ''
    try:
        date_str, time_str = date_time_str.split()[:2]
        dt = datetime.strptime(f"{date_str} {time_str}", '%d/%m/%y %H:%M')
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            dt = datetime.strptime(f"{date_time_str}", '%d/%m/%Y %H:%M')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return ''

def format_date(date_str):
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%d/%m/%y')
        return dt.strftime('%Y-%m-%d 23:59:59')  # Incluir a hora padrão
    except ValueError:
        try:
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d 23:59:59')  # Incluir a hora padrão
        except ValueError:
            return ''

def format_decimal(value):
    if not value:
        return 0.0
    try:
        return float(value.replace('.', '').replace(',', '.'))
    except ValueError:
        return 0.0

def format_cte(cte):
    if not cte:
        return '0', '0'
    parts = cte.split()
    serie = parts[0].lstrip('0') or '0' if parts else '0'
    numero = ''.join(parts[1:]).lstrip('0') or '0' if len(parts) > 1 else '0'
    return serie, numero

def format_nota_fiscal(nota):
    if not nota or '/' not in nota:
        return '', ''
    try:
        serie, numero = nota.split('/')
        return serie, numero.lstrip('0') or '0'
    except ValueError:
        return '', ''

def format_volumes(vol_pares):
    if not vol_pares or '/' not in vol_pares:
        return 0
    try:
        vol, _ = vol_pares.split('/')
        return int(vol)
    except ValueError:
        return 0

def format_situacao_atual(situacao):
    if not situacao:
        return '', '', ''
    match = re.match(r'(\w+\s+\w+)\s+(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+(\S+)', situacao)
    if match:
        dominio, data, hora, codigo = match.groups()
        data_hora = format_date_time(f"{data} {hora}")
        return dominio, data_hora, codigo
    return situacao, '', ''

def format_remessa(remessa, data_hora):
    if not remessa or not data_hora or len(data_hora.split()) < 2:
        return remessa or '', ''
    try:
        data_str, hora_str = data_hora.split()[:2]
        return remessa, format_date_time(f"{data_str} {hora_str}")
    except ValueError:
        return remessa, ''

# Função auxiliar para dividir strings com segurança
def safe_split(text, separator, expected=2, default=''):
    if not text or separator not in text:
        return [default] * expected
    parts = text.split(separator)
    if len(parts) < expected:
        parts.extend([default] * (expected - len(parts)))
    return parts

# Função auxiliar para extrair texto com segurança
def safe_text(element):
    return element.text.strip() if element and element.text.strip() else ''

# Função para extrair e formatar dados do HTML
def extract_data_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    if not soup.find("div", style="text-align:left;left:160px;top:80px;"):
        return None

    data = {}

    ctrc_number = safe_text(soup.find("div", style="text-align:left;left:160px;top:80px;"))
    if ctrc_number:
        match = re.match(r'([A-Za-z]+)(\d+)-(\d)', ctrc_number)
        if match:
            data['Unidade Emissor'] = match.group(1)
            data['N° CTRC'] = match.group(2)
            data['Dígito Verificador'] = match.group(3)
        else:
            data['Unidade Emissor'] = ''
            data['N° CTRC'] = ''
            data['Dígito Verificador'] = ''

    data['Tipo Operação'] = safe_text(soup.find("div", style="text-align:left;left:256px;top:64px;color:darkred;")) or 'NORMAL'
    data['Sequência CTRC'] = safe_text(soup.find("div", style="text-align:left;left:648px;top:64px;color:#777;"))
    cte = safe_text(soup.find("a", id="link_cte_rps"))
    data['Série CT-e'], data['Número CT-e'] = format_cte(cte)
    data['Status'] = safe_text(soup.find("div", style="text-align:left;left:504px;top:96px;color:red;"))
    situacao = safe_text(soup.find("div", style="text-align:left;left:64px;top:672px;"))
    data['Domínio/Origem'], data['Situação Data/Hora'], data['Código Situação'] = format_situacao_atual(situacao)
    data['Descrição Situação'] = safe_text(soup.find("div", id="descricao"))
    data['Domínio'] = safe_text(soup.find("div", style="text-align:left;left:776px;top:64px;"))
    data['Empresa'] = safe_text(soup.find("div", style="text-align:left;left:896px;top:64px;"))
    inclusao = safe_text(soup.find("div", style="text-align:left;left:160px;top:112px;"))
    data['Inclusão Data/Hora'] = format_date_time(inclusao)
    data['Usuário Inclusão'] = safe_text(soup.find("div", style="text-align:left;left:256px;top:112px;"))
    emissao = safe_text(soup.find("div", style="left:400px;top:96px;width:96px;color:red;"))
    data['Emissão Data/Hora'] = format_date_time(emissao)
    data['Previsão Entrega'] = format_date(safe_text(soup.find("div", style="text-align:left;left:776px;top:112px;")))
    data['Prazo Unidade Destinatária'] = format_date(safe_text(soup.find("div", style="text-align:left;left:776px;top:144px;")))
    data['Destino'] = safe_text(soup.find("div", style="text-align:left;left:776px;top:96px;color:darkred;")).replace('  ', ' ')

    nota = safe_text(soup.find("div", style="text-align:left;left:160px;top:128px;"))
    data['Série Nota Fiscal'], data['Número Nota Fiscal'] = format_nota_fiscal(nota)
    data['Quantidade Volumes'] = format_volumes(safe_text(soup.find("div", style="text-align:left;left:160px;top:144px;")))
    data['Tipo Mercadoria'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:160px;")).split('-')[-1] if '-' in safe_text(soup.find("div", style="text-align:left;left:160px;top:160px;")) else ''
    data['Peso Cálculo (Kg)'] = format_decimal(safe_text(soup.find("div", style="text-align:left;left:160px;top:176px;")))
    data['Peso Real (Kg)'] = format_decimal(safe_text(soup.find("div", style="text-align:left;left:504px;top:176px;")))
    data['Cubagem (m³)'] = format_decimal(safe_text(soup.find_all("div", style="text-align:left;left:776px;top:176px;")[-1]))
    data['Valor Nota Fiscal (R$)'] = format_decimal(safe_text(soup.find("div", style="text-align:left;left:160px;top:192px;")))
    data['Valor Frete (R$)'] = format_decimal(safe_text(soup.find("div", style="text-align:left;left:160px;top:208px;color:darkred;")))
    data['ICMS/ISS (R$)'] = format_decimal(safe_text(soup.find("div", style="text-align:left;left:160px;top:224px;")))
    data['Tipo Cobrança'] = safe_text(soup.find("div", style="text-align:left;left:504px;top:224px;")).replace('CIF', 'CIF').split('<')[0]
    data['Situação Liquidação'] = safe_text(soup.find("div", style="text-align:left;left:504px;top:208px;color:darkred;"))

    data['Remetente Nome'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:256px;")).replace(' (..)', '')
    data['Remetente CNPJ'] = format_cnpj(safe_text(soup.find("a", id="link_cli_rem")))
    data['Remetente Endereço'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:368px;'))
    data['Remetente Complemento'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:384px;'))
    data['Remetente Bairro'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:400px;'))
    cep_cidade = safe_text(soup.find("div", style="text-align:left;left:160px;top:288px;")).split()
    data['Remetente CEP'] = cep_cidade[0] if cep_cidade else ''
    data['Remetente Cidade'] = cep_cidade[-1].split('/')[0] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Remetente UF'] = cep_cidade[-1].split('/')[-1] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Remetente Telefone'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:160px;top:304px;")))

    data['Destinatário Nome'] = safe_text(soup.find("div", style="text-align:left;left:504px;top:256px;"))
    data['Destinatário CNPJ'] = format_cnpj(safe_text(soup.find("a", id="link_cli_dest")))
    data['Destinatário Endereço'] = safe_text(soup.find('div', style='text-align:left;left:504px;top:368px;'))
    complemento = safe_text(soup.find("div", style="text-align:left;left:504px;top:384px;"))
    data['Destinatário Complemento'] = '[Nenhum]' if complemento.startswith('CEL') else complemento
    data['Destinatário Bairro'] = safe_text(soup.find('div', style='text-align:left;left:504px;top:400px;'))
    cep_cidade = safe_text(soup.find("div", style="text-align:left;left:504px;top:288px;")).split()
    data['Destinatário CEP'] = cep_cidade[0] if cep_cidade else ''
    data['Destinatário Cidade'] = cep_cidade[-1].split('/')[0] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Destinatário UF'] = cep_cidade[-1].split('/')[-1] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Destinatário Telefone'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:504px;top:304px;")))
    data['Destinatário Celular'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:696px;top:304px;")))

    data['Expedidor Nome'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:336px;"))
    data['Expedidor CNPJ'] = format_cnpj(safe_text(soup.find("a", id="link_cli_exp")))
    data['Expedidor Endereço'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:368px;'))
    data['Expedidor Complemento'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:384px;'))
    data['Expedidor Bairro'] = safe_text(soup.find('div', style='text-align:left;left:160px;top:400px;'))
    cep_cidade = safe_text(soup.find("div", style="text-align:left;left:160px;top:416px;")).split()
    data['Expedidor CEP'] = cep_cidade[0] if cep_cidade else ''
    data['Expedidor Cidade'] = cep_cidade[-1].split('/')[0] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Expedidor UF'] = cep_cidade[-1].split('/')[-1] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Expedidor Telefone'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:160px;top:432px;")))

    data['Entrega Nome'] = safe_text(soup.find("div", style="text-align:left;left:504px;top:336px;"))
    data['Entrega CNPJ'] = format_cnpj(safe_text(soup.find("a", id="link_cli_ent")))
    data['Entrega Endereço'] = safe_text(soup.find('div', style='text-align:left;left:504px;top:368px;'))
    data['Entrega Complemento'] = '[Nenhum]' if complemento.startswith('CEL') else complemento
    data['Entrega Bairro'] = safe_text(soup.find('div', style='text-align:left;left:504px;top:400px;'))
    cep_cidade = safe_text(soup.find("div", style="text-align:left;left:504px;top:416px;")).split()
    data['Entrega CEP'] = cep_cidade[0] if cep_cidade else ''
    data['Entrega Cidade'] = cep_cidade[-1].split('/')[0] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Entrega UF'] = cep_cidade[-1].split('/')[-1] if cep_cidade and '/' in cep_cidade[-1] else ''
    data['Entrega Telefone'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:504px;top:432px;")))
    data['Entrega Celular'] = format_phone(safe_text(soup.find("div", style="text-align:left;left:696px;top:432px;")))

    data['Pagador Nome'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:464px;")).replace(' (..)', '')
    data['Pagador CNPJ'] = format_cnpj(safe_text(soup.find("a", id="link_cli_pag")))

    origem = safe_text(soup.find("div", style="text-align:left;left:160px;top:512px;"))
    data['Origem Código'], rest = safe_split(origem, ' / ', 2, '')
    data['Origem UF'], data['Origem Cidade'] = safe_split(rest, ' - ', 2, '')
    destino = safe_text(soup.find("div", style="text-align:left;left:160px;top:528px;"))
    data['Destino Código'], rest = safe_split(destino, ' / ', 2, '')
    data['Destino UF'], data['Destino Cidade'] = safe_split(rest, ' - ', 2, '')
    data['CFOP'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:544px;"))
    data['Veículo Coleta'] = safe_text(soup.find("div", style="text-align:left;left:776px;top:160px;"))
    conferente = safe_text(soup.find("div", style="text-align:left;left:504px;top:144px;"))
    data['Conferente Coleta'] = ' '.join(conferente.split()[1:]) if conferente else ''
    romaneio = safe_text(soup.find("div", style="text-align:left;left:568px;top:464px;"))
    data['Romaneio Número'], data['Placa Entrega'] = safe_split(romaneio, '/', 2, '')
    remessa = safe_text(soup.find("div", style="text-align:left;left:568px;top:480px;"))
    data_hora = safe_text(soup.find("div", style="text-align:left;left:688px;top:480px;"))
    data['Código Remessa'], data['Remessa Data/Hora'] = format_remessa(remessa, data_hora)

    data['Observação'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:560px;color:darkred;")) or '[Nenhuma]'
    data['Instrução Entrega'] = safe_text(soup.find("div", style="text-align:left;left:160px;top:640px;color:darkred;")) or '[Nenhuma]'

    return data

# Função para extrair a chave da NF
def extract_nf_key(cookies, headers, seq_ctrc):
    data = {
        'act': 'A',
        'aviso_resgate': '#aviso_resgate#',
        'g_ctrc_ser_ctrc': '',
        'g_ctrc_nro_ctrc': '0',
        'gw_nro_nf_ini': '',
        'g_ctrc_nf_vol_ini': '0',
        'gw_ctrc_nr_sscc': '',
        'g_ctrc_nro_ctl_form': '0',
        'gw_ctrc_parc_nro_ctrc_parc': '0',
        'g_ctrc_c_chave_fis': '',
        'gw_gaiola_codigo': '0',
        'gw_pallet_codigo': '0',
        'local': 'Q',
        'data_ini_inf': '9/2/25',
        'data_fin_inf': datetime.now().strftime('%d/%m/%y'),
        'seq_ctrc': seq_ctrc,
        'FAMILIA': 'RDM',
        'dummy': str(int(time.time() * 1000)),
    }

    try:
        response = requests.post('https://sistema.ssw.inf.br/bin/ssw0053', cookies=cookies, headers=headers, data=data)
        html_content = response.text
        pattern = r"portal_nfe\('(\d{44})'\)"
        match = re.search(pattern, html_content)
        return match.group(1) if match else ''
    except Exception as e:
        print(f"Erro ao extrair chave NF: {e}")
        return ''

# Função para verificar comprovante de entrega
def check_delivery_receipt(cookies, headers, seq_ctrc):
    data = {
        'act': 'O',
        'aviso_resgate': '#aviso_resgate#',
        'g_ctrc_ser_ctrc': '',
        'g_ctrc_nro_ctrc': '0',
        'gw_nro_nf_ini': '',
        'g_ctrc_nf_vol_ini': '0',
        'gw_ctrc_nr_sscc': '',
        'g_ctrc_nro_ctl_form': '0',
        'gw_ctrc_parc_nro_ctrc_parc': '0',
        'g_ctrc_c_chave_fis': '',
        'gw_gaiola_codigo': '0',
        'gw_pallet_codigo': '0',
        'local': 'Q',
        'data_ini_inf': '9/2/25',
        'data_fin_inf': datetime.now().strftime('%d/%m/%y'),
        'seq_ctrc': seq_ctrc,
        'FAMILIA': 'RDM',
        'dummy': str(int(time.time() * 1000)),
    }

    try:
        response = requests.post('https://sistema.ssw.inf.br/bin/ssw0053', cookies=cookies, headers=headers, data=data)
        soup = BeautifulSoup(response.text, 'html.parser')
        image_references = soup.find_all('f9')
        return "SIM" if any('Imagem' in ref.text for ref in image_references) else "NAO"
    except Exception as e:
        print(f"Erro ao verificar comprovante de entrega: {e}")
        return "NAO"

# Função para extrair informações de rastreamento
def extract_tracking_info(cookies, headers, seq_ctrc):
    data = {
        'act': 'O',
        'aviso_resgate': '#aviso_resgate#',
        'g_ctrc_ser_ctrc': '',
        'g_ctrc_nro_ctrc': '0',
        'gw_nro_nf_ini': '0',
        'g_ctrc_nf_vol_ini': '0',
        'gw_ctrc_nr_sscc': '',
        'g_ctrc_nro_ctl_form': '',
        'gw_ctrc_parc_nro_ctrc_parc': '0',
        'g_ctrc_c_chave_fis': '',
        'gw_gaiola_codigo': '0',
        'gw_pallet_codigo': '0',
        'local': 'Q',
        'data_ini_inf': '9/2/25',
        'data_fin_inf': datetime.now().strftime('%d/%m/%y'),
        'seq_ctrc': seq_ctrc,
        'FAMILIA': 'RDM',
        'dummy': str(int(time.time() * 1000)),
    }

    try:
        response = requests.post('https://sistema.ssw.inf.br/bin/ssw0053', cookies=cookies, headers=headers, data=data)
        if response.status_code == 200 and response.text:
            soup = BeautifulSoup(response.text, 'lxml')

            tracking_data = {
                "ocorrencia_data_Data de Emissão CTRC": "",
                "ocorrencia_data_Saída de Unidade": "",
                "ocorrencia_data_Chegada em Unidade de Entrega": "",
                "ocorrencia_data_Saída para Entrega": "",
                "ocorrencia_data_Entregue": "",
                "ocorrencia_data_Tentativas de Entrega": 0
            }

            xml_data = soup.find('xml', id='xmlsr')

            if xml_data:
                records = xml_data.find_all('r')

                for record in records:
                    data_hora_registro = record.f3.text.strip() if record.f3 else ""
                    if data_hora_registro:
                        data_hora_registro = format_date_time(data_hora_registro)
                    status_resumido = record.f10.text.strip() if record.f10 else ""

                    if status_resumido == "80 - DOCUMENTO DE TRANSPORTE EMITIDO":
                        tracking_data["ocorrencia_data_Data de Emissão CTRC"] = data_hora_registro
                    elif status_resumido == "82 - SAIDA DE UNIDADE":
                        tracking_data["ocorrencia_data_Saída de Unidade"] = data_hora_registro
                    elif status_resumido == "84 - CHEGADA EM UNIDADE DE ENTREGA":
                        tracking_data["ocorrencia_data_Chegada em Unidade de Entrega"] = data_hora_registro
                    elif status_resumido == "85 - SAIDA PARA ENTREGA":
                        tracking_data["ocorrencia_data_Tentativas de Entrega"] += 1
                        if not tracking_data["ocorrencia_data_Saída para Entrega"] or data_hora_registro > tracking_data["ocorrencia_data_Saída para Entrega"]:
                            tracking_data["ocorrencia_data_Saída para Entrega"] = data_hora_registro
                    elif status_resumido == "01 - MERCADORIA ENTREGUE":
                        tracking_data["ocorrencia_data_Entregue"] = data_hora_registro

            return tracking_data
        return None
    except Exception as e:
        print(f"Erro ao extrair informações de rastreamento: {e}")
        return None

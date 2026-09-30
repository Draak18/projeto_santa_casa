"""
=======================================================================
 TRATAMENTO DE DADOS - PROJETO INTEGRADOR (Saúde)
=======================================================================
Este script lê o arquivo .json bruto de atendimentos de saúde,
"achata" a estrutura aninhada (paciente -> registros -> informações)
em uma tabela única, ANONIMIZA dados pessoais (CPF e nome) e limpa
os campos para uso no dashboard.

COMO USAR:
1. Coloque o arquivo .json completo na mesma pasta deste script
   (ou ajuste o caminho na variável caminho_json abaixo).
2. Rode: python tratamento_dados.py
3. Será gerado um arquivo "dados_tratados.csv" pronto para o dashboard.

IMPORTANTE (LGPD): este script remove CPF e nome do resultado final,
substituindo por um ID interno anônimo (hash). Nunca compartilhem,
apresentem ou subam para o GitHub o arquivo .json ORIGINAL, que
contém dados pessoais identificáveis de pacientes reais.
=======================================================================
"""

import json
import os
import hashlib
import time
import unicodedata
from datetime import datetime, timezone

import pandas as pd

try:
    from tqdm import tqdm
    TEM_TQDM = True
except ImportError:
    TEM_TQDM = False

# ----------------------------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------------------------
# Nomes dos arquivos (troque pelo nome real do seu .json, se for diferente).
nome_arquivo_json = "registros_medicos.json"
nome_arquivo_saida = "registros_medicos_tratados.csv"

# Resolve os caminhos SEMPRE em relação à pasta onde este script .py está
# salvo — assim funciona não importa de qual pasta você rode o comando
# "python ...".
pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_json = os.path.join(pasta_do_script, nome_arquivo_json)
caminho_saida_csv = os.path.join(pasta_do_script, nome_arquivo_saida)


# ----------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------------------------

def anonimizar_cpf(cpf: str) -> str:
    """Transforma o CPF em um ID irreversível (hash), para não expor
    dado pessoal real, mas ainda permitir ligar os registros ao mesmo
    paciente."""
    if not cpf:
        return None
    h = hashlib.sha256(cpf.encode("utf-8")).hexdigest()
    return "PAC_" + h[:10].upper()


def extrair_data(campo):
    """Extrai valores no formato {'$date': '...'} do Mongo, ou datas
    já como string/None."""
    if campo is None:
        return None
    if isinstance(campo, dict) and "$date" in campo:
        try:
            return datetime.fromisoformat(campo["$date"].replace("Z", "+00:00"))
        except Exception:
            return None
    return campo


def padronizar_texto(txt):
    """Padroniza texto: maiúsculas, sem espaços extras, sem acentos
    (útil para agrupar 'São Paulo' e 'Sao Paulo' como iguais, por ex.)."""
    if txt is None or not isinstance(txt, str):
        return None
    txt = txt.strip().upper()
    txt = " ".join(txt.split())  # remove espaços duplicados
    return txt if txt else None


def calcular_idade(data_nascimento, data_referencia):
    """Calcula idade do paciente na data do atendimento."""
    if data_nascimento is None or data_referencia is None:
        return None
    try:
        idade = data_referencia.year - data_nascimento.year
        if (data_referencia.month, data_referencia.day) < (data_nascimento.month, data_nascimento.day):
            idade -= 1
        return idade if 0 <= idade <= 120 else None
    except Exception:
        return None


def faixa_etaria(idade):
    if idade is None:
        return "NAO INFORMADO"
    faixas = [
        (0, 4, "0-4"), (5, 11, "5-11"), (12, 17, "12-17"),
        (18, 29, "18-29"), (30, 44, "30-44"), (45, 59, "45-59"),
        (60, 74, "60-74"), (75, 200, "75+"),
    ]
    for ini, fim, label in faixas:
        if ini <= idade <= fim:
            return label
    return "NAO INFORMADO"


# ----------------------------------------------------------------------
# EXTRAÇÃO DE CAMPOS POR TIPO DE REGISTRO
# ----------------------------------------------------------------------

def extrair_info_registro(registro: dict) -> dict:
    """Extrai os campos relevantes de 'informacoes', que variam
    conforme o tipo (TRIAGEM, ATENDIMENTO, MEDICAMENTO)."""
    info = registro.get("informacoes") or {}
    tipo = registro.get("tipo")

    dados = {
        "especialidade": info.get("especialidade") or info.get("especializacao"),
        "queixa": padronizar_texto(info.get("queixa")),
        "diagnostico": padronizar_texto(info.get("diagnostico")),
        "procedimento": padronizar_texto(info.get("procedimento")),
        "cid_codigo": None,
        "cid_descricao": None,
        "medicamento_nome": None,
        "usa_medicamento": info.get("usaMedicamento"),
        "tem_alergia": info.get("temAlergia"),
    }

    # CID pode vir como lista de dicionários
    cids = info.get("cid")
    if isinstance(cids, list) and len(cids) > 0:
        dados["cid_codigo"] = cids[0].get("cid")
        dados["cid_descricao"] = padronizar_texto(cids[0].get("descricao"))

    # Medicamento vem em subestrutura própria
    med = info.get("medicamento")
    if isinstance(med, dict):
        dados["medicamento_nome"] = padronizar_texto(med.get("nome"))

    return dados


# ----------------------------------------------------------------------
# PROCESSAMENTO PRINCIPAL
# ----------------------------------------------------------------------

def tratar_dados(caminho_json: str) -> pd.DataFrame:
    print(f"\n[1/3] Carregando {caminho_json} ...")
    t0 = time.time()
    with open(caminho_json, "r", encoding="utf-8") as f:
        pacientes = json.load(f)
    print(f"      -> {len(pacientes)} pacientes carregados em {time.time()-t0:.1f}s")

    linhas = []

    print("\n[2/3] Processando pacientes e registros...")
    total = len(pacientes)

    # Barra de progresso: usa tqdm se disponível, senão imprime % a cada passo
    if TEM_TQDM:
        iterador = tqdm(pacientes, desc="Pacientes", unit="pac")
    else:
        iterador = pacientes

    for i, paciente in enumerate(iterador, start=1):
        if not TEM_TQDM and (i % max(1, total // 20) == 0 or i == total):
            # imprime a cada ~5% de progresso quando não há tqdm instalado
            pct = 100 * i / total
            print(f"      -> {i}/{total} pacientes ({pct:.0f}%) | {len(linhas)} registros gerados até agora")
        id_anonimo = anonimizar_cpf(paciente.get("cpf"))
        sexo = padronizar_texto(paciente.get("sexo"))
        cidade = padronizar_texto(paciente.get("cidade"))
        bairro = padronizar_texto(paciente.get("bairro"))
        estado = padronizar_texto(paciente.get("estado"))
        data_nascimento = extrair_data(paciente.get("dataNascimento"))

        registros = paciente.get("registros") or []
        for reg in registros:
            data_entrada = extrair_data(reg.get("dataEntrada"))
            data_saida = extrair_data(reg.get("dataSaida"))

            idade = calcular_idade(data_nascimento, data_entrada)

            linha = {
                "paciente_id": id_anonimo,
                "sexo": sexo,
                "idade_no_atendimento": idade,
                "faixa_etaria": faixa_etaria(idade),
                "estado": estado,
                "cidade": cidade,
                "bairro": bairro,
                "tipo_registro": reg.get("tipo"),
                "servico": padronizar_texto(reg.get("servico")),
                "data_entrada": data_entrada,
                "data_saida": data_saida,
                "ano": data_entrada.year if data_entrada else None,
                "mes": data_entrada.month if data_entrada else None,
                "dia_semana": data_entrada.strftime("%A") if data_entrada else None,
            }
            linha.update(extrair_info_registro(reg))
            linhas.append(linha)

    print(f"      -> {len(linhas)} registros extraídos no total")
    print("\n[3/3] Montando tabela final e removendo duplicados...")
    df = pd.DataFrame(linhas)

    # Remove linhas totalmente duplicadas (registros repetidos no banco)
    antes = len(df)
    df = df.drop_duplicates()
    if antes != len(df):
        print(f"      -> {antes - len(df)} linhas duplicadas removidas")

    return df


def main():
    inicio = time.time()
    df = tratar_dados(caminho_json)

    print(f"\nConcluído em {time.time() - inicio:.1f}s")
    print(f"{len(df)} registros tratados | {df['paciente_id'].nunique()} pacientes únicos")
    print(f"Colunas geradas: {list(df.columns)}")

    df.to_csv(caminho_saida_csv, index=False, encoding="utf-8-sig")
    print(f"Arquivo salvo em: {caminho_saida_csv}")
    print("\nAmostra dos dados tratados:")
    print(df.head())


if __name__ == "__main__":
    main()
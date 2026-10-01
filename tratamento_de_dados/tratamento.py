import json
import os
import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    from tqdm import tqdm
    tem_tqdm = True
except ImportError:
    tem_tqdm = False

nome_arquivo_json = "registros_medicos.json"
nome_arquivo_saida = "registros_medicos_tratados.csv"

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_json = os.path.join(pasta_do_script, nome_arquivo_json)
caminho_saida_csv = os.path.join(pasta_do_script, nome_arquivo_saida)

faixas_etarias = [(4, "0-4"), (11, "5-11"), (17, "12-17"), (29, "18-29"), (44, "30-44"), (59, "45-59"), (74, "60-74"), (200, "75+")]


def anonimizar_cpf(cpf):
    if not cpf:
        return None
    return "pac_" + hashlib.sha256(cpf.encode()).hexdigest()[:10]


def extrair_data(campo):
    if not isinstance(campo, dict) or "$date" not in campo:
        return None
    valor = campo["$date"]
    if isinstance(valor, str):
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if isinstance(valor, dict) and "$numberLong" in valor:
        valor = int(valor["$numberLong"])
    if isinstance(valor, (int, float)):
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=valor)
    return None


def padronizar(txt):
    if not isinstance(txt, str):
        return None
    txt = " ".join(txt.split()).upper()
    txt = txt.strip(". ")
    return txt or None


def calcular_idade(nascimento, referencia):
    if not nascimento or not referencia:
        return None
    idade = referencia.year - nascimento.year
    if (referencia.month, referencia.day) < (nascimento.month, nascimento.day):
        idade -= 1
    return idade if 0 <= idade <= 120 else None


def faixa_etaria(idade):
    if idade is None:
        return "NAO INFORMADO"
    return next(label for limite, label in faixas_etarias if idade <= limite)


def extrair_info(registro):
    info = registro.get("informacoes") or {}
    cids = info.get("cid") or []
    medicamento = info.get("medicamento") or {}
    return {
        "especialidade": info.get("especialidade") or info.get("especializacao"),
        "queixa": padronizar(info.get("queixa")),
        "diagnostico": padronizar(info.get("diagnostico")),
        "procedimento": padronizar(info.get("procedimento")),
        "cid_codigo": cids[0].get("cid") if cids else None,
        "cid_descricao": padronizar(cids[0].get("descricao")) if cids else None,
        "medicamento_nome": padronizar(medicamento.get("nome")),
        "usa_medicamento": info.get("usaMedicamento"),
        "tem_alergia": info.get("temAlergia"),
    }


def tratar_dados():
    print(f"\nLendo o arquivo: '{caminho_json}'")
    with open(caminho_json, "r", encoding="utf-8") as f:
        pacientes = json.load(f)
    print(f"[Pacientes encontrados: {len(pacientes)} ]\n")

    linhas = []
    for paciente in (tqdm(pacientes, desc="Processando") if tem_tqdm else pacientes): # type: ignore
        id_paciente = anonimizar_cpf(paciente.get("cpf"))
        nascimento = extrair_data(paciente.get("dataNascimento"))

        for reg in paciente.get("registros") or []:
            data_entrada = extrair_data(reg.get("dataEntrada"))
            idade = calcular_idade(nascimento, data_entrada)

            linha = {
                "paciente_id": id_paciente,
                "sexo": padronizar(paciente.get("sexo")),
                "idade": idade,
                "faixa_etaria": faixa_etaria(idade),
                "cidade": padronizar(paciente.get("cidade")),
                "bairro": padronizar(paciente.get("bairro")),
                "tipo_registro": reg.get("tipo"),
                "servico": padronizar(reg.get("servico")),
                "data_entrada": data_entrada,
                "ano": data_entrada.year if data_entrada else None,
                "mes": data_entrada.month if data_entrada else None,
            }
            linha.update(extrair_info(reg))
            linhas.append(linha)

    tabela = pd.DataFrame(linhas).drop_duplicates()

    for coluna in ["idade", "ano", "mes"]:
        tabela[coluna] = tabela[coluna].astype("Int64")
    return tabela


if __name__ == "__main__":
    tabela = tratar_dados()
    tabela.to_csv(caminho_saida_csv, index=False, encoding="utf-8-sig")
    print(f"[Quantidade real de pacientes: {tabela['paciente_id'].nunique()}]")

    titulo = "Mostruário da Tabela"
    print(f"\n{titulo}\n{'=' * len(titulo)}")
    print(tabela.head(3).T)
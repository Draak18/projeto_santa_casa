import json
import os
import hashlib
import re
from datetime import datetime, timedelta, timezone

import pandas as pd


try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


nome_arquivo_json = "registros_medicos.json"
nome_arquivo_saida = "registros_medicos_tratados.csv"

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_json = os.path.join(pasta_do_script, nome_arquivo_json)
caminho_saida_csv = os.path.join(pasta_do_script, nome_arquivo_saida)

faixas_etarias = [
    (4, "0-4"),
    (11, "5-11"),
    (17, "12-17"),
    (29, "18-29"),
    (44, "30-44"),
    (59, "45-59"),
    (74, "60-74"),
    (200, "75+"),
]

# Siglas que devem continuar em maiúsculas nos nomes exibidos.
siglas = {
    "UPA", "UBS", "SAMU", "SUS", "CAPS", "CEO", "CID",
    "UTI", "HIV", "AVC", "PCR", "RX", "USG", "TC", "RM",
}


def anonimizar_cpf(cpf):
    """Substitui o CPF por um identificador irreversível para a dashboard."""
    if not cpf:
        return None
    return "pac_" + hashlib.sha256(cpf.encode()).hexdigest()[:10]


def extrair_data(campo):
    """Converte datas do formato exportado pelo MongoDB para datetime."""
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


def padronizar_texto(txt):
    """Normaliza textos clínicos para manter consistência na análise."""
    if not isinstance(txt, str):
        return None
    txt = " ".join(txt.split()).strip(". ").upper()
    return txt or None


def padronizar_categoria(txt):
    """Padroniza nomes de categorias em Title Case, preservando siglas."""
    if not isinstance(txt, str):
        return None

    txt = " ".join(txt.split()).strip(" .")
    if not txt:
        return None

    if txt.casefold() in {"nao informado", "não informado"}:
        return "Não Informado"

    txt = txt.title()

    # Restaura siglas conhecidas que .title() transformaria em iniciais maiúsculas.
    for sigla in siglas:
        txt = re.sub(
            rf"\b{re.escape(sigla.title())}\b",
            sigla,
            txt,
            flags=re.IGNORECASE,
        )

    return txt


def calcular_idade(nascimento, referencia):
    """Calcula a idade do paciente na data do atendimento."""
    if not nascimento or not referencia:
        return None

    idade = referencia.year - nascimento.year
    if (referencia.month, referencia.day) < (nascimento.month, nascimento.day):
        idade -= 1

    return idade if 0 <= idade <= 120 else None


def faixa_etaria(idade):
    """Agrupa a idade em uma faixa etária."""
    if idade is None:
        return "Não Informado"
    return next(label for limite, label in faixas_etarias if idade <= limite)


def extrair_info(registro):
    """Extrai e padroniza as informações complementares do atendimento."""
    info = registro.get("informacoes") or {}
    cids = info.get("cid") or []
    medicamento = info.get("medicamento") or {}

    return {
        "especialidade": padronizar_categoria(
            info.get("especialidade") or info.get("especializacao")
        ),
        "queixa": padronizar_texto(info.get("queixa")),
        "diagnostico": padronizar_texto(info.get("diagnostico")),
        "procedimento": padronizar_texto(info.get("procedimento")),
        "cid_codigo": cids[0].get("cid") if cids else None,
        "cid_descricao": padronizar_texto(cids[0].get("descricao")) if cids else None,
        "medicamento_nome": padronizar_categoria(medicamento.get("nome")),
        "usa_medicamento": info.get("usaMedicamento"),
        "tem_alergia": info.get("temAlergia"),
    }


def resolver_data(registro, data_por_atendimento):
    """Procura a data em dataEntrada, no atendimento vinculado ou em dataCadastro."""
    data = extrair_data(registro.get("dataEntrada"))
    if data:
        return data, "original"

    atendimento_id = (registro.get("informacoes") or {}).get("atendimentoId")
    if atendimento_id in data_por_atendimento:
        return data_por_atendimento[atendimento_id], "atendimento_vinculado"

    data = extrair_data(registro.get("dataCadastro"))
    return (data, "data_cadastro") if data else (None, "ausente")


def tratar_dados():
    print(f"\nLendo o arquivo: '{caminho_json}'")
    with open(caminho_json, "r", encoding="utf-8") as arquivo:
        pacientes = json.load(arquivo)

    print(f"[Pacientes encontrados: {len(pacientes)}]\n")

    linhas = []

    iterador = tqdm(pacientes, desc="Processando") if tqdm is not None else pacientes

    for paciente in iterador:
        id_paciente = anonimizar_cpf(paciente.get("cpf"))
        nascimento = extrair_data(paciente.get("dataNascimento"))
        registros = paciente.get("registros") or []

        # Relaciona cada atendimento à primeira data válida encontrada.
        data_por_atendimento = {}
        for registro in registros:
            data = extrair_data(registro.get("dataEntrada"))
            atendimento_id = (registro.get("informacoes") or {}).get("atendimentoId")

            if data and atendimento_id is not None and atendimento_id not in data_por_atendimento:
                data_por_atendimento[atendimento_id] = data

        for registro in registros:
            data_entrada, origem_data = resolver_data(registro, data_por_atendimento)
            idade = calcular_idade(nascimento, data_entrada)

            linha = {
                "paciente_id": id_paciente,
                "sexo": padronizar_categoria(paciente.get("sexo")),
                "idade": idade,
                "faixa_etaria": faixa_etaria(idade),
                "cidade": padronizar_categoria(paciente.get("cidade")),
                "bairro": padronizar_categoria(paciente.get("bairro")),
                "tipo_registro": padronizar_categoria(registro.get("tipo")),
                "servico": padronizar_categoria(registro.get("servico")),
                "data_entrada": data_entrada,
                "origem_data": origem_data,
                "ano": data_entrada.year if data_entrada else None,
                "mes": data_entrada.month if data_entrada else None,
            }

            linha.update(extrair_info(registro))
            linhas.append(linha)

    tabela = pd.DataFrame(linhas).drop_duplicates()

    for coluna in ["idade", "ano", "mes"]:
        tabela[coluna] = tabela[coluna].astype("Int64")

    return tabela


if __name__ == "__main__":
    tabela = tratar_dados()
    tabela.to_csv(caminho_saida_csv, index=False, encoding="utf-8-sig")

    print(f"[Quantidade real de pacientes: {tabela['paciente_id'].nunique()}]")

    titulo = "Mostruário da tabela"
    print(f"\n{titulo}\n{'=' * len(titulo)}")
    print(tabela.head(3).T)

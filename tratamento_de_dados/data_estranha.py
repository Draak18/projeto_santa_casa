"""
Acha registros com dataEntrada fora de uma faixa razoavel (ex: ano 840),
direto no .json bruto - util pra achar a origem do problema, ja que no
csv tratado o paciente_id ja esta anonimizado e nao da pra rastrear.

Uso: coloque na mesma pasta do registros_medicos.json e rode:
python achar_datas_estranhas.py
"""

import json
import os
from datetime import datetime, timedelta, timezone

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_json = os.path.join(pasta_do_script, "registros_medicos.json")

limite_antigo = datetime(2000, 1, 1, tzinfo=timezone.utc)
limite_futuro = datetime.now(timezone.utc)


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


with open(caminho_json, "r", encoding="utf-8") as f:
    pacientes = json.load(f)

encontrados = 0
for paciente in pacientes:
    for reg in paciente.get("registros") or []:
        data = extrair_data(reg.get("dataEntrada"))
        if data and (data < limite_antigo or data > limite_futuro):
            encontrados += 1
            info = reg.get("informacoes") or {}
            print(f"--- registro suspeito #{encontrados} ---")
            print(f"  tipo: {reg.get('tipo')}")
            print(f"  dataEntrada bruta: {reg.get('dataEntrada')}")
            print(f"  data interpretada: {data}")
            print(f"  atendimentoId/triagemId: {info.get('atendimentoId') or info.get('triagemId')}")
            print()

if encontrados == 0:
    print("Nenhum registro com data suspeita encontrado.")
else:
    print(f"Total: {encontrados} registro(s) suspeito(s).")
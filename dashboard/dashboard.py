import os

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Dashboard Santa Casa", layout="wide")

# resolve o caminho a partir da pasta deste script, nao de onde o
# comando "streamlit run" foi chamado - assim funciona em qualquer pasta
pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(pasta_do_script, "..", "tratamento_de_dados", "registros_medicos_tratados.csv")


@st.cache_data
def carregar_dados():
    tabela = pd.read_csv(caminho_csv)
    tabela["data_entrada"] = pd.to_datetime(
        tabela["data_entrada"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    # algumas datas no banco original vêm corrompidas (ex: ano 840),
    # provavelmente erro de digitação em registro retroativo. Isso
    # distorce o seletor de período, então tratamos como inválida
    # (vira "não informada") qualquer data fora de uma faixa razoável.
    limite_antigo = pd.Timestamp("2000-01-01")
    limite_futuro = pd.Timestamp.now()
    invalida = (tabela["data_entrada"] < limite_antigo) | (tabela["data_entrada"] > limite_futuro)
    tabela.loc[invalida, "data_entrada"] = pd.NaT

    return tabela, int(invalida.sum())


tabela, qtd_datas_invalidas = carregar_dados()

st.title("Dashboard de Atendimentos — Santa Casa")

# ----------------------------------------------------------------------
# FILTROS (barra lateral) - afetam qualquer gráfico escolhido
# ----------------------------------------------------------------------
st.sidebar.header("Filtros")

if qtd_datas_invalidas > 0:
    st.sidebar.caption(f"⚠️ {qtd_datas_invalidas} registro(s) com data inválida foram ignorados no filtro de período.")

data_min = tabela["data_entrada"].min().date()
data_max = tabela["data_entrada"].max().date()
periodo = st.sidebar.date_input("Período", (data_min, data_max), min_value=data_min, max_value=data_max)

bairros = sorted(tabela["bairro"].dropna().unique())
bairros_selecionados = st.sidebar.multiselect("Bairro", bairros, default=bairros)

tipos = sorted(tabela["tipo_registro"].dropna().unique())
tipos_selecionados = st.sidebar.multiselect("Tipo de registro", tipos, default=tipos)

# se a pessoa só escolheu uma data (ainda não terminou de selecionar o
# intervalo), evita erro esperando o segundo clique
if len(periodo) == 2:
    data_inicio, data_fim = periodo
else:
    data_inicio, data_fim = data_min, data_max

filtrada = tabela[
    (tabela["data_entrada"].dt.date >= data_inicio)
    & (tabela["data_entrada"].dt.date <= data_fim)
    & (tabela["bairro"].isin(bairros_selecionados))
    & (tabela["tipo_registro"].isin(tipos_selecionados))
]

st.sidebar.markdown(f"**{len(filtrada)}** registros após o filtro (de {len(tabela)} no total)")

# ----------------------------------------------------------------------
# SELETOR DE VISUALIZAÇÃO
# ----------------------------------------------------------------------
visualizacao = st.selectbox(
    "Escolha a visualização",
    ["Volume de atendimentos por período"],
)

if filtrada.empty:
    st.warning("Nenhum registro encontrado com esses filtros.")
    st.stop()

if visualizacao == "Volume de atendimentos por período":
    st.subheader("Volume de atendimentos por mês")

    por_mes = (
        filtrada.groupby(filtrada["data_entrada"].dt.to_period("M"))
        .size()
        .reset_index(name="quantidade")
    )
    por_mes["data_entrada"] = por_mes["data_entrada"].astype(str)

    fig = px.line(por_mes, x="data_entrada", y="quantidade", markers=True)
    fig.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de registros")
    st.plotly_chart(fig, use_container_width=True)
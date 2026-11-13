import os
import re
import calendar
from datetime import date

import pandas as pd
import streamlit as st
import plotly.express as px

meses_pt = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

st.set_page_config(page_title="Dashboard Santa Casa", layout="wide", page_icon="⬡")

# cor de fundo dos "cartões" (cards) - mesma do secondaryBackgroundColor
# do config.toml, usada tanto no CSS quanto no fundo dos gráficos, pra
# o gráfico parecer parte do cartão e não ficar com fundo preto puro
cor_cartao = "#111C2E"

# paleta azul-marinho, com tons de azul para diferenciar categorias
paleta_cores = ["#3B82F6", "#60A5FA", "#93C5FD", "#1D4ED8", "#BFDBFE", "#2563EB", "#DBEAFE"]
px.defaults.color_discrete_sequence = paleta_cores  # type: ignore[assignment]
px.defaults.template = "plotly_dark"  # type: ignore[assignment]


def estilizar(fig):
    """Aplica o visual padrão (fundo de cartão, fonte, margens)."""
    fig.update_layout(
        paper_bgcolor=cor_cartao, plot_bgcolor=cor_cartao,
        font_color="#E2EAF6", margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


def grafico_ranking(valores, rotulo, top=15):
    """Barra horizontal com os top valores mais frequentes de uma
    coluna - usado por bairro, CID e medicamentos (mesmo formato)."""
    contagem = valores.value_counts().head(top).reset_index()
    contagem.columns = [rotulo, "quantidade"]
    rotulos = {rotulo: rotulo, "quantidade": "Quantidade de Registros"}
    fig = px.bar(contagem, x="quantidade", y=rotulo, orientation="h", labels=rotulos)
    fig.update_traces(
        marker_color=paleta_cores[0],
        hovertemplate=f"{rotulo} = %{{y}}<br>Quantidade de Registros = %{{x}}<extra></extra>",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return estilizar(fig)


# CSS customizado: fonte (Inter, mais clean que a padrão do navegador)
# e cartões arredondados nos indicadores (st.metric)
st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}

        div[data-testid="stMetric"] {{
            background-color: {cor_cartao};
            border: 1px solid #26364F;
            border-top: 3px solid #3B82F6;
            border-radius: 16px;
            padding: 18px 20px;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 16px !important;
        }}

        /* título de cada grupo de filtro na barra lateral: destacado,
        com uma barrinha azul do lado, pra separar visualmente */
        .titulo-filtro {{
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            color: #93C5FD;
            border-left: 3px solid #3B82F6;
            padding-left: 10px;
            margin: 18px 0 6px 0;
        }}

        /* divisórias (st.divider) na cor azul do tema, com menos espaço
        em volta (o padrão do streamlit é bem espaçado) */
        div[data-testid="stSidebar"] hr {{
            border-color: #3B82F6 !important;
            opacity: 0.3;
            margin: 6px 0 !important;
        }}

        /* título "Filtros" no topo da barra lateral - maior que os
        subtítulos de cada grupo (Período, Localização...) */
        .titulo-filtros-principal {{
            font-weight: 800;
            font-size: 1.9rem;
            letter-spacing: 0.01em;
            margin-top: 4px;
        }}

    </style>
    """,
    unsafe_allow_html=True,
)

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(pasta_do_script, "..", "tratamento_de_dados", "registros_medicos_tratados.csv")

# ano que o filtro de período abre selecionado (o campo "Ano Inicial"
# ainda permite digitar qualquer ano que exista de verdade na base,
# mesmo mais antigo que este)
ano_inicial_padrao = 2000

ordem_faixas = ["0-4", "5-11", "12-17", "18-29", "30-44", "45-59", "60-74", "75+", "Não Informado"]

# palavras comuns em queixas que não ajudam a identificar o assunto
# (verbos/conectivos típicos de anotação médica, não sintomas em si)
stopwords_pt = {
    "paciente", "refere", "apresenta", "relata", "nega", "que", "com", "sem",
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "para",
    "por", "um", "uma", "uns", "umas", "e", "o", "a", "os", "as", "nao",
    "ao", "aos", "desde", "ha", "dias", "dia", "horas", "hora", "foi",
    "esta", "estava", "estao", "mesmo", "mesma", "ser", "tem", "ter", "se",
    "sua", "seu", "suas", "seus", "ate", "mais", "menos", "muito", "pra",
    "pro", "ai", "tambem", "quando", "onde", "vez", "vezes", "ja", "ao",
    "pacientea", "trazida", "trazido", "acompanhado", "acompanhada",
}

# siglas de sinais vitais que aparecem em quase toda queixa (parte do
# "cabeçalho" da anotação, não é sintoma) - sozinhas elas dominam a
# nuvem de palavras e escondem as palavras que realmente importam
siglas_vitais = {
    "pa", "fc", "fr", "sat", "sao2", "spo2", "spo", "bpm", "mmhg", "pu",
    "pam", "pas", "pad", "t", "p", "kg", "cm", "mid", "mie", "ssvv",
}

# remove os trechos típicos de sinais vitais (ex: "PA:120X90", "SAT 98%",
# "T:36,4", "FC 94 BPM") do texto da queixa antes de gerar a nuvem
padrao_sinais_vitais = re.compile(
    r"\b(?:" + "|".join(siglas_vitais) + r")\s*[:\-]?\s*\d+[\d.,x/]*%?",
    flags=re.IGNORECASE,
)


def limpar_para_nuvem(texto):
    """Tira sinais vitais e números soltos do texto da queixa, deixando
    só as palavras que descrevem o quadro do paciente."""
    texto = padrao_sinais_vitais.sub(" ", texto)
    texto = re.sub(r"\b\d+[\d.,x/]*\b", " ", texto)  # números/códigos soltos restantes
    return texto


@st.cache_data
def carregar_dados():
    tabela = pd.read_csv(caminho_csv)
    tabela["data_entrada"] = pd.to_datetime(
        tabela["data_entrada"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    return tabela


tabela = carregar_dados()

# registros sem data nenhuma (NaT) - o campo não existia ou não foi
# reconhecido, diferente de uma data só "fora do normal" tipo ano 840
qtd_datas_ausentes = int(tabela["data_entrada"].isna().sum())
qtd_datas_antigas = int((tabela["data_entrada"] < pd.Timestamp(f"{ano_inicial_padrao}-01-01")).sum())

st.title("Dashboard de Atendimentos — Santa Casa")
st.caption("Monitoramento de Indicadores de Atendimento para Apoio à Gestão Hospitalar")

# ----------------------------------------------------------------------
# FILTROS (barra lateral) - afetam qualquer gráfico escolhido
# ----------------------------------------------------------------------
st.sidebar.markdown('<div class="titulo-filtros-principal">Filtros</div>', unsafe_allow_html=True)
st.sidebar.divider()

# seletores de ano/mês escritos por nós (em vez do calendário nativo
# do streamlit) - assim controlamos o idioma e a capitalização. O ano
# usa um campo numérico (em vez de lista suspensa) pra permitir digitar
# qualquer ano direto, incluindo os anos "atípicos" tipo 840, sem precisar
# rolar uma lista enorme - digitar é mais rápido que navegar 1000+ anos.
ano_minimo_possivel = tabela["data_entrada"].min().year
ano_maximo_possivel = min(tabela["data_entrada"].max(), pd.Timestamp.now()).year
ano_padrao_inicio = max(ano_minimo_possivel, ano_inicial_padrao)

st.sidebar.markdown('<div class="titulo-filtro">Período</div>', unsafe_allow_html=True)
col_ano_ini, col_mes_ini = st.sidebar.columns(2)
ano_inicio = col_ano_ini.number_input(
    "Ano Inicial", min_value=ano_minimo_possivel, max_value=ano_maximo_possivel, value=ano_padrao_inicio, step=1
)
mes_inicio = col_mes_ini.selectbox("Mês Inicial", meses_pt, index=0)

col_ano_fim, col_mes_fim = st.sidebar.columns(2)
ano_fim = col_ano_fim.number_input(
    "Ano Final", min_value=ano_minimo_possivel, max_value=ano_maximo_possivel, value=ano_maximo_possivel, step=1
)
mes_fim = col_mes_fim.selectbox("Mês Final", meses_pt, index=11)

data_inicio = date(ano_inicio, meses_pt.index(mes_inicio) + 1, 1)
ultimo_dia_mes_fim = calendar.monthrange(ano_fim, meses_pt.index(mes_fim) + 1)[1]
data_fim = date(ano_fim, meses_pt.index(mes_fim) + 1, ultimo_dia_mes_fim)

if data_inicio > data_fim:
    st.sidebar.error("O Período Inicial é Posterior ao Final — Ajuste as Datas.")
    data_inicio, data_fim = data_fim, data_inicio

# bairro/tipo com valor em branco viram uma categoria explícita
# "(Não informado)" em vez de simplesmente sumir do filtro - assim
# "Todos" realmente inclui 100% dos registros, até os incompletos
bairro_tratado = tabela["bairro"].fillna("(Não informado)")
tipo_tratado = tabela["tipo_registro"].fillna("(Não informado)")

# filtro de bairro, com "Todos" integrado (sem botão separado)
st.sidebar.markdown('<div class="titulo-filtro">Localização</div>', unsafe_allow_html=True)
bairros = sorted(bairro_tratado.unique())
todos_os_bairros = st.sidebar.checkbox("Todos os Bairros", value=True)
if todos_os_bairros:
    bairros_selecionados = bairros
else:
    bairros_selecionados = st.sidebar.multiselect("Bairro", bairros)

st.sidebar.markdown('<div class="titulo-filtro">Tipo de registro</div>', unsafe_allow_html=True)
tipos = sorted(tipo_tratado.unique())
tipos_selecionados = st.sidebar.multiselect("Tipo de Registro", tipos, default=tipos, label_visibility="collapsed")

# registros sem data (NaT) não têm como "estar dentro" de um período -
# aqui a pessoa decide se eles entram ou não no filtro, em vez de ficarem
# invisivelmente de fora (ou sempre dentro) sem ela saber
incluir_sem_data = st.sidebar.checkbox(
    f"Incluir {qtd_datas_ausentes} Registro(s) sem Data Reconhecida", value=True
)

# datas atípicas (ex: ano 840) e as dentro do intervalo típico
# respeitam o filtro de período normalmente
dentro_do_periodo = (tabela["data_entrada"].dt.date >= data_inicio) & (tabela["data_entrada"].dt.date <= data_fim)
sem_data = tabela["data_entrada"].isna()

filtrada = tabela[
    (dentro_do_periodo | (sem_data & incluir_sem_data))
    & (bairro_tratado.isin(bairros_selecionados))
    & (tipo_tratado.isin(tipos_selecionados))
]

st.sidebar.markdown(f"**{len(filtrada)}** Registros Após o Filtro (de {len(tabela)} no total)")

if qtd_datas_antigas > 0:
    st.sidebar.caption(
        f"{qtd_datas_antigas} registro(s) têm data anterior a {ano_inicial_padrao} e por isso "
        f'ficam fora do período inicial. Ajuste "Ano Inicial" acima pra incluí-los '
        f"(mínimo permitido: {ano_minimo_possivel})."
    )

# ----------------------------------------------------------------------
# CARTÕES DE INDICADORES (resumo rápido dos dados filtrados)
# ----------------------------------------------------------------------
if not filtrada.empty:
    bairro_top = str(filtrada["bairro"].value_counts().idxmax()) if filtrada["bairro"].notna().any() else "—"
    idade_media = filtrada["idade"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros no Filtro", f"{len(filtrada):,}".replace(",", "."))
    col2.metric("Pacientes Únicos", f"{filtrada['paciente_id'].nunique():,}".replace(",", "."))
    col3.metric("Idade Média", f"{idade_media:.0f} anos" if pd.notna(idade_media) else "—")
    col4.metric("Bairro Mais Comum", bairro_top)
    st.divider()

# ----------------------------------------------------------------------
# SELETOR DE VISUALIZAÇÃO
# ----------------------------------------------------------------------
visualizacao = st.selectbox(
    "Escolha a Visualização",
    [
        "Volume de Atendimentos por Período",
        "Distribuição por Sexo e Faixa Etária",
        "Atendimentos por Bairro",
        "Tipos de Atendimento",
        "Diagnósticos Mais Frequentes (CID)",
        "Medicamentos Mais Usados",
        "Nuvem de Palavras das Queixas",
    ],
)

if filtrada.empty:
    st.warning("Nenhum Registro Encontrado com Esses Filtros.")
    st.stop()


cartao = st.container(border=True)

# ----------------------------------------------------------------------
# 1. VOLUME POR PERÍODO
# ----------------------------------------------------------------------
if visualizacao == "Volume de Atendimentos por Período":
    with cartao:
        st.subheader("Volume de Atendimentos por Mês")

        por_mes = (
            filtrada.groupby(filtrada["data_entrada"].dt.to_period("M"))
            .size()
            .reset_index(name="quantidade")
        )
        por_mes["data_entrada"] = por_mes["data_entrada"].astype(str)

        rotulos = {"data_entrada": "Mês", "quantidade": "Quantidade de Registros"}
        fig = px.line(por_mes, x="data_entrada", y="quantidade", markers=True, labels=rotulos)
        fig.update_traces(
            line_color=paleta_cores[0],
            marker_color=paleta_cores[0],
            hovertemplate="Mês = %{x}<br>Quantidade de Registros = %{y}<extra></extra>",
        )
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 2. SEXO E FAIXA ETÁRIA
# ----------------------------------------------------------------------
elif visualizacao == "Distribuição por Sexo e Faixa Etária":
    with cartao:
        st.subheader("Distribuição de Pacientes por Sexo e Faixa Etária")

        contagem = filtrada.groupby(["faixa_etaria", "sexo"]).size().reset_index(name="quantidade")
        contagem["faixa_etaria"] = pd.Categorical(contagem["faixa_etaria"], categories=ordem_faixas, ordered=True)
        contagem = contagem.sort_values("faixa_etaria")

        rotulos = {"faixa_etaria": "Faixa Etária", "quantidade": "Quantidade de Registros", "sexo": "Sexo"}
        fig = px.bar(contagem, x="faixa_etaria", y="quantidade", color="sexo", barmode="group", labels=rotulos)
        fig.update_traces(
            hovertemplate=(
                "Faixa Etária = %{x}<br>"
                "Quantidade de Registros = %{y}<br>"
                "Sexo = %{fullData.name}<extra></extra>"
            )
        )
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 3. BAIRRO
# ----------------------------------------------------------------------
elif visualizacao == "Atendimentos por Bairro":
    with cartao:
        st.subheader("15 Bairros com Mais Atendimentos")
        st.plotly_chart(grafico_ranking(filtrada["bairro"], "Bairro"), use_container_width=True)


# ----------------------------------------------------------------------
# 4. TIPOS DE ATENDIMENTO
# ----------------------------------------------------------------------
elif visualizacao == "Tipos de Atendimento":
    with cartao:
        st.subheader("Distribuição por Tipo de Registro")

        contagem = filtrada["tipo_registro"].value_counts().reset_index()
        contagem.columns = ["tipo_registro", "quantidade"]

        rotulos = {"tipo_registro": "Tipo de Registro", "quantidade": "Quantidade de Registros"}
        fig = px.pie(contagem, names="tipo_registro", values="quantidade", hole=0.55, labels=rotulos)
        fig.update_traces(
            hovertemplate=(
                "Tipo de Registro = %{label}<br>"
                "Quantidade de Registros = %{value}<br>"
                "Participação = %{percent}<extra></extra>"
            )
        )
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 5. DIAGNÓSTICOS (CID)
# ----------------------------------------------------------------------
elif visualizacao == "Diagnósticos Mais Frequentes (CID)":
    with cartao:
        st.subheader("15 Diagnósticos (CID) Mais Frequentes")

        diagnosticados = filtrada["cid_descricao"].dropna()
        if diagnosticados.empty:
            st.info("Nenhum Diagnóstico (CID) Registrado com Esses Filtros.")
        else:
            st.plotly_chart(grafico_ranking(diagnosticados, "Diagnóstico"), use_container_width=True)


# ----------------------------------------------------------------------
# 6. MEDICAMENTOS
# ----------------------------------------------------------------------
elif visualizacao == "Medicamentos Mais Usados":
    with cartao:
        st.subheader("15 Medicamentos Mais Usados")

        medicados = filtrada["medicamento_nome"].dropna()
        if medicados.empty:
            st.info("Nenhum Medicamento Registrado com Esses Filtros.")
        else:
            st.plotly_chart(grafico_ranking(medicados, "Medicamento"), use_container_width=True)


# ----------------------------------------------------------------------
# 7. NUVEM DE PALAVRAS (QUEIXAS)
# ----------------------------------------------------------------------
elif visualizacao == "Nuvem de Palavras das Queixas":
    with cartao:
        st.subheader("Nuvem de Palavras das Queixas")

        try:
            from wordcloud import WordCloud, STOPWORDS
            import matplotlib.pyplot as plt
        except ImportError:
            st.error("Faltam Bibliotecas para Este Gráfico. Execute: pip install wordcloud matplotlib")
            st.stop()

        incluir_vitais = st.checkbox(
            "Incluir Siglas de Sinais Vitais (PA, FC, SAT, SPO2...) na Nuvem", value=False
        )
        st.caption(
            "Por padrão, siglas de sinais vitais (PA, FC, SAT, SPO2, BPM, MMHG e seus números) "
            "são retiradas da nuvem — elas aparecem em quase toda queixa e, por isso, dominam "
            "visualmente sem indicar o sintoma relatado. Marque a opção acima para trazê-las de volta."
        )

        queixas = filtrada["queixa"].dropna()
        texto_bruto = " ".join(queixas)

        if incluir_vitais:
            texto = re.sub(r"\b\d+[\d.,x/]*\b", " ", texto_bruto)  # tira só números soltos
            todas_stopwords = STOPWORDS.union(stopwords_pt)
        else:
            texto = limpar_para_nuvem(texto_bruto)
            todas_stopwords = STOPWORDS.union(stopwords_pt).union(siglas_vitais)

        if not texto.strip():
            st.info("Nenhuma Queixa Registrada com Esses Filtros.")
        else:
            nuvem = WordCloud(
                width=1200,
                height=600,
                background_color=cor_cartao,
                colormap="Blues",
                stopwords=todas_stopwords,
                max_words=60,
                prefer_horizontal=0.95,
                collocation_threshold=15,
            ).generate(texto)

            fig, eixo = plt.subplots(figsize=(12, 6))
            fig.patch.set_facecolor(cor_cartao)
            eixo.imshow(nuvem, interpolation="bilinear")
            eixo.axis("off")
            st.pyplot(fig)
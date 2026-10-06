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
cor_cartao = "#1A1B23"

# paleta roxa, igual à referência, com cores de apoio pra gráficos
# com mais de uma categoria (ex: sexo)
paleta_cores = ["#8B5CF6", "#A78BFA", "#C4B5FD", "#6D28D9", "#DDD6FE", "#5B21B6", "#EDE9FE"]
px.defaults.color_discrete_sequence = paleta_cores
px.defaults.template = "plotly_dark"


def estilizar(fig):
    """Aplica o visual padrão (fundo de cartão, fonte, margens)."""
    fig.update_layout(
        paper_bgcolor=cor_cartao, plot_bgcolor=cor_cartao,
        font_color="#E5E7EB", margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


def grafico_ranking(valores, rotulo, top=15):
    """Barra horizontal com os top valores mais frequentes de uma
    coluna - usado por bairro, CID e medicamentos (mesmo formato)."""
    contagem = valores.value_counts().head(top).reset_index()
    contagem.columns = [rotulo, "quantidade"]
    fig = px.bar(contagem, x="quantidade", y=rotulo, orientation="h")
    fig.update_traces(marker_color=paleta_cores[0])
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Quantidade de registros", yaxis_title=rotulo)
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
            border: 1px solid #2A2B36;
            border-top: 3px solid #8B5CF6;
            border-radius: 16px;
            padding: 18px 20px;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 16px !important;
        }}

        /* título de cada grupo de filtro na barra lateral: destacado,
        com uma barrinha roxa do lado, pra separar visualmente */
        .titulo-filtro {{
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            color: #A78BFA;
            border-left: 3px solid #8B5CF6;
            padding-left: 10px;
            margin: 18px 0 6px 0;
        }}

        /* divisórias (st.divider) na cor roxa do tema, com menos espaço
        em volta (o padrão do streamlit é bem espaçado) */
        div[data-testid="stSidebar"] hr {{
            border-color: #8B5CF6 !important;
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

        /* textos de apoio (st.caption) em itálico */
        [data-testid="stCaptionContainer"] {{
            font-style: italic;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(pasta_do_script, "..", "tratamento_de_dados", "registros_medicos_tratados.csv")

# ano usado só pra destacar (não pra excluir) datas fora do comum
ano_tipico_inicio = 2000

ordem_faixas = ["0-4", "5-11", "12-17", "18-29", "30-44", "45-59", "60-74", "75+", "NAO INFORMADO"]

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

# dois tipos diferentes de "problema" na data:
# - atípica: tem data válida, mas fora da faixa típica (ex: ano 840)
# - ausente: não tem data nenhuma, ou o formato não foi reconhecido (NaT)
qtd_datas_atipicas = int((tabela["data_entrada"] < pd.Timestamp(f"{ano_tipico_inicio}-01-01")).sum())
qtd_datas_ausentes = int(tabela["data_entrada"].isna().sum())

st.title("Dashboard de Atendimentos — Santa Casa")
st.caption("Monitoramento de indicadores de atendimento para apoio à gestão hospitalar")

# ----------------------------------------------------------------------
# FILTROS (barra lateral) - afetam qualquer gráfico escolhido
# ----------------------------------------------------------------------
st.sidebar.markdown('<div class="titulo-filtros-principal">Filtros</div>', unsafe_allow_html=True)
st.sidebar.divider()

# seletores de ano/mês escritos por nós (em vez do calendário nativo
# do streamlit) - assim controlamos o idioma, a capitalização e não
# ficamos reféns da navegação travada do componente pronto.
limite_inferior = max(tabela["data_entrada"].min(), pd.Timestamp(f"{ano_tipico_inicio}-01-01"))
limite_superior = min(tabela["data_entrada"].max(), pd.Timestamp.now())
if limite_inferior > limite_superior:  # caso raro: toda a base é atípica
    limite_inferior, limite_superior = tabela["data_entrada"].min(), tabela["data_entrada"].max()

anos_disponiveis = list(range(limite_inferior.year, limite_superior.year + 1))

st.sidebar.markdown('<div class="titulo-filtro">Período</div>', unsafe_allow_html=True)
col_ano_ini, col_mes_ini = st.sidebar.columns(2)
ano_inicio = col_ano_ini.selectbox("Ano inicial", anos_disponiveis, index=0)
mes_inicio = col_mes_ini.selectbox("Mês inicial", meses_pt, index=0)

col_ano_fim, col_mes_fim = st.sidebar.columns(2)
ano_fim = col_ano_fim.selectbox("Ano final", anos_disponiveis, index=len(anos_disponiveis) - 1)
mes_fim = col_mes_fim.selectbox("Mês final", meses_pt, index=11)

data_inicio = date(ano_inicio, meses_pt.index(mes_inicio) + 1, 1)
ultimo_dia_mes_fim = calendar.monthrange(ano_fim, meses_pt.index(mes_fim) + 1)[1]
data_fim = date(ano_fim, meses_pt.index(mes_fim) + 1, ultimo_dia_mes_fim)

if data_inicio > data_fim:
    st.sidebar.error("O período inicial é depois do final — ajuste as datas.")
    data_inicio, data_fim = data_fim, data_inicio

# bairro/tipo com valor em branco viram uma categoria explícita
# "(Não informado)" em vez de simplesmente sumir do filtro - assim
# "Todos" realmente inclui 100% dos registros, até os incompletos
bairro_tratado = tabela["bairro"].fillna("(Não informado)")
tipo_tratado = tabela["tipo_registro"].fillna("(Não informado)")

# filtro de bairro, com "Todos" integrado (sem botão separado)
st.sidebar.markdown('<div class="titulo-filtro">Localização</div>', unsafe_allow_html=True)
bairros = sorted(bairro_tratado.unique())
todos_os_bairros = st.sidebar.checkbox("Todos os bairros", value=True)
if todos_os_bairros:
    bairros_selecionados = bairros
else:
    bairros_selecionados = st.sidebar.multiselect("Bairro", bairros)

st.sidebar.markdown('<div class="titulo-filtro">Tipo de registro</div>', unsafe_allow_html=True)
tipos = sorted(tipo_tratado.unique())
tipos_selecionados = st.sidebar.multiselect("Tipo de registro", tipos, default=tipos, label_visibility="collapsed")

# registros sem data (NaT) não têm como "estar dentro" de um período -
# aqui a pessoa decide se eles entram ou não no filtro, em vez de ficarem
# invisivelmente de fora (ou sempre dentro) sem ela saber
incluir_sem_data = st.sidebar.checkbox(
    f"Incluir {qtd_datas_ausentes} registro(s) sem data reconhecida", value=True
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

st.sidebar.markdown(f"**{len(filtrada)}** registros após o filtro (de {len(tabela)} no total)")

if qtd_datas_atipicas > 0:
    st.sidebar.divider()
    st.sidebar.caption(
        f"{qtd_datas_atipicas} registro(s) têm data anterior a {ano_tipico_inicio} e por isso "
        f"ficam fora do filtro acima (o seletor de ano começa em {ano_tipico_inicio})."
    )

# ----------------------------------------------------------------------
# CARTÕES DE INDICADORES (resumo rápido dos dados filtrados)
# ----------------------------------------------------------------------
if not filtrada.empty:
    bairro_top = filtrada["bairro"].value_counts().idxmax() if filtrada["bairro"].notna().any() else "—"
    idade_media = filtrada["idade"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros no filtro", f"{len(filtrada):,}".replace(",", "."))
    col2.metric("Pacientes únicos", f"{filtrada['paciente_id'].nunique():,}".replace(",", "."))
    col3.metric("Idade média", f"{idade_media:.0f} anos" if pd.notna(idade_media) else "—")
    col4.metric("Bairro mais comum", bairro_top)
    st.divider()

# ----------------------------------------------------------------------
# SELETOR DE VISUALIZAÇÃO
# ----------------------------------------------------------------------
visualizacao = st.selectbox(
    "Escolha a visualização",
    [
        "Volume de atendimentos por período",
        "Distribuição por sexo e faixa etária",
        "Atendimentos por bairro",
        "Tipos de atendimento",
        "Diagnósticos mais frequentes (CID)",
        "Medicamentos mais usados",
        "Nuvem de palavras das queixas",
    ],
)

if filtrada.empty:
    st.warning("Nenhum registro encontrado com esses filtros.")
    st.stop()


cartao = st.container(border=True)

# ----------------------------------------------------------------------
# 1. VOLUME POR PERÍODO
# ----------------------------------------------------------------------
if visualizacao == "Volume de atendimentos por período":
    with cartao:
        st.subheader("Volume de atendimentos por mês")

        por_mes = (
            filtrada.groupby(filtrada["data_entrada"].dt.to_period("M"))
            .size()
            .reset_index(name="quantidade")
        )
        por_mes["data_entrada"] = por_mes["data_entrada"].astype(str)

        fig = px.line(por_mes, x="data_entrada", y="quantidade", markers=True)
        fig.update_traces(line_color=paleta_cores[0], marker_color=paleta_cores[0])
        fig.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de registros")
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 2. SEXO E FAIXA ETÁRIA
# ----------------------------------------------------------------------
elif visualizacao == "Distribuição por sexo e faixa etária":
    with cartao:
        st.subheader("Distribuição de pacientes por sexo e faixa etária")

        contagem = filtrada.groupby(["faixa_etaria", "sexo"]).size().reset_index(name="quantidade")
        contagem["faixa_etaria"] = pd.Categorical(contagem["faixa_etaria"], categories=ordem_faixas, ordered=True)
        contagem = contagem.sort_values("faixa_etaria")

        fig = px.bar(contagem, x="faixa_etaria", y="quantidade", color="sexo", barmode="group")
        fig.update_layout(xaxis_title="Faixa etária", yaxis_title="Quantidade de registros")
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 3. BAIRRO
# ----------------------------------------------------------------------
elif visualizacao == "Atendimentos por bairro":
    with cartao:
        st.subheader("Top 15 bairros por quantidade de atendimentos")
        st.plotly_chart(grafico_ranking(filtrada["bairro"], "Bairro"), use_container_width=True)


# ----------------------------------------------------------------------
# 4. TIPOS DE ATENDIMENTO
# ----------------------------------------------------------------------
elif visualizacao == "Tipos de atendimento":
    with cartao:
        st.subheader("Distribuição por tipo de registro")

        contagem = filtrada["tipo_registro"].value_counts().reset_index()
        contagem.columns = ["tipo_registro", "quantidade"]

        fig = px.pie(contagem, names="tipo_registro", values="quantidade", hole=0.55)
        st.plotly_chart(estilizar(fig), use_container_width=True)


# ----------------------------------------------------------------------
# 5. DIAGNÓSTICOS (CID)
# ----------------------------------------------------------------------
elif visualizacao == "Diagnósticos mais frequentes (CID)":
    with cartao:
        st.subheader("Top 15 diagnósticos (CID) mais frequentes")

        diagnosticados = filtrada["cid_descricao"].dropna()
        if diagnosticados.empty:
            st.info("Nenhum diagnóstico (CID) registrado com esses filtros.")
        else:
            st.plotly_chart(grafico_ranking(diagnosticados, "Diagnóstico"), use_container_width=True)


# ----------------------------------------------------------------------
# 6. MEDICAMENTOS
# ----------------------------------------------------------------------
elif visualizacao == "Medicamentos mais usados":
    with cartao:
        st.subheader("Top 15 medicamentos mais usados")

        medicados = filtrada["medicamento_nome"].dropna()
        if medicados.empty:
            st.info("Nenhum medicamento registrado com esses filtros.")
        else:
            st.plotly_chart(grafico_ranking(medicados, "Medicamento"), use_container_width=True)


# ----------------------------------------------------------------------
# 7. NUVEM DE PALAVRAS (QUEIXAS)
# ----------------------------------------------------------------------
elif visualizacao == "Nuvem de palavras das queixas":
    with cartao:
        st.subheader("Nuvem de palavras das queixas")

        try:
            from wordcloud import WordCloud, STOPWORDS
            import matplotlib.pyplot as plt
        except ImportError:
            st.error("Faltam bibliotecas para esse gráfico. Rode: pip install wordcloud matplotlib")
            st.stop()

        incluir_vitais = st.checkbox(
            "Incluir siglas de sinais vitais (PA, FC, SAT, SPO2...) na nuvem", value=False
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
            st.info("Nenhuma queixa registrada com esses filtros.")
        else:
            nuvem = WordCloud(
                width=1200,
                height=600,
                background_color=cor_cartao,
                colormap="Purples",
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
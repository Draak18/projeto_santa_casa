# Projeto Santa Casa

Dashboard interativo desenvolvido para apoiar a gestão hospitalar, permitindo monitorar indicadores de atendimento, analisar dados de saúde e auxiliar na tomada de decisões.

Projeto Integrador em Sistemas Inteligentes I, desenvolvido por uma equipe de alunos a partir de uma base de dados real cedida por um órgão de saúde local.

## Status do projeto

- [x] Tratamento e limpeza dos dados
- [x] Anonimização dos registros
- [x] Desenvolvimento do dashboard interativo
- [x] Implementação de filtros e visualizações
- [x] Tratamento de datas ausentes e inconsistentes
- [x] Documentação do projeto

## Privacidade dos dados

Este repositório **não contém dados pessoais ou identificáveis de pacientes**.

O arquivo `.json` original, que contém CPF, nome e outras informações sensíveis, assim como o `.csv` gerado pelo tratamento, estão incluídos no `.gitignore` e não devem ser enviados ao repositório.

O script de tratamento remove os campos de identificação direta e gera um ID interno baseado em hash para cada paciente. Dessa forma, o dashboard utiliza esse identificador para relacionar registros sem exibir CPF ou nome.

## Estrutura do repositório

```text
projeto_santa_casa/
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── dashboard/
│   └── dashboard.py
└── tratamento_de_dados/
    ├── tratamento.py
    ├── registros_medicos.json
    └── registros_medicos_tratados.csv
```

Os arquivos `registros_medicos.json` e `registros_medicos_tratados.csv` são arquivos locais e não fazem parte do repositório.

## Como executar

### Pré-requisitos

- Python 3 instalado.
- Arquivo original `registros_medicos.json`, disponibilizado localmente.

### 1. Instalar as dependências

```bash
pip install pandas tqdm streamlit plotly wordcloud matplotlib
```

### 2. Tratar os dados

Coloque o arquivo `registros_medicos.json` dentro da pasta `tratamento_de_dados/` e execute:

```bash
python tratamento_de_dados/tratamento.py
```

O script gera o arquivo `registros_medicos_tratados.csv` na mesma pasta.

### 3. Executar o dashboard

```bash
python -m streamlit run dashboard/dashboard.py
```

O dashboard será iniciado localmente e poderá ser acessado pelo navegador.

> O uso de `python -m streamlit` evita possíveis problemas de PATH no Windows.

## Como o tratamento funciona

O banco de dados original está em formato `.json` e possui uma estrutura aninhada: cada paciente contém uma lista de registros, que podem pertencer a diferentes categorias, como `TRIAGEM`, `ATENDIMENTO`, `MEDICAMENTO` ou `CIRURGIA`. Cada categoria possui seus próprios campos dentro de `informacoes`.

Estrutura simplificada:

```text
paciente
 ├── cpf, nome, sexo, cidade, bairro, dataNascimento...
 └── registros[]
      ├── tipo: TRIAGEM | ATENDIMENTO | MEDICAMENTO | CIRURGIA
      └── informacoes: { queixa, diagnostico, medicamento, cid, ... }
```

O `tratamento.py` realiza as seguintes etapas:

**1. Estruturação dos dados**

Percorre os pacientes e seus respectivos registros, gerando uma linha para cada registro em uma única tabela. Os dados do paciente, como sexo, cidade e bairro, são combinados com as informações específicas de cada registro.

**2. Anonimização**

Remove os campos de identificação direta, como CPF e nome, substituindo a identificação do paciente por um ID interno baseado em hash.

**3. Tratamento de datas**

Alguns registros, especialmente os de `MEDICAMENTO`, podem não possuir uma data de entrada própria. Nesses casos, o script tenta recuperar a data seguindo esta ordem:

1. Data do atendimento vinculado, utilizando o mesmo `atendimentoId`.
2. `dataCadastro` do próprio registro.
3. Caso nenhuma data válida seja encontrada, o registro permanece sem data.

A coluna `origem_data` identifica a origem da data utilizada, permitindo rastrear como cada registro foi preenchido.

**4. Limpeza e padronização**

Realiza a limpeza e padronização dos campos textuais, categorias e informações clínicas. Também calcula a idade do paciente na data do atendimento, em vez de utilizar sua idade atual, e agrupa os resultados em faixas etárias.

**5. Exportação**

Gera o arquivo `registros_medicos_tratados.csv`, utilizado pelo dashboard.

## Como o dashboard funciona

Desenvolvido com [Streamlit](https://streamlit.io/) e [Plotly](https://plotly.com/python/), o dashboard utiliza o CSV tratado como fonte de dados.

### Filtros

Os filtros disponíveis na lateral permitem selecionar:

- Período, por ano e mês.
- Bairro.
- Tipo de registro.

As seleções são aplicadas às visualizações, permitindo analisar diferentes recortes dos dados.

### Visualizações

O dashboard disponibiliza sete opções de visualização:

1. **Volume por período:** acompanha a quantidade de registros ao longo do tempo.
2. **Sexo e faixa etária:** apresenta a distribuição dos registros por sexo e idade.
3. **Bairros:** identifica a distribuição geográfica dos atendimentos.
4. **Tipos de registro:** compara a quantidade de registros por categoria.
5. **Diagnósticos (CID):** apresenta os diagnósticos mais frequentes.
6. **Medicamentos:** identifica os medicamentos mais registrados.
7. **Nuvem de palavras:** permite visualizar os termos mais frequentes nas queixas.

### Tratamento de datas inconsistentes

O dashboard também contempla registros com datas ausentes ou fora do intervalo habitual.

Datas inconsistentes, como registros associados ao ano 840, não são descartadas silenciosamente. O sistema permite identificar esses casos e ajustar o período analisado, incluindo registros anteriores ao intervalo inicial padrão.

O ano mínimo permitido é calculado automaticamente com base na data mais antiga encontrada na base de dados.

## Tecnologias utilizadas

- **Python:** linguagem utilizada no desenvolvimento do projeto.
- **Pandas:** manipulação, limpeza e estruturação dos dados.
- **TQDM:** acompanhamento do processamento dos registros.
- **Streamlit:** desenvolvimento da interface interativa.
- **Plotly:** criação dos gráficos e visualizações.
- **WordCloud:** geração da nuvem de palavras.
- **Matplotlib:** suporte à visualização gráfica.

---

**Projeto Integrador em Sistemas Inteligentes I — FATEC Pompeia**
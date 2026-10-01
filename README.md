# Projeto Santa Casa
Dashboard para otimização da gestão hospitalar, monitoramento de indicadores de atendimento e apoio à tomada de decisão, desenvolvido a partir de dados reais de atendimentos de saúde.

## Status do projeto
- [x] Tratamento e limpeza dos dados
- [ ] Dashboard interativo
- [ ] Proposta de ação
- [ ] Relatório final

## Privacidade dos dados
Este repositório **não contém nenhum dado de paciente**. O arquivo `.json` bruto (com CPF, nome e demais dados sensíveis) e o `.csv` gerado a partir dele estão no `.gitignore` e nunca devem ser commitados.
O script de tratamento remove CPF e nome automaticamente, substituindo por um ID interno anônimo (hash). Toda a análise e o dashboard trabalham apenas com esse ID, nunca com dado identificável do paciente — ver seção [Como o tratamento funciona](#como-o-tratamento-funciona) abaixo.

## Estrutura do repositório
```
projeto_santa_casa/
├── README.md
├── .gitignore
└── tratamento_de_dados/
    ├── tratamento.py              # script de limpeza/tratamento
    ├── registros_medicos.json     # dado bruto (ignorado pelo git)
    └── registros_medicos_tratados.csv   # dado tratado (ignorado pelo git)
```

## Como rodar
**Pré-requisitos:** Python 3 instalado.
```bash
pip install pandas tqdm
```
Coloque o arquivo `registros_medicos.json` dentro da pasta `tratamento_de_dados/` e rode:
```bash
python tratamento_de_dados/tratamento.py
```
Isso gera `registros_medicos_tratados.csv` na mesma pasta, pronto para ser usado no dashboard.

## Como o tratamento funciona
O banco de dados original vem em formato `.json`, com uma estrutura aninhada: cada paciente tem uma lista de `registros`, e cada registro pode ser de um tipo diferente (`TRIAGEM`, `ATENDIMENTO` ou `MEDICAMENTO`), cada um com seus próprios campos dentro de `informacoes`.
```
paciente
 ├── cpf, nome, sexo, cidade, bairro, dataNascimento...
 └── registros[]
      ├── tipo: "TRIAGEM" | "ATENDIMENTO" | "MEDICAMENTO"
      └── informacoes: { queixa, diagnostico, medicamento, cid, ... }
```
O script `tratamento.py` faz 4 coisas, nessa ordem:
**1. Achata a estrutura.** Para cada paciente, percorre todos os `registros` e gera **uma linha por registro** numa tabela só, combinando os dados do paciente (sexo, cidade, bairro) com os dados daquele registro específico (tipo, data, queixa, diagnóstico etc). Isso é o que permite depois somar/filtrar/agrupar os dados numa ferramenta de dashboard.
**2. Anonimiza.** O CPF nunca entra na tabela final — ele passa por uma função de hash (`anonimizar_cpf`) que gera um ID interno (`pac_xxxxxxxxxx`) irreversível, mas que ainda permite saber que vários registros pertencem ao mesmo paciente, sem saber quem ele é.
**3. Limpa e padroniza:**
- Datas no formato do MongoDB (`{"$date": ...}`) são convertidas para datas de verdade, incluindo dois formatos diferentes que o export pode usar (texto ISO ou número de milissegundos).
- Textos (bairro, cidade, queixa, diagnóstico...) são colocados em maiúsculas e sem espaços/pontuação sobrando nas pontas, para que valores escritos de forma diferente (ex: `"São Paulo"` vs `"sao paulo "`) sejam agrupados como iguais no dashboard.
- A idade do paciente é calculada na data de cada atendimento (não a idade atual), e agrupada automaticamente numa faixa etária (`0-4`, `5-11`, `12-17`...).
**4. Exporta.** O resultado vira `registros_medicos_tratados.csv`, com uma linha por registro de atendimento/triagem/medicamento e uma coluna por campo relevante (paciente_id, sexo, idade, faixa_etaria, cidade, bairro, tipo_registro, data_entrada, diagnostico, cid, medicamento, entre outras).

## Tecnologias
- Python (pandas) — tratamento dos dados
- _(dashboard: a definir)_

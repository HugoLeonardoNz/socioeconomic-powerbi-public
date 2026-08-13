# Audit Report — Brecha Digital Brasil (Power BI)

**Data:** 2026-04-27  
**Auditor:** Hugo Leonardo  
**Versão:** v1.0

---

## Resumo do Projeto

Dashboard Power BI sobre penetração de internet no Brasil 2019–2023 com dados do IBGE PNAD Contínua. Analisa a brecha digital urbano-rural, CAGR de 5 anos por UF e identifica oportunidades de expansão via Score composto (baixa penetração × população × IDH moderado). Star schema com 5 tabelas.

---

## Tecnologias

- **Power BI Desktop** — dashboard e visualizações (arquivo `.pbix`)
- **DAX** — 20+ medidas (CALCULATE, RANKX, SAMEPERIODLASTYEAR, DIVIDE, CAGR)
- **Python / Pandas** — preparação e transformação dos dados (`data_prep/prepare_data.py`)
- **IBGE PNAD Contínua** — fonte de dados oficial

---

## Estrutura

```
socioeconomic-powerbi-public/
├── README.md                   — Documentação completa (200 linhas)
├── AUDIT_REPORT.md             — Este arquivo
├── requirements.txt            — Dependências Python
├── digital_divide_brasil.pbix  — Arquivo Power BI (binário)
├── data/
│   └── README.md               — Instruções de download (IBGE SIDRA)
├── data_prep/
│   └── prepare_data.py         — Gera star schema a partir dos CSVs brutos
├── schema/
│   └── star_schema.md          — Documentação do modelo dimensional
└── dax/
    └── measures.md             — 20+ medidas DAX documentadas
```

---

## Status da Estrutura

| Item | Status |
|---|---|
| README.md real (200 linhas) | ✅ |
| Arquivo .pbix | ⚠️ pendente — construir seguindo `docs/PBIX_BUILD_GUIDE.md` |
| Star schema documentado | ✅ |
| Medidas DAX documentadas | ✅ |
| Script de preparação de dados | ✅ |
| .gitignore Python | ✅ (adicionado 2026-04-27) |
| AUDIT_REPORT.md | ✅ (criado 2026-04-27) |

---

## Pontos Fortes

- Dados de fonte oficial (IBGE PNAD Contínua 2019–2023) — reproduzíveis via API
- Star schema limpo: `fato_indicadores` + `dim_uf` + `dim_periodo` + `dim_area` + `dim_renda`
- Score de Oportunidade composto: `(1 - penetração) × população × IDH` — prioriza estados com gap real
- 4 abas no dashboard: Nacional, Urbano/Rural, Socioeconômico, Oportunidade
- DAX avançado: CAGR via `DIVIDE(POWER(...), 1)`, Gap Digital por UF com `RANKX`

---

## Melhorias Aplicadas (2026-04-27)

- Adicionado `.gitignore` Python padrão
- Criado `AUDIT_REPORT.md` para rastreabilidade do projeto

---

# Construção do dashboard — 2026-08-13

## Estado antes

O projeto se anunciava como "Power BI Dashboard" e **não tinha arquivo `.pbix`**. Havia
dados, medidas documentadas e um guia de montagem manual — o entregável em si nunca foi
feito. O ROADMAP do portfólio marcava 60% de conteúdo e 0% de publicação.

Além disso, o que existia tinha problemas de fundo:

- **`dim_metrica` anunciava cinco métricas; o fato carregava uma.** Renda e população
  nunca chegaram à tabela fato. Dimensão para a qual nada aponta é decoração.
- **Atributos de UF duplicados no fato.** População, densidade e IDH estavam copiados
  para dentro de `fato_indicadores`, repetidos cinco vezes por estado. O IDH (censo 2010)
  aparecia replicado em 2019–2023, fingindo uma série anual que não existe.
- **Recorte urbano × rural sintético.** O fallback offline produzia urbano e rural
  aplicando desvio fixo sobre o total (+5pp / −20pp), gerando um gap de exatamente
  25,0pp em **todos** os 27 estados, em todos os anos. Um indicador construído para não
  distinguir estado nenhum.
- **README anunciava "Dados Reais IBGE"** enquanto a série 2019–2022 era retropolada a
  partir da tendência nacional. Só 2023 é observado por estado.
- **`dim_regiao` criava um floco de neve** (fato → dim_uf → dim_regiao) sem ganho.

## O que foi feito

### Dados e modelo
- Recorte urbano × rural **removido** do pipeline, do modelo e do dashboard. Preferi um
  indicador a menos do que um indicador falso.
- `dim_metrica` e `dim_regiao` removidas. O star schema ficou com um fato e duas
  dimensões — menor, e todas as tabelas com função.
- População, densidade e IDH vivem só em `dim_uf`; as medidas alcançam com `RELATED()`.
- Caminho dos CSVs virou o parâmetro **`PastaDados`** do Power Query.
- README, `schema/star_schema.md` e `dax/measures.md` reescritos contra o modelo real. O
  guia de montagem manual e o `dax/insight_measures.md` foram removidos (descreviam
  montagem à mão e medidas que não existem).

### Bug de tipagem encontrado na verificação
Os CSVs usam ponto decimal e o modelo está em pt-BR, onde ponto é separador de milhar.
Sem cultura explícita, `74.5` virava `745`: a penetração nacional apareceu como 874,5% e
a população sem acesso ficou **negativa**. Corrigido declarando `"en-US"` no
`Table.TransformColumnTypes`. Não gerava erro — só número errado.

### Bug de contexto em DAX
Os dois rankings devolviam `1` para todos os estados. `RANKX` avaliado dentro de uma
tabela que também exibe região ou IDH sofre transição de contexto sobre a **linha inteira**
de `dim_uf`, não só sobre a coluna do ranking: todas as avaliações retornam o mesmo valor.
Reescrito reconstruindo a série com `REMOVEFILTERS(dim_uf)` + reaplicação da UF. Mesmo
cuidado aplicado à correlação e ao score de oportunidade.

### O dashboard
`digital_divide_brasil.pbix` construído do zero: 5 páginas, 54 visuais, 24 medidas.
A camada visual é gerada por **`tools/build_report.py`**, que reescreve
`Report/definition/**` (formato PBIR) a partir de especificação declarativa.

- **A brecha em números** — indicadores, leitura automática, evolução e penetração por UF.
- **Taxa ou volume?** — o paradoxo: São Paulo é 3º em taxa e 1º em gente desconectada.
- **O que explica o acesso** — IDH × penetração, com correlação (0,883) e R² (78%)
  calculados em DAX.
- **Onde investir primeiro** — score de oportunidade e fila de prioridade.
- **Metodologia e limites** — o que é observado, o que é retropolado, o que o painel não
  autoriza concluir.

Design deliberadamente distinto do telecom-powerbi-public: claro cor de papel, paleta
terrosa, rail vertical com os filtros dentro, títulos em serifa.

### Screenshots
`docs/img/` com as 5 páginas, embutidas no README. Antes o repositório não tinha uma
imagem sequer — o painel só existia para quem baixasse o arquivo e abrisse no Desktop.

# Brecha Digital no Brasil — Power BI Dashboard Socioeconômico

<div align="center">

![Power BI](https://img.shields.io/badge/Power%20BI-Desktop-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![DAX](https://img.shields.io/badge/DAX-CALCULATE%20%7C%20RANKX%20%7C%20DIVIDE-F2C811?style=for-the-badge)
![Star Schema](https://img.shields.io/badge/Modelo-Star%20Schema-8B5CF6?style=for-the-badge)
![Domain](https://img.shields.io/badge/Domain-Socioeconômico%20%2F%20Telecom-0ea5e9?style=for-the-badge)
![Data](https://img.shields.io/badge/Dados-Reais%20IBGE-10b981?style=for-the-badge)

**Dashboard que cruza penetração de internet com IDH, renda e densidade populacional por estado brasileiro.**  
Star schema modelado no Power BI com DAX avançado: CALCULATE, FILTER, RANKX, SAMEPERIODLASTYEAR.

</div>

---

## O Problema de Negócio

A brecha digital no Brasil não é uniforme. Estados com menor IDH têm menor penetração de internet — mas também têm maior potencial de crescimento para ISPs. Este dashboard cruza três dimensões simultaneamente: **acesso à internet**, **capacidade socioeconômica** e **oportunidade de mercado**, entregando uma visão única para decisões de expansão de infraestrutura.

---

## Fontes de Dados

| Dataset | Fonte | Cobertura |
|---------|-------|-----------|
| % Domicílios com internet | IBGE PNAD Contínua | 2019–2023, por UF |
| % Acesso urbano × rural | IBGE PNAD Contínua | 2019–2023, por UF |
| IDH por estado | PNUD Brasil (Programa da ONU) | 2010–2022 |
| Renda domiciliar per capita | IBGE PNAD Contínua | 2019–2023, por UF |
| Estimativas populacionais | IBGE Estimativas | 2023, por UF |
| Densidade demográfica | IBGE Censo | 2022 |

---

## Estrutura do Projeto

```
socioeconomic-powerbi-public/
├── README.md
├── requirements.txt
├── data_prep/
│   └── prepare_data.py      ← Gera todas as tabelas do star schema
├── dax/
│   └── measures.md          ← 20+ medidas DAX com CALCULATE/FILTER/DIVIDE
├── schema/
│   └── star_schema.md       ← Documentação completa do modelo de dados
├── data/
│   ├── README.md            ← Fontes de download
│   └── processed/           ← CSVs gerados pelo script
│       ├── fato_indicadores.csv
│       ├── dim_uf.csv
│       ├── dim_periodo.csv
│       ├── dim_metrica.csv
│       └── dim_regiao.csv
└── digital_divide_brasil.pbix  ← Arquivo Power BI (não versionado)
```

---

## Star Schema

```
                    ┌─────────────────┐
                    │   dim_periodo   │
                    │ id_periodo (PK) │
                    │ ano             │
                    │ semestre        │
                    └────────┬────────┘
                             │
┌──────────────┐    ┌────────▼──────────────┐    ┌───────────────────┐
│   dim_uf     │    │   fato_indicadores    │    │   dim_metrica     │
│ id_uf (PK)   ├───►│ id_uf (FK)           │◄───┤ id_metrica (PK)   │
│ sigla        │    │ id_periodo (FK)       │    │ nome              │
│ nome         │    │ id_metrica (FK)       │    │ unidade           │
│ id_regiao(FK)│    │ id_regiao (FK)        │    │ categoria         │
│ populacao    │    │ valor                 │    │ direcao_positiva  │
│ densidade    │    │ valor_urbano          │    └───────────────────┘
│ idh          │    │ valor_rural           │
│ renda_pc     │    │ ranking_nacional      │
└──────────────┘    └───────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   dim_regiao    │
                    │ id_regiao (PK)  │
                    │ nome            │
                    │ sigla           │
                    └─────────────────┘
```

**Grão da tabela fato:** 1 registro por UF × período × métrica.

---

## Medidas DAX — Destaques

```dax
-- Penetração atual (contexto filtrado)
% Internet Domicílios =
CALCULATE(
    AVERAGE(fato_indicadores[valor]),
    dim_metrica[nome] = "pct_domicilios_internet"
)

-- Gap digital urbano × rural
Gap Digital =
VAR urbano = CALCULATE(AVERAGE(fato_indicadores[valor_urbano]),
                       dim_metrica[nome] = "pct_domicilios_internet")
VAR rural  = CALCULATE(AVERAGE(fato_indicadores[valor_rural]),
                       dim_metrica[nome] = "pct_domicilios_internet")
RETURN urbano - rural

-- Ranking nacional de penetração
Ranking Penetração =
RANKX(
    ALL(dim_uf),
    [% Internet Domicílios],
    ,
    DESC,
    DENSE
)

-- Variação vs ano anterior
Var Anual % =
VAR atual    = [% Internet Domicílios]
VAR anterior = CALCULATE([% Internet Domicílios],
                          SAMEPERIODLASTYEAR(dim_periodo[data_ref]))
RETURN DIVIDE(atual - anterior, anterior, BLANK())

-- Score de oportunidade de mercado (ISP)
Score Oportunidade =
VAR penetracao = [% Internet Domicílios] / 100
VAR pop        = RELATED(dim_uf[populacao])
VAR idh        = RELATED(dim_uf[idh])
RETURN (1 - penetracao) * pop / 1000000 * idh
```

Medidas completas em [`dax/measures.md`](dax/measures.md).

---

## KPIs do Dashboard

### Aba 1 — Visão Nacional
- Cards: % domicílios com internet (Brasil), gap digital, variação 5 anos
- Choropleth: penetração por estado (preenchimento por cor)
- Barras: top 5 e bottom 5 estados

### Aba 2 — Brecha Urbano × Rural
- Scattered plot: penetração urbana × rural por estado
- Barras empilhadas: composição por tipo de área
- Mapa de calor: gap digital por região

### Aba 3 — Correlação Socioeconômica
- Scatter: penetração × IDH (bolhas proporcionais à população)
- Scatter: penetração × renda domiciliar per capita
- Linha de tendência com R² calculado via DAX

### Aba 4 — Oportunidade de Mercado
- Matrix: estados ranqueados por score de oportunidade
- Barras: domicílios ainda sem internet × capacidade de pagamento
- Tabela exportável para uso em planejamento de expansão

---

## Como Reproduzir

```bash
# 1. Baixar dados brutos (ver data/README.md)

# 2. Gerar star schema
pip install -r requirements.txt
python data_prep/prepare_data.py
# → Gera data/processed/*.csv

# 3. Power BI Desktop
#    - Importar todos os CSVs
#    - Criar relacionamentos conforme star_schema.md
#    - Adicionar medidas de dax/measures.md
#    - Habilitar mapa preenchido (Bing Maps ou ArcGIS)
```

---

## Stack

`Python` · `Pandas` · `Power BI Desktop` · `DAX` · `Power Query (M)` · `Star Schema`

---

## Autor

**Hugo Leonardo**  
Analista de Dados Pleno — SQL · Python · Power BI  
Speed Fibra · Santa Luzia, MG

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Hugo%20Leonardo-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/hugo-leonardo-data-analyst/)
[![GitHub](https://img.shields.io/badge/GitHub-HugoLeonardoNz-181717?style=flat&logo=github)](https://github.com/HugoLeonardoNz)

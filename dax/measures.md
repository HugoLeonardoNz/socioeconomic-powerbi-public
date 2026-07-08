# DAX Measures — Brecha Digital no Brasil Dashboard

## Configuração de Relacionamentos

```
fato_indicadores[id_uf]       → dim_uf[id_uf]           (Many-to-One)
fato_indicadores[id_periodo]  → dim_periodo[id_periodo]  (Many-to-One)
fato_indicadores[id_metrica]  → dim_metrica[id_metrica]  (Many-to-One)
dim_uf[id_regiao]             → dim_regiao[id_regiao]    (Many-to-One)
```

---

## Medidas Base de Acesso

```dax
-- % Domicílios com internet (contexto filtrado)
% Internet Total =
CALCULATE(
    AVERAGE(fato_indicadores[valor]),
    dim_metrica[nome] = "pct_domicilios_internet"
)

-- % Acesso em domicílios urbanos
% Internet Urbano =
CALCULATE(
    AVERAGE(fato_indicadores[valor_urbano]),
    dim_metrica[nome] = "pct_domicilios_internet"
)

-- % Acesso em domicílios rurais
% Internet Rural =
CALCULATE(
    AVERAGE(fato_indicadores[valor_rural]),
    dim_metrica[nome] = "pct_domicilios_internet"
)

-- Cobertura nacional (sem filtros de UF)
% Internet Brasil =
CALCULATE(
    [% Internet Total],
    ALL(dim_uf),
    ALL(dim_regiao)
)
```

---

## Brecha Digital

```dax
-- Gap entre acesso urbano e rural (pp)
Gap Digital =
VAR urbano = [% Internet Urbano]
VAR rural  = [% Internet Rural]
RETURN
    IF(NOT ISBLANK(urbano) && NOT ISBLANK(rural), urbano - rural, BLANK())

-- Gap vs média nacional
Gap vs Brasil =
[% Internet Total] - [% Internet Brasil]

-- Classificação por gap digital
Classificação Gap =
SWITCH(
    TRUE(),
    [Gap Digital] >= 30, "🔴 Gap Crítico (≥30pp)",
    [Gap Digital] >= 20, "🟡 Gap Alto (20–30pp)",
    [Gap Digital] >= 10, "🟠 Gap Moderado (10–20pp)",
    "🟢 Gap Baixo (<10pp)"
)
```

---

## Variações Temporais

```dax
-- Penetração no período anterior (ano anterior via slicer)
% Internet Ano Anterior =
CALCULATE(
    [% Internet Total],
    DATEADD(dim_periodo[data_ref], -1, YEAR)
)

-- Variação anual em pontos percentuais
Variação Anual pp =
[% Internet Total] - [% Internet Ano Anterior]

-- Variação anual em %
Variação Anual % =
DIVIDE(
    [Variação Anual pp],
    [% Internet Ano Anterior],
    BLANK()
)

-- CAGR 5 anos (2019 → 2023)
CAGR 5 Anos =
VAR v_2019 = CALCULATE([% Internet Total], dim_periodo[ano] = 2019)
VAR v_2023 = CALCULATE([% Internet Total], dim_periodo[ano] = 2023)
RETURN
    IF(
        NOT ISBLANK(v_2019) && v_2019 > 0,
        POWER(v_2023 / v_2019, 1/4) - 1,
        BLANK()
    )
```

---

## Rankings

```dax
-- Ranking nacional de penetração (1 = maior penetração)
Ranking Penetração =
RANKX(
    ALL(dim_uf),
    [% Internet Total],
    ,
    DESC,
    DENSE
)

-- Ranking de gap digital (1 = maior gap)
Ranking Gap Digital =
RANKX(
    ALL(dim_uf),
    [Gap Digital],
    ,
    DESC,
    DENSE
)

-- Ranking de oportunidade de mercado (1 = maior oportunidade)
Ranking Oportunidade =
RANKX(
    ALL(dim_uf),
    [Score Oportunidade Mercado],
    ,
    DESC,
    DENSE
)
```

---

## Score de Oportunidade de Mercado

```dax
-- Domicílios estimados sem internet (em milhares)
Domicílios sem Internet (mil) =
VAR pop         = RELATED(dim_uf[populacao])
VAR pct_sem     = 1 - [% Internet Total] / 100
VAR media_morad = 3.1   -- média de moradores por domicílio Brasil (IBGE 2022)
RETURN
    DIVIDE(pop * pct_sem, media_morad * 1000, BLANK())

-- Score composto: penetração baixa × população alta × IDH moderado
Score Oportunidade Mercado =
VAR pct_sem = 1 - [% Internet Total] / 100
VAR pop     = RELATED(dim_uf[populacao]) / 1000000   -- em milhões
VAR idh     = RELATED(dim_uf[idh_2010])
-- IDH moderado (0.65–0.75) = maior propensão a adotar se ofertado
VAR idh_peso = IF(idh >= 0.65 && idh <= 0.75, 1.2, IF(idh < 0.65, 0.8, 1.0))
RETURN
    IF(
        NOT ISBLANK(pct_sem) && NOT ISBLANK(pop),
        pct_sem * pop * idh_peso,
        BLANK()
    )

-- Texto descritivo do score para tooltip
Label Oportunidade =
"Score: " & FORMAT([Score Oportunidade Mercado], "0.00") &
" | " & FORMAT([Domicílios sem Internet (mil)], "#,##0") & "k domicílios"
```

---

## Correlação Socioeconômica (para scatter plots)

```dax
-- IDH do estado selecionado (para scatter)
IDH Estado =
RELATED(dim_uf[idh_2010])

-- Quartil de penetração (para segmentação no scatter)
Quartil Penetração =
VAR v = [% Internet Total]
VAR p25 = PERCENTILEINC(ALL(dim_uf), 0.25, [% Internet Total])
VAR p50 = PERCENTILEINC(ALL(dim_uf), 0.50, [% Internet Total])
VAR p75 = PERCENTILEINC(ALL(dim_uf), 0.75, [% Internet Total])
RETURN
    SWITCH(
        TRUE(),
        v <= p25, "Q1 — Baixo",
        v <= p50, "Q2 — Médio-Baixo",
        v <= p75, "Q3 — Médio-Alto",
        "Q4 — Alto"
    )

-- Desvio da linha de tendência (penetração observada vs esperada por IDH)
-- Coeficientes estimados via regressão: pct_internet ≈ 0.93 * IDH_normalizado
Desvio Tendência =
VAR idh_norm = (RELATED(dim_uf[idh_2010]) - 0.630) / (0.824 - 0.630)  -- min-max [0,1]
VAR esperado = 65 + 30 * idh_norm  -- intercepto 65%, slope empírico
RETURN [% Internet Total] - esperado
```

---

## Medidas de Contexto (Cards e KPIs)

```dax
-- Estado selecionado (para título dinâmico)
Estado Selecionado =
IF(
    HASONEVALUE(dim_uf[nome]),
    SELECTEDVALUE(dim_uf[nome]),
    "Brasil"
)

-- Ano selecionado
Ano Selecionado =
IF(
    HASONEVALUE(dim_periodo[ano]),
    FORMAT(SELECTEDVALUE(dim_periodo[ano]), "0"),
    "2019–2023"
)

-- Texto de variação anual formatado
Texto Variação Anual =
VAR v = [Variação Anual pp]
RETURN
    IF(
        ISBLANK(v),
        "—",
        IF(v >= 0,
            "▲ +" & FORMAT(v, "0.0") & "pp vs ano ant.",
            "▼ " & FORMAT(v, "0.0") & "pp vs ano ant."
        )
    )
```

---

## Tabela Calculada — Resumo Executivo

```dax
Resumo por Região =
SUMMARIZECOLUMNS(
    dim_regiao[nome],
    dim_periodo[ano],
    "% Internet",              [% Internet Total],
    "% Urbano",                [% Internet Urbano],
    "% Rural",                 [% Internet Rural],
    "Gap Digital (pp)",        [Gap Digital],
    "Variação Anual pp",       [Variação Anual pp],
    "Score Oportunidade",      [Score Oportunidade Mercado]
)
```

---

## Dicas de Implementação

1. **Scatter plot IDH × Internet**: use `IDH Estado` no eixo X e `% Internet Total` no Y, tamanho da bolha = `Domicílios sem Internet (mil)`
2. **Choropleth**: usar visual de Mapa Preenchido com `dim_uf[sigla]` em Localização e `% Internet Total` em Saturação de Cor
3. **Seletor de ano**: conectar slicer de `dim_periodo[ano]` — as medidas YoY funcionam automaticamente
4. **Formatação condicional**: aplicar escala de cor Branca→Azul escuro em qualquer coluna numérica de penetração

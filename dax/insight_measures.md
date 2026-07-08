# Medidas de Insight — camada de storytelling

> Complemento de `measures.md`: títulos dinâmicos, narrativa automática e cores
> condicionais para o dashboard contar a história sozinho.

## Título dinâmico (Título do visual → fx)

```dax
Título Dinâmico =
"Brecha Digital · " & [Estado Selecionado] & " · " & [Ano Selecionado]
```

## Narrativa automática (card de texto na página Nacional)

```dax
Insight Automático =
VAR piorGap =
    TOPN(1, ALL(dim_uf), [Gap Digital], DESC)
VAR ufGap   = MAXX(piorGap, dim_uf[sigla])
VAR vGap    = MAXX(piorGap, [Gap Digital])
VAR topOpp  =
    TOPN(1, ALL(dim_uf), [Score Oportunidade Mercado], DESC)
VAR ufOpp   = MAXX(topOpp, dim_uf[sigla])
RETURN
    "Maior brecha urbano-rural: " & ufGap & " (" & FORMAT(vGap, "0.0") & " pp). " &
    "Maior oportunidade de expansão: " & ufOpp & " — ver página Oportunidade."
```

## Cores condicionais (fx → por valor de campo)

```dax
Cor Gap =
SWITCH(TRUE(),
    ISBLANK([Gap Digital]), "#7C8894",
    [Gap Digital] >= 30, "#C0564B",   -- crítico
    [Gap Digital] >= 20, "#C9A83C",   -- alto
    [Gap Digital] >= 10, "#D97706",   -- moderado
    "#0F766E")                        -- baixo

Cor vs Brasil =
IF([Gap vs Brasil] >= 0, "#0F766E", "#C0564B")
```

## Delta com seta (rótulo secundário de card)

```dax
Seta Variação =
VAR v = [Variação Anual pp]
RETURN IF(ISBLANK(v), "—",
    IF(v >= 0, "▲ +" & FORMAT(v, "0.0"), "▼ " & FORMAT(v, "0.0")) & " pp vs ano ant.")
```

## Checklist de aplicação por página

| Página | Aplicar |
|---|---|
| Panorama Nacional | `Título Dinâmico` no cabeçalho, card `Insight Automático`, `Seta Variação` sob o card principal |
| Urbano vs Rural | `Cor Gap` no fundo da coluna Gap Digital da tabela |
| Socioeconômico | `Cor vs Brasil` nos pontos/rótulos do scatter |
| Oportunidade | `Cor Gap` na matriz de rankings |

> Tema visual: importar `theme/brecha_digital_theme.json` (Exibição → Temas → Procurar temas).

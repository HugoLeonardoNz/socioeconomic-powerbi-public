# Medidas DAX — Brecha Digital

24 medidas na tabela `_Medidas`, agrupadas em pastas numeradas por domínio. **O modelo é
a fonte da verdade**; se este documento divergir dele, o modelo está certo.

```
[00] Parâmetros   [01] Acesso        [02] Brecha
[03] Rankings     [04] Tempo         [05] Socioeconômico
[06] Oportunidade [08] Narrativa     [09] Auxiliares
```

### Convenções

- Toda divisão usa `DIVIDE`, nunca `/` — evita erro de divisão por zero.
- Percentual guarda a fração (0–1); o formato cuida da exibição. Nada de `* 100` na fórmula.
- Medida sem sentido no contexto devolve `BLANK()`, nunca zero: um zero mente, um vazio
  admite que não sabe.
- Formato definido na medida, não no visual — o número sai igual em qualquer lugar.

---

## [00] Parâmetros

```dax
-- Constante isolada: um único lugar para mudar se a fonte revisar o número.
Moradores por Domicílio = 3.1   -- PNAD Contínua 2023

-- Âncora temporal de todas as medidas de estoque. Num cartão sem filtro devolve
-- 2023; dentro de um gráfico quebrado por ano, devolve o ano daquele ponto.
Ano de Referência = MAX(dim_periodo[Ano])
```

---

## [01] Acesso

```dax
-- Penetração no contexto: para uma UF é o valor dela, para várias é a média simples.
Penetração =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        AVERAGE(fato_indicadores[pct_domicilios_internet]) / 100,
        dim_periodo[Ano] = _ano
    )

-- Nacional PONDERADA pela população: 87,4% em 2023.
-- Ignora seleção de UF de propósito, para servir de linha de base comparável.
Penetração Brasil =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        DIVIDE(
            SUMX(fato_indicadores, fato_indicadores[pct_domicilios_internet] / 100 * RELATED(dim_uf[População])),
            SUMX(fato_indicadores, RELATED(dim_uf[População]))
        ),
        dim_periodo[Ano] = _ano,
        REMOVEFILTERS(dim_uf)
    )

-- Média simples dos 27 estados: 84,9%. Fica exposta ao lado da ponderada porque
-- a diferença de 2,5pp não é ruído — é o efeito de os estados grandes terem mais
-- acesso, e as duas médias respondem perguntas diferentes.
Penetração Média das UFs = ...  -- igual à de cima, sem a ponderação

População Total = SUM(dim_uf[População])
```

---

## [02] Brecha

```dax
-- Leitura em gente do percentual de domicílios. Assume tamanho de domicílio
-- uniforme dentro da UF: não é contagem individual.
Pessoas sem Acesso =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        SUMX(
            fato_indicadores,
            (1 - fato_indicadores[pct_domicilios_internet] / 100) * RELATED(dim_uf[População])
        ),
        dim_periodo[Ano] = _ano
    )

Domicílios sem Internet = DIVIDE([Pessoas sem Acesso], [Moradores por Domicílio])

Lacuna até 100% = IF(NOT ISBLANK([Penetração]), 1 - [Penetração])

Gap vs Brasil (pp) = IF(NOT ISBLANK([Penetração]), ([Penetração] - [Penetração Brasil]) * 100)

-- Distância entre o melhor e o pior estado: 21,3pp em 2023. É a medida da
-- desigualdade, que é o assunto do painel.
Amplitude entre UFs (pp) = ...
```

---

## [03] Rankings

Os dois rankings existem para discordar entre si — é o achado central do painel.

```dax
-- 1 = maior penetração.
--
-- Não usa RANKX direto. Quando a tabela mostra também região ou IDH, a transição
-- de contexto fixa a LINHA INTEIRA de dim_uf, não só a coluna do ranking: toda
-- avaliação devolve o mesmo valor e o ranking sai 1 para todo mundo. Não dá erro,
-- só devolve número errado. Reconstruir a série com REMOVEFILTERS resolve.
Ranking Penetração =
IF(
    NOT ISBLANK([Penetração]),
    VAR _serie =
        ADDCOLUMNS(
            ALLSELECTED(dim_uf[UF]),
            "@p",
            VAR _u = dim_uf[UF]
            RETURN CALCULATE([Penetração], REMOVEFILTERS(dim_uf), dim_uf[UF] = _u)
        )
    VAR _eu = [Penetração]
    RETURN COUNTROWS(FILTER(_serie, [@p] > _eu)) + 1
)

Ranking Volume sem Acesso = ...   -- mesmo padrão, sobre [Pessoas sem Acesso]

-- Quantas posições o estado anda ao trocar o critério. São Paulo anda 2
-- (3º em taxa, 1º em volume); o Maranhão anda 21 (27º em taxa, 6º em volume).
Distância entre Rankings =
IF(
    NOT ISBLANK([Penetração]),
    ABS([Ranking Penetração] - [Ranking Volume sem Acesso])
)
```

---

## [04] Tempo

```dax
Penetração Ano Anterior = ...   -- REMOVEFILTERS(dim_periodo) + Ano = _ano - 1
Variação Anual (pp)     = ([Penetração] - [Penetração Ano Anterior]) * 100
Avanço 2019-2023 (pp)   = ...   -- primeira contra última observação da série
```

> Lembrete de leitura: a série 2019–2022 é retropolada pela variação nacional. Todo
> estado cresce no mesmo ritmo **por construção** — estas medidas dão ordem de grandeza,
> não comparação de velocidade entre estados.

---

## [05] Socioeconômico

```dax
IDH Médio = AVERAGE(dim_uf[IDH])

-- Pearson entre IDH e penetração no conjunto de UFs visível: 0,883 em 2023.
-- Reage ao slicer — não é número fixo escrito no título.
Correlação IDH x Penetração =
VAR _ano = [Ano de Referência]
VAR _t =
    CALCULATETABLE(
        ADDCOLUMNS(
            SUMMARIZE(ALLSELECTED(dim_uf), dim_uf[UF], dim_uf[IDH]),
            "@pen",
            VAR _u = dim_uf[UF]
            RETURN CALCULATE([Penetração], REMOVEFILTERS(dim_uf), dim_uf[UF] = _u)
        ),
        dim_periodo[Ano] = _ano
    )
VAR _n   = COUNTROWS(_t)
VAR _mx  = AVERAGEX(_t, dim_uf[IDH])
VAR _my  = AVERAGEX(_t, [@pen])
VAR _cov = SUMX(_t, (dim_uf[IDH] - _mx) * ([@pen] - _my))
VAR _sx  = SQRT(SUMX(_t, (dim_uf[IDH] - _mx) ^ 2))
VAR _sy  = SQRT(SUMX(_t, ([@pen] - _my) ^ 2))
RETURN IF(_n > 2, DIVIDE(_cov, _sx * _sy))

-- 78,0%: o quanto da variação de acesso entre estados o IDH sozinho explica.
R² IDH = [Correlação IDH x Penetração] ^ 2
```

---

## [06] Oportunidade

```dax
-- Fila de prioridade de expansão: 60% mercado endereçável (quanta gente está
-- fora) + 40% lacuna até universalizar (quão fácil é ganhar share).
-- Os pesos são escolha de modelagem — mudam a fila, por isso estão declarados
-- na página de metodologia do painel e não escondidos no código.
Score Oportunidade = ...   -- componentes reescalados pelo máximo do conjunto

Prioridade =
SWITCH(
    TRUE(),
    ISBLANK([Score Oportunidade]), BLANK(),
    [Score Oportunidade] >= 0.60, "Prioridade alta",
    [Score Oportunidade] >= 0.35, "Prioridade média",
    "Prioridade baixa"
)
```

---

## [08] Narrativa

`Título Dinâmico` e `Leitura da Brecha` leem os próprios números e reagem aos filtros do
rail. A `Leitura da Brecha` é o texto da faixa da primeira página: identifica a
penetração nacional, o total de pessoas sem acesso, a amplitude entre estados, o R² do
IDH e o estado com maior volume desconectado — tudo em uma frase.

## [09] Auxiliares

`Cor Prioridade` e `Cor Gap` devolvem hexadecimal para formatação condicional por valor
de campo. Funcionam em cartão; em gráfico de barras a cor precisa ser declarada por
seletor de categoria (ver `tools/build_report.py`), porque ali o Power BI avalia a
expressão fora do contexto do ponto e pintaria tudo igual.

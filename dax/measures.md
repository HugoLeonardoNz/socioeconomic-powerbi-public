# Medidas DAX — Brecha Digital

26 medidas na tabela `_Medidas`, agrupadas em pastas numeradas por domínio. **O modelo é
a fonte da verdade**; se este documento divergir dele, o modelo está certo.

```
[00] Parâmetros   [01] Acesso        [02] Brecha
[03] Rankings     [04] Tempo         [05] Socioeconômico
[06] Oportunidade [08] Narrativa     [09] Auxiliares
```

O modelo tem três tabelas — `fato_indicadores`, `dim_uf` e `dim_periodo` — e mais nada.
A **data/hora automática do Power BI está desligada**: ela cria uma tabela de datas oculta
por coluna de data, e aqui o grão é ano, não dia. Um modelo com três tabelas deve ter três
tabelas quando alguém abre a visão de Modelo.

### Convenções

- Toda divisão usa `DIVIDE`, nunca `/` — evita erro de divisão por zero.
- Percentual guarda a fração (0–1); o formato cuida da exibição. Nada de `* 100` na fórmula.
- Medida sem sentido no contexto devolve `BLANK()`, nunca zero: um zero mente, um vazio
  admite que não sabe.
- Formato definido na medida, não no visual — o número sai igual em qualquer lugar.

---

## [00] Parâmetros

```dax
-- Sai do próprio modelo: população sobre total de domicílios do ano. Era a
-- constante 3,1 escrita à mão; os dados do painel implicam 2,78 em 2023 e 2,66
-- em 2025, então a constante inflava em ~11% toda conversão de domicílio para
-- gente. Constante que ninguém reconfere envelhece calada.
Moradores por Domicílio =
VAR _ano = [Ano de Referência]
RETURN
    DIVIDE(
        CALCULATE(SUM(dim_uf[População]), REMOVEFILTERS(dim_periodo)),
        CALCULATE(SUM(fato_indicadores[domicilios_total]) * 1000, dim_periodo[Ano] = _ano)
    )

-- Âncora temporal de todas as medidas de estoque. Num cartão sem filtro devolve
-- 2025 (último ano da série); dentro de um gráfico quebrado por ano, devolve o
-- ano daquele ponto.
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

-- Nacional PONDERADA por domicílios: 92,6% em 2023 (IBGE publica 92,5%; a
-- diferença é arredondamento — as tabelas do SIDRA publicam em "mil domicílios").
-- Ignora seleção de UF de propósito, para servir de linha de base comparável.
-- Ponderada por DOMICÍLIOS: razão entre duas somas observadas, que é o método
-- do próprio IBGE. Por isso bate com o release: 92,6% aqui contra 92,5%
-- publicado em 2023. A versão anterior ponderava por POPULAÇÃO sobre o
-- percentual de cada UF — aproximação que existia só porque o modelo não tinha
-- as contagens de domicílios.
Penetração Brasil =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        DIVIDE(
            SUM(fato_indicadores[domicilios_com_internet]),
            SUM(fato_indicadores[domicilios_total])
        ),
        dim_periodo[Ano] = _ano,
        REMOVEFILTERS(dim_uf)
    )

-- Média simples dos 27 estados: 94,6% em 2025 (91,9% em 2023). Fica exposta ao
-- lado da ponderada porque a diferença não é ruído — é o efeito de os estados
-- grandes terem mais acesso, e as duas médias respondem perguntas diferentes.
-- A distância entre elas encolheu junto com a desigualdade: 0,7pp em 2023,
-- 0,4pp em 2025.
Penetração Média das UFs = ...  -- igual à de cima, sem a ponderação

População Total = SUM(dim_uf[População])
```

---

## [02] Brecha

```dax
-- O OBSERVADO vem primeiro. Antes era o contrário: [Pessoas sem Acesso] era
-- calculado do percentual x população, e [Domicílios sem Internet] saia dividindo
-- aquilo por uma constante — ou seja, o número medido pelo IBGE era derivado de
-- uma estimativa. A PNAD publica a contagem de domicílios; ela é a base.
Domicílios sem Internet =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        SUM(fato_indicadores[domicilios_sem_internet]) * 1000,   -- a PNAD publica em mil
        dim_periodo[Ano] = _ano
    )

-- ESTIMATIVA derivada. Assume que domicílio sem internet tem o mesmo tamanho
-- médio que o resto — o que provavelmente subestima, já que domicílio sem acesso
-- tende a ser menor e mais pobre.
Pessoas sem Acesso = [Domicílios sem Internet] * [Moradores por Domicílio]

Lacuna até 100% = IF(NOT ISBLANK([Penetração]), 1 - [Penetração])

Gap vs Brasil (pp) = IF(NOT ISBLANK([Penetração]), ([Penetração] - [Penetração Brasil]) * 100)

-- Distância entre o melhor e o pior estado: 7,7pp em 2025, contra 13,0pp em
-- 2023 e 21,3pp em 2016. É a medida da desigualdade entre estados — e o que ela
-- mostra é que essa desigualdade praticamente fechou.
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

Ranking Volume sem Acesso = ...   -- mesmo padrão, sobre [Domicílios sem Internet]

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
Avanço no Período (pp)   = ...   -- primeira contra última observação da SELEÇÃO
-- Chamava-se "Avanço 2019-2023" e o rótulo passou a mentir quando a série
-- começou em 2016: a medida sempre foi dinâmica, o nome é que era fixo.
-- Sem filtro devolve +24,2pp (2016 → 2025).
```

> Lembrete de leitura: a série 2016–2025 é observada ano a ano, por estado. 2020 não
> existe (a PNAD não coletou o módulo de TIC naquele ano), então medida de variação
> anual precisa tratar o salto 2019 → 2021 como dois anos, não um.

---

## [05] Socioeconômico

```dax
IDH Médio = AVERAGE(dim_uf[IDH])

-- Pearson entre IDH e penetração no conjunto de UFs visível: 0,769 em 2023 e
-- 0,829 em 2025. Não caiu de forma monotônica — foi 0,894 em 2018, 0,769 em 2023
-- e voltou a subir. O que caiu sem parar foi a DISPERSÃO entre estados: 9,6pp de
-- desvio-padrão em 2016 contra 1,9pp em 2025. O IDH continua explicando quase
-- tudo do que sobrou; o que sobrou é que é pouco.
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

## [07] Urbano × Rural

Vivem sobre `fato_situacao`, uma tabela fato **separada**, porque o grão é outro: o IBGE
não publica o cruzamento por UF — a amostra da PNAD não sustenta, e a API devolve `-`
para os 27 estados. O indicador existe em Brasil e Grandes Regiões.

```dax
-- Sem Local selecionado, lê o Brasil explicitamente. Somar Brasil + as 5 regiões
-- devolveria o número certo por acidente (as regiões somam o Brasil, então a razão
-- se preserva) — e depender de acidente é como este painel já errou antes.
Penetração Urbana =
VAR _ano = [Ano de Referência]
RETURN
    CALCULATE(
        DIVIDE(SUM(fato_situacao[domicilios_com_internet]), SUM(fato_situacao[domicilios_total])),
        fato_situacao[Situação] = "Urbana",
        fato_situacao[Ano] = _ano,
        IF(ISFILTERED(fato_situacao[Local]), TRUE(), fato_situacao[Escopo] = "Brasil"),
        REMOVEFILTERS(dim_uf)
    )

Penetração Rural = ...   -- idêntica, com Situação = "Rural"

-- O que sobrou da brecha depois que a diferença entre estados praticamente fechou.
-- 2025: 7,8pp no Brasil, 13,1pp no Norte, 1,8pp no Centro-Oeste.
-- 2023: 13,0pp no Brasil, 24,8pp no Norte, 7,0pp no Centro-Oeste.
Gap Urbano-Rural (pp) =
VAR _u = [Penetração Urbana]
VAR _r = [Penetração Rural]
RETURN IF(NOT ISBLANK(_u) && NOT ISBLANK(_r), (_u - _r) * 100)
```

> **Variar entre regiões é o ponto.** A versão anterior deste painel produzia um gap de
> exatamente 25,0pp em todo estado e todo ano, porque era desvio fixo (+5pp urbano,
> −20pp rural) aplicado sobre o total. Número que não distingue ninguém não é indicador,
> é decoração.

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

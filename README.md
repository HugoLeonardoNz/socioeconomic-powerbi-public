# Brecha Digital no Brasil — Dashboard Power BI

<div align="center">

![Power BI](https://img.shields.io/badge/Power%20BI-Desktop-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![DAX](https://img.shields.io/badge/DAX-23%20medidas-F2C811?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-ETL%20%2B%20report%20as%20code-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Star Schema](https://img.shields.io/badge/Modelo-Star%20Schema-8B5CF6?style=for-the-badge)
![Dados](https://img.shields.io/badge/Dados-IBGE%20PNAD%20observado%202016--2025-0F5F52?style=for-the-badge)
![testes](https://github.com/HugoLeonardoNz/socioeconomic-powerbi-public/actions/workflows/tests.yml/badge.svg)

**Onde está a população brasileira sem internet — e por que o ranking por percentual
aponta para o lugar errado.**

</div>

![Panorama da brecha digital](docs/img/01-brecha.png)

---

## O achado

95,0% dos domicílios brasileiros tinham internet em 2025. Ainda assim, **4,0 milhões de
domicílios seguem sem acesso** — e eles não estão onde o mapa da desigualdade sugere.

E aqui está a parte que muda decisão: **São Paulo é o 5º estado com maior taxa de acesso
do país e o 1º em número absoluto de domicílios desconectados.** Ranking por percentual e
ranking por volume apontam para lugares diferentes.

| Estado | Taxa de acesso | Posição por taxa | Domicílios sem acesso | Posição por volume |
|---|---:|---:|---:|---:|
| São Paulo | 96,6% | 5º | 606 mil | **1º** |
| Minas Gerais | 94,5% | 15º | 445 mil | **2º** |
| Bahia | 92,7% | 22º | 416 mil | **3º** |
| Acre | 90,6% | **27º** | 28 mil | 23º |

O Acre tem a pior taxa do país e o 23º maior volume: 28 mil domicílios. A Bahia anda
**19 posições** ao trocar um critério pelo outro. Um plano de universalização que ignore
o segundo ranking atende o país inteiro em percentual e quase ninguém em gente.

**O segundo achado é maior que o primeiro: a brecha entre estados praticamente fechou.**
O desvio-padrão da penetração entre as 27 unidades caiu de **9,6pp em 2016 para 1,9pp em
2025**, e a distância entre o melhor e o pior estado, de 41,4pp para 7,7pp. O gap entre
Norte+Nordeste e Sul+Sudeste é de **2,8pp** — era 4,6pp em 2023.

O que restou é a distância entre a cidade e o campo: **7,8pp no Brasil**, e **13,1pp no
Norte**, onde o domicílio urbano tem 96,4% de acesso (acima da média nacional) e o rural
tem 83,3%, o pior do país. No Centro-Oeste esse mesmo gap é de 1,8pp. Para um ISP, o
Norte não é praça urbana a cobrir — é obra rural.

**E o que explica o acesso?** O IDH do estado explica **69% da variação** de penetração
entre as unidades da federação (r = 0,829). Aqui vale uma ressalva contra a leitura
fácil: **a correlação não caiu de forma constante** — foi 0,894 em 2018, desceu a 0,769
em 2023 e voltou a 0,829 em 2025. Quem olhasse só dois anos concluiria uma tendência que
a série inteira não mostra. O que caiu sem parar foi a **dispersão**: o IDH continua
explicando quase tudo do que sobrou de variação entre estados; o que mudou é que sobrou
pouca variação.

> **Por que 2025 e não 2023?** O painel se ancora sempre no último ano observado da série.
> O ano de **2023 continua sendo a referência de validação do método**, porque é o ano em
> que dá para conferir a conta contra o release publicado do IBGE (92,6% calculado aqui
> contra 92,5% publicado). Todo número deste README pode ser reproduzido para qualquer
> ano da série mudando o filtro de ano no painel.

O paradoxo em um gráfico: eixo X é a taxa de acesso, eixo Y é quanta gente está de fora.
Os dois rankings, lado a lado, discordam.

![Taxa ou volume](docs/img/02-paradoxo.png)

### O que explica o acesso
IDH contra penetração, com a correlação e o R² calculados em DAX — não escritos à mão no
título.

![O que explica o acesso](docs/img/03-explica.png)

### Onde investir primeiro
Score que combina mercado endereçável com facilidade de ganho, e a fila de prioridade
pronta para uso.

![Onde investir](docs/img/04-oportunidade.png)

### Metodologia e limites
O que é observado, o que é estimado e o que o painel **não** autoriza concluir.

![Metodologia](docs/img/05-metodologia.png)

---

### A PNAD é amostra, e o painel passou a dizer isso

Toda estimativa deste painel vem de pesquisa amostral. Ordenar 27 estados por
estimativa pontual esconde que **os 26 pares vizinhos do ranking por taxa não se
distinguem a 95% de confiança** — o Distrito Federal, 1º com 97,4%, tem intervalo
\[94,7 ; 100\], e São Paulo, 5º com 95,0%, tem \[93,9 ; 96,1\].

O IBGE publica o coeficiente de variação de cada estimativa (variável 10629 do
SIDRA) justamente para isso. Ele entra no modelo em `fato_indicadores` como
`cv_pct`, `margem_pp`, `ic_inferior` e `ic_superior`, e as medidas
`Margem de Erro (pp)` e `Intervalo de Confiança` o expõem no painel.

O método, e o que ele não resolve, estão em
[`data_prep/sidra.py`](data_prep/sidra.py) na função `margem_erro`: o IBGE publica
o CV de cada contagem, não o da razão entre duas, e a correlação entre numerador e
denominador não é publicada. A suposição adotada (denominador fixo) fica no meio
dos dois extremos possíveis e erra para o lado conservador.

**Consequência para a leitura:** o paradoxo taxa × volume fica mais forte, não mais
fraco. O ranking por volume separa de verdade — 606 mil domicílios em SP contra
445 mil em Minas em 2025 não é empate técnico. O ranking por taxa, entre vizinhos, é.

---

## Honestidade sobre os dados

Este é o ponto que separa um painel bonito de um painel confiável, então fica no topo e
não escondido no rodapé:

| Dado | Situação |
|------|----------|
| Penetração por UF, **2025** (último ano) | **Observado** — IBGE, PNAD Contínua |
| Penetração por UF, **2016–2025** | **Observado** — série anual da PNAD Contínua, sem retropolação |
| IDH por estado | **Observado** — PNUD, Atlas do Desenvolvimento Humano (censo 2010) |
| População e densidade | **Observado** — IBGE, estimativas 2023 e Censo 2022 |

**Consequência prática:** a série 2016–2025 é observada ano a ano, por estado — dá para
comparar velocidade de adoção entre estados, o que a versão retropolada anterior não
permitia (lá todo estado crescia no mesmo ritmo, por construção).

**2020 não existe na série.** A PNAD Contínua não coletou o módulo de TIC naquele ano por
causa da pandemia. O ponto não é interpolado só para a linha do gráfico ficar contínua —
o buraco é a informação. Isso está dito também na página de metodologia do painel.

### O recorte urbano × rural voltou — e mudou de grão

Ele tinha sido removido. A fonte offline só sabia produzi-lo aplicando um desvio fixo sobre
o total (+5pp urbano, −20pp rural), o que gerava um gap de **exatamente 25,0 pontos
percentuais em todos os 27 estados, em todos os anos**. Um número que parece análise e não
é: não distinguia estado nenhum porque foi construído para não distinguir.

Agora ele está de volta, observado — e é o achado mais forte do painel: em 2025, **7,8pp
no Brasil, 13,1pp no Norte, 1,8pp no Centro-Oeste** (em 2023 eram 13,0 / 24,8 / 7,0). Variar entre regiões é o que faz dele um
indicador em vez de uma decoração.

Uma coisa mudou junto: **o grão**. O IBGE não publica urbano × rural por UF — a amostra da
PNAD não sustenta o cruzamento, e a API devolve `-` para os 27 estados. O recorte existe em
Brasil e Grandes Regiões, e é assim que ele entra no modelo: numa tabela fato **separada**
(`fato_situacao`), não como coluna do fato de UF.

Essa separação é deliberada. Enfiar um indicador de grão regional no fato de UF obrigaria a
repetir o valor da região em cada um dos seus estados — que é exatamente a forma como a
versão anterior produziu um "gap por UF" que não existia.

---

## Camada visual gerada por código

A pasta `Report/definition` dentro do `.pbix` é JSON. [`tools/build_report.py`](tools/build_report.py)
reescreve essa camada inteira a partir de uma especificação declarativa, preservando o
modelo de dados.

```bash
python tools/build_report.py
```

Isso dá grid calculado (nenhum visual 3px fora do alinhamento), formatação definida uma
vez só e revisão do relatório por diff de código.

O design é deliberadamente diferente do meu outro projeto Power BI
([telecom-powerbi-public](https://github.com/HugoLeonardoNz/telecom-powerbi-public)):
lá é escuro, ciano sobre preto, navegação no topo e faixa densa de KPIs; aqui é claro cor
de papel, paleta terrosa, rail vertical à esquerda com os filtros dentro, títulos em
serifa e menos visuais por página. Dashboard não é template — cada assunto pede uma
leitura diferente.

---

## Modelo de dados

```
        ┌──────────────────────────┐
        │   fato_indicadores       │        grão: UF × ano
        │──────────────────────────│        135 linhas
   ┌────┤ id_uf                    ├────┐
   │    │ id_periodo               │    │
   │    │ pct_domicilios_internet  │    │
   │    └──────────────────────────┘    │
   │                                    │
 dim_uf                            dim_periodo
 ──────                            ───────────
 UF · Estado · Região              Ano
 População · Densidade · IDH
```

**Duas dimensões, e isso é intencional.** Havia uma `dim_metrica` anunciando cinco
métricas das quais o fato carregava uma — dimensão que ninguém aponta é decoração, foi
removida. `dim_regiao` também saiu: região é atributo da UF, e mantê-la como tabela
criaria um floco de neve sem ganho.

População, densidade e IDH vivem **só** em `dim_uf`. Estavam copiados no fato, repetidos
cinco vezes por estado — e no caso do IDH, um valor de 2010 fingindo série anual.

---

## Medidas

29 medidas na tabela `_Medidas`, agrupadas por domínio. As que carregam decisão:

| Medida | Por que existe |
|--------|----------------|
| `Penetração Brasil` | Nacional **ponderada por domicílios**: 95,0% em 2025, contra 94,6% da média simples dos 27 estados. É a razão entre duas somas observadas — o método do próprio IBGE, e por isso bate com o release (92,6% contra 92,5% em 2023). As duas médias respondem perguntas diferentes e o painel mostra as duas. |
| `Pessoas sem Acesso` | Traduz percentual de domicílios em gente. É o eixo do paradoxo taxa × volume. |
| `Distância entre Rankings` | Quantas posições o estado se move ao trocar taxa por volume. Mede o paradoxo direto: a Bahia anda 20 posições. |
| `Correlação IDH x Penetração` | Pearson calculado em DAX sobre o conjunto filtrado — reage ao slicer, não é número fixo no título. |
| `Score Oportunidade` | 60% volume endereçável + 40% lacuna até 100%. Os pesos são escolha minha, declarada na página de metodologia. |
| `Leitura da Brecha` | Narrativa que lê os próprios números e acompanha os filtros. |

Dicionário completo em [`dax/measures.md`](dax/measures.md).

> Três dessas medidas precisaram reconstruir a série com `REMOVEFILTERS` + reaplicação da
> UF. Sem isso, o `CALCULATE` dentro do iterador herda o filtro do próprio ponto, a série
> de comparação colapsa num valor só e o ranking sai `1` para todo mundo. É uma armadilha
> silenciosa: não dá erro, só devolve número errado.

---

## Reproduzir

```bash
pip install -r requirements.txt
python data_prep/prepare_data.py    # star schema em data/processed/
```

Depois, abrir `digital_divide_brasil.pbix` no Power BI Desktop.

O caminho dos CSVs é o parâmetro **`PastaDados`** do Power Query. Ao clonar em outra
máquina: *Transformar dados → Gerenciar parâmetros → PastaDados*, apontando para a pasta
`data/processed` local.

> O script tenta a API SIDRA do IBGE primeiro e cai para a base offline embutida quando a
> API está fora (ela retorna 500 com frequência). O aviso aparece no console.

---

## Stack

`Python 3.x` · `pandas` · `requests` · `Power BI Desktop` · `DAX` · `Power Query (M)` ·
`PBIR` (formato JSON do relatório)

---

## Autor

**Hugo Leonardo**
Analista de Dados Pleno — SQL · Python · Power BI
Speed Fibra · Santa Luzia, MG

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Hugo%20Leonardo-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/hugo-leonardo-data-analyst/)
[![GitHub](https://img.shields.io/badge/GitHub-HugoLeonardoNz-181717?style=flat&logo=github)](https://github.com/HugoLeonardoNz)

# Brecha Digital no Brasil — Dashboard Power BI

<div align="center">

![Power BI](https://img.shields.io/badge/Power%20BI-Desktop-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![DAX](https://img.shields.io/badge/DAX-24%20medidas-F2C811?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-ETL%20%2B%20report%20as%20code-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Star Schema](https://img.shields.io/badge/Modelo-Star%20Schema-8B5CF6?style=for-the-badge)
![Dados](https://img.shields.io/badge/Dados-IBGE%20%2B%20série%20retropolada-0F5F52?style=for-the-badge)

**Onde está a população brasileira sem internet — e por que o ranking por percentual
aponta para o lugar errado.**

</div>

![Panorama da brecha digital](docs/img/01-brecha.png)

---

## O achado

87,4% dos domicílios brasileiros tinham internet em 2023. Ainda assim, **26,7 milhões de
pessoas** viviam em casas sem acesso.

E aqui está a parte que muda decisão: **São Paulo é o 3º estado com maior taxa de acesso
e o 1º em número absoluto de pessoas desconectadas** — 3,0 milhões, mais que o Maranhão
(1,9 mi), que é o último colocado em taxa.

| Estado | Penetração | Posição em taxa | Pessoas sem acesso | Posição em volume |
|--------|-----------:|----------------:|-------------------:|------------------:|
| São Paulo | 93,5% | 3º | 3,03 mi | **1º** |
| Bahia | 80,3% | 21º | 2,94 mi | **2º** |
| Minas Gerais | 88,7% | 10º | 2,42 mi | **3º** |
| Maranhão | 73,8% | **27º** | 1,87 mi | 6º |

Quem planeja infraestrutura com o ranking de percentual na mão vai para o estado errado.
O painel mostra os dois critérios lado a lado justamente porque eles discordam.

**E o que explica o acesso?** O IDH do estado sozinho explica **78% da variação** de
penetração entre as unidades da federação (r = 0,883). A brecha digital é, antes de tudo,
um retrato da brecha social.

---

## As páginas

### Taxa ou volume?
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

## Honestidade sobre os dados

Este é o ponto que separa um painel bonito de um painel confiável, então fica no topo e
não escondido no rodapé:

| Dado | Situação |
|------|----------|
| Penetração por UF, **2023** | **Observado** — IBGE, PNAD Contínua |
| Penetração por UF, **2019–2022** | **Retropolado** — aplica a variação nacional do período a cada estado |
| IDH por estado | **Observado** — PNUD, Atlas do Desenvolvimento Humano (censo 2010) |
| População e densidade | **Observado** — IBGE, estimativas 2023 e Censo 2022 |

**Consequência prática:** como a série anterior a 2023 é retropolada pela média nacional,
todo estado cresce no mesmo ritmo por construção. A série serve para dar ordem de
grandeza da evolução; **não serve** para comparar velocidade de adoção entre estados. Isso
está dito também dentro do painel, na página de metodologia.

### O recorte urbano × rural foi removido

Ele existia. A fonte offline só sabia produzi-lo aplicando um desvio fixo sobre o total
(+5pp urbano, −20pp rural), o que gerava um gap de **exatamente 25,0 pontos percentuais em
todos os 27 estados, em todos os anos**. Um número que parece análise e não é: não
distinguia estado nenhum porque foi construído para não distinguir.

Preferi um indicador a menos do que um indicador falso.

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

24 medidas na tabela `_Medidas`, agrupadas por domínio. As que carregam decisão:

| Medida | Por que existe |
|--------|----------------|
| `Penetração Brasil` | Nacional **ponderada por população** (87,4%), diferente da média simples dos 27 estados (84,9%). Os estados grandes têm mais acesso — as duas médias respondem perguntas diferentes e o painel mostra as duas. |
| `Pessoas sem Acesso` | Traduz percentual de domicílios em gente. É o eixo do paradoxo taxa × volume. |
| `Distância entre Rankings` | Quantas posições o estado se move ao trocar taxa por volume. Mede o paradoxo direto: Maranhão anda 21 posições. |
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

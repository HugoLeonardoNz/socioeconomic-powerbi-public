# Guia de Construção Manual — digital_divide_brasil.pbix

> Passo a passo para montar o arquivo Power BI do zero. Tempo estimado: 3–5 horas.
> Pré-requisito: Power BI Desktop (gratuito) instalado.

---

## Etapa 0 — Dados prontos

Os CSVs do star schema já estão gerados em `data/processed/`:

| Arquivo | Linhas | Papel |
|---|---|---|
| `fato_indicadores.csv` | 135 | Fato (27 UFs × 5 anos) |
| `dim_uf.csv` | 27 | Dimensão estado (com população, densidade, IDH) |
| `dim_periodo.csv` | 5 | Dimensão ano (2019–2023) |
| `dim_metrica.csv` | 5 | Dimensão métrica |
| `dim_regiao.csv` | 5 | Dimensão região |

Se precisar regerar: `python data_prep/prepare_data.py` (usa API SIDRA do IBGE; se a API estiver fora do ar, cai automaticamente no fallback offline com dados PNAD 2023 embutidos).

---

## Etapa 1 — Importar os CSVs

1. Power BI Desktop → **Obter Dados → Texto/CSV**
2. Importe os 5 arquivos de `data/processed/` (um por vez)
3. Em cada um, clique **Transformar Dados** e confira no Power Query:
   - `fato_indicadores`: `valor`, `valor_urbano`, `valor_rural`, `densidade_km2`, `idh_2010` como **Número Decimal**; ids e `populacao` como **Número Inteiro**
   - `dim_periodo`: `data_ref` como **Data**
   - Encoding: os CSVs estão em UTF-8 com BOM — acentos devem aparecer corretos
4. **Fechar e Aplicar**

## Etapa 2 — Modelo (relacionamentos)

Na exibição **Modelo**, crie (ou confirme, se autodetectados):

```
fato_indicadores[id_uf]      → dim_uf[id_uf]            (N:1, filtro único)
fato_indicadores[id_periodo] → dim_periodo[id_periodo]  (N:1)
fato_indicadores[id_metrica] → dim_metrica[id_metrica]  (N:1)
dim_uf[id_regiao]            → dim_regiao[id_regiao]    (N:1)
```

Extras recomendados:
- Marcar `dim_periodo` como **tabela de data** (campo `data_ref`) — necessário para o `DATEADD` da medida `% Internet Ano Anterior`
- Ocultar as colunas `id_*` da fato (botão direito → Ocultar no modo relatório)

## Etapa 3 — Medidas DAX

Copie todas as medidas de [`dax/measures.md`](../dax/measures.md), nesta ordem (as de cima são dependência das de baixo):

1. Base: `% Internet Total`, `% Internet Urbano`, `% Internet Rural`, `% Internet Brasil`
2. Brecha: `Gap Digital`, `Gap vs Brasil`, `Classificação Gap`
3. Temporais: `% Internet Ano Anterior`, `Variação Anual pp`, `Variação Anual %`, `CAGR 5 Anos`
4. Score: `Domicílios sem Internet (mil)`, `Score Oportunidade Mercado`, `Label Oportunidade`
5. Rankings: `Ranking Penetração`, `Ranking Gap Digital`, `Ranking Oportunidade`
6. Scatter: `IDH Estado`, `Quartil Penetração`, `Desvio Tendência`
7. Contexto: `Estado Selecionado`, `Ano Selecionado`, `Texto Variação Anual`

Dica: crie uma tabela vazia `_Medidas` (Inserir → Tabela) e mova as medidas para lá — organização que entrevistador repara.

**Atenção:** `Domicílios sem Internet (mil)`, `Score Oportunidade Mercado`, `IDH Estado` e `Desvio Tendência` usam `RELATED(dim_uf[...])` — elas devem ser criadas **na tabela `fato_indicadores`** (contexto de linha da fato).

## Etapa 4 — Páginas e visuais

### Página 1 — Panorama Nacional
- 4 cards no topo: `% Internet Brasil`, `Variação Anual pp`, `CAGR 5 Anos`, `Domicílios sem Internet (mil)`
- **Mapa preenchido (choropleth)**: Localização = `dim_uf[sigla]`, Saturação = `% Internet Total`
- **Linha**: eixo = `dim_periodo[ano]`, valores = `% Internet Total`, legenda = `dim_regiao[nome]`
- Slicers: `dim_periodo[ano]`, `dim_regiao[nome]`

### Página 2 — Urbano vs Rural
- **Barras agrupadas** (ou dumbbell via tornado): `% Internet Urbano` vs `% Internet Rural` por `dim_uf[sigla]`, ordenado por `Gap Digital`
- **Tabela**: UF, `% Internet Urbano`, `% Internet Rural`, `Gap Digital`, `Classificação Gap` (formatação condicional por cor)
- Card: `Gap Digital` médio nacional

### Página 3 — Socioeconômico
- **Dispersão**: X = `IDH Estado`, Y = `% Internet Total`, tamanho = `Domicílios sem Internet (mil)`, legenda = `dim_regiao[nome]`, detalhe = `dim_uf[sigla]`
- Ative a **linha de tendência** no painel Análise
- **Tabela**: UF, IDH, `% Internet Total`, `Desvio Tendência`, `Quartil Penetração`

### Página 4 — Oportunidade de Mercado
- **Barras horizontais**: `Score Oportunidade Mercado` por UF (top 10), tooltip = `Label Oportunidade`
- **Matriz**: região → UF com `Ranking Oportunidade`, `Ranking Penetração`, `Domicílios sem Internet (mil)`
- Card de título dinâmico: `Estado Selecionado` + `Texto Variação Anual`

## Etapa 5 — Validação (números esperados com o fallback offline)

| Checagem | Valor esperado |
|---|---|
| `% Internet Brasil` (ano 2023) | ≈ 85,5% (média simples das UFs) |
| `% Internet Total` SP 2023 | 93,5% |
| `% Internet Total` MA 2023 | 73,8% |
| `Gap Digital` (qualquer UF) | 25,0 pp (urbano +5 / rural −20 do fallback) |
| Linhas na fato | 135 |

Se importar dados reais da API depois, os valores urbano/rural deixam de ser offsets fixos e o Gap varia por UF.

## Etapa 6 — Finalizar

1. Tema: Exibição → Temas → Procurar temas → importar `theme/brecha_digital_theme.json` (cards com borda arredondada, paleta teal/âmbar, fundo de página cinza-claro). Depois aplique as medidas de `dax/insight_measures.md` (título dinâmico, narrativa automática, cores condicionais)
2. Salvar como `digital_divide_brasil.pbix` na raiz do projeto
3. Exportar screenshots das 4 páginas para `docs/img/` e referenciá-los no README (repos de Power BI sem imagem não convencem recrutador)
4. Opcional: publicar no Power BI Service e incluir link "ao vivo" no README

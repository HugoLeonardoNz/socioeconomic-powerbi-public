# Modelo de dados — Brecha Digital

```
        ┌──────────────────────────┐
        │   fato_indicadores       │        grão: UF × ano
        │──────────────────────────│        135 linhas (27 UFs × 5 anos)
   ┌────┤ id_fato        (chave)   ├────┐
   │    │ id_uf          (FK)      │    │
   │    │ id_periodo     (FK)      │    │
   │    │ pct_domicilios_internet  │    │
   │    └──────────────────────────┘    │
   │                                    │
   ▼                                    ▼
 dim_uf (27)                       dim_periodo (5)
 ───────────                       ──────────────
 id_uf          (PK)               id_periodo  (PK)
 codigo_ibge                       Ano
 UF · Estado · Região              data_ref
 População
 Densidade (hab/km²)
 IDH
```

**Relacionamentos:** muitos-para-um, filtro simples, do fato para a dimensão. Nenhuma
relação bidirecional.

---

## Grão

Uma linha por unidade da federação por ano. A única medida observada é
`pct_domicilios_internet` — proporção de domicílios com acesso à internet.

---

## Decisões de modelagem

### Duas dimensões, não quatro

O modelo tinha `dim_metrica` (cinco métricas) e `dim_regiao`. Ambas saíram:

- **`dim_metrica`** anunciava cinco métricas — penetração total, urbana, rural, renda e
  população — das quais o fato carregava **uma**. Dimensão para a qual nenhuma chave
  aponta é decoração: infla o diagrama e não muda nenhuma consulta.
- **`dim_regiao`** transformava o modelo em floco de neve (fato → dim_uf → dim_regiao)
  sem ganho nenhum. Região é atributo do estado e vive como coluna de `dim_uf`.

### Atributos da UF ficam só na dimensão

`População`, `Densidade` e `IDH` estavam **copiados dentro do fato**, repetidos cinco
vezes por estado. Pior no caso do IDH: um valor do censo 2010 replicado ao longo de
2019–2023, dando aparência de série anual a um número que não varia.

Agora vivem apenas em `dim_uf`. As medidas alcançam esses valores com `RELATED()` quando
precisam ponderar — por exemplo, `Penetração Brasil`, que pondera a média nacional pela
população de cada estado.

### O recorte urbano × rural não existe mais

Existia como duas colunas no fato. A fonte offline só sabia produzi-lo aplicando um
desvio fixo sobre o total (+5pp urbano, −20pp rural), o que resultava num gap de
**exatamente 25,0 pontos percentuais em todos os 27 estados, em todos os anos**.

Um indicador construído para não distinguir estado nenhum não pode ser usado para
comparar estados. Foi removido do pipeline, do modelo e do dashboard.

---

## Tipagem e cultura

Os CSVs usam ponto como separador decimal e o modelo está em pt-BR, onde o ponto é
separador de milhar. Sem cultura explícita na conversão, `74.5` vira `745` — silenciosamente,
sem erro, com a penetração indo para 874% e a população sem acesso ficando negativa.

As consultas M declaram a cultura:

```m
Table.TransformColumnTypes(fonte, {{"pct_domicilios_internet", type number}}, "en-US")
```

---

## Origem do caminho dos arquivos

O caminho da pasta de CSVs é o parâmetro **`PastaDados`** do Power Query, não um literal
dentro de cada consulta. Ao clonar o repositório, muda-se em um lugar só:
*Transformar dados → Gerenciar parâmetros*.

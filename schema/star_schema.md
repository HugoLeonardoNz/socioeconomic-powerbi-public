# Star Schema — Brecha Digital no Brasil

## Diagrama

```
                         ┌────────────────────────────────┐
                         │         dim_periodo             │
                         │ id_periodo  INT  PK             │
                         │ ano         INT                 │
                         │ data_ref    DATE                │
                         └────────────────┬───────────────┘
                                          │ 1
                                          │
┌──────────────────────┐    ┌─────────────▼──────────────────────────┐    ┌──────────────────────────┐
│      dim_uf          │    │           fato_indicadores              │    │       dim_metrica        │
│ id_uf      INT  PK   │1   │ id_fato        INT  PK                  │  1 │ id_metrica   INT  PK     │
│ codigo_ibge INT      ├────┤ id_uf          INT  FK → dim_uf        ├────┤ nome         VARCHAR     │
│ sigla      CHAR(2)   │    │ id_periodo     INT  FK → dim_periodo   │    │ unidade      VARCHAR     │
│ nome       VARCHAR   │    │ id_metrica     INT  FK → dim_metrica   │    │ categoria    VARCHAR     │
│ id_regiao  INT  FK   │    │ valor          FLOAT  (valor principal) │    │ descricao    TEXT        │
│ populacao  INT       │    │ valor_urbano   FLOAT                   │    └──────────────────────────┘
│ densidade  FLOAT     │    │ valor_rural    FLOAT                   │
│ idh_2010   FLOAT     │    │ populacao      INT    (desnorm.)        │
└──────────────────────┘    │ densidade_km2  FLOAT  (desnorm.)        │
                            │ idh_2010       FLOAT  (desnorm.)        │
       ┌────────────────────└────────────────────────────────────────┘
       │
       │ Many-to-One (via dim_uf[id_regiao])
       ▼
┌──────────────────────┐
│      dim_regiao      │
│ id_regiao   INT  PK  │
│ nome        VARCHAR  │
│ sigla       CHAR(2)  │
└──────────────────────┘
```

## Grão da Tabela Fato

**1 registro = 1 estado × 1 período × 1 métrica**

| Campo | Exemplo |
|-------|---------|
| id_uf | 35 (São Paulo) |
| id_periodo | 5 (2023) |
| id_metrica | 1 (pct_domicilios_internet) |
| valor | 88.4 (%) |
| valor_urbano | 91.2 |
| valor_rural | 68.7 |

---

## Tabela Fato: fato_indicadores

| Campo | Tipo | Nulo | Descrição |
|-------|------|------|-----------|
| `id_fato` | INT | ✗ | Chave surrogate |
| `id_uf` | INT | ✗ | FK → dim_uf |
| `id_periodo` | INT | ✗ | FK → dim_periodo |
| `id_metrica` | INT | ✗ | FK → dim_metrica |
| `valor` | FLOAT | ✓ | Valor principal da métrica |
| `valor_urbano` | FLOAT | ✓ | Valor para domicílios urbanos |
| `valor_rural` | FLOAT | ✓ | Valor para domicílios rurais |
| `populacao` | INT | ✓ | Desnormalizado para cálculos de oportunidade |
| `densidade_km2` | FLOAT | ✓ | Desnormalizado |
| `idh_2010` | FLOAT | ✓ | Desnormalizado |

> **Nota sobre desnormalização:** `populacao`, `densidade_km2` e `idh_2010` foram copiados de `dim_uf` para a fato para facilitar medidas DAX que precisam de `SUMPRODUCT` ou `SUMX` sem `RELATED()`. É uma opção deliberada de performance.

---

## dim_uf

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_uf` | INT PK | Código IBGE do estado |
| `codigo_ibge` | INT | Mesmo que id_uf (para JOIN com GeoJSON) |
| `sigla` | CHAR(2) | Ex: SP, MG, RJ |
| `nome` | VARCHAR | Nome completo |
| `id_regiao` | INT FK | Chave para dim_regiao |
| `regiao` | VARCHAR | Desnormalizado para facilidade |
| `populacao` | INT | Estimativa IBGE 2023 |
| `densidade_km2` | FLOAT | Hab/km² |
| `idh_2010` | FLOAT | IDH-M 2010 (PNUD Brasil) |

---

## dim_periodo

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_periodo` | INT PK | 1–5 |
| `ano` | INT | 2019–2023 |
| `data_ref` | DATE | 31/12 do ano (para DATEADD/SAMEPERIODLASTYEAR) |

---

## dim_metrica

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_metrica` | INT PK | 1–5 |
| `nome` | VARCHAR | Identificador (slug) da métrica |
| `unidade` | VARCHAR | %, R$, hab, etc. |
| `categoria` | VARCHAR | Acesso, Renda, Demo |
| `direcao_positiva` | BIT | 1 = maior é melhor |
| `descricao` | TEXT | Descrição completa |

---

## dim_regiao

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_regiao` | INT PK | 1–5 |
| `nome` | VARCHAR | Norte, Nordeste, Sudeste, Sul, Centro-Oeste |
| `sigla` | CHAR(2) | N, NE, SE, S, CO |

---

## Decisões de Modelagem

### Por que star schema (e não snowflake)?
O dataset tem apenas 27 estados e 5 anos — volume muito baixo para justificar normalização adicional. O star schema reduz a complexidade dos relacionamentos no Power BI e melhora a legibilidade das medidas DAX.

### Por que `valor_urbano` e `valor_rural` na fato (e não numa dimensão)?
Essas são quebras da **mesma métrica** (penetração de internet), não dimensões independentes. Manter como colunas da fato permite calcular `Gap Digital = valor_urbano - valor_rural` diretamente em DAX sem JOINS adicionais.

### Por que desnormalizar populacao/IDH na fato?
O DAX tem performance ruim com `SUMX(..., RELATED(...))` em tabelas grandes. Para as fórmulas de `Score Oportunidade` que precisam de produto entre métricas de UFs diferentes, ter os valores na fato evita o custo de lookup.

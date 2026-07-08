# Dados — IBGE + PNUD Brasil

## Fontes

| Dataset | Fonte | Como obter |
|---------|-------|-----------|
| % Domicílios com internet | IBGE PNAD Contínua | API SIDRA (automático no script) |
| % Urbano/Rural | IBGE PNAD Contínua | API SIDRA (automático no script) |
| Estimativas populacionais | IBGE | API (automático no script) |
| IDH por estado | PNUD Brasil | Download manual — ver abaixo |
| Renda domiciliar per capita | IBGE PNAD Contínua | API SIDRA (automático no script) |
| Densidade demográfica | IBGE Censo 2022 | API (automático no script) |

## Download Automático

Execute o script:
```bash
python data_prep/prepare_data.py
```

O script faz chamadas à API pública do IBGE SIDRA para todos os dados, exceto IDH.

## IDH por Estado (download manual)

O IDH estadual é disponibilizado pelo PNUD Brasil:
1. Acesse **atlasbrasil.org.br** → Banco de Dados → consultar por UF
2. Selecione variável: IDH-M (Índice de Desenvolvimento Humano Municipal — agregado por UF)
3. Exporte como CSV
4. Salve como `data/raw/idh_estados.csv`

Formato esperado:
```
uf_sigla,uf_nome,idh_2010,idh_2017,idh_2021
AC,Acre,0.663,0.692,0.708
AL,Alagoas,0.631,0.666,0.683
```

## Saída Esperada em `data/processed/`

| Arquivo | Linhas | Chave |
|---------|--------|-------|
| `fato_indicadores.csv` | ~675 | uf × periodo × metrica |
| `dim_uf.csv` | 27 | id_uf |
| `dim_periodo.csv` | 5 | id_periodo (anos 2019–2023) |
| `dim_metrica.csv` | 5 | id_metrica |
| `dim_regiao.csv` | 5 | id_regiao |

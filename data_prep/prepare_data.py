"""
Data preparation pipeline for Brecha Digital no Brasil Power BI Dashboard.

Fetches IBGE PNAD Contínua data via SIDRA API and loads IDH CSV,
then builds a star-schema set of CSVs ready for Power BI import.

Usage:
    python data_prep/prepare_data.py

Requires internet access for IBGE API calls.

Input (auto-fetched via API):
    IBGE SIDRA: % domicílios com internet, urbano/rural breakdown, renda, população

Input (manual):
    data/raw/idh_estados.csv    (PNUD Brasil — see data/README.md)

Output (data/processed/):
    fato_indicadores.csv
    dim_uf.csv
    dim_periodo.csv
    dim_metrica.csv
    dim_regiao.csv
"""

import os
import json
import requests
import pandas as pd
import numpy as np
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

SIDRA_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"

# ---------------------------------------------------------------------------
# Geographic reference
# ---------------------------------------------------------------------------

UF_INFO = {
    "11": ("RO", "Rondônia",            "Norte",        1581019,  6.58,  0.736),
    "12": ("AC", "Acre",                "Norte",         830026,  4.47,  0.708),
    "13": ("AM", "Amazonas",            "Norte",        4144597,  2.23,  0.708),
    "14": ("RR", "Roraima",             "Norte",         636707,  2.01,  0.750),
    "15": ("PA", "Pará",                "Norte",        8603850,  6.07,  0.646),
    "16": ("AP", "Amapá",               "Norte",         845731,  4.69,  0.708),
    "17": ("TO", "Tocantins",           "Norte",        1590248,  5.00,  0.699),
    "21": ("MA", "Maranhão",            "Nordeste",     7153262,  7.28,  0.639),
    "22": ("PI", "Piauí",               "Nordeste",     3289290,  7.28,  0.646),
    "23": ("CE", "Ceará",               "Nordeste",     9240580, 12.40,  0.682),
    "24": ("RN", "Rio Grande do Norte", "Nordeste",     3560903, 60.06,  0.684),
    "25": ("PB", "Paraíba",             "Nordeste",     4059905, 66.70,  0.658),
    "26": ("PE", "Pernambuco",          "Nordeste",     9674793, 89.62,  0.673),
    "27": ("AL", "Alagoas",             "Nordeste",     3351543,112.33,  0.631),
    "28": ("SE", "Sergipe",             "Nordeste",     2338474,106.76,  0.665),
    "29": ("BA", "Bahia",               "Nordeste",    14930634, 24.82,  0.660),
    "31": ("MG", "Minas Gerais",        "Sudeste",     21411923, 33.41,  0.731),
    "32": ("ES", "Espírito Santo",      "Sudeste",      4108508, 76.96,  0.740),
    "33": ("RJ", "Rio de Janeiro",      "Sudeste",     17463349,365.23,  0.761),
    "35": ("SP", "São Paulo",           "Sudeste",     46649132,166.25,  0.783),
    "41": ("PR", "Paraná",              "Sul",         11597484, 52.40,  0.749),
    "42": ("SC", "Santa Catarina",      "Sul",          7609601, 65.27,  0.774),
    "43": ("RS", "Rio Grande do Sul",   "Sul",         11466630, 39.79,  0.746),
    "50": ("MS", "Mato Grosso do Sul",  "Centro-Oeste", 2833469,  6.86,  0.729),
    "51": ("MT", "Mato Grosso",         "Centro-Oeste", 3784239,  3.36,  0.725),
    "52": ("GO", "Goiás",               "Centro-Oeste", 7266975, 17.65,  0.735),
    "53": ("DF", "Distrito Federal",    "Centro-Oeste", 3094325,444.66,  0.824),
}
# columns: sigla, nome, regiao, populacao, densidade_km2, idh_2010


# ---------------------------------------------------------------------------
# 1. Dimension tables
# ---------------------------------------------------------------------------

def build_dim_regiao() -> pd.DataFrame:
    regioes = sorted(set(v[2] for v in UF_INFO.values()))
    df = pd.DataFrame({"nome": regioes, "sigla": ["CO", "NE", "N", "SE", "S"][:len(regioes)]})
    # deterministic order
    order = {"Norte": 1, "Nordeste": 2, "Sudeste": 3, "Sul": 4, "Centro-Oeste": 5}
    df["id_regiao"] = df["nome"].map(order)
    regiao_siglas = {"Norte": "N", "Nordeste": "NE", "Sudeste": "SE", "Sul": "S", "Centro-Oeste": "CO"}
    df["sigla"] = df["nome"].map(regiao_siglas)
    return df.sort_values("id_regiao").reset_index(drop=True)


def build_dim_uf(dim_regiao: pd.DataFrame) -> pd.DataFrame:
    regiao_id = dim_regiao.set_index("nome")["id_regiao"]
    rows = []
    for cod, (sigla, nome, regiao, pop, dens, idh) in UF_INFO.items():
        rows.append({
            "id_uf":          int(cod),
            "codigo_ibge":    int(cod),
            "sigla":          sigla,
            "nome":           nome,
            "id_regiao":      regiao_id[regiao],
            "regiao":         regiao,
            "populacao":      pop,
            "densidade_km2":  dens,
            "idh_2010":       idh,
        })
    return pd.DataFrame(rows).sort_values("id_uf").reset_index(drop=True)


def build_dim_periodo() -> pd.DataFrame:
    anos = list(range(2019, 2024))
    df = pd.DataFrame({
        "id_periodo": range(1, len(anos) + 1),
        "ano":        anos,
        "data_ref":   [f"{a}-12-31" for a in anos],
    })
    return df


# ---------------------------------------------------------------------------
# 2. Fetch IBGE data via SIDRA API
# ---------------------------------------------------------------------------

# O recorte urbano/rural (agregado 9174) foi REMOVIDO do pipeline.
#
# Ele existia aqui, mas o fallback offline só sabia produzi-lo aplicando um
# deslocamento fixo sobre o total (+5pp urbano, -20pp rural). O resultado era um
# gap de exatamente 25,0pp em todos os 27 estados, todos os anos — um número que
# parece análise e não é: não distingue estado nenhum, porque foi construído
# para não distinguir. Publicar isso como "gap digital por UF" seria inventar
# achado. Melhor não ter o indicador do que ter um indicador falso.
SIDRA_QUERIES = {
    "pct_total": "https://servicodados.ibge.gov.br/api/v3/agregados/9173/periodos/2019|2020|2021|2022|2023/variaveis/49109?localidades=N3[all]",
}


def fetch_sidra(url: str, label: str) -> pd.DataFrame:
    cache_path = RAW_DIR / f"sidra_{label}.json"
    if cache_path.exists():
        print(f"  [cache] {label}")
        with open(cache_path) as f:
            data = json.load(f)
    else:
        print(f"  [fetch] {label} ...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        with open(cache_path, "w") as f:
            json.dump(data, f)

    rows = []
    for serie in data:
        codigo_uf = serie.get("localidade", {}).get("id", "")
        if len(codigo_uf) != 2:
            continue
        for periodo, valor in serie.get("resultados", [{}])[0].get("series", [{}])[0].get("serie", {}).items():
            try:
                v = float(str(valor).replace(",", "."))
            except (ValueError, TypeError):
                v = np.nan
            rows.append({"codigo_ibge": int(codigo_uf), "ano": int(periodo), "valor": v})
    return pd.DataFrame(rows)


# Fallback offline: penetração de internet por UF em 2023 (IBGE PNAD Contínua)
# e tendência nacional 2019–2023 para retropolar a série quando a API SIDRA
# estiver indisponível. Mesma base embutida usada em market-expansion-eda.
PCT_TOTAL_2023 = {
    "11": 82.4, "12": 81.2, "13": 77.6, "14": 85.6, "15": 77.8, "16": 82.5,
    "17": 82.1, "21": 73.8, "22": 79.3, "23": 78.9, "24": 83.6, "25": 80.5,
    "26": 82.4, "27": 78.4, "28": 82.8, "29": 80.3, "31": 88.7, "32": 89.5,
    "33": 91.3, "35": 93.5, "41": 91.6, "42": 93.8, "43": 92.8, "50": 89.4,
    "51": 88.2, "52": 90.0, "53": 95.1,
}
TENDENCIA_NACIONAL = {2019: 79.1, 2020: 82.7, 2021: 85.0, 2022: 86.8, 2023: 87.0}


def build_fallback_sidra() -> dict[str, pd.DataFrame]:
    """Reconstrói a série 2019–2023 por UF a partir dos valores reais de 2023,
    deslocados pela tendência nacional do mesmo período.

    IMPORTANTE para quem lê os números: só 2023 é observado. Os anos anteriores
    são RETROPOLADOS — assumem que todo estado se moveu no mesmo ritmo da média
    nacional. Serve para dar ordem de grandeza da evolução, não para comparar
    velocidade de crescimento entre estados: por construção, todos crescem
    igual. Essa limitação está declarada no README e na página de metodologia
    do dashboard.
    """
    linhas = []
    for cod, v2023 in PCT_TOTAL_2023.items():
        for ano, media_nacional in TENDENCIA_NACIONAL.items():
            offset = TENDENCIA_NACIONAL[2023] - media_nacional
            total = max(min(v2023 - offset, 99.0), 1.0)
            linhas.append({"codigo_ibge": int(cod), "ano": ano, "valor": round(total, 1)})
    return {"pct_total": pd.DataFrame(linhas)}


def load_all_sidra() -> dict[str, pd.DataFrame]:
    result = {}
    try:
        for label, url in SIDRA_QUERIES.items():
            result[label] = fetch_sidra(url, label)
        if any(df.empty for df in result.values()):
            raise ValueError("SIDRA retornou serie vazia")
    except Exception as exc:
        print(f"  [aviso] API SIDRA indisponivel ({exc})")
        print("  [aviso] usando fallback offline (PNAD 2023 embutida + tendencia nacional)")
        result = build_fallback_sidra()
    return result


# ---------------------------------------------------------------------------
# 3. Build fact table
# ---------------------------------------------------------------------------

def build_fato(
    dim_uf: pd.DataFrame,
    dim_periodo: pd.DataFrame,
    sidra: dict,
) -> pd.DataFrame:
    """Fato no grão UF × ano, com uma única medida observada.

    População, densidade e IDH NÃO entram aqui: são atributos da UF, já vivem em
    dim_uf e não variam no tempo. Copiá-los para o fato repetia cada valor cinco
    vezes e, no caso do IDH (censo 2010), fingia uma série anual que não existe.
    """
    uf_lookup   = dim_uf.set_index("codigo_ibge")["id_uf"]
    periodo_map = dim_periodo.set_index("ano")["id_periodo"]

    linhas = []
    for _, row in sidra["pct_total"].iterrows():
        if row["codigo_ibge"] not in uf_lookup.index:
            continue
        id_periodo = periodo_map.get(row["ano"])
        if pd.isna(id_periodo):
            continue
        linhas.append({
            "id_uf":                    int(uf_lookup.loc[row["codigo_ibge"]]),
            "id_periodo":               int(id_periodo),
            "pct_domicilios_internet":  row["valor"],
        })

    fato = pd.DataFrame(linhas).sort_values(["id_uf", "id_periodo"]).reset_index(drop=True)
    fato.insert(0, "id_fato", range(1, len(fato) + 1))
    return fato


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main():
    print("Building dimension tables...")
    # dim_regiao continua sendo montada porque build_dim_uf a usa para resolver
    # o nome da região, mas não é exportada: região é atributo da UF e vira
    # coluna de dim_uf. Exportá-la criaria um floco de neve (fato -> dim_uf ->
    # dim_regiao) sem ganho nenhum de modelagem.
    dim_regiao  = build_dim_regiao()
    dim_uf      = build_dim_uf(dim_regiao)
    dim_periodo = build_dim_periodo()

    print("Fetching IBGE SIDRA data...")
    sidra = load_all_sidra()

    print("Building fact table...")
    fato = build_fato(dim_uf, dim_periodo, sidra)

    exports = {
        "fato_indicadores.csv": fato,
        "dim_uf.csv":           dim_uf,
        "dim_periodo.csv":      dim_periodo,
    }

    print("\nExporting CSVs...")
    for fname, df in exports.items():
        path = OUT_DIR / fname
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  {fname} ({len(df):,} rows)")

    print("\nDone. Import CSVs from data/processed/ into Power BI.")
    print("Apply relationships and measures from dax/measures.md.")


if __name__ == "__main__":
    main()

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
    # Anos OBSERVADOS, não um range bonito. 2020 não está aqui porque a PNAD
    # Contínua não coletou o módulo de TIC naquele ano (pandemia) — criar o
    # ponto para a linha do gráfico não ter buraco seria inventar dado.
    anos = [2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
    df = pd.DataFrame({
        "id_periodo": range(1, len(anos) + 1),
        "ano":        anos,
        "data_ref":   [f"{a}-12-31" for a in anos],
    })
    return df


# ---------------------------------------------------------------------------
# 2. Fetch IBGE data via SIDRA API
# ---------------------------------------------------------------------------

# O DADO VEM DA API. Ver data_prep/sidra.py para o porquê de cada tabela e para
# a história do agregado 9173 — que estava aqui, é do Censo Agropecuário, nunca
# retornou nada, e mantinha o projeto rodando com número escrito à mão sob um
# rodapé que dizia "Fonte: IBGE".
#
# O recorte urbano x rural VOLTOU, agora observado. Ele tinha sido removido por
# ser fabricado (`total+5` e `total-20`, gap de exatos 25,0pp em todo estado).
# O real existe — 13,0pp no Brasil em 2023 — mas só em Brasil e Grandes Regioes:
# em UF o IBGE suprime por amostra. O grão mudou porque o dado manda no grão,
# e não o contrário.
from sidra import carregar as _carregar_sidra   # noqa: E402


def load_all_sidra() -> dict[str, pd.DataFrame]:
    """Linhas observadas do SIDRA, separadas por nível territorial.

    Sem fallback: se a API não responde e não há cache, `sidra.carregar` levanta
    SidraIndisponivel e o build para. É a mudança de postura que mais importa
    neste arquivo — antes, indisponibilidade virava número inventado.
    """
    linhas = pd.DataFrame(_carregar_sidra())
    return {
        "uf":     linhas[(linhas["nivel"] == "N3") & (linhas["situacao"] == "Total")],
        "regiao": linhas[linhas["nivel"] == "N2"],
        "brasil": linhas[linhas["nivel"] == "N1"],
    }


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
    for _, row in sidra["uf"].iterrows():
        codigo = int(row["codigo_ibge"])
        if codigo not in uf_lookup.index:
            continue
        id_periodo = periodo_map.get(row["ano"])
        if pd.isna(id_periodo):
            continue
        linhas.append({
            "id_uf":                    int(uf_lookup.loc[codigo]),
            "id_periodo":               int(id_periodo),
            "pct_domicilios_internet":  row["pct"],
            # Absolutos junto do percentual: o achado central do painel é que o
            # ranking por taxa e o por volume discordam, e sem o denominador o
            # segundo ranking não existe.
            "domicilios_com_internet":  row["com_internet"],
            "domicilios_total":         row["total"],
            "domicilios_sem_internet":  round(row["total"] - row["com_internet"], 1),
        })

    fato = pd.DataFrame(linhas).sort_values(["id_uf", "id_periodo"]).reset_index(drop=True)
    fato.insert(0, "id_fato", range(1, len(fato) + 1))
    return fato


def build_fato_situacao(dim_periodo: pd.DataFrame, sidra: dict) -> pd.DataFrame:
    """Acesso por situação do domicílio (urbana × rural), grão região × ano.

    Tabela SEPARADA do fato de UF, e não uma coluna a mais nele, porque o grão é
    outro: este indicador só é publicado em Brasil e Grandes Regiões. Enfiá-lo
    no fato de UF exigiria repetir o valor da região em cada um dos seus estados
    — que é precisamente como a versão anterior inventou um "gap por UF"
    constante em 25,0pp.
    """
    periodo_map = dim_periodo.set_index("ano")["id_periodo"]
    nomes = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul",
             "5": "Centro-Oeste"}

    linhas = []
    for origem, escopo in (("brasil", "Brasil"), ("regiao", "Região")):
        for _, row in sidra[origem].iterrows():
            id_periodo = periodo_map.get(row["ano"])
            if pd.isna(id_periodo):
                continue
            local = "Brasil" if escopo == "Brasil" else nomes.get(row["codigo_ibge"])
            if not local:
                continue
            linhas.append({
                "id_periodo":              int(id_periodo),
                "ano":                     int(row["ano"]),
                "escopo":                  escopo,
                "local":                   local,
                "situacao":                row["situacao"],
                "pct_domicilios_internet": row["pct"],
                "domicilios_com_internet": row["com_internet"],
                "domicilios_total":        row["total"],
            })

    fato = (pd.DataFrame(linhas)
            .sort_values(["escopo", "local", "ano", "situacao"])
            .reset_index(drop=True))
    fato.insert(0, "id_situacao", range(1, len(fato) + 1))
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

    print("Building fact tables...")
    fato = build_fato(dim_uf, dim_periodo, sidra)
    fato_situacao = build_fato_situacao(dim_periodo, sidra)

    exports = {
        "fato_indicadores.csv": fato,
        "fato_situacao.csv":    fato_situacao,
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

"""
Os números publicados, como asserção — Brecha Digital (Power BI)

Execute com: pytest tests/ -v

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O README deste repositório publica um ranking, quatro estados com posição
exata, um desvio-padrão que cai ao longo de nove anos e uma correlação que
sobe e desce. Nada disso era conferido — e a versão anterior deste mesmo
projeto chegou a afirmar que São Paulo tinha a melhor taxa do país enquanto o
CSV do repositório dizia que era o 5º.

O .pbix é binário e não dá para testar aqui. O que dá é a base sobre a qual o
modelo roda (data/processed) e a coerência entre o que o repositório declara
sobre si em três lugares diferentes: o badge, o cabeçalho do measures.md e as
medidas que ele de fato documenta.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"


def _csv(nome):
    return pd.read_csv(PROC / f"{nome}.csv", encoding="utf-8-sig")


@pytest.fixture(scope="module")
def uf_ano():
    """Fato de UF com dimensão colada e os dois rankings já calculados."""
    df = _csv("fato_indicadores").merge(_csv("dim_uf"), on="id_uf").merge(
        _csv("dim_periodo"), on="id_periodo")
    df["rk_taxa"] = df.groupby("ano")["pct_domicilios_internet"].rank(
        ascending=False, method="min")
    df["rk_volume"] = df.groupby("ano")["domicilios_sem_internet"].rank(
        ascending=False, method="min")
    return df


@pytest.fixture(scope="module")
def ultimo(uf_ano):
    return uf_ano[uf_ano["ano"] == 2025]


# ── Integridade do modelo ─────────────────────────────────────────────────

def test_as_27_unidades_em_todo_ano(uf_ano):
    assert (uf_ano.groupby("ano").size() == 27).all()


def test_serie_declarada_no_site(uf_ano):
    """2020 não existe: a PNAD Contínua não foi a campo na pandemia. O buraco
    é do IBGE, não do pipeline — e some se alguém "preencher" a série."""
    anos = sorted(uf_ano["ano"].unique())
    assert anos[0] == 2016 and anos[-1] == 2025
    assert 2020 not in anos


def test_nenhuma_chave_orfa():
    fato = _csv("fato_indicadores")
    assert not set(fato["id_uf"]) - set(_csv("dim_uf")["id_uf"])
    assert not set(fato["id_periodo"]) - set(_csv("dim_periodo")["id_periodo"])


def test_intervalo_de_confianca_contem_a_estimativa():
    """A margem vem do coeficiente de variação que o próprio SIDRA publica.
    Se o IC não contiver o ponto, a conta está invertida em algum lugar."""
    f = _csv("fato_indicadores")
    assert (f["ic_inferior"] <= f["pct_domicilios_internet"]).all()
    assert (f["pct_domicilios_internet"] <= f["ic_superior"]).all()


# ── O achado que o site publica ───────────────────────────────────────────

def test_penetracao_nacional_2025(ultimo):
    """Ponderada por domicílios, que é o método do próprio IBGE."""
    pct = ultimo["domicilios_com_internet"].sum() / ultimo["domicilios_total"].sum() * 100
    assert round(pct, 1) == 95.0


def test_quatro_milhoes_de_domicilios_sem_internet(ultimo):
    milhoes = ultimo["domicilios_sem_internet"].sum() / 1000
    assert round(milhoes, 1) == 4.0


@pytest.mark.parametrize("sigla,taxa,pos_taxa,volume,pos_volume", [
    ("SP", 96.6,  5, 606,  1),
    ("MG", 94.5, 15, 445,  2),
    ("BA", 92.7, 22, 416,  3),
    ("AC", 90.6, 27,  28, 23),
])
def test_tabela_do_readme(ultimo, sigla, taxa, pos_taxa, volume, pos_volume):
    linha = ultimo[ultimo["sigla"] == sigla].iloc[0]
    assert round(linha["pct_domicilios_internet"], 1) == taxa
    assert int(linha["rk_taxa"]) == pos_taxa
    assert round(linha["domicilios_sem_internet"]) == volume
    assert int(linha["rk_volume"]) == pos_volume


def test_sao_paulo_nao_e_o_melhor_do_pais(ultimo):
    """A afirmação que a versão anterior publicou e que o dado desmentia."""
    assert ultimo.loc[ultimo["pct_domicilios_internet"].idxmax(), "sigla"] != "SP"


def test_os_dois_rankings_discordam(ultimo):
    """Todo o argumento da página: percentual e volume apontam para lugares
    diferentes. Se um dia coincidirem, o texto perde o sentido."""
    melhor_taxa = ultimo.loc[ultimo["rk_taxa"].idxmin(), "sigla"]
    maior_volume = ultimo.loc[ultimo["rk_volume"].idxmin(), "sigla"]
    assert melhor_taxa != maior_volume


def test_bahia_anda_19_posicoes(ultimo):
    ba = ultimo[ultimo["sigla"] == "BA"].iloc[0]
    assert int(ba["rk_taxa"]) - int(ba["rk_volume"]) == 19


def test_a_brecha_entre_estados_fechou(uf_ano):
    """O segundo achado, e o maior: 9,6pp para 1,9pp de desvio-padrão."""
    def desvio(ano):
        return uf_ano[uf_ano["ano"] == ano]["pct_domicilios_internet"].std(ddof=1)
    assert round(desvio(2016), 1) == 9.6
    assert round(desvio(2025), 1) == 1.9
    assert desvio(2025) < desvio(2016)


def test_amplitude_entre_melhor_e_pior(uf_ano):
    def amplitude(ano):
        s = uf_ano[uf_ano["ano"] == ano]["pct_domicilios_internet"]
        return s.max() - s.min()
    # O README dizia 21,3pp para 2016 — numero que nao sai deste dado e que
    # SUBESTIMAVA o proprio achado: a distancia real entre o melhor e o pior
    # estado era de 41,4pp. Foi este teste que pegou.
    assert round(amplitude(2016), 1) == 41.4
    assert round(amplitude(2025), 1) == 7.7


def test_o_ranking_por_taxa_nao_separa_vizinhos(ultimo):
    """26 pares vizinhos, 26 intervalos que se encostam. É o que impede o
    ranking por percentual de virar fila de investimento."""
    ordenado = ultimo.sort_values("pct_domicilios_internet", ascending=False)
    acima = ordenado.iloc[:-1].reset_index(drop=True)
    abaixo = ordenado.iloc[1:].reset_index(drop=True)
    assert len(acima) == 26
    sobrepostos = (acima["ic_inferior"] <= abaixo["ic_superior"]).sum()
    assert sobrepostos == 26


def test_o_gap_que_sobrou_e_urbano_rural():
    """A brecha regional fechou; a rural não. E ela é maior no Norte."""
    ano = _csv("fato_situacao")
    ano = ano[ano["ano"] == 2025]

    def gap(local):
        linhas = ano[ano["local"] == local].set_index("situacao")
        return (linhas.loc["Urbana", "pct_domicilios_internet"]
                - linhas.loc["Rural", "pct_domicilios_internet"])

    regioes = [x for x in ano["local"].unique() if x != "Brasil"]
    assert round(gap("Brasil"), 1) == 7.8
    assert round(gap("Norte"), 1) == 13.1
    assert gap("Norte") == max(gap(r) for r in regioes)


def test_o_urbano_do_norte_esta_acima_da_media_nacional():
    """A leitura que troca a natureza do investimento: a cidade do Norte não
    é praça a cobrir, é praça disputada."""
    ano = _csv("fato_situacao")
    ano = ano[ano["ano"] == 2025]
    urbano_norte = ano[(ano["local"] == "Norte") & (ano["situacao"] == "Urbana")
                       ]["pct_domicilios_internet"].iloc[0]
    assert round(urbano_norte, 1) == 96.4


def test_idh_explica_a_maior_parte_da_variacao(ultimo):
    r = ultimo["idh_2010"].corr(ultimo["pct_domicilios_internet"])
    assert round(r, 3) == 0.829
    assert round(r ** 2 * 100) == 69


def test_a_correlacao_nao_caiu_de_forma_constante(uf_ano):
    """A ressalva contra a leitura fácil: quem olhasse só 2018 e 2023
    concluiria uma tendência que a série inteira não mostra."""
    def r(ano):
        u = uf_ano[uf_ano["ano"] == ano]
        return u["idh_2010"].corr(u["pct_domicilios_internet"])
    assert r(2018) > r(2023)
    assert r(2025) > r(2023)


def test_o_gap_entre_blocos_regionais(uf_ano):
    """N+NE contra S+SE, ponderado por domicilios: 4,6pp em 2023, 2,8pp em
    2025. E a frase que sustenta "a brecha regional praticamente fechou"."""
    def gap(ano):
        u = uf_ano[uf_ano["ano"] == ano]
        def pond(regioes):
            s = u[u["regiao"].isin(regioes)]
            return s["domicilios_com_internet"].sum() / s["domicilios_total"].sum() * 100
        return pond(["Sul", "Sudeste"]) - pond(["Norte", "Nordeste"])
    assert round(gap(2023), 1) == 4.6
    assert round(gap(2025), 1) == 2.8


def test_o_pior_rural_do_pais_e_o_do_norte():
    ano = _csv("fato_situacao")
    ano = ano[(ano["ano"] == 2025) & (ano["situacao"] == "Rural") & (ano["local"] != "Brasil")]
    pior = ano.loc[ano["pct_domicilios_internet"].idxmin()]
    assert pior["local"] == "Norte"
    assert round(pior["pct_domicilios_internet"], 1) == 83.3


def test_centro_oeste_e_o_contraste():
    """1,8pp de gap urbano-rural contra 13,1pp do Norte: mesma pergunta,
    resposta sete vezes menor. E o que mostra que o gap nao e' nacional."""
    ano = _csv("fato_situacao")
    ano = ano[ano["ano"] == 2025].set_index(["local", "situacao"])
    co = (ano.loc[("Centro-Oeste", "Urbana"), "pct_domicilios_internet"]
          - ano.loc[("Centro-Oeste", "Rural"), "pct_domicilios_internet"])
    assert round(co, 1) == 1.8


# ── Coerência do que o repositório declara sobre si ───────────────────────

def _medidas_documentadas():
    """Medidas que dax/measures.md NOMEIA.

    Duas formas convivem no arquivo: definição em bloco dax (a maioria) e
    citação em prosa nas seções de Narrativa e Auxiliares, onde o interesse é
    a regra e não a fórmula. As duas contam — o que não pode é o cabeçalho
    afirmar um número que o arquivo não sustenta, como acontecia: o badge dizia
    29, o cabeçalho dizia 26 e o documento nomeava outra coisa.
    """
    texto = (RAIZ / "dax" / "measures.md").read_text(encoding="utf-8")
    corpo = texto[texto.index("## [00]"):]
    ignora = ("VAR ", "RETURN", "--", '"', "CALCULATE", "ADDCOLUMNS",
              "SUMMARIZE", "IF(", "SWITCH", "DIVIDE")
    nomes, dentro, secao = [], False, ""
    for ln in corpo.split("\n"):
        if ln.startswith("## "):
            secao = ln
        if ln.startswith("```dax"):
            dentro = True
            continue
        if ln.startswith("```"):
            dentro = False
            continue
        if dentro and ln and not ln[0].isspace() and not ln.startswith(ignora):
            m = re.match(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 %ºª_/.×\-]*?)\s*=(?!=)", ln)
            if m:
                nomes.append(m.group(1).strip())
        elif not dentro and ("Narrativa" in secao or "Auxiliares" in secao):
            nomes += re.findall(r"`([A-ZÀ-Ú][A-Za-zÀ-ÿ ]+)`", ln)
    return sorted(set(nomes))


def test_measures_md_documenta_o_que_diz_documentar():
    texto = (RAIZ / "dax" / "measures.md").read_text(encoding="utf-8")
    declarado = int(re.search(r"^(\d+) medidas", texto, re.M).group(1))
    assert declarado == len(_medidas_documentadas())


def test_badge_do_readme_bate_com_o_documento():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    n = len(_medidas_documentadas())
    assert f"DAX-{n}%20medidas" in readme


def test_os_dois_intervalos_citados_no_readme_batem_com_o_modelo(ultimo):
    """O parágrafo do IC cita DF e SP com número exato — e ficou para trás.

    POR QUE ESTE TESTE EXISTE
    -------------------------
    Na migração da série para 2025, a TABELA do README foi atualizada e o
    parágrafo sobre intervalo de confiança, quarenta linhas abaixo, não. O
    README publicava São Paulo com 96,6% na tabela e 95,0% no parágrafo — e
    95,0% é a taxa do BRASIL, colada por engano. O DF aparecia com 97,4%
    quando o modelo diz 98,3%.

    O teste que já existia conferia que os 26 pares se sobrepõem (e isso
    continuava verdadeiro), mas nenhum conferia os dois números citados. Foi
    exatamente por essa fresta que o erro passou.
    """
    import re

    md = (RAIZ / "README.md").read_text(encoding="utf-8")
    trecho = md[md.index("não se\ndistinguem a 95%"):][:400]

    ordenado = ultimo.sort_values("pct_domicilios_internet", ascending=False).reset_index(drop=True)
    df = ordenado.iloc[0]
    sp = ordenado[ordenado["sigla"] == "SP"].iloc[0]
    pos_sp = ordenado.index[ordenado["sigla"] == "SP"][0] + 1

    assert df["sigla"] == "DF", "o 1º do ranking deixou de ser o DF"
    assert pos_sp == 5, f"São Paulo não é mais o 5º, e sim o {pos_sp}º"

    def br(v):
        return f"{v:.1f}".replace(".", ",")

    for esperado in (br(df["pct_domicilios_internet"]), br(sp["pct_domicilios_internet"]),
                     br(df["ic_inferior"]), br(sp["ic_inferior"]), br(sp["ic_superior"])):
        assert esperado in trecho, (
            f"o parágrafo do IC não cita {esperado}% — texto e modelo divergiram de novo"
        )

    # e o número do Brasil não pode reaparecer ali como se fosse de um estado
    brasil = re.search(r"^([0-9]{2},[0-9])% dos domicílios brasileiros", md, re.M)
    if brasil:
        assert f"São Paulo, 5º com {brasil.group(1)}%" not in trecho, (
            "a taxa do Brasil voltou a ser citada como se fosse a de São Paulo"
        )

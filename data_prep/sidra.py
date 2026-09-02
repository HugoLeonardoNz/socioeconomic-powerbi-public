"""
sidra.py — acesso domiciliar à internet por UF, direto da API do IBGE.

POR QUE ESTE ARQUIVO EXISTE
───────────────────────────
A versão anterior deste projeto dizia "IBGE · PNAD Contínua" no rodapé do painel
e trazia os números numa constante escrita à mão. Dois problemas, e o segundo é
pior que o primeiro:

1. A chamada de API que existia apontava para o agregado 9173, que é
   "Produção, Venda e Valor da produção na agroindústria rural" do CENSO
   AGROPECUÁRIO de 2017. Tabela errada, pesquisa errada, ano errado. Ela nunca
   retornou nada — e como o `except` caía num fallback offline com um `print` de
   aviso, o projeto rodava inteiro sem que nada falhasse.

2. Os números do fallback não batiam com o PNAD. O Brasil aparecia com 87,0% de
   domicílios com internet em 2023 quando o IBGE publicou 92,5%, e o erro NÃO
   era uniforme: Maranhão saía 13,0 pontos abaixo do real e São Paulo, 1,5. Como
   o erro era maior justamente nos estados pobres, ele mudava o ranking de
   prioridade de expansão — que é a única coisa que este projeto entrega.

Agora o dado vem da API, o cache fica versionado no repositório, e quando a API
não responde o script FALHA em vez de inventar. Ver `carregar()`.

DE ONDE VEM CADA NÚMERO
───────────────────────
Não existe tabela do SIDRA que já entregue "% de domicílios com internet por UF".
O percentual é uma divisão entre duas tabelas da mesma pesquisa, no mesmo grão
(UF × situação do domicílio × ano):

    numerador    9649  Domicílios em que havia utilização da internet   (2022-2025)
                 7311  idem                                             (2016-2021)
    denominador  7167  Domicílios, por situação e existência de televisão
                       — a categoria "Total" da classificação de televisão é o
                       total de domicílios. É a tabela da PNAD Contínua que
                       publica domicílios por UF E por situação; a 7304 (telefone)
                       serviria para o total, mas não abre urbano × rural.

O método foi conferido contra o número publicado pelo IBGE: 70.972/76.656 mil
domicílios = 92,6% para o Brasil em 2023, contra os 92,5% do release. A diferença
de 0,1pp é arredondamento — as duas tabelas publicam em "mil domicílios".
"""
from __future__ import annotations

import gzip
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "sidra_cache"

# Situação do domicílio (classificação 1) — as três que o painel usa.
SITUACAO = {6795: "Total", 1: "Urbana", 2: "Rural"}

# (agregado, variável, classificações fixas além da situação, anos)
FONTES = {
    "com_internet_2022_2025": dict(
        agregado=9649, variavel=10628, extra="1704[59918]",
        anos="2022|2023|2024|2025",
        descricao="Domicílios em que havia utilização da internet",
    ),
    "com_internet_2016_2021": dict(
        agregado=7311, variavel=10628, extra="680[33214]",
        anos="2016|2017|2018|2019|2021",
        descricao="Domicílios em que havia utilização da internet",
    ),
    "total_domicilios": dict(
        agregado=7167, variavel=162, extra="937[48455]",
        anos="2016|2017|2018|2019|2021|2022|2023|2024|2025",
        descricao="Domicílios (total)",
    ),
    # ââ Precisão da amostra ââââââââââââââââââââââââââââââââââââââââââââââââââ
    # A PNAD Contínua é AMOSTRA, não censo. Publicar um ranking de 27 estados por
    # estimativa pontual, sem dizer o quanto cada ponto pode se mover, é tratar
    # pesquisa amostral como contagem. O IBGE publica o coeficiente de variação
    # de toda estimativa justamente para isso — só que numa variável separada.
    "cv_com_internet_2022_2025": dict(
        agregado=9649, variavel=10629, extra="1704[59918]",
        anos="2022|2023|2024|2025",
        descricao="Coeficiente de variação — domicílios com internet",
    ),
    "cv_com_internet_2016_2021": dict(
        agregado=7311, variavel=10629, extra="680[33214]",
        anos="2016|2017|2018|2019|2021",
        descricao="Coeficiente de variação — domicílios com internet",
    ),
    "cv_total_domicilios": dict(
        agregado=7167, variavel=5123, extra="937[48455]",
        anos="2016|2017|2018|2019|2021|2022|2023|2024|2025",
        descricao="Coeficiente de variação — total de domicílios",
    ),
}


class SidraIndisponivel(RuntimeError):
    """A API não respondeu e não há cache. Falha alta de propósito.

    O antecessor deste módulo caía num fallback de números escritos à mão e
    seguia em frente imprimindo um aviso. O resultado é que o projeto rodou
    meses publicando número inventado com "Fonte: IBGE" no rodapé. Um erro que
    interrompe é barato; um número errado com selo de fonte oficial, não.
    """


def _http_json(url: str, tentativas: int = 5) -> list:
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "portfolio-hugo-nazario/1.0",
                "Accept-Encoding": "gzip",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            if not raw.strip():
                # A API devolve 200 com corpo vazio quando está sobrecarregada.
                raise ValueError("resposta vazia (200 sem corpo)")
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
            ultimo = e
            if i < tentativas - 1:
                time.sleep(2 * (i + 1))
    raise SidraIndisponivel(f"{url[:110]} :: {ultimo}")


# Z de 95% numa normal. A PNAD tem amostra grande o bastante em todo grao que
# este projeto usa para a aproximacao normal valer.
Z95 = 1.96


def margem_erro(pct: float, cv_numerador: float | None) -> float | None:
    """Metade do intervalo de 95% da PENETRACAO, em pontos percentuais.

    O IBGE publica o coeficiente de variacao de cada CONTAGEM, nao da razao
    entre duas. Para p = X/N, com X contido em N e as duas estimadas da mesma
    amostra:

        CV²(p) = CV²(X) + CV²(N) - 2ρ·CV(X)·CV(N)

    E o ρ nao e publicado. Os dois extremos limitam a resposta:

      ρ = 0  (independentes)  -> CV(p) = √(CV²X + CV²N), MAIOR que qualquer um
                                  dos dois. Falso: X e parte de N, sobem juntos.
      ρ = 1  (perfeita)       -> CV(p) = |CV(X) - CV(N)|, quase zero. Otimista
                                  demais para assumir sem poder conferir.

    Aqui fica o meio: trata o denominador como fixo, entao CV(p) = CV(X). E a
    pratica comum quando so o CV do numerador esta a mao, e erra para o lado
    CONSERVADOR - o intervalo sai mais largo que o real, porque ignora a
    correlacao positiva que reduz a variancia da razao.

    Escolha declarada de proposito: intervalo largo demais faz o portfolio
    afirmar menos do que poderia; intervalo estreito demais o faz afirmar o que
    o dado nao sustenta. Entre os dois erros, o primeiro e o barato.
    """
    if cv_numerador is None:
        return None
    return round(Z95 * (cv_numerador / 100.0) * pct, 2)


def _url(fonte: dict) -> str:
    cls = "1[6795,1,2]"
    if fonte["extra"]:
        cls += "|" + fonte["extra"]
    # N1 Brasil · N2 Grandes Regiões · N3 UF.
    #
    # As três, e não só UF, porque o recorte urbano × rural SÓ existe em N1 e N2:
    # em N3 o IBGE devolve "-" (supressão — a amostra da PNAD não sustenta
    # UF × situação para este indicador). Conferido chamando a API com
    # classificacao=1[1,2] em N3[31,35]: volta "-" para todos.
    #
    # É por isso que o gap urbano × rural aparece por REGIÃO no painel e não por
    # estado. A versão anterior deste projeto publicava o gap por UF — mas ele
    # era `total+5` e `total-20`, constante em todos os 27 estados. O dado real
    # existe num grão mais grosso; o dado fabricado existia em qualquer grão.
    return (f"{BASE}/{fonte['agregado']}/periodos/{fonte['anos']}"
            f"/variaveis/{fonte['variavel']}"
            f"?localidades=N1[all]|N2[all]|N3[all]&classificacao={cls}")


def _achatar(dados: list) -> dict:
    """{(nivel, codigo_localidade, situacao, ano): valor_em_mil_domicilios}

    A chave inclui o NÍVEL territorial, e isso não é preciosismo: no IBGE o
    Brasil (N1) e a região Norte (N2) têm ambos o id "1". Sem o nível na chave,
    a região sobrescreve o país em silêncio e o "Brasil" do painel passa a
    mostrar os números do Norte — que foi exatamente o que aconteceu aqui na
    primeira versão, e só apareceu porque o total nacional conferido contra o
    release do IBGE (92,5%) veio 90,4%.
    """
    out: dict = {}
    for bloco in dados:
        for res in bloco.get("resultados", []):
            situacao = "Total"
            for c in res.get("classificacoes", []):
                if c.get("id") == "1":
                    for cid in c.get("categoria", {}):
                        situacao = SITUACAO.get(int(cid), "Total")
            for s in res.get("series", []):
                loc = s["localidade"]
                nivel = (loc.get("nivel") or {}).get("id", "N3")
                for ano, valor in s.get("serie", {}).items():
                    try:
                        out[(nivel, loc["id"], situacao, int(ano))] = \
                            float(str(valor).replace(",", "."))
                    except (TypeError, ValueError):
                        pass  # "..." e "-" são supressão amostral do IBGE
    return out


def baixar(forcar: bool = False) -> dict:
    """Baixa (ou lê do cache versionado) as três fontes."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bruto = {}
    for nome, fonte in FONTES.items():
        cache = CACHE_DIR / f"{nome}.json"
        if cache.exists() and not forcar:
            bruto[nome] = json.loads(cache.read_text(encoding="utf-8"))
            continue
        dados = _http_json(_url(fonte))
        cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        bruto[nome] = dados
    return bruto


def carregar(forcar: bool = False) -> list[dict]:
    """Devolve linhas {codigo_ibge, situacao, ano, pct, com_internet, total}.

    `pct` é observado em todos os anos e em todas as UFs — não há retropolação
    nem interpolação aqui. 2020 não existe: a PNAD Contínua não coletou o módulo
    de TIC naquele ano por causa da pandemia, e inventar o ponto para a linha do
    gráfico ficar contínua seria fabricar dado.
    """
    bruto = baixar(forcar)
    com = _achatar(bruto["com_internet_2016_2021"])
    com.update(_achatar(bruto["com_internet_2022_2025"]))
    total = _achatar(bruto["total_domicilios"])

    cv_com = _achatar(bruto["cv_com_internet_2016_2021"])
    cv_com.update(_achatar(bruto["cv_com_internet_2022_2025"]))
    cv_total = _achatar(bruto["cv_total_domicilios"])

    linhas = []
    for chave, valor_com in sorted(com.items()):
        valor_total = total.get(chave)
        if not valor_total:
            continue
        nivel, loc, situacao, ano = chave
        pct = valor_com / valor_total * 100
        cv = cv_com.get(chave)
        margem = margem_erro(pct, cv)
        linhas.append({
            "nivel":        nivel,
            "codigo_ibge":  loc,
            "situacao":     situacao,
            "ano":          ano,
            "com_internet": valor_com,
            "total":        valor_total,
            "pct":          round(pct, 1),
            # Precisao da amostra. `cv_*` sao os publicados pelo IBGE; `margem`
            # e a metade do intervalo de 95%, em pontos percentuais.
            "cv_com":       cv,
            "cv_total":     cv_total.get(chave),
            "margem_pp":    margem,
            "ic_inf":       None if margem is None else round(max(pct - margem, 0.0), 1),
            "ic_sup":       None if margem is None else round(min(pct + margem, 100.0), 1),
        })
    if not linhas:
        raise SidraIndisponivel("nenhuma linha cruzou numerador e denominador")
    return linhas


if __name__ == "__main__":
    import sys
    linhas = carregar(forcar="--forcar" in sys.argv)
    print(f"{len(linhas)} linhas (UF x situacao x ano)")
    br = [l for l in linhas if l["nivel"] == "N1" and l["ano"] == 2023]
    for l in sorted(br, key=lambda x: x["situacao"]):
        print(f"  Brasil 2023 {l['situacao']:7} {l['pct']:5.1f}%")

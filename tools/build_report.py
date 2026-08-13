"""
Gerador do relatorio (camada visual) do digital_divide_brasil.pbix.

O .pbix e um zip; no formato PBIR a camada de relatorio vive em
`Report/definition/**` como JSON versionavel. Este script reescreve essa camada
inteira a partir da especificacao declarativa abaixo, preservando o modelo de
dados (`DataModel`).

O mesmo padrao e usado no telecom-powerbi-public. A infraestrutura PBIR e
duplicada de proposito: cada repositorio do portfolio precisa rodar sozinho,
sem depender de um pacote compartilhado que o avaliador nao tem.

DESIGN — este relatorio NAO se parece com o de telecom, e isso e intencional:

    telecom            : escuro, ciano sobre preto, navegacao no topo,
                         faixa densa de KPIs, tipografia toda em Segoe UI.
    brecha digital     : claro cor de papel, paleta terrosa, rail vertical a
                         esquerda com filtros dentro, titulos em serifa,
                         menos visuais por pagina e mais respiro.

Uso:
    python tools/build_report.py [origem.pbix] [destino.pbix]
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PBIX = ROOT / "digital_divide_brasil.pbix"
THEME_FILE = ROOT / "theme" / "brecha_digital_theme.json"

# ---------------------------------------------------------------------------
# Design tokens — papel, tinta e terra
# ---------------------------------------------------------------------------

BG_OUT = "#EBE6DC"     # area fora do canvas
BG_PAGE = "#F5F2EC"    # papel
BG_RAIL = "#EDE8DE"    # rail lateral
BG_CARD = "#FFFFFF"    # superficie dos paineis
BORDER = "#E0D9CC"     # fio de contorno
GRID = "#EDE8DE"       # linhas de grade
BG_ALT = "#FAF7F1"     # faixa alternada das tabelas

INK = "#1B1D21"        # tinta primaria
INK_MUT = "#5B616B"    # tinta secundaria
INK_DIM = "#8D939C"    # tinta terciaria

TEAL = "#0F5F52"       # cor de dado primaria
AMBER = "#B45309"      # atencao / lacuna
BRICK = "#9C3D2E"      # negativo
SAGE = "#7A9E7E"
OCHRE = "#B8A055"
SLATE = "#40697F"
PLUM = "#8C6A93"

# Cor fixa por regiao, em todas as paginas.
REGIAO = {
    "Norte": SAGE,
    "Nordeste": "#C8763C",
    "Centro-Oeste": OCHRE,
    "Sudeste": SLATE,
    "Sul": PLUM,
}
SERIES = [TEAL, "#C8763C", SLATE, OCHRE, PLUM, SAGE, BRICK, "#6E8CA0"]

FONT_TITLE = "Georgia"          # serifa: o que diferencia a peca
FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"

# Grid da pagina (1920x1080) — rail a esquerda, conteudo a direita
PAGE_W, PAGE_H = 1920, 1080
RAIL_W = 208
MARGIN = 40
GUTTER = 20
CONTENT_X = RAIL_W + MARGIN                    # 248
CONTENT_W = PAGE_W - CONTENT_X - MARGIN        # 1632
HEAD_Y = 52
BODY_Y = 196                                   # abaixo do titulo + linha fina
BODY_H = PAGE_H - BODY_Y - MARGIN              # 844

ENTITY_M = "_Medidas"


def cols(n: int, gutter: int = GUTTER, x0: int = CONTENT_X, total: int = CONTENT_W):
    w = (total - gutter * (n - 1)) / n
    return [(x0 + i * (w + gutter), w) for i in range(n)]


def split(*weights: float, gutter: int = GUTTER, y0: int = BODY_Y, total: int = BODY_H):
    """Faixas horizontais com alturas proporcionais."""
    free = total - gutter * (len(weights) - 1)
    unit = free / sum(weights)
    out, y = [], y0
    for w in weights:
        h = unit * w
        out.append((y, h))
        y += h + gutter
    return out


def split_x(*weights: float, gutter: int = GUTTER, x0: int = CONTENT_X, total: int = CONTENT_W):
    """Colunas com larguras proporcionais."""
    free = total - gutter * (len(weights) - 1)
    unit = free / sum(weights)
    out, x = [], x0
    for w in weights:
        wd = unit * w
        out.append((x, wd))
        x += wd + gutter
    return out


# ---------------------------------------------------------------------------
# Helpers de expressao (formato PBIR)
# ---------------------------------------------------------------------------

def lit(value) -> dict:
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, str):
        v = "'" + value.replace("'", "''") + "'"
    else:
        v = f"{value}D"
    return {"expr": {"Literal": {"Value": v}}}


def solid(color: str) -> dict:
    return {"solid": {"color": lit(color)}}


def solid_by_measure(measure: str) -> dict:
    return {
        "solid": {
            "color": {
                "expr": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": ENTITY_M}},
                        "Property": measure,
                    }
                }
            }
        }
    }


def obj(**props) -> list:
    return [{"properties": props}]


def category_colors(entity: str, prop: str, mapping: dict[str, str]) -> list:
    """Cor amarrada ao valor da categoria.

    Cor por medida so funciona em cartao; em grafico de barras o Power BI
    avalia a expressao fora do contexto do ponto e pinta tudo igual.
    """
    return [
        {
            "properties": {"fill": solid(color)},
            "selector": {
                "data": [{
                    "scopeId": {
                        "Comparison": {
                            "ComparisonKind": 0,
                            "Left": {"Column": {
                                "Expression": {"SourceRef": {"Entity": entity}},
                                "Property": prop,
                            }},
                            "Right": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}},
                        }
                    }
                }]
            },
        }
        for value, color in mapping.items()
    ]


def measure_field(name: str, entity: str = ENTITY_M) -> dict:
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}},
        "queryRef": f"{entity}.{name}",
        "nativeQueryRef": name,
    }


def column_field(entity: str, prop: str, active: bool = True) -> dict:
    d = {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }
    if active:
        d["active"] = True
    return d


def sort_by_measure(name: str, direction: str = "Descending", entity: str = ENTITY_M) -> dict:
    return {
        "sort": [{
            "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}},
            "direction": direction,
        }],
        "isDefaultSort": True,
    }


def sort_by_column(entity: str, prop: str, direction: str = "Ascending") -> dict:
    return {
        "sort": [{
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "direction": direction,
        }],
        "isDefaultSort": True,
    }


# ---------------------------------------------------------------------------
# Chrome dos paineis — quadrado, fio fino, titulo em serifa
# ---------------------------------------------------------------------------

def panel(title: str | None = None, subtitle: str | None = None, framed: bool = True,
          centro: bool = False) -> dict:
    c: dict = {
        "background": obj(show=lit(framed), color=solid(BG_CARD), transparency=lit(0)),
        "border": obj(show=lit(framed), color=solid(BORDER), radius=lit(14)),
        "dropShadow": obj(show=lit(False)),
        "visualHeader": obj(show=lit(False)),
    }
    if title:
        c["title"] = obj(
            show=lit(True), text=lit(title),
            fontColor=solid(INK), background=solid(BG_CARD),
            fontFamily=lit(FONT_TITLE), fontSize=lit(16),
            alignment=lit("center" if centro else "left"), titleWrap=lit(False),
        )
        c["subTitle"] = obj(
            show=lit(bool(subtitle)), text=lit(subtitle or ""),
            fontColor=solid(INK_DIM), fontFamily=lit(FONT),
            fontSize=lit(11), alignment=lit("center" if centro else "left"),
            titleWrap=lit(False),
        )
    else:
        c["title"] = obj(show=lit(False))
    return c


def bare() -> dict:
    return {
        "background": obj(show=lit(False)),
        "border": obj(show=lit(False)),
        "dropShadow": obj(show=lit(False)),
        "visualHeader": obj(show=lit(False)),
        "title": obj(show=lit(False)),
    }


def axis_cat(font: int = 11, categorical: bool = False) -> list:
    props = {
        "show": lit(True), "labelColor": solid(INK_MUT),
        "fontFamily": lit(FONT), "fontSize": lit(font),
        "showAxisTitle": lit(False), "gridlineShow": lit(False),
        "concatenateLabels": lit(False),
    }
    if categorical:
        # Ano e inteiro; sem isso o Power BI trata como escala continua e
        # rotula 2019,5 no eixo.
        props["axisType"] = lit("Categorical")
    return [{"properties": props}]


def axis_val(show: bool = True, font: int = 11, start: float | None = None) -> list:
    props = {
        "show": lit(show), "labelColor": solid(INK_MUT),
        "fontFamily": lit(FONT), "fontSize": lit(font),
        "showAxisTitle": lit(False), "gridlineShow": lit(True),
        "gridlineColor": solid(GRID), "gridlineThickness": lit(1),
        "gridlineStyle": lit("solid"),
    }
    if start is not None:
        props["start"] = lit(start)
    return [{"properties": props}]


def legend(position: str = "TopLeft", show: bool = True) -> list:
    return obj(
        show=lit(show), labelColor=solid(INK_MUT), fontFamily=lit(FONT),
        fontSize=lit(11), showTitle=lit(False), position=lit(position),
    )


def data_labels(show: bool = True, color: str = INK_MUT, font: int = 11) -> list:
    return obj(show=lit(show), color=solid(color), fontFamily=lit(FONT), fontSize=lit(font))


def table_style(total: bool = False, font: int = 12) -> dict:
    return {
        "columnHeaders": obj(
            fontColor=solid(INK_MUT), backColor=solid(BG_ALT),
            fontFamily=lit(FONT_SEMI), fontSize=lit(11),
            outline=lit("BottomOnly"), wordWrap=lit(False),
            alignment=lit("left"),
        ),
        # Faixa alternada: em tabela de 27 linhas o olho perde a linha no meio
        # do caminho. As duas cores sao proximas de proposito — a faixa guia,
        # nao chama atencao.
        "values": obj(
            fontColorPrimary=solid(INK), backColorPrimary=solid(BG_CARD),
            fontColorSecondary=solid(INK), backColorSecondary=solid(BG_ALT),
            fontFamily=lit(FONT), fontSize=lit(font),
            outline=lit("None"), urlIcon=lit(False),
        ),
        "grid": obj(
            gridVertical=lit(False), gridHorizontal=lit(True),
            gridHorizontalColor=solid(GRID), gridHorizontalWeight=lit(1),
            outlineColor=solid(BORDER), outlineWeight=lit(1),
            rowPadding=lit(9), textSize=lit(font),
        ),
        "total": obj(
            totals=lit(total), fontColor=solid(INK_MUT), backColor=solid(BG_CARD),
            fontFamily=lit(FONT_SEMI), fontSize=lit(font),
        ),
    }


# ---------------------------------------------------------------------------
# Construtores de visual
# ---------------------------------------------------------------------------

_seq = {"n": 0}


def visual(page: str, key: str, vtype: str, box, *,
           query: dict | None = None, objects: dict | None = None,
           container: dict | None = None, z: int | None = None) -> dict:
    x, y, w, h = box
    _seq["n"] += 1
    n = _seq["n"]
    z = n * 1000 if z is None else z
    v: dict = {"visualType": vtype}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = container or panel()
    v["drillFilterOtherVisuals"] = True
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json",
        "name": hashlib.md5(f"{page}:{key}:{n}".encode()).hexdigest()[:20],
        "position": {
            "x": round(x, 2), "y": round(y, 2), "z": z,
            "height": round(h, 2), "width": round(w, 2), "tabOrder": z,
        },
        "visual": v,
    }


def q(state: dict, sort: dict | None = None) -> dict:
    d = {"queryState": {k: {"projections": v} for k, v in state.items()}}
    if sort:
        d["sortDefinition"] = sort
    return d


def run(text: str, size: int, color: str, bold: bool = False, font: str = FONT) -> dict:
    style = {"fontSize": f"{size}px", "color": color, "fontFamily": font}
    if bold:
        style["fontWeight"] = "bold"
    return {"value": text, "textStyle": style}


def textbox(page: str, key: str, box, runs: list, align: str = "left",
            container: dict | None = None) -> dict:
    return visual(
        page, key, "textbox", box,
        objects={"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": align}])},
        container=container or bare(),
    )


def block(page: str, key: str, box, color: str) -> dict:
    """Retangulo de fundo — usado para o rail lateral."""
    return visual(
        page, key, "textbox", box,
        objects={"general": obj(paragraphs=[{"textRuns": [run(" ", 9, color)]}])},
        container={
            "background": obj(show=lit(True), color=solid(color), transparency=lit(0)),
            "border": obj(show=lit(False)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
        z=0,
    )


def stat(page: str, key: str, box, label: str, measure: str, color: str,
         note: str | None = None, color_measure: str | None = None,
         precision: int | None = None) -> dict:
    """Numero grande com rotulo acima. Sem moldura: o respiro faz a separacao."""
    return visual(
        page, key, "card", box,
        query=q({"Values": [measure_field(measure)]}),
        objects={
            "labels": [{"properties": {
                "color": solid_by_measure(color_measure) if color_measure else solid(color),
                "fontFamily": lit(FONT_TITLE), "fontSize": lit(34),
                **({"labelPrecision": lit(precision)} if precision is not None else {}),
            }}],
            "categoryLabels": obj(show=lit(False)),
            "wordWrap": obj(show=lit(False)),
        },
        container=panel(label, note, centro=True),
    )


def bar(page: str, key: str, box, title: str, subtitle: str,
        cat_entity: str, cat_prop: str, measure: str, *,
        vtype: str = "barChart", color: str | None = None, points: list | None = None,
        labels: bool = True, legend_pos: str | None = None, series: tuple | None = None,
        sort: dict | None = None, categorical: bool = False) -> dict:
    state = {"Category": [column_field(cat_entity, cat_prop)], "Y": [measure_field(measure)]}
    if series:
        state["Series"] = [column_field(series[0], series[1])]
    objects = {
        "categoryAxis": axis_cat(categorical=categorical),
        "valueAxis": axis_val(show=not labels),
        "legend": legend(legend_pos or "TopLeft", show=bool(series or legend_pos)),
        "labels": data_labels(labels),
    }
    if points:
        objects["dataPoint"] = points
    elif color:
        objects["dataPoint"] = obj(fill=solid(color))
    return visual(
        page, key, vtype, box,
        query=q(state, sort or sort_by_measure(measure)),
        objects=objects,
        container=panel(title, subtitle),
    )


def line(page: str, key: str, box, title: str, subtitle: str,
         cat_entity: str, cat_prop: str, measures: list[str],
         colors: list[str] | None = None, start: float | None = None,
         labels: bool = True) -> dict:
    colors = colors or SERIES
    points = [
        {"properties": {"fill": solid(c)}, "selector": {"metadata": f"{ENTITY_M}.{m}"}}
        for m, c in zip(measures, colors)
    ]
    return visual(
        page, key, "lineChart", box,
        query=q(
            {"Category": [column_field(cat_entity, cat_prop)],
             "Y": [measure_field(m) for m in measures]},
            sort_by_column(cat_entity, cat_prop),
        ),
        objects={
            "categoryAxis": axis_cat(categorical=True),
            "valueAxis": axis_val(start=start),
            "legend": legend("TopLeft", show=len(measures) > 1),
            "labels": data_labels(labels),
            "lineStyles": obj(strokeWidth=lit(3), lineStyle=lit("solid"),
                              showMarker=lit(True), markerSize=lit(5)),
            "dataPoint": points,
        },
        container=panel(title, subtitle),
    )


def table(page: str, key: str, box, title: str, subtitle: str, fields: list, *,
          totals: bool = False, sort: dict | None = None, font: int = 10) -> dict:
    projections = [
        column_field(f[1], f[2], active=False) if f[0] == "col" else measure_field(f[1])
        for f in fields
    ]
    return visual(
        page, key, "tableEx", box,
        query=q({"Values": projections}, sort),
        objects=table_style(total=totals, font=font),
        container=panel(title, subtitle),
    )


def scatter(page: str, key: str, box, title: str, subtitle: str,
            cat_entity: str, cat_prop: str, x: str, y: str,
            size: str | None = None, points: list | None = None,
            series: tuple | None = None) -> dict:
    state = {
        "Category": [column_field(cat_entity, cat_prop)],
        "X": [measure_field(x)],
        "Y": [measure_field(y)],
    }
    if size:
        state["Size"] = [measure_field(size)]
    if series:
        state["Series"] = [column_field(series[0], series[1])]
    objects = {
        "categoryAxis": axis_val(),
        "valueAxis": axis_val(),
        "legend": legend("Bottom", show=bool(series)),
        "categoryLabels": obj(show=lit(True), color=solid(INK_MUT),
                              fontFamily=lit(FONT), fontSize=lit(11)),
        "fillPoint": obj(show=lit(True)),
    }
    if points:
        objects["dataPoint"] = points
    return visual(
        page, key, "scatterChart", box,
        query=q(state), objects=objects, container=panel(title, subtitle),
    )


def slicer(page: str, key: str, box, label: str, entity: str, prop: str,
           blocos: bool = False) -> dict:
    """`blocos=True` renderiza cada valor como botao — o acabamento do Chiclet
    Slicer feito com o visual nativo. So vale a pena com poucos valores: no rail
    de 168px, Estado (27) precisa continuar como lista suspensa."""
    return visual(
        page, key, "slicer", box,
        query=q({"Values": [column_field(entity, prop)]}),
        objects={
            "data": obj(mode=lit("Basic" if blocos else "Dropdown")),
            "general": obj(orientation=lit(0 if blocos else 1)),
            "selection": obj(singleSelect=lit(False), strictSingleSelect=lit(False)),
            "header": obj(
                show=lit(True), text=lit(label), fontColor=solid(INK_DIM),
                background=solid(BG_CARD), fontFamily=lit(FONT_SEMI),
                fontSize=lit(11), outline=lit("None"),
            ),
            "items": obj(
                fontColor=solid(INK), background=solid(BG_ALT),
                fontFamily=lit(FONT_SEMI), fontSize=lit(11),
                outline=lit("Frame") if blocos else lit("None"),
                outlineColor=solid(BORDER), outlineWeight=lit(1),
                padding=lit(8),
            ),
        },
        container={
            "background": obj(show=lit(True), color=solid(BG_CARD), transparency=lit(0)),
            "border": obj(show=lit(True), color=solid(BORDER), radius=lit(12)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
    )


# ---------------------------------------------------------------------------
# Rail + cabecalho de pagina
# ---------------------------------------------------------------------------

def chrome(page: str, titulo: str, lede: str, filtros: bool = True) -> list:
    """Rail lateral: marca, filtros e fonte.

    Sem navegador de paginas: o visual nativo do Power BI so distribui os botoes
    na horizontal, e dentro de um rail estreito ele quebra cada rotulo numa
    coluna de letras. A navegacao fica nas abas nativas do rodape, que todo
    usuario de Power BI ja conhece.
    """
    v = [
        block(page, "rail", (0, 0, RAIL_W, PAGE_H), BG_RAIL),
        textbox(page, "marca", (28, 44, RAIL_W - 44, 76), [
            run("BRECHA\nDIGITAL", 15, TEAL, bold=True, font=FONT_TITLE),
            run("\nBrasil · 2019–2023", 9, INK_DIM),
        ]),
    ]
    if filtros:
        # Regiao em blocos (5 valores empilham bem no rail); Ano e Estado
        # continuam suspensos — 27 estados em botao nao caberiam em 168px.
        v.append(slicer(page, "slicer_Ano", (20, 176, RAIL_W - 40, 62),
                        "Ano", "dim_periodo", "Ano"))
        v.append(slicer(page, "slicer_Regiao", (20, 254, RAIL_W - 40, 200),
                        "Região", "dim_uf", "Região", blocos=True))
        v.append(slicer(page, "slicer_Estado", (20, 470, RAIL_W - 40, 62),
                        "Estado", "dim_uf", "Estado"))
    v.append(textbox(page, "fonte", (24, PAGE_H - 132, RAIL_W - 44, 100), [
        run("FONTE\n", 9, INK_DIM, bold=True),
        run("IBGE · PNAD Contínua\nPNUD · Atlas do IDH\nSérie 2019–2022 retropolada", 9, INK_DIM),
    ]))

    # Cabecalho editorial: titulo em serifa + linha de apoio
    v.append(textbox(page, "titulo", (CONTENT_X, HEAD_Y, CONTENT_W, 116), [
        run(titulo, 30, INK, bold=True, font=FONT_TITLE),
        run("\n" + lede, 13, INK_MUT),
    ]))
    return v


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

def page_brecha() -> tuple[str, list]:
    p = "brecha"
    v = chrome(p, "A brecha em números",
               "87% dos domicílios brasileiros têm internet. O que esse número esconde é onde estão os 13% que não têm.")

    # Faixa de indicadores
    stat_y, stat_h = BODY_Y, 128
    for (x, w), (key, label, measure, color, note, prec) in zip(cols(4), [
        ("s1", "PENETRAÇÃO NACIONAL", "Penetração Brasil", TEAL, "ponderada por população", None),
        ("s2", "PESSOAS SEM ACESSO", "Pessoas sem Acesso", AMBER, "vivem em domicílios sem internet", 1),
        ("s3", "AMPLITUDE ENTRE ESTADOS", "Amplitude entre UFs (pp)", BRICK, "do melhor ao pior, em pontos", None),
        ("s4", "AVANÇO NO PERÍODO", "Avanço 2019-2023 (pp)", SLATE, "pontos ganhos desde 2019", None),
    ]):
        v.append(stat(p, key, (x, stat_y, w, stat_h), label, measure, color, note, precision=prec))

    ins_y = stat_y + stat_h + GUTTER
    ins_h = 124
    v.append(visual(
        p, "leitura", "card", (CONTENT_X, ins_y, CONTENT_W, ins_h),
        query=q({"Values": [measure_field("Leitura da Brecha")]}),
        objects={
            "labels": obj(color=solid(INK), fontFamily=lit(FONT_TITLE), fontSize=lit(14)),
            "categoryLabels": obj(show=lit(False)),
            "wordWrap": obj(show=lit(True)),
        },
        container=panel("LEITURA DO PERÍODO", "texto gerado por medida DAX — acompanha os filtros do rail"),
    ))

    top = ins_y + ins_h + GUTTER
    h = PAGE_H - MARGIN - top
    (xa, wa), (xb, wb) = split_x(1, 2)

    v.append(line(p, "evolucao", (xa, top, wa, h),
                  "Como o acesso avançou",
                  "penetração nacional ponderada, por ano",
                  "dim_periodo", "Ano", ["Penetração Brasil"], [TEAL], start=0.7))

    # Coluna, e nao barra deitada: 27 estados nao cabem na vertical do painel
    # (o visual cria barra de rolagem e joga o rotulo para dentro da barra).
    # Em coluna, a ordenacao e a inclinacao do conjunto ficam legiveis de uma
    # vez; o valor exato de cada estado sai na dica de contexto e na tabela da
    # pagina "O que explica".
    v.append(bar(p, "por_uf", (xb, top, wb, h),
                 "Penetração por estado",
                 "ordenado do maior para o menor · cor por região",
                 "dim_uf", "UF", "Penetração",
                 vtype="clusteredColumnChart",
                 points=category_colors("dim_uf", "Região", REGIAO),
                 series=("dim_uf", "Região"),
                 labels=False, legend_pos="Bottom"))
    return "A brecha em números", v


def page_paradoxo() -> tuple[str, list]:
    p = "paradoxo"
    v = chrome(p, "Taxa ou volume?",
               "São Paulo é o 3º estado com maior acesso e o 1º em número de pessoas desconectadas. Os dois rankings apontam para lugares diferentes — e planejar expansão exige olhar os dois.")

    r = split(3, 2)
    v.append(scatter(p, "disp", (CONTENT_X, r[0][0], CONTENT_W, r[0][1]),
                     "Penetração × população desconectada",
                     "eixo X: % de domicílios com internet · eixo Y: pessoas sem acesso · tamanho: população do estado · canto superior direito = alto acesso e muita gente de fora",
                     "dim_uf", "UF",
                     "Penetração", "Pessoas sem Acesso", "População Total",
                     points=category_colors("dim_uf", "Região", REGIAO),
                     series=("dim_uf", "Região")))

    (xa, wa), (xb, wb) = split_x(1, 1)
    v.append(table(p, "rk_taxa", (xa, r[1][0], wa, r[1][1]),
                   "Ranking por taxa de acesso",
                   "do pior para o melhor · role para ver os 27 estados",
                   [("col", "dim_uf", "Estado"), ("mea", "Penetração"),
                    ("mea", "Ranking Penetração"), ("mea", "Ranking Volume sem Acesso"),
                    ("mea", "Distância entre Rankings")],
                   sort=sort_by_measure("Penetração", "Ascending")))

    v.append(table(p, "rk_vol", (xb, r[1][0], wb, r[1][1]),
                   "Ranking por volume desconectado",
                   "do maior para o menor · onde de fato mora a população sem acesso",
                   [("col", "dim_uf", "Estado"), ("mea", "Pessoas sem Acesso"),
                    ("mea", "Ranking Volume sem Acesso"), ("mea", "Ranking Penetração"),
                    ("mea", "Distância entre Rankings")],
                   sort=sort_by_measure("Pessoas sem Acesso")))
    return "Taxa ou volume?", v


def page_explica() -> tuple[str, list]:
    p = "explica"
    v = chrome(p, "O que explica o acesso",
               "O IDH do estado sozinho explica 78% da variação de penetração entre as unidades da federação. A brecha digital é, antes de tudo, um retrato da brecha social.")

    r = split(3, 2)
    (xa, wa), (xb, wb) = split_x(2, 1)

    v.append(scatter(p, "idh", (xa, r[0][0], wa, r[0][1]),
                     "IDH × penetração de internet",
                     "cada ponto é um estado · a inclinação da nuvem é a própria desigualdade digital",
                     "dim_uf", "UF", "IDH Médio", "Penetração", "População Total",
                     points=category_colors("dim_uf", "Região", REGIAO),
                     series=("dim_uf", "Região")))

    kh = (r[0][1] - GUTTER) / 2
    v.append(stat(p, "corr", (xb, r[0][0], wb, kh),
                  "CORRELAÇÃO IDH × ACESSO", "Correlação IDH x Penetração", TEAL,
                  "Pearson, entre os estados visíveis"))
    v.append(stat(p, "r2", (xb, r[0][0] + kh + GUTTER, wb, kh),
                  "VARIAÇÃO EXPLICADA PELO IDH", "R² IDH", TEAL,
                  "o quanto do acesso o IDH sozinho prevê"))

    (xc, wc), (xd, wd) = split_x(1, 1)
    v.append(bar(p, "regiao", (xc, r[1][0], wc, r[1][1]),
                 "Penetração por região",
                 "média dos estados de cada região",
                 "dim_uf", "Região", "Penetração",
                 points=category_colors("dim_uf", "Região", REGIAO)))

    v.append(table(p, "detalhe", (xd, r[1][0], wd, r[1][1]),
                   "Estado a estado",
                   "acesso, distância da média nacional e contexto socioeconômico",
                   [("col", "dim_uf", "Estado"), ("col", "dim_uf", "Região"),
                    ("mea", "Penetração"), ("mea", "Gap vs Brasil (pp)"), ("mea", "IDH Médio")],
                   sort=sort_by_measure("Penetração", "Ascending"), font=9))
    return "O que explica", v


def page_oportunidade() -> tuple[str, list]:
    p = "oportunidade"
    v = chrome(p, "Onde investir primeiro",
               "Score que combina mercado endereçável (quanta gente está fora) com facilidade de ganho (quanto falta para universalizar). Não é previsão de retorno — é uma fila de prioridade.")

    r = split(2, 3.2)
    (xa, wa), (xb, wb) = split_x(1, 1)

    v.append(bar(p, "score", (xa, r[0][0], wa, r[0][1]),
                 "Ranking de oportunidade",
                 "60% volume de gente sem acesso + 40% lacuna até 100%",
                 "dim_uf", "UF", "Score Oportunidade",
                 color=TEAL, vtype="clusteredColumnChart", labels=False))

    v.append(bar(p, "mercado", (xb, r[0][0], wb, r[0][1]),
                 "Mercado endereçável",
                 "domicílios sem internet, por estado",
                 "dim_uf", "UF", "Domicílios sem Internet",
                 color=AMBER, vtype="clusteredColumnChart", labels=False))

    v.append(table(p, "fila", (CONTENT_X, r[1][0], CONTENT_W, r[1][1]),
                   "Fila de prioridade",
                   "clique em uma linha para filtrar os gráficos acima",
                   [("col", "dim_uf", "Estado"), ("col", "dim_uf", "Região"),
                    ("mea", "Penetração"), ("mea", "Lacuna até 100%"),
                    ("mea", "Pessoas sem Acesso"), ("mea", "Domicílios sem Internet"),
                    ("mea", "Score Oportunidade"), ("mea", "Prioridade")],
                   sort=sort_by_measure("Score Oportunidade")))
    return "Onde investir", v


def page_metodo() -> tuple[str, list]:
    p = "metodo"
    v = chrome(p, "Metodologia e limites",
               "O que é observado, o que é estimado e o que este painel não autoriza concluir.",
               filtros=False)

    # Ancorado no topo: centrar verticalmente abria um vao entre o titulo da
    # pagina e o primeiro painel, que lia como erro de alinhamento. A pagina e
    # um documento — termina onde o texto termina.
    r = split(3, 2)
    c3 = cols(3)

    blocos = [
        ("Origem do dado", [
            ("Penetração 2023", "IBGE · PNAD Contínua, proporção de domicílios com acesso à "
                                "internet por unidade da federação. Observado."),
            ("Série 2019–2022", "RETROPOLADA. Só 2023 é observado por estado; os anos anteriores "
                                "aplicam a variação nacional do período a cada UF."),
            ("IDH", "PNUD · Atlas do Desenvolvimento Humano, censo 2010. É constante na série — "
                    "não existe IDH anual por estado."),
            ("População e densidade", "IBGE · estimativas 2023 e Censo 2022. Observados."),
        ]),
        ("Modelagem", [
            ("Esquema", "Star schema: um fato (fato_indicadores) no grão UF × ano e duas "
                        "dimensões (dim_uf, dim_periodo)."),
            ("Por que só duas dimensões", "Havia uma dim_metrica com cinco métricas, das quais o "
                                          "fato carregava uma. Dimensão que ninguém aponta é "
                                          "decoração — foi removida."),
            ("Atributos da UF", "População, densidade e IDH vivem só em dim_uf. Estavam copiados "
                                "no fato, repetidos cinco vezes por estado, fingindo série anual."),
            ("Região", "É atributo de dim_uf, não tabela própria: evita um floco de neve sem "
                       "ganho de modelagem."),
        ]),
        ("Como ler os números", [
            ("Duas médias diferentes", "A média simples dos 27 estados dá 84,9%. A ponderada por "
                                       "população dá 87,4%. A diferença existe porque os estados "
                                       "grandes têm mais acesso. O painel usa a ponderada."),
            ("Pessoas sem acesso", "É a leitura em gente do percentual de domicílios, assumindo "
                                   "tamanho de domicílio uniforme (3,1 moradores, PNAD 2023). "
                                   "Não é contagem individual."),
            ("Score de oportunidade", "Ponderação escolhida por mim: 60% volume, 40% lacuna. "
                                      "Muda a fila se mudarem os pesos — por isso está declarado."),
        ]),
    ]

    for (x, w), (titulo, itens) in zip(c3, blocos):
        runs = []
        for i, (rot, txt) in enumerate(itens):
            if i:
                runs.append(run("\n\n", 11, INK_DIM))
            runs.append(run(rot + "\n", 11, TEAL, bold=True))
            runs.append(run(txt, 11, INK_MUT))
        v.append(visual(
            p, f"bloco_{titulo}", "textbox", (x, r[0][0], w, r[0][1]),
            objects={"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": "left"}])},
            container=panel(titulo.upper(), None),
        ))

    limites = [
        ("O que este painel NÃO responde",
         "Não há dado de velocidade, preço, tecnologia de acesso nem qualidade de conexão. "
         "\"Ter internet no domicílio\" inclui do 4G compartilhado à fibra de 500 mega — "
         "duas realidades que o indicador trata como iguais."),
        ("Por que não existe recorte urbano × rural",
         "Existia, e foi removido. A fonte offline só sabia produzi-lo aplicando um desvio fixo "
         "sobre o total (+5pp urbano, −20pp rural), o que gerava um gap de exatamente 25,0 pontos "
         "em todos os 27 estados. Um número que parece análise e não é: não distinguia estado "
         "nenhum porque foi construído para não distinguir."),
        ("Consequência para a leitura da série",
         "Como 2019–2022 é retropolado pela média nacional, todo estado cresce no mesmo ritmo por "
         "construção. A série serve para ordem de grandeza da evolução; não serve para comparar "
         "velocidade de adoção entre estados."),
    ]
    runs = []
    for i, (rot, txt) in enumerate(limites):
        if i:
            runs.append(run("\n\n", 11, INK_DIM))
        runs.append(run(rot + "\n", 11, AMBER, bold=True))
        runs.append(run(txt, 11, INK_MUT))
    v.append(visual(
        p, "limites", "textbox", (CONTENT_X, r[1][0], CONTENT_W, r[1][1]),
        objects={"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": "left"}])},
        container=panel("LEITURA CRÍTICA", None),
    ))
    return "Metodologia", v


PAGES = [page_brecha, page_paradoxo, page_explica, page_oportunidade, page_metodo]


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------

def build_theme() -> dict:
    return {
        "name": "Brecha Digital",
        "dataColors": SERIES + ["#A8B5A2", "#D0A87C", "#7E93A6", "#B9A6BE"],
        "foreground": INK,
        "foregroundNeutralSecondary": INK_MUT,
        "foregroundNeutralTertiary": INK_DIM,
        "background": BG_PAGE,
        "backgroundLight": BG_CARD,
        "backgroundNeutral": BORDER,
        "tableAccent": TEAL,
        "good": TEAL,
        "neutral": OCHRE,
        "bad": AMBER,
        "maximum": TEAL,
        "center": "#9CBBB2",
        "minimum": "#F0EDE6",
        "null": "#C9C2B6",
        "hyperlink": TEAL,
        "textClasses": {
            "title": {"fontFace": FONT_TITLE, "fontSize": 13, "color": INK},
            "header": {"fontFace": FONT_SEMI, "fontSize": 10, "color": INK_MUT},
            "label": {"fontFace": FONT, "fontSize": 10, "color": INK_MUT},
            "callout": {"fontFace": FONT_TITLE, "fontSize": 34, "color": INK},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": BG_CARD}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": BORDER}}, "radius": 2}],
                    "dropShadow": [{"show": False}],
                    "visualHeader": [{"show": False}],
                    "title": [{
                        "show": True,
                        "fontColor": {"solid": {"color": INK}},
                        "background": {"solid": {"color": BG_CARD}},
                        "fontFamily": FONT_TITLE, "fontSize": 13, "alignment": "left",
                    }],
                    "labels": [{"color": {"solid": {"color": INK_MUT}}, "fontSize": 9, "fontFamily": FONT}],
                    "categoryAxis": [{
                        "show": True, "labelColor": {"solid": {"color": INK_MUT}},
                        "fontSize": 9, "showAxisTitle": False, "gridlineShow": False,
                    }],
                    "valueAxis": [{
                        "show": True, "labelColor": {"solid": {"color": INK_MUT}},
                        "fontSize": 9, "showAxisTitle": False,
                        "gridlineColor": {"solid": {"color": GRID}},
                        "gridlineThickness": 1, "gridlineStyle": "solid",
                    }],
                    "legend": [{
                        "show": True, "labelColor": {"solid": {"color": INK_MUT}},
                        "fontSize": 9, "showTitle": False, "position": "TopLeft",
                    }],
                    "outline": [{"show": False}],
                }
            },
            "page": {
                "*": {
                    "background": [{"color": {"solid": {"color": BG_PAGE}}, "transparency": 0}],
                    "outspace": [{"color": {"solid": {"color": BG_OUT}}, "transparency": 0}],
                }
            },
            "card": {
                "*": {
                    "labels": [{"color": {"solid": {"color": INK}}, "fontSize": 34, "fontFamily": FONT_TITLE}],
                    "categoryLabels": [{"show": False}],
                }
            },
            "tableEx": {
                "*": {
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": {"solid": {"color": GRID}},
                              "outlineColor": {"solid": {"color": BORDER}}, "rowPadding": 7}],
                    "columnHeaders": [{"fontColor": {"solid": {"color": INK_DIM}},
                                       "backColor": {"solid": {"color": BG_CARD}},
                                       "fontSize": 9, "fontFamily": FONT_SEMI}],
                }
            },
        },
    }


# ---------------------------------------------------------------------------
# Montagem do pacote
# ---------------------------------------------------------------------------

def page_json(name: str, display: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": name, "displayName": display, "displayOption": "FitToPage",
        "height": PAGE_H, "width": PAGE_W,
        "objects": {
            "background": obj(color=solid(BG_PAGE), transparency=lit(0)),
            "outspace": obj(color=solid(BG_OUT), transparency=lit(0)),
            "displayArea": obj(verticalAlignment=lit("Top")),
        },
    }


def report_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY26SU04",
                "reportVersionAtImport": {"visual": "2.8.0", "report": "3.2.0", "page": "2.3.1"},
                "type": "SharedResources",
            },
            "customTheme": {
                "name": "brecha_digital",
                "reportVersionAtImport": {"visual": "2.11.0", "report": "3.4.0", "page": "2.3.1"},
                "type": "RegisteredResources",
            },
        },
        "objects": {
            "section": obj(verticalAlignment=lit("Top")),
            "outspacePane": obj(expanded=lit(False)),
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY26SU04", "path": "BaseThemes/CY26SU04.json", "type": "BaseTheme"}]},
            # O `path` precisa da extensao; sem ela o Desktop cai no tema base
            # em silencio e a paleta customizada nao vale.
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "brecha_digital", "path": "brecha_digital.json", "type": "BaseTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    }


def build(src: Path, dst: Path) -> None:
    theme = build_theme()
    THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    THEME_FILE.write_text(json.dumps(theme, indent=2, ensure_ascii=False), encoding="utf-8")

    built = []
    for i, fn in enumerate(PAGES):
        display, visuals = fn()
        pname = hashlib.md5(f"page{i}:{display}".encode()).hexdigest()[:20]
        built.append((pname, display, visuals))

    files: dict[str, str] = {
        "Report/definition/version.json": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        }, ensure_ascii=False),
        "Report/definition/report.json": json.dumps(report_json(), ensure_ascii=False),
        "Report/definition/pages/pages.json": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
            "pageOrder": [p[0] for p in built],
            "activePageName": built[0][0],
        }, ensure_ascii=False),
        "Report/StaticResources/RegisteredResources/brecha_digital.json":
            json.dumps(theme, ensure_ascii=False),
    }
    for pname, display, visuals in built:
        files[f"Report/definition/pages/{pname}/page.json"] = json.dumps(
            page_json(pname, display), ensure_ascii=False)
        for vis in visuals:
            files[f"Report/definition/pages/{pname}/visuals/{vis['name']}/visual.json"] = \
                json.dumps(vis, ensure_ascii=False)

    # SecurityBindings sai junto: e um blob DPAPI que assina as partes do
    # pacote. Reescrever Report/definition invalida a assinatura e o Desktop
    # recusa o arquivo inteiro com "esse arquivo esta corrompido". Sem a parte,
    # ele abre e regrava a assinatura no primeiro save.
    # BuiltInThemes tambem sai: ao salvar, o Desktop despeja o catalogo de temas
    # embutidos dele no arquivo (Bloom.json sozinho tem 3 MB). Nada no relatorio
    # aponta para eles e o Desktop os recria sozinho quando precisa.
    drop_prefixes = ("Report/definition/", "Report/CustomVisuals/",
                     "Report/StaticResources/RegisteredResources/",
                     "Report/StaticResources/SharedResources/BuiltInThemes/")
    drop_exact = {"Report/Layout", "SecurityBindings"}

    with zipfile.ZipFile(src) as zin:
        keep = [i for i in zin.infolist()
                if not i.filename.startswith(drop_prefixes) and i.filename not in drop_exact]
        payload = {i.filename: zin.read(i.filename) for i in keep}

    content_types = payload.pop("[Content_Types].xml", None)
    if content_types:
        xml = content_types.decode("utf-8-sig")
        xml = xml.replace('<Override PartName="/SecurityBindings" ContentType="" />', "")
        content_types = "﻿".encode() + xml.encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for fname, data in payload.items():
            zout.writestr(fname, data)
        for fname, text in files.items():
            zout.writestr(fname, text.encode("utf-8"))
        zout.writestr("[Content_Types].xml", content_types or b"")

    n_vis = sum(len(p[2]) for p in built)
    print(f"OK  {dst.name}  ·  {len(built)} paginas  ·  {n_vis} visuais")
    for pname, display, visuals in built:
        print(f"    {display:<24} {len(visuals):>2} visuais")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PBIX
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source
    if target == source:
        backup = source.with_suffix(".prebuild.pbix")
        shutil.copy2(source, backup)
        print(f"backup: {backup.name}")
    build(source, target)

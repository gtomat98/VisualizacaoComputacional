"""
Gera public/data/usp.json a partir das planilhas do Anuário Estatístico e do CSV histórico.

Execute na raiz do projeto:
    python scripts/processar_dados.py

Dependências:
    pip install pandas openpyxl

O script não altera componentes React nem realiza processamento no navegador.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORIGINAIS = ROOT / "data" / "originais"
CSV_HISTORICO = ROOT / "public" / "data" / "historico_transcrito.csv"
ARQUIVO_SAIDA = ROOT / "public" / "data" / "usp.json"

RACAS = {
    "Amar": "Amarela",
    "Bran": "Branca",
    "Indig": "Indígena",
    "Pard": "Parda",
    "Pret": "Preta",
    "N/I": "Não informada",
}
ORDEM_RACAS = [
    "Amarela", "Branca", "Indígena", "Parda", "Preta", "Não informada"
]

# Correções manuais já presentes no usp.json de referência.
# O CSV original ainda contém quantidade vazia para esses dois pontos.
# Mantemos os valores explícitos aqui para que a geração reproduza a série atual.
CORRECOES_HISTORICO = {
    (1989, "Servidores técnicos-administrativos"): (
        17735,
        "valor corrigido conforme informação fornecida; conferir com a fonte oficial",
    ),
    (1990, "Servidores técnicos-administrativos"): (
        17788,
        "valor corrigido conforme informação fornecida; conferir com a fonte oficial",
    ),
    (1991, "Servidores técnicos-administrativos"): (
        16628,
        "valor corrigido conforme informação fornecida; conferir com a fonte oficial",
    ),
}

FONTES = {
    "demografia": (
        "Anuário Estatístico da USP 2025, tabelas 2.19, 2.20 e 2.21 "
        "(processado em 2026)."
    ),
    "evolucao": (
        "Anuário Estatístico da USP 2025, tabelas 2.03, 2.10 e 2.13 "
        "(processado em 2026)."
    ),
    "historico": (
        "Transcrição visual inicial dos gráficos USP em Números enviados "
        "pelo grupo; requer conferência com a série oficial."
    ),
}


def ler_planilha(nome: str) -> pd.DataFrame:
    caminho = ORIGINAIS / nome
    if not caminho.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho}")
    # Nas planilhas do Anuário, a linha 7 (índice 6) contém os cabeçalhos.
    return pd.read_excel(caminho, header=6)


def inteiro(valor: Any, contexto: str) -> int:
    if pd.isna(valor):
        raise ValueError(f"Valor numérico ausente em {contexto}.")
    numero = float(valor)
    if not numero.is_integer():
        raise ValueError(f"Esperado inteiro em {contexto}; recebido {valor!r}.")
    return int(numero)


def validar_colunas(df: pd.DataFrame, esperadas: list[str], arquivo: str) -> None:
    ausentes = [coluna for coluna in esperadas if coluna not in df.columns]
    if ausentes:
        raise ValueError(
            f"{arquivo}: colunas ausentes {ausentes}. "
            f"Colunas encontradas: {list(df.columns)}"
        )


def processar_demografia(
    arquivo: str, grupo: str, coluna_categoria: str
) -> list[dict[str, Any]]:
    df = ler_planilha(arquivo)
    validar_colunas(
        df,
        ["Tipo de Unidade", "Unidade", coluna_categoria, "racacor", "Total"],
        arquivo,
    )

    registros = []
    for indice, linha in df.iterrows():
        codigo_raca = linha["racacor"]
        if codigo_raca not in RACAS:
            raise ValueError(
                f"{arquivo}, linha Excel {indice + 8}: código racial "
                f"não mapeado: {codigo_raca!r}"
            )
        if pd.isna(linha["Tipo de Unidade"]) or pd.isna(linha["Unidade"]):
            raise ValueError(f"{arquivo}, linha Excel {indice + 8}: unidade vazia.")
        if pd.isna(linha[coluna_categoria]):
            raise ValueError(
                f"{arquivo}, linha Excel {indice + 8}: categoria vazia."
            )

        registros.append({
            "tipoUnidade": str(linha["Tipo de Unidade"]),
            "unidade": str(linha["Unidade"]),
            "grupo": grupo,
            "categoria": str(linha[coluna_categoria]),
            "raca": RACAS[codigo_raca],
            "total": inteiro(linha["Total"], f"{arquivo}, linha {indice + 8}"),
        })
    return registros


def processar_evolucao(
    arquivo: str, grupo: str, coluna_regime: str | None = None
) -> list[dict[str, Any]]:
    df = ler_planilha(arquivo)
    colunas = ["Tipo de Unidade", "Unidade", "Ano", "Total"]
    if coluna_regime:
        colunas.append(coluna_regime)
    validar_colunas(df, colunas, arquivo)

    registros = []
    for indice, linha in df.iterrows():
        if pd.isna(linha["Tipo de Unidade"]) or pd.isna(linha["Unidade"]):
            raise ValueError(f"{arquivo}, linha Excel {indice + 8}: unidade vazia.")
        registro = {
            "tipoUnidade": str(linha["Tipo de Unidade"]),
            "unidade": str(linha["Unidade"]),
            "ano": inteiro(linha["Ano"], f"{arquivo}, ano, linha {indice + 8}"),
            "grupo": grupo,
            "regime": (
                None if coluna_regime is None or pd.isna(linha[coluna_regime])
                else str(linha[coluna_regime])
            ),
            "total": inteiro(linha["Total"], f"{arquivo}, total, linha {indice + 8}"),
        }
        registros.append(registro)
    return registros


def processar_historico() -> list[dict[str, Any]]:
    if not CSV_HISTORICO.exists():
        raise FileNotFoundError(f"CSV histórico não encontrado: {CSV_HISTORICO}")
    df = pd.read_csv(CSV_HISTORICO)
    validar_colunas(df, ["ano", "grupo", "quantidade", "observacao"], CSV_HISTORICO.name)

    registros = []
    for indice, linha in df.iterrows():
        ano = inteiro(linha["ano"], f"CSV histórico, linha {indice + 2}, ano")
        grupo = str(linha["grupo"])
        chave = (ano, grupo)

        if chave in CORRECOES_HISTORICO:
            total, observacao = CORRECOES_HISTORICO[chave]
        else:
            total = inteiro(
                linha["quantidade"],
                f"CSV histórico, linha {indice + 2}, quantidade",
            )
            observacao = (
                "" if pd.isna(linha["observacao"]) else str(linha["observacao"])
            )

        registros.append({
            "ano": ano,
            "grupo": grupo,
            "total": total,
            "observacao": observacao,
        })
    return registros


def validar_estrutura(dados: dict[str, Any]) -> None:
    obrigatorias = {"racas", "demografia", "historico", "evolucaoUnidade", "fontes"}
    if set(dados) != obrigatorias:
        raise AssertionError(
            f"Estrutura JSON inesperada. Esperado {obrigatorias}; recebido {set(dados)}"
        )
    if dados["racas"] != ORDEM_RACAS:
        raise AssertionError("A ordem ou os rótulos das categorias raciais foram alterados.")

    for nome, registros in (
        ("demografia", dados["demografia"]),
        ("historico", dados["historico"]),
        ("evolucaoUnidade", dados["evolucaoUnidade"]),
    ):
        if not registros:
            raise AssertionError(f"A coleção {nome} está vazia.")
        if any(not isinstance(item["total"], int) for item in registros):
            raise AssertionError(f"A coleção {nome} contém total que não é inteiro.")

    grupos_demografia = {item["grupo"] for item in dados["demografia"]}
    if grupos_demografia != {"Docentes", "Servidores", "Alunos"}:
        raise AssertionError(f"Grupos demográficos inesperados: {grupos_demografia}")

    racas_encontradas = {item["raca"] for item in dados["demografia"]}
    if racas_encontradas != set(ORDEM_RACAS):
        raise AssertionError(f"Categorias raciais inesperadas: {racas_encontradas}")


def gerar() -> dict[str, Any]:
    demografia = []
    demografia.extend(processar_demografia("T2.19.xlsx", "Docentes", "Nivel"))
    demografia.extend(processar_demografia("T2.20.xlsx", "Servidores", "Categoria"))
    demografia.extend(processar_demografia("T2.21.xlsx", "Alunos", "Categoria"))

    evolucao = []
    evolucao.extend(processar_evolucao("T2.03.xlsx", "Alunos de graduação"))
    evolucao.extend(processar_evolucao("T2.13.xlsx", "Servidores"))
    evolucao.extend(
        processar_evolucao("T2.10.xlsx", "Docentes", "Regime de Trabalho")
    )

    dados = {
        "racas": ORDEM_RACAS,
        "demografia": demografia,
        "historico": processar_historico(),
        "evolucaoUnidade": evolucao,
        "fontes": FONTES,
    }
    validar_estrutura(dados)
    return dados


def main() -> None:
    dados = gerar()
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("JSON gerado com sucesso:")
    print(f"  Arquivo: {ARQUIVO_SAIDA.relative_to(ROOT)}")
    print(f"  Demografia: {len(dados['demografia']):,} registros")
    print(f"  Histórico: {len(dados['historico']):,} registros")
    print(f"  Evolução por unidade: {len(dados['evolucaoUnidade']):,} registros")
    print("  Estrutura e tipos básicos validados.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Busca lista M3U com failover entre múltiplas fontes.
Tenta cada fonte em ordem; usa a primeira que responder com conteúdo válido.
Se todas falharem, mantém o arquivo de saída anterior (não sobrescreve com vazio).
Filtra o conteúdo final para manter apenas canais de TV (remove filmes/séries/VOD).
"""

import os
import re
import sys
import requests
from datetime import datetime, timezone

# ----------------------------------------------------------------
# CONFIGURAÇÃO: liste suas fontes em ordem de prioridade
# Pode ler de variável de ambiente (mais seguro) ou deixar fixo aqui
# ----------------------------------------------------------------
FONTES = [
    os.environ.get("M3U_FONTE_1", ""),
    os.environ.get("M3U_FONTE_2", ""),
    # adicione mais fontes aqui se quiser:
    # os.environ.get("M3U_FONTE_3", ""),
]
FONTES = [f for f in FONTES if f]  # remove vazias

TIMEOUT = 10  # segundos por tentativa
TAMANHO_MINIMO = 200  # bytes — abaixo disso, considera resposta inválida
ARQUIVO_SAIDA = "playlist.m3u"
ARQUIVO_LOG = "status.txt"

# ----------------------------------------------------------------
# FILTRO: remove filmes/séries/VOD, mantém só canais de TV
# Ajuste essa lista conforme os group-title das suas fontes
# ----------------------------------------------------------------
VOD_KEYWORDS = [
    "filme", "filmes", "movie", "movies",
    "serie", "series", "séries",
    "vod", "novela", "anime",
    "documentario", "documentário", "show", "shows",
]


def is_vod(group_title: str, url: str) -> bool:
    group = (group_title or "").lower()
    if any(kw in group for kw in VOD_KEYWORDS):
        return True
    if re.search(r"\.(mp4|mkv|avi)(\?.*)?$", url.lower()):
        return True
    return False


def filtrar_apenas_canais(conteudo: str) -> tuple[str, int, int]:
    """Recebe o M3U completo e retorna (m3u_filtrado, total_original, total_filtrado)."""
    linhas = conteudo.splitlines(keepends=True)
    resultado = ["#EXTM3U\n"]
    total_original = 0
    total_filtrado = 0

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if linha.startswith("#EXTINF"):
            total_original += 1
            match = re.search(r'group-title="([^"]*)"', linha)
            group_title = match.group(1) if match else ""
            url_linha = linhas[i + 1] if i + 1 < len(linhas) else ""

            if not is_vod(group_title, url_linha):
                resultado.append(linha)
                resultado.append(url_linha)
                total_filtrado += 1
            i += 2
        else:
            i += 1

    return "".join(resultado), total_original, total_filtrado


def validar_conteudo(texto: str) -> bool:
    """Confirma que o conteúdo parece um M3U válido."""
    if not texto or len(texto) < TAMANHO_MINIMO:
        return False
    if not texto.lstrip().startswith("#EXTM3U"):
        return False
    if "#EXTINF" not in texto:
        return False
    return True


def buscar_com_failover():
    """Tenta cada fonte em ordem, retorna (conteudo, indice_da_fonte) ou (None, None)."""
    for i, url in enumerate(FONTES, start=1):
        try:
            print(f"Tentando fonte {i}/{len(FONTES)}...")
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            if validar_conteudo(resp.text):
                print(f"✅ Fonte {i} respondeu com conteúdo válido.")
                return resp.text, i
            else:
                print(f"⚠️  Fonte {i} respondeu, mas conteúdo parece inválido.")
        except requests.RequestException as e:
            print(f"❌ Fonte {i} falhou: {e}")
            continue
    return None, None


def main():
    if not FONTES:
        print("Nenhuma fonte configurada. Defina M3U_FONTE_1, M3U_FONTE_2, etc.")
        sys.exit(1)

    conteudo, indice_usado = buscar_com_failover()
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if conteudo:
        conteudo_filtrado, total_original, total_filtrado = filtrar_apenas_canais(conteudo)

        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(conteudo_filtrado)

        removidos = total_original - total_filtrado
        status = (
            f"OK - fonte {indice_usado} usada em {agora} | "
            f"{total_filtrado} canais mantidos, {removidos} itens removidos (filmes/séries)"
        )
        print(status)
    else:
        status = f"FALHA - todas as fontes offline em {agora}. Mantendo arquivo anterior."
        print(status)
        if not os.path.exists(ARQUIVO_SAIDA):
            print("Nenhum arquivo anterior existe. Encerrando com erro.")
            sys.exit(1)

    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        f.write(status + "\n")


if __name__ == "__main__":
    main()
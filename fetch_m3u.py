#!/usr/bin/env python3
"""
Busca lista M3U com failover entre múltiplas fontes.
Tenta cada fonte em ordem; usa a primeira que responder com conteúdo válido.
Se todas falharem, mantém o arquivo de saída anterior (não sobrescreve com vazio).
"""

import os
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
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(conteudo)
        status = f"OK - fonte {indice_usado} usada em {agora}"
        print(status)
    else:
        # Todas as fontes falharam: mantém o arquivo antigo, só registra o problema
        status = f"FALHA - todas as fontes offline em {agora}. Mantendo arquivo anterior."
        print(status)
        if not os.path.exists(ARQUIVO_SAIDA):
            print("Nenhum arquivo anterior existe. Encerrando com erro.")
            sys.exit(1)

    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        f.write(status + "\n")


if __name__ == "__main__":
    main()

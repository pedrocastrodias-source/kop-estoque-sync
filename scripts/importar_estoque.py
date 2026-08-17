import os
import sys
import traceback
from pathlib import Path

import pandas as pd
import requests

# --- 1. CONFIGURAÇÕES ---
URL_SUPABASE = os.environ.get("SUPABASE_URL", "")
KEY_SUPABASE = os.environ.get("SUPABASE_KEY", "")
NOME_TABELA = os.getenv("NOME_TABELA", "estoque_kopenhagen")

PASTA_ARQUIVO = os.getenv("PASTA_ARQUIVO", str(Path(__file__).resolve().parent.parent / "downloads"))
NOME_ARQUIVO = os.getenv("NOME_ARQUIVO", "5358 - Controle de Lote.xls")

caminho_completo = Path(PASTA_ARQUIVO) / NOME_ARQUIVO

SUPABASE_HEADERS = {
    "apikey": KEY_SUPABASE,
    "Authorization": f"Bearer {KEY_SUPABASE}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Prefer": "return=minimal",
}


def print_header():
    print("\n=== IMPORTAR ESTOQUE - KOPENHAGEN ===\n")


def validate_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() not in {".xls", ".xlsx", ".csv"}:
        raise ValueError("Formato de arquivo inválido. Use .xls, .xlsx ou .csv.")


def load_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str, encoding="utf-8", keep_default_na=False)
    return pd.read_excel(path, dtype=str)


def delete_all_records_via_http():
    endpoint = f"{URL_SUPABASE}/rest/v1/{NOME_TABELA}?id=not.is.null"
    response = requests.delete(endpoint, headers=SUPABASE_HEADERS)
    if not response.ok:
        raise RuntimeError(f"Falha ao limpar tabela via API: {response.status_code} {response.text}")


def insert_batch_via_http(records: list[dict], batch_num: int):
    endpoint = f"{URL_SUPABASE}/rest/v1/{NOME_TABELA}"
    response = requests.post(endpoint, headers=SUPABASE_HEADERS, json=records)
    if not response.ok:
        raise RuntimeError(f"Falha ao inserir lote {batch_num}: {response.status_code} {response.text}")


def main():
    print_header()

    if not URL_SUPABASE or not KEY_SUPABASE:
        print("❌ ERRO: SUPABASE_URL ou SUPABASE_KEY não definidos!")
        print("Configure os Secrets no repositório GitHub.")
        sys.exit(1)

    print(f"📂 Lendo arquivo: {caminho_completo}")

    try:
        validate_file(caminho_completo)

        df = load_dataframe(caminho_completo)
        if df.empty:
            raise ValueError("O arquivo está vazio. Verifique o Excel/CSV.")

        de_para_colunas = {
            "DS_NOME_FANTASIA": "nome_fantasia",
            "Data de Validade": "data_validade",
            "Número Lote": "numero_lote",
            "Produto": "id_produto",
            "Cód. SAP": "cod_sap",
            "Descrição": "descricao",
            "Código de Barras": "codigo_barras",
            "Quantidade": "quantidade",
            "Custo": "custo_unitario",
            "Custo Total": "custo_total",
        }

        df = df.rename(columns=de_para_colunas)

        obrigatorias = ["nome_fantasia", "id_produto", "quantidade"]
        faltantes = [c for c in obrigatorias if c not in df.columns]
        if faltantes:
            raise ValueError(f"Faltam colunas obrigatórias no arquivo: {faltantes}")

        # Filtrar produtos descontinuados que saíram de linha e não podem ser baixados no sistema
        PRODUTOS_DESCONTINUADOS = {
            "2002299": "MINITABLETE BRANCO FRIENDS 10G",
            "2002298": "MINITABLETE AO LEITE FRIENDS 10G",
        }
        if "id_produto" in df.columns:
            ids_descontinuados = set(PRODUTOS_DESCONTINUADOS.keys()) | {
                f"{k}.0" for k in PRODUTOS_DESCONTINUADOS
            }
            total_antes = len(df)
            df = df[~df["id_produto"].astype(str).str.strip().isin(ids_descontinuados)]
            removidos = total_antes - len(df)
            if removidos > 0:
                print(f"⚠️ Filtrando {removidos} registros de produtos descontinuados:")
                for pid, pname in PRODUTOS_DESCONTINUADOS.items():
                    print(f"   - {pid}: {pname}")

        if "data_validade" in df.columns:
            df["data_validade"] = pd.to_datetime(df["data_validade"], errors="coerce").dt.strftime("%Y-%m-%d")

        df = df.where(pd.notnull(df), None)
        dados = df.to_dict(orient="records")

        if not dados:
            print("⚠️ Não há registros para inserir após a leitura do arquivo.")
            return

        print("🧹 Limpando tabela no Supabase...")
        delete_all_records_via_http()

        print(f"🚀 Enviando {len(dados)} registros em lotes...")
        lote_tamanho = 500

        for i in range(0, len(dados), lote_tamanho):
            lote = dados[i : i + lote_tamanho]
            insert_batch_via_http(lote, i // lote_tamanho + 1)
            print(f"✅ Lote {i}-{min(i + lote_tamanho, len(dados))} inserido.")

        print("🏁 Importação concluída com sucesso.")

    except Exception:
        print("❌ Erro durante a importação:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

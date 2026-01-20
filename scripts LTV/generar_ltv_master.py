import re
import pandas as pd
from conexion_mysql import crear_conexion

# ======================================================
#  OBL DIGITAL — GENERAL_LTV_CLEAN (Power BI replica)
#  Replica del M-code que mostraste en el Advanced Editor
# ======================================================

# mismos países que en ListaPaises del M-code
POSSIBLE_COUNTRIES = {
    "Argentina", "Colombia", "Costa Rica", "Ecuador", "Mexico", "Peru"
}

# número de filas que Power Query salta:
ROWS_TO_SKIP = 1113


def leer_tabla_original():
    """Lee la tabla general_ltv desde Railway MySQL."""
    conexion = crear_conexion()
    if conexion is None:
        print("❌ No se pudo conectar a Railway.")
        return None, pd.DataFrame()

    print("===> Leyendo tabla original general_ltv ...")
    df = pd.read_sql("SELECT * FROM general_ltv", conexion)
    print(f"   🔸 Columnas originales: {list(df.columns)}")
    print(f"   🔸 Registros brutos: {len(df)}")
    return conexion, df


def limpiar_monto(valor):
    """Normaliza montos estilo Power BI (TOTAL AMOUNT, GENERAL LTV)."""
    if pd.isna(valor):
        return 0.0
    s = str(valor).strip()
    if s == "":
        return 0.0

    # quitar símbolos raros
    s = re.sub(r"[^\d,.\-]", "", s)

    # lógica similar a la que usamos en otros dashboards
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        partes = s.split(",")
        s = s.replace(",", ".") if len(partes[-1]) == 2 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")

    try:
        return float(s)
    except Exception:
        return 0.0


def limpiar_general_ltv(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Replica paso a paso el M-code del Advanced Editor
    y devuelve un DataFrame con columnas:
    date, country, affiliate, usd_total, count_ftd, general_ltv
    """

    # ============================
    # LIMPIEZA INICIAL (Removed Columns + Renamed Columns)
    # ============================
    df = df_raw.copy()

    for col in ["id", "fecha_registro", "general_ltv"]:
        if col in df.columns:
            df.drop(columns=col, inplace=True)

    rename_map = {
        "pais": "country_affiliate",      # "COUNTRY + AFFILIATE"
        "fecha": "date",                  # "DATE"
        "afiliado": "total_amount",       # "TOTAL AMOUNT"
        "usd_total": "ftds",              # "FTD'S"
        "count_ftd": "general_ltv_raw"    # "GENERAL LTV"
    }
    df.rename(columns=rename_map, inplace=True)

    # ============================
    # BORRAR LAS PRIMERAS 1113 FILAS
    # ============================
    if len(df) > ROWS_TO_SKIP:
        df = df.iloc[ROWS_TO_SKIP:].reset_index(drop=True)
    else:
        print(f"⚠️ El dataset tiene menos de {ROWS_TO_SKIP} filas, no se hará skip.")
        df = df.copy()

    # asegurar string limpio
    df["country_affiliate"] = (
        df["country_affiliate"].astype(str).str.strip()
    )

    # ============================
    # IDENTIFICAR PAÍS O AFILIADO (AddType)
    # ============================
    def tipo_fila(valor):
        return "PAIS" if valor in POSSIBLE_COUNTRIES else "AFILIADO"

    df["tipo"] = df["country_affiliate"].apply(tipo_fila)

    # ============================
    # ASIGNAR PAÍS (AddPaisTemp + FillDown)
    # ============================
    df["PaisTemp"] = df.apply(
        lambda r: r["country_affiliate"] if r["tipo"] == "PAIS" else pd.NA,
        axis=1,
    )
    df["PaisTemp"] = df["PaisTemp"].ffill()

    # ============================
    # ASIGNAR AFILIADO (AddAfiliado)
    # ============================
    df["affiliate"] = df.apply(
        lambda r: r["country_affiliate"] if r["tipo"] == "AFILIADO" else pd.NA,
        axis=1,
    )

    # ============================
    # CREAR COLUMNA PAIS (AddPaisFinal)
    # ============================
    df["country"] = df["PaisTemp"]

    # ============================
    # ELIMINAR AFILIADOS NULOS O VACÍOS (RemoveNullAffiliate)
    #   => esto también elimina las filas de tipo "PAIS"
    # ============================
    df = df[
        df["affiliate"].notna()
        & (df["affiliate"].astype(str).str.strip() != "")
    ].copy()

    # ============================
    # ELIMINAR FILAS "TOTAL GENERAL" (RemoveTotalGeneral)
    # ============================
    up_country_aff = df["country_affiliate"].astype(str).str.strip().str.upper()
    up_aff = df["affiliate"].astype(str).str.strip().str.upper()

    df = df[
        (up_country_aff != "TOTAL GENERAL") &
        (up_aff != "TOTAL GENERAL")
    ].copy()

    # ============================
    # ELIMINAR DUPLICADOS (RemoveDuplicates)
    # Distinct por: DATE, COUNTRY + AFFILIATE, TOTAL AMOUNT
    # ============================
    df["date_str"] = df["date"].astype(str)
    df["total_amount_str"] = df["total_amount"].astype(str)

    df = df.drop_duplicates(
        subset=["date_str", "country_affiliate", "total_amount_str"]
    ).reset_index(drop=True)

    # ============================
    # TIPOS FINALES similar a Power BI:
    # DATE como fecha, TOTAL AMOUNT y GENERAL LTV como número
    # ============================
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    df["usd_total"] = df["total_amount"].apply(limpiar_monto)
    df["count_ftd"] = pd.to_numeric(df["ftds"], errors="coerce").fillna(0).astype(float)

    # general_ltv por fila: si viene en count_ftd/raw la usamos, si no la calculamos
    if "general_ltv_raw" in df.columns:
        df["general_ltv"] = pd.to_numeric(
            df["general_ltv_raw"], errors="coerce"
        ).fillna(0.0)
    else:
        df["general_ltv"] = 0.0

    # recalcular cuando sea posible (como hace el M/Power BI)
    df["general_ltv"] = df.apply(
        lambda r: (r["usd_total"] / r["count_ftd"])
        if r["count_ftd"] not in (0, None) else r["general_ltv"],
        axis=1,
    ).fillna(0.0)

    # normalizar texto
    df["country"] = (
        df["country"].astype(str).str.strip().str.title()
    )
    df["affiliate"] = (
        df["affiliate"].astype(str).str.strip().str.title()
    )

    # dataframe final con columnas "limpias" para MySQL
    df_final = df[["date", "country", "affiliate", "usd_total", "count_ftd", "general_ltv"]].copy()
    df_final = df_final.sort_values("date").reset_index(drop=True)

    print(f"✅ GENERAL_LTV_CLEAN generado correctamente con {len(df_final)} registros.")
    return df_final


def guardar_y_cargar_mysql(df_final: pd.DataFrame):
    """Guarda CSV y sube la tabla GENERAL_LTV_CLEAN a Railway."""
    df_final.to_csv("GENERAL_LTV_preview.csv", index=False, encoding="utf-8-sig")
    print("💾 Vista previa guardada: GENERAL_LTV_preview.csv")

    try:
        conexion = crear_conexion()
        if conexion is None:
            print("❌ No se pudo conectar a Railway para escribir la tabla.")
            return

        cursor = conexion.cursor()

        cursor.execute("DROP TABLE IF EXISTS GENERAL_LTV_CLEAN;")
        cursor.execute("""
            CREATE TABLE GENERAL_LTV_CLEAN (
                date DATETIME,
                country VARCHAR(100),
                affiliate VARCHAR(150),
                usd_total DECIMAL(18,2),
                count_ftd INT,
                general_ltv DECIMAL(18,4)
            );
        """)
        conexion.commit()

        insert_sql = """
            INSERT INTO GENERAL_LTV_CLEAN
            (date, country, affiliate, usd_total, count_ftd, general_ltv)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        data = [
            (
                row["date"],
                row["country"],
                row["affiliate"],
                float(row["usd_total"]),
                int(row["count_ftd"]),
                float(row["general_ltv"]),
            )
            for _, row in df_final.iterrows()
        ]

        cursor.executemany(insert_sql, data)
        conexion.commit()
        conexion.close()

        print("✅ Tabla GENERAL_LTV_CLEAN creada y poblada correctamente en Railway.")
    except Exception as e:
        print(f"⚠️ Error al crear GENERAL_LTV_CLEAN: {e}")


if __name__ == "__main__":
    _, df_raw = leer_tabla_original()
    if not df_raw.empty:
        df_final = limpiar_general_ltv(df_raw)
        guardar_y_cargar_mysql(df_final)

        print("\nPrimeras filas del resultado final:")
        print(df_final.head(15))

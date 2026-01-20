import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — GENERAL LTV (RTN ONLY) ===
# ======================================================

def cargar_datos():
    """Carga datos desde MySQL o CSV local."""
    try:
        conexion = crear_conexion()
        if conexion:
            print("✅ Leyendo CMN_MASTER_MEX_CLEAN desde Railway MySQL...")
            query = "SELECT * FROM CMN_MASTER_MEX_CLEAN"
            df = pd.read_sql(query, conexion)
            conexion.close()
            return df
    except Exception as e:
        print(f"⚠️ Error conectando a SQL, leyendo CSV local: {e}")

    print("📁 Leyendo CMN_MASTER_MEX_CLEAN_preview.csv (local)...")
    return pd.read_csv("CMN_MASTER_MEX_CLEAN_preview.csv", dtype=str)


# === 1️⃣ Cargar datos ===
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# === 2️⃣ Normalizar columnas esperadas ===
if "source" not in df.columns:
    df["source"] = None

if "usd_total" not in df.columns:
    for alt in ["usd", "total_amount", "amount_usd"]:
        if alt in df.columns:
            df.rename(columns={alt: "usd_total"}, inplace=True)
            break

if "deposit_type" not in df.columns:
    for alt in ["type", "deposit", "deposit_kind"]:
        if alt in df.columns:
            df.rename(columns={alt: "deposit_type"}, inplace=True)
            break

# === 3️⃣ Normalizar fechas ===
def convertir_fecha(valor):
    try:
        s = str(valor).strip()
        if "/" in s:
            return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
        return pd.to_datetime(s.split(" ")[0], errors="coerce")
    except:
        return pd.NaT

df["date"] = df["date"].astype(str).apply(convertir_fecha)
df = df[df["date"].notna()]
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

# === 4️⃣ Limpieza de montos ===
def limpiar_usd(valor):
    if pd.isna(valor):
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

df["usd_total"] = df["usd_total"].apply(limpiar_usd)

# === 5️⃣ Limpieza de texto ===
for col in ["country", "affiliate", "source", "deposit_type"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()
        df[col].replace({"Nan": None, "None": None, "": None}, inplace=True)

# === 6️⃣ Rango de fechas ===
fecha_min, fecha_max = df["date"].min(), df["date"].max()

# === 7️⃣ Formato ===
def formato_km(valor):
    try:
        return f"{valor:,.2f}"
    except:
        return "0.00"


# === 8️⃣ Inicializar app ===
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — GENERAL LTV RTN"


# === 9️⃣ Layout ===
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD GENERAL LTV — RTN ONLY", style={
            "textAlign": "center",
            "color": "#D4AF37",
            "marginBottom": "30px"
        }),

        html.Div(
            style={"display": "flex", "justifyContent": "space-between"},
            children=[

                html.Div(style={"width": "25%"}, children=[
                    dcc.DatePickerRange(
                        id="filtro-fecha",
                        start_date=fecha_min,
                        end_date=fecha_max
                    )
                ]),

                html.Div(style={"width": "72%"}, children=[

                    html.Div(
                        style={"display": "flex", "justifyContent": "space-around"},
                        children=[
                            html.Div(id="indicador-ftds", style={"width": "22%"}),
                            html.Div(id="indicador-amount", style={"width": "22%"}),
                            html.Div(id="indicador-usd-rtn", style={"width": "22%"}),
                            html.Div(id="indicador-ltv", style={"width": "22%"}),
                        ]
                    ),

                    dcc.Graph(id="grafico-ltv-affiliate"),
                    dcc.Graph(id="grafico-ltv-country"),
                    dcc.Graph(id="grafico-bar-country-aff"),

                    dash_table.DataTable(id="tabla-detalle")
                ])
            ]
        )
    ]
)


# === 🔟 CALLBACK ===
@app.callback(
    [
        Output("indicador-ftds", "children"),
        Output("indicador-amount", "children"),
        Output("indicador-usd-rtn", "children"),
        Output("indicador-ltv", "children"),
        Output("grafico-ltv-affiliate", "figure"),
        Output("grafico-ltv-country", "figure"),
        Output("grafico-bar-country-aff", "figure"),
        Output("tabla-detalle", "data"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
    ],
)
def actualizar_dashboard(start, end):

    df_filtrado = df.copy()

    if start and end:
        df_filtrado = df_filtrado[
            (df_filtrado["date"] >= pd.to_datetime(start)) &
            (df_filtrado["date"] <= pd.to_datetime(end))
        ]

    total_ftds = (df_filtrado["deposit_type"].str.upper() == "FTD").sum()

    total_amount_rtn = df_filtrado.loc[
        df_filtrado["deposit_type"].str.upper() != "FTD",
        "usd_total"
    ].sum()

    general_ltv = total_amount_rtn / total_ftds if total_ftds > 0 else 0

    card_style = {
        "backgroundColor": "#1a1a1a",
        "padding": "20px",
        "borderRadius": "10px",
        "textAlign": "center"
    }

    indicador_ftds = html.Div([
        html.H4("FTD'S", style={"color": "#D4AF37"}),
        html.H2(f"{total_ftds:,}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_amount = html.Div([
        html.H4("TOTAL AMOUNT RTN", style={"color": "#D4AF37"}),
        html.H2(f"${formato_km(total_amount_rtn)}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_usd_rtn = html.Div([
        html.H4("USD RTN", style={"color": "#D4AF37"}),
        html.H2(f"${formato_km(total_amount_rtn)}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_ltv = html.Div([
        html.H4("GENERAL LTV", style={"color": "#D4AF37"}),
        html.H2(f"${general_ltv:,.2f}", style={"color": "#FFF"})
    ], style=card_style)

    fig = px.bar()

    return (
        indicador_ftds,
        indicador_amount,
        indicador_usd_rtn,
        indicador_ltv,
        fig,
        fig,
        fig,
        []
    )

# === 9️⃣ Captura PDF/PPT desde iframe ===
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>OBL Digital — Dashboard FTD</title>
  {%favicon%}
  {%css%}
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
</head>
<body>
  {%app_entry%}
  <footer>
    {%config%}
    {%scripts%}
    {%renderer%}
  </footer>

  <script>
    window.addEventListener("message", async (event) => {
      if (!event.data || event.data.action !== "capture_dashboard") return;

      try {
        const canvas = await html2canvas(document.body, { useCORS: true, scale: 2, backgroundColor: "#0d0d0d" });
        const imgData = canvas.toDataURL("image/png");

        window.parent.postMessage({
          action: "capture_image",
          img: imgData,
          filetype: event.data.type
        }, "*");
      } catch (err) {
        console.error("Error al capturar dashboard:", err);
        window.parent.postMessage({ action: "capture_done" }, "*");
      }
    });
  </script>
</body>
</html>
'''


if __name__ == "__main__":
    app.run_server(debug=True, port=8053)

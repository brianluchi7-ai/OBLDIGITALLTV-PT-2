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
    try:
        conexion = crear_conexion()
        if conexion:
            query = "SELECT * FROM CMN_MASTER_MEX_CLEAN"
            df = pd.read_sql(query, conexion)
            conexion.close()
            return df
    except Exception:
        return pd.read_csv("CMN_MASTER_MEX_CLEAN_preview.csv", dtype=str)


# === 1️⃣ Cargar datos ===
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# === 2️⃣ Normalizar columnas ===
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

# === 3️⃣ Fechas ===
def convertir_fecha(v):
    try:
        s = str(v).strip()
        if "/" in s:
            return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
        return pd.to_datetime(s.split(" ")[0], errors="coerce")
    except:
        return pd.NaT

df["date"] = df["date"].astype(str).apply(convertir_fecha)
df = df[df["date"].notna()]
df["date"] = df["date"].dt.tz_localize(None)

# === 4️⃣ Limpiar USD ===
def limpiar_usd(v):
    if pd.isna(v):
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

df["usd_total"] = df["usd_total"].apply(limpiar_usd)

# === 5️⃣ Texto ===
for c in ["country", "affiliate", "source", "deposit_type"]:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.title()
        df[c].replace({"Nan": None, "None": None, "": None}, inplace=True)

fecha_min, fecha_max = df["date"].min(), df["date"].max()

def formato(v):
    return f"{v:,.2f}"


# === APP ===
app = dash.Dash(__name__)
server = app.server

app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD GENERAL LTV (RTN)", style={
            "textAlign": "center", "color": "#D4AF37", "marginBottom": "30px"
        }),

        html.Div(style={"display": "flex", "justifyContent": "space-between"}, children=[

            html.Div(style={"width": "25%", "backgroundColor": "#1a1a1a", "padding": "20px"}, children=[
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max
                )
            ]),

            html.Div(style={"width": "72%"}, children=[

                html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(id="kpi-ftd"),
                    html.Div(id="kpi-rtn"),
                    html.Div(id="kpi-total"),
                    html.Div(id="kpi-ltv"),
                ]),

                dcc.Graph(id="grafico-affiliate"),
                dcc.Graph(id="grafico-country"),
            ])
        ])
    ]
)


@app.callback(
    [
        Output("kpi-ftd", "children"),
        Output("kpi-rtn", "children"),
        Output("kpi-total", "children"),
        Output("kpi-ltv", "children"),
        Output("grafico-affiliate", "figure"),
        Output("grafico-country", "figure"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
    ]
)
def actualizar(start, end):

    dff = df.copy()
    if start and end:
        dff = dff[(dff["date"] >= start) & (dff["date"] <= end)]

    total_ftd = (dff["deposit_type"].str.upper() == "FTD").sum()

    total_rtn = dff.loc[
        dff["deposit_type"].str.upper() != "FTD",
        "usd_total"
    ].sum()

    general_ltv = total_rtn / total_ftd if total_ftd > 0 else 0

    style = {
        "backgroundColor": "#1a1a1a",
        "padding": "20px",
        "borderRadius": "10px",
        "color": "#FFF",
        "textAlign": "center",
        "width": "22%"
    }

    kpi_ftd = html.Div([html.H4("FTD'S"), html.H2(f"{total_ftd:,}")], style=style)
    kpi_rtn = html.Div([html.H4("USD RTN"), html.H2(f"${formato(total_rtn)}")], style=style)
    kpi_total = html.Div([html.H4("TOTAL AMOUNT RTN"), html.H2(f"${formato(total_rtn)}")], style=style)
    kpi_ltv = html.Div([html.H4("GENERAL LTV"), html.H2(f"${general_ltv:,.2f}")], style=style)

    df_aff = dff[dff["deposit_type"].str.upper() != "FTD"].groupby("affiliate", as_index=False)["usd_total"].sum()
    fig_aff = px.pie(df_aff, names="affiliate", values="usd_total", title="RTN by Affiliate")

    df_cty = dff[dff["deposit_type"].str.upper() != "FTD"].groupby("country", as_index=False)["usd_total"].sum()
    fig_cty = px.pie(df_cty, names="country", values="usd_total", title="RTN by Country")

    for fig in [fig_aff, fig_cty]:
        fig.update_layout(
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#0d0d0d",
            font_color="#FFF",
            title_font_color="#D4AF37"
        )

    return kpi_ftd, kpi_rtn, kpi_total, kpi_ltv, fig_aff, fig_cty
    
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


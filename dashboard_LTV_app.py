import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — GENERAL LTV (Dark Gold) ===
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

# TEAM & AGENT
for col in ["team", "agent"]:
    if col not in df.columns:
        df[col] = None
    else:
        df[col] = df[col].astype(str).str.strip().str.title()
        df[col].replace({"Nan": None, "None": None, "": None}, inplace=True)


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
external_scripts = [
    "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/pptxgenjs/3.10.0/pptxgen.bundle.js"
]

app = dash.Dash(__name__, external_scripts=external_scripts)
server = app.server
app.title = "OBL Digital — GENERAL LTV Dashboard"


# === 9️⃣ Layout ===
app.layout = html.Div(
    style={
        "backgroundColor": "#0d0d0d",
        "color": "#000000",
        "fontFamily": "Arial",
        "padding": "20px"
    },
    children=[

        html.H1("📊 DASHBOARD RTN LTV", style={
            "textAlign": "center",
            "color": "#D4AF37",
            "marginBottom": "30px",
            "fontWeight": "bold"
        }),

        html.Div(
            style={"display": "flex", "justifyContent": "space-between"},
            children=[

                # === FILTROS ===
                html.Div(
                    style={
                        "width": "25%",
                        "backgroundColor": "#1a1a1a",
                        "padding": "20px",
                        "borderRadius": "12px",
                        "boxShadow": "0 0 15px rgba(212,175,55,0.3)",
                        "textAlign": "center",
                    },
                    children=[
                        html.H4("Date", style={"color": "#D4AF37"}),
                        dcc.DatePickerRange(
                            id="filtro-fecha",
                            start_date=fecha_min,
                            end_date=fecha_max,
                            display_format="YYYY-MM-DD",
                        ),

                        html.H4("Affiliate", style={"color": "#D4AF37", "marginTop": "10px"}),
                        dcc.Dropdown(
                            sorted(df["affiliate"].dropna().unique()),
                            multi=True,
                            id="filtro-affiliate"
                        ),

                        html.H4("Source", style={"color": "#D4AF37", "marginTop": "10px"}),
                        dcc.Dropdown(
                            sorted(df["source"].dropna().unique()),
                            multi=True,
                            id="filtro-source"
                        ),

                        html.H4("Country", style={"color": "#D4AF37", "marginTop": "10px"}),
                        dcc.Dropdown(
                            sorted(df["country"].dropna().unique()),
                            multi=True,
                            id="filtro-country"
                        ),

                        html.H4("Team Leader (RTN)", style={"color": "#D4AF37", "marginTop": "10px"}),
                        dcc.Dropdown(
                            sorted(
                                df.loc[df["deposit_type"].str.upper() == "RTN", "team"]
                                .dropna()
                                .unique()
                            ),
                            multi=True,
                            id="filtro-team"
                        ),
                        
                        html.H4("Agent (RTN)", style={"color": "#D4AF37", "marginTop": "10px"}),
                        dcc.Dropdown(
                            sorted(
                                df.loc[df["deposit_type"].str.upper() == "RTN", "agent"]
                                .dropna()
                                .unique()
                            ),
                            multi=True,
                            id="filtro-agent"
                        ),
                    ]
                ),

                # === PANEL PRINCIPAL ===
                html.Div(
                    style={"width": "72%"},
                    children=[

                        html.Div(
                            style={"display": "flex", "justifyContent": "space-around"},
                            children=[
                                html.Div(id="indicador-ftds", style={"width": "22%"}),
                                html.Div(id="indicador-usd-rtn", style={"width": "22%"}),
                                html.Div(id="indicador-total-rtn", style={"width": "22%"}),
                                html.Div(id="indicador-ltv", style={"width": "22%"}),
                            ]
                        ),

                        html.Br(),

                        html.Div(
                            style={"display": "flex", "flexWrap": "wrap", "gap": "20px"},
                            children=[
                                dcc.Graph(id="grafico-ltv-affiliate", style={"width": "48%", "height": "340px"}),
                                dcc.Graph(id="grafico-ltv-country", style={"width": "48%", "height": "340px"}),
                                dcc.Graph(id="grafico-ltv-team", style={"width": "48%", "height": "340px"}),
                                dcc.Graph(id="grafico-ltv-agent", style={"width": "48%", "height": "340px"}),
                                dcc.Graph(id="grafico-bar-country-aff", style={"width": "100%", "height": "360px"}),
                            ]
                        ),

                        html.Br(),

                        html.H4("📋 Detalle General LTV", style={"color": "#D4AF37"}),

                        dash_table.DataTable(
                            id="tabla-detalle",
                            columns=[
                                {"name": "DATE", "id": "date"},
                                {"name": "COUNTRY", "id": "country"},
                                {"name": "TEAM LEADER", "id": "team"},
                                {"name": "AFFILIATE", "id": "affiliate"},
                                {"name": "SOURCE", "id": "source"},
                                {"name": "TOTAL AMOUNT RTN", "id": "usd_total"},
                                {"name": "FTD'S", "id": "count_ftd"},
                                {"name": "GENERAL LTV", "id": "general_ltv"},
                            ],
                            page_size=15,
                            style_cell={
                                "textAlign": "center",
                                "color": "#f2f2f2",
                                "backgroundColor": "#1a1a1a"
                            },
                            style_header={
                                "backgroundColor": "#D4AF37",
                                "color": "#000",
                                "fontWeight": "bold"
                            },
                        ),
                    ]
                )
            ]
        )
    ]
)


# === 🔟 CALLBACK ===
@app.callback(
    [
        Output("indicador-ftds", "children"),
        Output("indicador-usd-rtn", "children"),
        Output("indicador-total-rtn", "children"),
        Output("indicador-ltv", "children"),
        Output("grafico-ltv-affiliate", "figure"),
        Output("grafico-ltv-country", "figure"),
        Output("grafico-ltv-team", "figure"),
        Output("grafico-ltv-agent", "figure"),
        Output("grafico-bar-country-aff", "figure"),
        Output("tabla-detalle", "data"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
        Input("filtro-affiliate", "value"),
        Input("filtro-source", "value"),
        Input("filtro-team", "value"),
        Input("filtro-agent", "value"),
        Input("filtro-country", "value"),
    ],
)
def actualizar_dashboard(start, end, affiliates, sources, countries, teams, agents):

    df_filtrado = df.copy()

    if start and end:
        df_filtrado = df_filtrado[
            (df_filtrado["date"] >= pd.to_datetime(start)) &
            (df_filtrado["date"] <= pd.to_datetime(end))
        ]
    if affiliates:
        df_filtrado = df_filtrado[df_filtrado["affiliate"].isin(affiliates)]
    if sources:
        df_filtrado = df_filtrado[df_filtrado["source"].isin(sources)]
    if countries:
        df_filtrado = df_filtrado[df_filtrado["country"].isin(countries)]
   # === FILTRO POR TEAM LEADER (RTN) ===
    if teams:
        teams = [t for t in teams if t]
    
        rtn_keys = (
            df_filtrado[
                (df_filtrado["deposit_type"].str.upper() == "RTN") &
                (df_filtrado["team"].isin(teams))
            ][["country", "affiliate", "source"]]
            .drop_duplicates()
        )
    
        if not rtn_keys.empty:
            df_filtrado = df_filtrado[
                df_filtrado.set_index(["country", "affiliate", "source"]).index.isin(
                    rtn_keys.set_index(["country", "affiliate", "source"]).index
                )
            ]
        else:
            df_filtrado = df_filtrado.iloc[0:0]
    
    
    # === FILTRO POR AGENT (RTN) ===
    if agents:
        agents = [a for a in agents if a]
    
        rtn_keys = (
            df_filtrado[
                (df_filtrado["deposit_type"].str.upper() == "RTN") &
                (df_filtrado["agent"].isin(agents))
            ][["country", "affiliate", "source"]]
            .drop_duplicates()
        )
    
        if not rtn_keys.empty:
            df_filtrado = df_filtrado[
                df_filtrado.set_index(["country", "affiliate", "source"]).index.isin(
                    rtn_keys.set_index(["country", "affiliate", "source"]).index
                )
            ]
        else:
            df_filtrado = df_filtrado.iloc[0:0]
    

    # ====================================================
    # ✅ AJUSTE ÚNICO: FTDs CALCULADOS POR GRUPO (CORRECTO)
    # ====================================================

    df_rtn = df_filtrado[df_filtrado["deposit_type"].str.upper() != "FTD"].copy()
    df_ftd = df_filtrado[df_filtrado["deposit_type"].str.upper() == "FTD"].copy()

    df_rtn["month"] = df_rtn["date"].dt.to_period("M")
    df_ftd["month"] = df_ftd["date"].dt.to_period("M")

    df_rtn_grp = (
        df_rtn
        .groupby(["month", "country", "affiliate", "source"], as_index=False)
        .agg({"usd_total": "sum"})
    )

    df_ftd_grp = (
        df_ftd
        .groupby(["month", "country", "affiliate", "source"], as_index=False)
        .size()
        .rename(columns={"size": "count_ftd"})
    )

    df_month = df_rtn_grp.merge(
        df_ftd_grp,
        on=["month", "country", "affiliate", "source"],
        how="left"
    )

    df_month["count_ftd"] = df_month["count_ftd"].fillna(0)

    df_month["general_ltv"] = df_month.apply(
        lambda r: r["usd_total"] / r["count_ftd"] if r["count_ftd"] > 0 else 0,
        axis=1
    )

    df_month["date"] = df_month["month"].dt.to_timestamp("M")
    df_month.drop(columns=["month"], inplace=True)

    # ====================================================

    total_ftds = (df_filtrado["deposit_type"].str.upper() == "FTD").sum()
    usd_rtn = df_rtn["usd_total"].sum()
    general_ltv_total = usd_rtn / total_ftds if total_ftds > 0 else 0
    
    card_style = {
        "backgroundColor": "#1a1a1a",
        "borderRadius": "10px",
        "padding": "20px",
        "width": "80%",
        "textAlign": "center",
        "boxShadow": "0 0 10px rgba(212,175,55,0.3)",
    }

    indicador_ftds = html.Div([
        html.H4("FTD'S", style={"color": "#D4AF37"}),
        html.H2(f"{int(total_ftds):,}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_usd_rtn = html.Div([
        html.H4("USD RTN", style={"color": "#D4AF37"}),
        html.H2(f"${formato_km(usd_rtn)}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_total_rtn = html.Div([
        html.H4("TOTAL AMOUNT RTN", style={"color": "#D4AF37"}),
        html.H2(f"${formato_km(usd_rtn)}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_ltv = html.Div([
        html.H4("GENERAL LTV", style={"color": "#D4AF37"}),
        html.H2(f"${general_ltv_total:,.2f}", style={"color": "#FFF"})
    ], style=card_style)

    # === GRÁFICAS (RTN) ===
    df_aff = df_month.groupby("affiliate", as_index=False)["general_ltv"].mean()
    fig_affiliate = px.pie(
        df_aff, names="affiliate", values="general_ltv",
        title="GENERAL LTV by Affiliate",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

    df_cty = df_month.groupby("country", as_index=False)["general_ltv"].mean()
    fig_country = px.pie(
        df_cty, names="country", values="general_ltv",
        title="GENERAL LTV by Country",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

        # --- GENERAL LTV by TEAM LEADER (SOLO RTN) ---
    df_rtn = df_filtrado[df_filtrado["deposit_type"].str.upper() == "RTN"].copy()
    
    df_team = df_rtn.groupby("team", as_index=False).agg(
        {
            "usd_total": "sum",
            "deposit_type": "count"
        }
    ).rename(columns={"deposit_type": "count_rtn"})
    
    df_team = df_team[df_team["count_rtn"] > 0]
    df_team["general_ltv"] = df_team["usd_total"] / df_team["count_rtn"]
    
    fig_team = px.pie(
        df_team,
        names="team",
        values="general_ltv",
        title="GENERAL LTV by Team Leader (RTN)",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )
    
    # --- GENERAL LTV by AGENT (SOLO RTN) ---
    df_agent = df_rtn.groupby("agent", as_index=False).agg(
        {
            "usd_total": "sum",
            "deposit_type": "count"
        }
    ).rename(columns={"deposit_type": "count_rtn"})
    
    df_agent = df_agent[df_agent["count_rtn"] > 0]
    df_agent["general_ltv"] = df_agent["usd_total"] / df_agent["count_rtn"]
    
    fig_agent = px.pie(
        df_agent,
        names="agent",
        values="general_ltv",
        title="GENERAL LTV by Agent (RTN)",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

    fig_bar = px.bar(
        df_month,
        x="country",
        y="general_ltv",
        color="affiliate",
        barmode="group",
        title="GENERAL LTV by Country and Affiliate",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

     # --- ESTILO DARK ---
    for fig in [fig_affiliate, fig_country, fig_team, fig_agent, fig_bar]:
        fig.update_layout(
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#0d0d0d",
            font_color="#f2f2f2",
            title_font_color="#D4AF37"
        )    


    tabla = df_month.copy()
    tabla["date"] = tabla["date"].dt.strftime("%Y-%m-%d")

    return (
        indicador_ftds,
        indicador_usd_rtn,
        indicador_total_rtn,
        indicador_ltv,
        fig_affiliate,
        fig_country,
        fig_team,
        fig_agent,
        fig_bar,
        tabla.round(2).to_dict("records")
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







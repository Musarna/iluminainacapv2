from __future__ import annotations

import hashlib
import json
from datetime import datetime
from math import cos, radians, sin

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data import TOLOLO_LAT, TOLOLO_LON, load_zones
from src.model import rank_zones

# ---------------------------------------------------------------------------
# Configuración general y estilo
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Priorización lumínica · Cerro Tololo",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

NIVEL_COLORES = {"Alta": "#c0392b", "Media": "#e67e22", "Baja": "#7f8c9d"}
NIVEL_ICONO = {"Alta": "🔴", "Media": "🟠", "Baja": "⚪"}
UNIDAD_RAD = "nW/cm²/sr"

st.markdown(
    """
    <style>
      .block-container {padding-top: 3.2rem; padding-bottom: 2rem;}
      .hero {
        background: linear-gradient(120deg, #0b1d3a 0%, #1b3a6b 60%, #2c5aa0 100%);
        color: #fff; padding: 1.3rem 1.6rem; border-radius: 14px; margin-bottom: 1rem;
      }
      .hero h1 {color:#fff; font-size: 1.75rem; margin: 0 0 .25rem 0; padding:0;}
      .hero p {color:#dbe6f7; margin: 0; font-size: 1rem;}
      .steps {display:flex; gap:.75rem; margin: .4rem 0 1rem 0; flex-wrap: wrap;}
      .step {
        flex:1; min-width: 200px; background:#f3f6fb; border:1px solid #dde5f1;
        border-radius: 12px; padding: .7rem .9rem; font-size: .92rem; color:#1c2b44;
      }
      .step b {color:#1b3a6b;}
      .step .n {
        display:inline-block; width:1.5rem; height:1.5rem; border-radius:50%;
        background:#1b3a6b; color:#fff; text-align:center; line-height:1.5rem;
        font-weight:700; margin-right:.4rem; font-size:.85rem;
      }
      .card {
        border:1px solid #e3e8f0; border-left: 6px solid #c0392b; border-radius: 10px;
        padding: .65rem .9rem; margin-bottom: .55rem; background:#fff;
      }
      .card .t {font-weight:700; font-size:1.02rem; color:#1c2b44;}
      .card .d {font-size:.9rem; color:#46536a; margin-top:.15rem;}
      .badge {
        display:inline-block; padding:.12rem .55rem; border-radius: 999px; font-size:.8rem;
        font-weight:600; margin-left:.35rem;
      }
      .legend-row {font-size:.88rem; color:#46536a; margin-top:-.3rem;}
      div[data-testid="stMetricValue"] {font-size: 1.6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------
def nivel_prioridad(score: float) -> str:
    """Traduce el percentil del ranking a una categoría fácil de leer."""
    if score >= 90:
        return "Alta"
    if score >= 60:
        return "Media"
    return "Baja"


def circulo(lat: float, lon: float, radio_km: float, n: int = 90) -> tuple[list[float], list[float]]:
    """Puntos de un círculo aproximado (para dibujar anillos de distancia)."""
    lats, lons = [], []
    for k in range(n + 1):
        ang = radians(360 * k / n)
        dlat = (radio_km / 111.32) * cos(ang)
        dlon = (radio_km / (111.32 * cos(radians(lat)))) * sin(ang)
        lats.append(lat + dlat)
        lons.append(lon + dlon)
    return lats, lons


def explicar_zona(row: pd.Series, total: int) -> str:
    """Frase en lenguaje simple que explica por qué la zona está donde está."""
    dist = float(row["distance_km"])
    dist_txt = "menos de 1 km" if dist < 1 else f"{dist:.0f} km"
    br = int(row["brightness_rank"])
    delta = int(row["rank_delta"])
    base = f"A {dist_txt} de Tololo · {br}ª más brillante de {total}."
    if delta > 0:
        return base + f" Sube {delta} {'puesto' if delta == 1 else 'puestos'} por su cercanía al observatorio."
    if delta < 0:
        return base + f" Baja {abs(delta)} {'puesto' if abs(delta) == 1 else 'puestos'} porque está lejos del observatorio."
    return base + " Su brillo y su distancia la ubican en el mismo puesto."


@st.cache_data(show_spinner=False)
def cargar_csv(origen: str, contenido: bytes | None) -> pd.DataFrame:
    from io import BytesIO

    if contenido is not None:
        return load_zones(BytesIO(contenido))
    return load_zones(origen)


def huella_ejecucion(df: pd.DataFrame, params: dict) -> str:
    payload = df.to_csv(index=False).encode("utf-8") + json.dumps(params, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Encabezado y guía de uso
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>🌌 ¿Dónde conviene reducir la luz primero?</h1>
      <p>Herramienta de apoyo para priorizar zonas cuya iluminación más afecta el cielo de
      <b>Cerro Tololo</b> (Región de Coquimbo). Prototipo académico · INACAP · Proyecto de Integración.</p>
    </div>
    <div class="steps">
      <div class="step"><span class="n">1</span><b>Elige el escenario</b> en el panel izquierdo:
        cuánto se reduciría la luz de cada zona.</div>
      <div class="step"><span class="n">2</span><b>Revisa el mapa</b> y las zonas recomendadas:
        rojo = intervenir primero.</div>
      <div class="step"><span class="n">3</span><b>Descarga el ranking</b> en CSV para
        respaldar la decisión.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Panel lateral: parámetros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("① Escenario")

    opciones_datos = {
        "Datos satelitales VIIRS (Tololo)": "data/viirs_tololo.csv",
        "Datos de demostración (ficticios)": "data/demo_zones.csv",
        "Cargar mi propio CSV": None,
    }
    from pathlib import Path

    disponibles = [k for k, v in opciones_datos.items() if v is None or Path(v).exists()]
    fuente_sel = st.radio(
        "Datos a analizar",
        disponibles,
        help="Los datos VIIRS son radiancia nocturna satelital promediada por celda de 10 km.",
    )
    uploaded = None
    if opciones_datos[fuente_sel] is None:
        uploaded = st.file_uploader(
            "Archivo CSV de zonas",
            type=["csv"],
            help="Columnas mínimas: zone_id, latitude, longitude, radiance. "
                 "La distancia a Tololo se calcula si no viene incluida.",
        )

    reduction_pct = st.select_slider(
        "Reducción de luz simulada en cada zona",
        options=[10, 20, 30],
        value=20,
        format_func=lambda x: f"{x} %",
        help="Se simula, zona por zona, que su radiancia baja este porcentaje y se mide cuánto mejora el cielo en Tololo.",
    )

    st.divider()
    st.header("② Vista")
    solo_top = st.slider("Zonas destacadas en el mapa", 5, 30, 10, step=5,
                         help="Cantidad de zonas prioritarias que se rotulan en el mapa.")
    mapa_offline = st.toggle("Mapa sin conexión a internet", value=False,
                             help="Muestra las zonas sobre ejes de latitud/longitud, sin mapa de fondo. Útil si no hay internet.")

    with st.expander("⚙️ Parámetros técnicos (avanzado)"):
        alpha = st.slider(
            "Peso de la distancia (α)", 1.0, 3.0, 2.0, 0.1,
            help="Mientras mayor, más importan las zonas cercanas al observatorio. 2 = ley del inverso del cuadrado.",
        )
        spatial_scale_km = st.number_input(
            "Distancia mínima de suavizado (km)", min_value=1.0, max_value=20.0, value=5.0, step=1.0,
            help="Evita tratar la celda que contiene a Tololo como una fuente a distancia cero.",
        )

    st.divider()
    st.caption(
        "⚠️ Resultado **comparativo y estimativo**. No mide el brillo real del cielo ni "
        "certifica cumplimiento de la Norma Lumínica (D.S. N.° 1/2022 MMA)."
    )

# ---------------------------------------------------------------------------
# Carga y cálculo
# ---------------------------------------------------------------------------
if opciones_datos[fuente_sel] is None and uploaded is None:
    st.info("👈 Sube un archivo CSV en el panel izquierdo para comenzar.")
    st.stop()

try:
    if uploaded is not None:
        df = cargar_csv(uploaded.name, uploaded.getvalue())
        source_label = f"CSV cargado: {uploaded.name}"
    else:
        df = cargar_csv(opciones_datos[fuente_sel], None)
        source_label = opciones_datos[fuente_sel]

    # La celda que contiene al sitio receptor no es una zona emisora candidata.
    receiver_zone = None
    candidates = df.copy()
    nearest_idx = candidates["distance_km"].astype(float).idxmin()
    if float(candidates.loc[nearest_idx, "distance_km"]) < 1.0:
        receiver_zone = candidates.loc[[nearest_idx]].copy()
        candidates = candidates.drop(index=nearest_idx).copy()

    params = {
        "reduccion_pct": float(reduction_pct),
        "alpha": float(alpha),
        "escala_km": float(spatial_scale_km),
    }
    ranked = rank_zones(
        candidates,
        reduction_pct=params["reduccion_pct"],
        alpha=params["alpha"],
        spatial_scale_km=params["escala_km"],
    )
except Exception as exc:  # mensaje simple al usuario
    st.error(
        "No se pudo procesar el archivo. Revisa que tenga las columnas "
        "`zone_id`, `latitude`, `longitude` y `radiance`."
    )
    with st.expander("Detalle técnico del error"):
        st.code(str(exc))
    st.stop()

ranked["nivel"] = ranked["priority_score"].map(nivel_prioridad)
n_zonas = len(ranked)
huella = huella_ejecucion(candidates, params)
fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M")

is_synthetic = ranked.get("data_source", pd.Series(dtype=str)).astype(str).str.contains(
    "synthetic|sint", case=False, regex=True
).any()

if is_synthetic:
    st.warning("🧪 Estás viendo **datos ficticios de demostración**. Úsalos solo para probar la herramienta.")
else:
    periodo = ""
    src_txt = str(ranked["data_source"].iloc[0]) if "data_source" in ranked else ""
    partes = src_txt.split(":")
    if src_txt.startswith("VIIRS") and len(partes) >= 4:
        periodo = f" · período {partes[-2]} a {partes[-1]}"
    st.success(f"🛰️ Datos satelitales VIIRS (NOAA){periodo} · {n_zonas} zonas analizadas.")

top_k = min(10, n_zonas)
top_priority = set(ranked.nsmallest(top_k, "priority_rank")["zone_id"])
top_brightness = set(ranked.nsmallest(top_k, "brightness_rank")["zone_id"])
overlap = len(top_priority & top_brightness)
top = ranked.iloc[0]
n_alta = int((ranked["nivel"] == "Alta").sum())

# ---------------------------------------------------------------------------
# Indicadores principales
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Zonas analizadas", f"{n_zonas}",
          help="Celdas alrededor de Tololo. La celda del propio observatorio se excluye.")
c2.metric("Prioridad alta", f"{n_alta} zonas", help="Zonas en el 10 % superior del ranking.")
c3.metric("Zona a intervenir primero", str(top["zone_id"]),
          help=f"A {float(top['distance_km']):.0f} km del observatorio.")
c4.metric(f"Top {top_k} = las más brillantes", f"{overlap} de {top_k}",
          help="Si es bajo, significa que priorizar solo por brillo llevaría a intervenir zonas equivocadas.")

# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
tab_res, tab_rank, tab_comp, tab_ayuda = st.tabs(
    ["📍 Resultado", "📋 Ranking completo", "⚖️ Comparar escenarios", "❓ Cómo se calcula"]
)

# --- Pestaña 1: Resultado -------------------------------------------------
with tab_res:
    col_mapa, col_top = st.columns([1.6, 1])

    with col_mapa:
        st.subheader("Mapa de prioridad")
        st.markdown(
            "<div class='legend-row'>"
            f"{NIVEL_ICONO['Alta']} <b>Alta</b>: intervenir primero (10 % superior) &nbsp;·&nbsp; "
            f"{NIVEL_ICONO['Media']} <b>Media</b> &nbsp;·&nbsp; {NIVEL_ICONO['Baja']} <b>Baja</b> &nbsp;·&nbsp; "
            "⭐ Cerro Tololo &nbsp;·&nbsp; círculos: 25 / 50 / 100 km"
            "</div>",
            unsafe_allow_html=True,
        )

        use_plain = mapa_offline or not hasattr(go, "Scattermap")

        def Scatter(lat, lon, **kw):
            """Usa mapa con teselas (online) o un plano lat/lon que no requiere internet."""
            if use_plain:
                return go.Scatter(x=lon, y=lat, **kw)
            return go.Scattermap(lat=lat, lon=lon, **kw)

        fig = go.Figure()

        for r_km in (25, 50, 100):
            la, lo = circulo(TOLOLO_LAT, TOLOLO_LON, r_km)
            fig.add_trace(Scatter(
                lat=la, lon=lo, mode="lines", hoverinfo="skip", showlegend=False,
                line=dict(width=1, color="#5d6d7e"),
            ))
            fig.add_trace(Scatter(
                lat=[la[0]], lon=[lo[0]], mode="text", text=[f"{r_km} km"],
                textfont=dict(size=11, color="#34495e"), hoverinfo="skip", showlegend=False,
            ))

        for nivel in ["Baja", "Media", "Alta"]:
            sub = ranked[ranked["nivel"] == nivel]
            if sub.empty:
                continue
            fig.add_trace(Scatter(
                lat=sub["latitude"], lon=sub["longitude"], mode="markers",
                name=f"Prioridad {nivel.lower()}",
                marker=dict(
                    size={"Alta": 15, "Media": 11, "Baja": 8}[nivel],
                    color=NIVEL_COLORES[nivel], opacity=0.9 if nivel != "Baja" else 0.6,
                ),
                customdata=np.stack([
                    sub["zone_id"], sub["priority_rank"], sub["radiance"],
                    sub["distance_km"], sub["relative_benefit"],
                ], axis=-1),
                hovertemplate=(
                    "<b>Zona %{customdata[0]}</b><br>"
                    "Puesto en el ranking: %{customdata[1]}<br>"
                    f"Radiancia: %{{customdata[2]:.2f}} {UNIDAD_RAD}<br>"
                    "Distancia a Tololo: %{customdata[3]:.1f} km<br>"
                    "Beneficio relativo: %{customdata[4]:.0f} / 100<extra></extra>"
                ),
            ))

        destacadas = ranked.head(solo_top)
        fig.add_trace(Scatter(
            lat=destacadas["latitude"], lon=destacadas["longitude"], mode="text",
            text=[f"#{int(p)}" for p in destacadas["priority_rank"]],
            textposition="top right", textfont=dict(size=12, color="#1c2b44"),
            hoverinfo="skip", showlegend=False,
        ))

        if receiver_zone is not None:
            rz = receiver_zone.iloc[0]
            fig.add_trace(Scatter(
                lat=[float(rz["latitude"])], lon=[float(rz["longitude"])], mode="markers",
                marker=dict(size=12, color="#2c3e50", opacity=0.35),
                text=[f"{rz['zone_id']} · celda del observatorio (no se prioriza)"],
                hoverinfo="text", name="Celda del observatorio",
            ))

        fig.add_trace(Scatter(
            lat=[TOLOLO_LAT], lon=[TOLOLO_LON], mode="markers+text",
            marker=dict(size=20, color="#f1c40f", **({"symbol": "star", "line": dict(width=1, color="#7d6608")} if use_plain else {})),
            text=["Cerro Tololo"],
            textposition="bottom center", textfont=dict(size=13, color="#111"),
            name="Observatorio", hovertemplate="<b>Cerro Tololo</b><br>Sitio a proteger<extra></extra>",
        ))

        if use_plain:
            fig.update_xaxes(title="Longitud", showgrid=True, gridcolor="#e5e9f0", zeroline=False)
            fig.update_yaxes(title="Latitud", showgrid=True, gridcolor="#e5e9f0", zeroline=False,
                             scaleanchor="x", scaleratio=1 / cos(radians(TOLOLO_LAT)))
            fig.update_layout(plot_bgcolor="#f7f9fc")
        else:
            fig.update_layout(map=dict(
                style="carto-positron",
                center=dict(lat=TOLOLO_LAT, lon=TOLOLO_LON),
                zoom=7.3 if ranked["distance_km"].max() > 60 else 8.5,
            ))
        fig.update_layout(
            height=560, margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(orientation="h", yanchor="top", y=-0.08 if use_plain else 0.99,
                        xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.85)"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_top:
        st.subheader("Zonas recomendadas")
        st.caption(f"Si se reduce la luz un {reduction_pct} %, estas zonas son las que más mejoran el cielo de Tololo.")
        for _, row in ranked.head(5).iterrows():
            color = NIVEL_COLORES[row["nivel"]]
            st.markdown(
                f"""
                <div class="card" style="border-left-color:{color}">
                  <div class="t">#{int(row['priority_rank'])} · Zona {row['zone_id']}
                    <span class="badge" style="background:{color}22;color:{color}">
                      Prioridad {row['nivel'].lower()}</span></div>
                  <div class="d">{explicar_zona(row, n_zonas)}</div>
                  <div class="d">Beneficio relativo: <b>{row['relative_benefit']:.0f}/100</b>
                    · Radiancia {row['radiance']:.2f} {UNIDAD_RAD}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.expander("¿Por qué no basta con apagar la zona más brillante?"):
            st.write(
                "Una zona muy brillante pero lejana puede afectar menos el cielo de Tololo que una zona "
                "moderada pero cercana. El gráfico muestra cada zona según su brillo (eje X) y su puesto "
                "de prioridad (eje Y)."
            )
            sc = px.scatter(
                ranked, x="radiance", y="priority_score", color="nivel",
                color_discrete_map=NIVEL_COLORES, hover_name="zone_id",
                hover_data={"distance_km": ":.1f", "priority_rank": True, "nivel": False,
                            "radiance": ":.2f", "priority_score": False},
                labels={"radiance": f"Brillo satelital ({UNIDAD_RAD})",
                        "priority_score": "Prioridad (0 = baja, 100 = alta)",
                        "distance_km": "Distancia (km)", "priority_rank": "Puesto", "nivel": "Prioridad"},
            )
            sc.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            sc.update_yaxes(range=[-3, 103])
            st.plotly_chart(sc, use_container_width=True)

# --- Pestaña 2: Ranking completo -----------------------------------------
with tab_rank:
    st.subheader("Ranking de zonas")
    st.caption(
        "Ordenado de mayor a menor beneficio. «Beneficio relativo» = mejora estimada comparada con la "
        "zona #1 (que vale 100)."
    )

    f1, f2 = st.columns([1, 2])
    filtro_nivel = f1.multiselect("Filtrar por prioridad", ["Alta", "Media", "Baja"],
                                  default=["Alta", "Media", "Baja"])
    buscar = f2.text_input("Buscar zona", placeholder="Ej.: G045")
    tecnico = st.toggle("Mostrar columnas técnicas", value=False)

    vista = ranked[ranked["nivel"].isin(filtro_nivel)].copy()
    if buscar:
        vista = vista[vista["zone_id"].astype(str).str.contains(buscar.strip(), case=False)]

    vista["Prioridad"] = vista["nivel"].map(lambda n: f"{NIVEL_ICONO[n]} {n}")
    vista["Efecto de la distancia"] = vista["rank_delta"].map(
        lambda d: f"▲ sube {int(d)}" if d > 0 else (f"▼ baja {abs(int(d))}" if d < 0 else "= igual")
    )
    cols = ["priority_rank", "zone_id", "Prioridad", "relative_benefit", "radiance",
            "distance_km", "brightness_rank", "Efecto de la distancia"]
    if tecnico:
        cols += ["marginal_benefit", "contribution_base", "priority_score"]

    st.dataframe(
        vista[cols],
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "priority_rank": st.column_config.NumberColumn("Puesto", width="small"),
            "zone_id": st.column_config.TextColumn("Zona", width="small"),
            "relative_benefit": st.column_config.ProgressColumn(
                "Beneficio relativo", min_value=0, max_value=100, format="%.0f",
                help="Mejora estimada respecto de la zona #1 (=100).",
            ),
            "radiance": st.column_config.NumberColumn(f"Brillo ({UNIDAD_RAD})", format="%.2f"),
            "distance_km": st.column_config.NumberColumn("Distancia a Tololo (km)", format="%.1f"),
            "brightness_rank": st.column_config.NumberColumn(
                "Puesto por brillo", help="Posición si solo se ordenara por brillo satelital."),
            "Efecto de la distancia": st.column_config.TextColumn(
                help="Cuántos puestos cambia la zona al considerar su distancia al observatorio."),
            "marginal_benefit": st.column_config.NumberColumn("Beneficio marginal (índice)", format="%.5f"),
            "contribution_base": st.column_config.NumberColumn("Contribución base (índice)", format="%.5f"),
            "priority_score": st.column_config.NumberColumn("Percentil", format="%.1f"),
        },
    )
    st.caption(f"Mostrando {len(vista)} de {n_zonas} zonas.")

    export = ranked.copy()
    export.insert(0, "sitio_receptor", "Cerro Tololo")
    export["escenario_reduccion_pct"] = reduction_pct
    export["alpha"] = alpha
    export["escala_espacial_km"] = spatial_scale_km
    export["fuente"] = source_label
    export["fecha_ejecucion"] = fecha_ejec
    export["hash_ejecucion"] = huella
    export["advertencia"] = "Estimacion comparativa; no mide brillo real ni certifica cumplimiento normativo"

    d1, d2 = st.columns([1, 2])
    d1.download_button(
        "⬇️ Descargar ranking (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"ranking_tololo_reduccion_{reduction_pct}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
    with d2.expander("🔎 Datos de esta ejecución (trazabilidad)"):
        st.markdown(
            f"- **Fuente:** `{source_label}`\n"
            f"- **Escenario:** reducción {reduction_pct} % · α = {alpha} · suavizado = {spatial_scale_km} km\n"
            f"- **Fecha:** {fecha_ejec}\n"
            f"- **Huella SHA-256:** `{huella[:16]}…`\n\n"
            "La misma huella indica que se usaron exactamente los mismos datos y parámetros."
        )

# --- Pestaña 3: Comparar escenarios --------------------------------------
with tab_comp:
    st.subheader("¿Qué pasa con 10 %, 20 % y 30 % de reducción?")
    escenarios = []
    for r in (10, 20, 30):
        tmp = rank_zones(candidates, reduction_pct=float(r), alpha=float(alpha),
                         spatial_scale_km=float(spatial_scale_km))
        tmp["Escenario"] = f"{r} %"
        escenarios.append(tmp)
    comp = pd.concat(escenarios, ignore_index=True)

    top_ids = ranked.head(10)["zone_id"].tolist()
    comp_top = comp[comp["zone_id"].isin(top_ids)].copy()
    comp_top["zone_id"] = pd.Categorical(comp_top["zone_id"], categories=top_ids, ordered=True)
    comp_top = comp_top.sort_values("zone_id")

    base_max = float(comp[comp["Escenario"] == "10 %"]["marginal_benefit"].max()) or 1.0
    comp_top["Beneficio (10 % en zona #1 = 100)"] = 100 * comp_top["marginal_benefit"] / base_max

    bar = px.bar(
        comp_top, x="zone_id", y="Beneficio (10 % en zona #1 = 100)", color="Escenario",
        barmode="group", color_discrete_sequence=["#9ecae1", "#4292c6", "#08519c"],
        category_orders={"Escenario": ["10 %", "20 %", "30 %"]},
        labels={"zone_id": "Zona (ordenadas por prioridad)"},
    )
    bar.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.08))
    st.plotly_chart(bar, use_container_width=True)

    mismos = all(
        comp[comp["Escenario"] == e].head(10)["zone_id"].tolist() == top_ids for e in ("10 %", "20 %", "30 %")
    )
    if mismos:
        st.info(
            "**Conclusión:** el orden de las zonas es el mismo en los tres escenarios; "
            "lo que cambia es *cuánto* mejora el cielo. Con 30 % el beneficio es el triple que con 10 %. "
            "Esto ocurre porque el modelo base es lineal."
        )
    else:
        st.info("El orden de las zonas cambia entre escenarios: revisa la tabla de cada uno.")

# --- Pestaña 4: Cómo se calcula ------------------------------------------
with tab_ayuda:
    a1, a2 = st.columns([1.1, 1])
    with a1:
        st.subheader("Cómo funciona, en 4 pasos")
        st.markdown(
            "1. **Se mide el brillo** de cada zona con imágenes satelitales nocturnas (VIIRS, NOAA).\n"
            "2. **Se estima su aporte** al cielo de Tololo: más brillo y más cercanía = más aporte.\n"
            "3. **Se simula** que cada zona, por separado, reduce su luz en el porcentaje elegido.\n"
            "4. **Se ordenan** las zonas según cuánto mejora el cielo en esa simulación."
        )
        st.markdown("**Fórmula del modelo base**")
        st.latex(r"C_i = \frac{L_i}{\left(d_i^2 + s^2\right)^{\alpha/2}} \qquad B_i = C_i - C_i^{\,reducido}")
        st.caption(
            "Lᵢ: radiancia de la zona · dᵢ: distancia a Tololo · s: distancia mínima de suavizado · "
            "α: peso de la distancia · Bᵢ: beneficio marginal."
        )
    with a2:
        st.subheader("Glosario")
        st.markdown(
            f"- **Radiancia / brillo:** luz nocturna captada por satélite, en {UNIDAD_RAD}.\n"
            "- **Zona:** celda de territorio (≈10 × 10 km en los datos VIIRS).\n"
            "- **Beneficio relativo:** mejora estimada de la zona comparada con la #1 (=100).\n"
            "- **Puesto por brillo:** lugar que tendría si solo se mirara el brillo.\n"
            "- **Prioridad alta / media / baja:** 10 % superior / siguiente 30 % / resto del ranking."
        )
        st.subheader("Limitaciones")
        st.warning(
            "- No es un modelo físico validado de brillo del cielo.\n"
            "- No considera relieve, atmósfera ni tipo de luminaria (próximas etapas).\n"
            "- No certifica cumplimiento de la Norma Lumínica; para eso se requiere información de cada fuente emisora."
        )

st.divider()
st.caption(
    f"Fuente: {source_label} · Celda del observatorio excluida del ranking"
    f"{' (' + str(receiver_zone.iloc[0]['zone_id']) + ')' if receiver_zone is not None else ''} · "
    "Prototipo académico INACAP · TIHI63"
)

# MVP · Priorización de mitigación de contaminación lumínica

Prototipo académico para demostrar el flujo central del proyecto de Proyecto de Integración (INACAP):

**datos territoriales → índice base → reducción estandarizada → beneficio marginal → ranking → mapa**.

## Alcance de esta versión

- Un único sitio receptor: **Cerro Tololo**.
- Una grilla de zonas alrededor del sitio.
- Radiancia nocturna por zona (datos sintéticos incluidos; VIIRS real preparado para Earth Engine).
- Línea base exploratoria ponderada por distancia.
- Simulación de reducción de 10 %, 20 % o 30 % en cada zona por separado.
- Ranking de beneficio marginal y comparación contra el ranking de radiancia.
- Mapa geográfico, tabla y descarga CSV.

**Importante:** el índice no es un modelo físico validado de skyglow y no certifica incumplimiento normativo. Su propósito es demostrar la lógica del sistema de apoyo a decisiones.

## 0. Respaldo inmediato sin instalar nada

Abrir `demo_offline.html` con doble clic. Funciona en el navegador con datos sintéticos y también permite cargar un CSV compatible. Es el respaldo para la evaluación si Streamlit o Internet fallan.

## 1. Ejecutar ahora, sin Google Earth Engine

En Windows, dentro de esta carpeta:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

La app usará automáticamente `data/demo_zones.csv`.

## 2. Pruebas

```powershell
pytest -q
```

## 3. Incorporar VIIRS real cuando la cuenta Earth Engine esté lista

Earth Engine requiere autenticación e inicialización con un Google Cloud Project habilitado. Después:

```powershell
python scripts/gee_export_viirs.py --project TU_PROJECT_ID
```

Por defecto el script:

- usa `NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG`;
- consulta 2026-06-01 a 2026-09-01;
- crea celdas de 10 km dentro de 100 km de Cerro Tololo;
- calcula radiancia media (`avg_rad`) y cobertura (`cf_cvg`);
- guarda `data/viirs_tololo.csv`.

Al reiniciar Streamlit, la app detectará ese archivo y dejará de usar los datos sintéticos.

Ejemplo con otros parámetros:

```powershell
python scripts/gee_export_viirs.py --project TU_PROJECT_ID --start 2026-05-01 --end 2026-09-01 --radius-km 120 --cell-km 10
```

## Cómo usar la interfaz

1. **Panel izquierdo → ① Escenario:** elige los datos (VIIRS reales, demostración o tu CSV) y la reducción de luz (10/20/30 %).
2. **Pestaña 📍 Resultado:** mapa con zonas en rojo (prioridad alta), naranjo (media) y gris (baja), anillos de 25/50/100 km y las 5 zonas recomendadas explicadas en lenguaje simple.
3. **Pestaña 📋 Ranking completo:** tabla filtrable con barra de beneficio relativo y descarga CSV con metadatos y huella SHA-256 (trazabilidad).
4. **Pestaña ⚖️ Comparar escenarios:** beneficio de las 10 zonas principales con 10, 20 y 30 %.
5. **Pestaña ❓ Cómo se calcula:** pasos, fórmula, glosario y limitaciones.

Si no hay internet, activa **«Mapa sin conexión a internet»** en el panel izquierdo (las zonas se dibujan sobre ejes de latitud/longitud).

## Estructura

```text
app.py                         interfaz Streamlit
.streamlit/config.toml         tema visual de la app
src/model.py                   índice, simulación y ranking
src/data.py                    carga de datos y distancias
scripts/make_demo_data.py      reconstruye dataset sintético
scripts/gee_export_viirs.py    genera CSV real desde Earth Engine
data/demo_zones.csv            fallback inmediato
tests/test_model.py            pruebas del motor
```

## Fórmula de la línea base

Para cada zona `i`:

`C_i = L_i / max(d_i, d0)^alpha`

Luego se reduce `L_i` por el porcentaje seleccionado y se calcula:

`B_i = C_i - C_i_reducido`

El ranking se ordena por `B_i`. La app muestra además el ranking por radiancia para evidenciar si una zona brillante deja de ser prioritaria al considerar su distancia al sitio receptor.

## Qué NO intenta demostrar esta versión

- causalidad;
- cumplimiento de la norma lumínica;
- brillo real del cielo;
- costos de recambio;
- topografía/atmósfera detalladas;
- validación con fotómetros terrestres.

Estas piezas quedan como extensiones posteriores, coherentes con el alcance mayor descrito en los informes del proyecto.

# Procesamiento de datos Radar TRH

Esta guía documenta el flujo de procesamiento actual: sync raw, detección de períodos afectados y extracción de keywords.

## Resumen

```text
TRH noticias_historico
  ↓ sync por fecha_extraccion
Radar radar_raw_noticias
  ↓ detectar meses afectados por fecha_publicacion
radar_affected_periods
  ↓ extraer keywords por mes, marcando cada noticia procesada
radar_news_keyword_processing
  ↓ refrescar estadísticas
radar_news_keywords + radar_monthly_keyword_stats
  ↓ construir agregados internos con fuentes reales
radar_monthly_overview + radar_daily_activity + radar_source_*_stats
```

## Regla base

El sync y el análisis usan fechas distintas:

- `fecha_extraccion`: sirve para saber qué noticias fueron incorporadas recientemente por TRH.
- `fecha_publicacion`: sirve para saber a qué mes de agenda pertenece la noticia.
- `synced_at`: sirve para saber cuándo Radar copió la noticia.

Esto permite que una noticia antigua incorporada hoy actualice el mes histórico correcto.

## Ejecución por cron

Los scripts principales usan locks de PostgreSQL (`pg_try_advisory_lock`) para evitar que dos crons se pisen. Si ya hay una instancia activa del mismo script, la segunda sale sin hacer cambios.

Esto protege ejecuciones desde el mismo servidor y también desde dos servidores distintos, siempre que usen la misma base Radar.

Para cron operativo, usar el orquestador de raíz:

```bash
./.venv/bin/python proceso.py
```

`proceso.py` toma un lock global `radar_trh:proceso` y ejecuta en orden:

1. `scripts/sync_trh_raw_to_radar.py`
2. `scripts/detect_affected_periods.py`
3. `scripts/extract_keywords.py`
4. `scripts/build_monthly_aggregates.py`

Si ya hay otro `proceso.py` corriendo, sale con código `0` sin hacer cambios. Si un paso falla, corta y devuelve el código de salida del script fallido.

Ejemplo de cron cada 30 minutos:

```cron
*/30 * * * * cd "/home/ren/proyectos/radar trh" && ./.venv/bin/python proceso.py >> logs/proceso.log 2>&1
```

Crear la carpeta de logs si se usa esa ruta:

```bash
mkdir -p logs
```

Si se interrumpe el proceso, PostgreSQL libera el advisory lock al cerrar la conexión. En la siguiente ejecución, el flujo normal puede retomar porque los scripts mantienen locks propios y estados retomables para períodos pendientes/en procesamiento.

## 1. Sync raw

Script:

```bash
python scripts/sync_trh_raw_to_radar.py
```

Incremental por defecto:

```sql
fecha_extraccion >= NOW() - INTERVAL '48 hours'
AND embedding IS NOT NULL
```

Opciones:

```bash
python scripts/sync_trh_raw_to_radar.py --full
python scripts/sync_trh_raw_to_radar.py --lookback-hours 48
```

## 2. Detectar períodos afectados

Script:

```bash
python scripts/detect_affected_periods.py
```

Modos:

| Modo | Comando | Uso |
| --- | --- | --- |
| Full | `python scripts/detect_affected_periods.py --full` | Primera inicialización o reproceso completo |
| Incremental por `synced_at` | `python scripts/detect_affected_periods.py` | Después del sync normal |
| Incremental por `fecha_extraccion` | `python scripts/detect_affected_periods.py --from-extraction-date` | Si se quiere seguir la fecha TRH explícitamente |

Para inicializar el sistema, corré primero el modo full. Eso deja todos los meses existentes como `pending` para que el extractor pueda procesarlos.

Salida esperada:

```text
processing run: 1
mode: incremental | reason: recent_sync
affected periods: 3 | rows detected: 120
- 2021-10-01: 25 rows
- 2024-05-01: 15 rows
- 2026-06-01: 80 rows
```

## 3. Extraer keywords

Script:

```bash
python scripts/extract_keywords.py
```

Fuentes de keywords:

| Fuente | Qué aporta |
| --- | --- |
| Diccionario | Keywords canónicas, aliases, prioridad editorial |
| spaCy | Personas, lugares, organizaciones y entidades |
| YAKE | Frases clave del texto |

Modos:

| Comando | Qué procesa | Uso |
| --- | --- | --- |
| `python scripts/extract_keywords.py` | Períodos `pending` y `processing` | Flujo normal y reanudación después de detectar períodos |
| `python scripts/extract_keywords.py --period 2025-05 --reset-period` | Un mes específico | Reproceso puntual |
| `python scripts/extract_keywords.py --full --reset-period` | Todos los meses con noticias | Reproceso global, especialmente si cambió el diccionario |
| `python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20` | Hasta 20 noticias de un mes | Smoke test |

Sin argumentos, el extractor no es full por definición: procesa períodos `pending` y períodos `processing` que hayan quedado de una interrupción previa. Si antes ejecutaste `detect_affected_periods.py --full`, entonces todos los meses quedan pendientes y `extract_keywords.py` puede procesar todo el corpus.

### Corridas largas, interrupción y reanudación

El extractor está pensado para corridas largas:

```bash
python scripts/extract_keywords.py --commit-every 10
```

- Guarda avances cada 10 noticias por defecto.
- Si se interrumpe, el período queda en `processing`.
- Al relanzarlo sin `--reset-period`, salta noticias marcadas como `completed` en `radar_news_keyword_processing`, incluso si produjeron cero keywords.
- Cuando termina un mes, refresca `radar_monthly_keyword_stats` y marca el período como `completed`.

Comandos útiles:

```bash
# Reanudar pendientes/interrumpidos
python scripts/extract_keywords.py

# Reanudar incluyendo períodos fallidos
python scripts/extract_keywords.py --retry-failed

# Cambiar frecuencia de commits
python scripts/extract_keywords.py --commit-every 25
```

No uses `--reset-period` para reanudar una corrida interrumpida, porque borra keywords/stats existentes del período antes de reprocesar.

## 4. Agregados mensuales MVP

Script:

```bash
python scripts/build_monthly_aggregates.py
```

Este paso se ejecuta después de keywords y genera tablas rápidas para una futura Home/API:

| Tabla | Uso |
| --- | --- |
| `radar_monthly_overview` | Totales del mes, top keywords y resumen interno de fuentes |
| `radar_daily_activity` | Cantidad de noticias por día |
| `radar_source_monthly_stats` | Ranking mensual interno por fuente real |
| `radar_source_keyword_stats` | Cobertura interna fuente real × keyword |

Modos:

| Comando | Qué procesa | Uso |
| --- | --- | --- |
| `python scripts/build_monthly_aggregates.py` | Períodos afectados `completed` | Flujo normal después de keywords |
| `python scripts/build_monthly_aggregates.py --period 2025-05` | Un mes específico | Reproceso puntual |
| `python scripts/build_monthly_aggregates.py --full` | Todos los meses con noticias | Inicialización o reconstrucción global |
| `python scripts/build_monthly_aggregates.py --include-processing` | También períodos `processing` | Agregados parciales, uso excepcional |

### Fuentes y anonimización

Las tablas de DB guardan nombres reales de medios/fuentes. La anonimización ocurre solamente en la futura UI/API cuando se renderiza algo visible para usuarios.

Regla del proyecto:

```text
DB / procesamiento interno → fuente real
UI / salida para usuario   → alias visible, por ejemplo Fuente 1
```

Por eso los agregados mensuales pueden tener `source_media` real. La capa de presentación deberá mapear esos nombres a aliases antes de mostrarlos.

## 5. Diccionario canónico

Archivo:

```text
config/keyword_dictionary.yml
```

Usalo para mantener keywords navegables, evitar fragmentación y omitir ruido de sitios.

La clave `omitted_keywords` descarta frases automáticas que no son temas reales, por ejemplo botones o llamados a la acción. Esta limpieza ocurre en procesamiento, no en la UI: las keywords omitidas no deben generarse ni permanecer en `radar_news_keywords`.

```yaml
omitted_keywords:
  - "click"
  - "unirte al"
  - "leer más"
  - "compartir"
```

Si agregás nuevas omisiones después de haber procesado un mes, corré:

```bash
python scripts/extract_keywords.py --period 2026-05
python scripts/build_monthly_aggregates.py --period 2026-05
```

Eso poda de la DB las keywords omitidas del mes y reconstruye los agregados. Usá `--reset-period` solo si querés recalcular todas las keywords del mes desde cero.

Ejemplo de keyword canónica:

```yaml
- canonical: "Violencia de género"
  type: "topic"
  category: "seguridad"
  priority: 7
  enabled: true
  aliases:
    - "violencia de género"
    - "violencia contra la mujer"
    - "femicidio"
```

Cuando cambia el diccionario, correr:

```bash
python scripts/extract_keywords.py --full --reset-period
```

## 6. Orden recomendado para una primera prueba

```bash
. .venv/bin/activate
pip install -r requirements.txt
psql radar_trh -f db/002_create_processing_tables.sql
psql radar_trh -f db/003_create_keywords_tables.sql
psql radar_trh -f db/004_create_keyword_processing_state.sql
psql radar_trh -f db/005_create_monthly_aggregates.sql
psql radar_trh -f db/006_alter_affected_periods_add_consumed.sql
python scripts/detect_affected_periods.py --full
python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20
python scripts/build_monthly_aggregates.py --period 2025-05
```

Migration `006` upgrades existing `radar_affected_periods` constraints to allow the `consumed` status written by the monthly aggregate builder. Apply numbered migrations in order when upgrading an existing database.

Si el smoke test funciona, seguir con los períodos pendientes creados por `detect_affected_periods.py --full` y luego construir agregados:

```bash
python scripts/extract_keywords.py
python scripts/build_monthly_aggregates.py
```

Si cambiaste `config/keyword_dictionary.yml` y querés reconstruir todo desde cero:

```bash
python scripts/extract_keywords.py --full --reset-period
```

## Pendientes

- Agregar generación de clusters por mes usando embeddings.
- Definir API/UI cuando los datos derivados estén estabilizados.

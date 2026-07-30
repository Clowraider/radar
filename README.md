# Radar TRH

- **TRH:** https://trh.com.ar
- **Radar:** https://radar.trh.com.ar

Radar TRH es la primera versión pública del observatorio visual de agenda mediática derivado de TRH. Usa noticias históricas sincronizadas desde la base de TRH para detectar temas, keywords, fuentes y cambios de agenda por mes.

El proyecto arranca por la capa de datos: primero sincroniza noticias raw, después detecta períodos afectados y finalmente genera keywords/agregados para alimentar la web pública.

## Estado actual

| Área | Estado |
| --- | --- |
| Sync raw TRH → Radar | Implementado |
| Procesamiento incremental | Implementado |
| Keywords canónicas | Implementado con YAML editable |
| Extracción automática | Implementado con spaCy + YAKE |
| Agregados mensuales MVP | Implementado |
| Alias de fuentes estables | Implementado en `radar_source_aliases` |
| Web v0.1 / Radar público | Funcionalmente completo en `web/` |
| Tests Python | 64 tests (`pytest`) |
| API / frontend | Implementado con SvelteKit |
| Clusters | Pendiente para v0.3 |

## Concepto clave de fechas

Radar separa dos fechas con significados distintos:

| Campo | Significado | Uso |
| --- | --- | --- |
| `fecha_extraccion` | Cuándo TRH encontró/indexó la noticia | Sync incremental |
| `fecha_publicacion` | Cuándo fue publicada la noticia | Análisis de agenda mensual |
| `synced_at` | Cuándo Radar copió la noticia | Detección de períodos afectados |

Una noticia puede sincronizarse hoy aunque haya sido publicada hace años. Por eso el flujo incremental detecta entradas recientes, pero recalcula los meses históricos afectados por `fecha_publicacion`.

## Quick path

Fresh databases should be created from the canonical `db/schema.sql` snapshot. Existing databases must apply the numbered SQL migrations in order; in particular, apply `db/006_alter_affected_periods_add_consumed.sql` before running monthly aggregates on a database created before the `consumed` status was introduced.

```bash
# 1. Activar entorno
. .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear la base de datos y aplicar el schema completo
#    (el schema ya incluye tablas, índices, triggers y constraints)
psql postgres -c "CREATE DATABASE radar_trh;"
psql radar_trh -f db/schema.sql

# 4. Configurar .env (copiar y editar credenciales)
cp .env.example .env
# editar .env con los datos de TRH y de la base Radar

# 5. Sync full inicial
python scripts/sync_trh_raw_to_radar.py --full

# 6. Detectar todos los períodos existentes para la primera inicialización
python scripts/detect_affected_periods.py --full

# 7. Smoke test de keywords con pocas noticias de un mes
python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20

# 8. Si el smoke test funciona, procesar todos los períodos pendientes
python scripts/extract_keywords.py

# 9. Construir agregados mensuales
python scripts/build_monthly_aggregates.py

# 10. Ejecutar la web v0.1 de Radar
cd web
cp radar-web.env.example radar-web.env
# editar radar-web.env si no alcanza con el .env del proyecto padre
npm install
npm run dev
```

Producción manual en LXC:

```bash
cd web
npm install
npm run build
HOST=0.0.0.0 PORT=3000 node build
```

Producción permanente en LXC con systemd:

```bash
sudo cp web/radar-web.service.example /etc/systemd/system/radar-web.service
sudo nano /etc/systemd/system/radar-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now radar-web
sudo systemctl status radar-web
```

El servicio debe tener sección `[Install]` para poder habilitarse al reinicio:

```ini
[Install]
WantedBy=multi-user.target
```

Logs de la web:

```bash
sudo journalctl -u radar-web -f
```

> La web no tiene `app.py`: no es FastAPI/Flask. Se ejecuta con Node/SvelteKit (`npm run dev`, `npm run build`, `node build`).
>
> No subas ni edites credenciales reales en `.env` o `web/radar-web.env`. Usá los `.example` como referencia.

## Ejecución por cron y locks

Los scripts principales usan `pg_try_advisory_lock` en PostgreSQL para evitar ejecuciones simultáneas. Esto funciona incluso si el mismo cron corre desde dos servidores, siempre que ambos apunten a la misma DB Radar.

Si otra instancia ya está corriendo, el segundo proceso sale sin hacer cambios con un mensaje como:

```text
extract_keywords: ya hay otra ejecución activa; saliendo sin hacer cambios
```

Scripts protegidos:

- `scripts/sync_trh_raw_to_radar.py`
- `scripts/detect_affected_periods.py`
- `scripts/extract_keywords.py`
- `scripts/build_monthly_aggregates.py`

Además, `proceso.py` permite correr todo el flujo incremental desde cron con un lock global `radar_trh:proceso`:

```bash
./.venv/bin/python proceso.py
```

Ejemplo de cron cada 30 minutos:

```cron
*/30 * * * * cd "/home/ren/proyectos/radar trh" && ./.venv/bin/python proceso.py >> logs/proceso.log 2>&1
```

Creá `logs/` antes si usás esa ruta:

```bash
mkdir -p logs
```

Si `proceso.py` se interrumpe, PostgreSQL libera el lock cuando se cierra la conexión. La siguiente ejecución puede retomar: los scripts hijos son idempotentes/retomables para el flujo normal y mantienen sus propios locks como defensa adicional.

## Fuentes y anonimización

La DB interna conserva los nombres reales de las fuentes en las tablas raw y de agregados. La web pública nunca los muestra.

El pipeline crea y mantiene una tabla `radar_source_aliases` que asigna aliases estables del tipo `Fuente 1`, `Fuente 2`, etc. Cada nombre real de fuente recibe un número la primera vez que aparece, y ese número se mantiene estable en todos los meses.

Regla del proyecto:

```text
DB / procesamiento interno → fuente real
UI / salida para usuario   → Fuente N (alias estable)
```

La asignación corre automáticamente dentro de `scripts/build_monthly_aggregates.py`. Las fuentes nuevas reciben el siguiente número disponible.

## Sync de noticias

El script principal es:

```bash
python scripts/sync_trh_raw_to_radar.py
```

### Full sync

```bash
python scripts/sync_trh_raw_to_radar.py --full
```

Copia todas las noticias raw válidas desde TRH hacia Radar.

### Sync incremental / cron

```bash
python scripts/sync_trh_raw_to_radar.py --lookback-hours 48
```

Condición incremental:

```sql
fecha_extraccion >= NOW() - INTERVAL '48 hours'
AND embedding IS NOT NULL
```

La variable equivalente es:

```env
RADAR_SYNC_LOOKBACK_HOURS=48
```

## Procesamiento de períodos afectados

Después del sync, Radar detecta qué meses deben recalcularse.

| Comando | Qué hace | Cuándo usarlo |
| --- | --- | --- |
| `python scripts/detect_affected_periods.py --full` | Marca todos los meses con noticias publicadas como pendientes | Primera inicialización o reproceso global |
| `python scripts/detect_affected_periods.py` | Marca meses afectados por noticias sincronizadas recientemente usando `synced_at` | Flujo incremental normal después del sync |
| `python scripts/detect_affected_periods.py --from-extraction-date` | Marca meses afectados usando `fecha_extraccion` reciente | Cuando querés seguir explícitamente la fecha TRH |

Primera inicialización recomendada:

```bash
python scripts/detect_affected_periods.py --full
```

Flujo incremental recomendado después del cron de sync:

```bash
python scripts/detect_affected_periods.py
```

## Keywords

Radar combina tres fuentes:

1. `config/keyword_dictionary.yml` — keywords canónicas, aliases editables y lista de omisión.
2. spaCy `es_core_news_lg` — entidades en español.
3. YAKE — frases clave en español.

La lista `omitted_keywords` sirve para descartar ruido de sitios y llamadas a la acción, por ejemplo `click`, `unirte al`, `leer más` o `compartir`. Esta lista actúa en procesamiento: las keywords omitidas no deben generarse ni quedar guardadas en `radar_news_keywords`.

Si se edita esta lista, para limpiar un mes ya procesado alcanza con correr extracción de ese período y reconstruir agregados:

```bash
python scripts/extract_keywords.py --period 2026-05
python scripts/build_monthly_aggregates.py --period 2026-05
```

Usá `--reset-period` solo si además querés recalcular todas las keywords del mes desde cero.

Opciones importantes:

| Comando | Qué procesa | Cuándo usarlo |
| --- | --- | --- |
| `python scripts/extract_keywords.py` | Períodos `pending` y `processing` en `radar_affected_periods` | Flujo normal y reanudación después de detectar períodos |
| `python scripts/extract_keywords.py --full --reset-period` | Todos los meses con noticias, borrando keywords/stats previas de cada período | Primera corrida completa o cambio grande del diccionario |
| `python scripts/extract_keywords.py --period 2025-05 --reset-period` | Un mes específico | Corrección o reproceso puntual |
| `python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20` | Hasta 20 noticias de un mes | Smoke test inicial |

Importante: sin argumentos, `extract_keywords.py` **no significa full por sí mismo**. Procesa períodos `pending` y también períodos que quedaron en `processing` por una interrupción previa. Si antes corriste `detect_affected_periods.py --full`, entonces todos los meses quedan pendientes y ese comando puede terminar procesando todo.

Para corridas largas, el extractor guarda avance cada 10 noticias por defecto:

```bash
python scripts/extract_keywords.py --commit-every 10
```

Si se corta el proceso, volvé a ejecutar el mismo comando sin `--reset-period`; salta noticias marcadas como `completed` en `radar_news_keyword_processing`, incluso si produjeron cero keywords, y continúa con lo restante. Para incluir períodos marcados como `failed`:

```bash
python scripts/extract_keywords.py --retry-failed
```

Primera prueba recomendada:

```bash
python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20
```

Primera corrida completa recomendada después del smoke test:

```bash
python scripts/extract_keywords.py
```

Reproceso global por cambio de diccionario:

```bash
python scripts/extract_keywords.py --full --reset-period
```

## Agregados mensuales MVP

Después de keywords, construí los agregados listos para la Home/API:

```bash
python scripts/build_monthly_aggregates.py
```

Opciones:

| Comando | Qué procesa | Cuándo usarlo |
| --- | --- | --- |
| `python scripts/build_monthly_aggregates.py` | Períodos afectados con estado `completed` | Flujo normal después de keywords |
| `python scripts/build_monthly_aggregates.py --period 2025-05` | Un mes específico | Reproceso puntual |
| `python scripts/build_monthly_aggregates.py --full` | Todos los meses con noticias | Primera inicialización o reconstrucción global |
| `python scripts/build_monthly_aggregates.py --include-processing` | Incluye períodos `processing` además de `completed` | Uso excepcional si querés agregados parciales |

Tablas generadas:

- `radar_monthly_overview`
- `radar_daily_activity`
- `radar_source_monthly_stats`
- `radar_source_keyword_stats`

Además, `build_monthly_aggregates.py` mantiene `radar_source_aliases` para que los aliases de fuente sean estables en la web.

## Diccionario canónico

El archivo editable es:

```text
config/keyword_dictionary.yml
```

Usalo para normalizar nombres, lugares, instituciones y temas locales. Ejemplo conceptual:

```yaml
- canonical: "Transporte público"
  aliases:
    - "colectivos"
    - "servicio de colectivos"
```

Si cambiás este archivo, conviene reprocesar todo:

```bash
python scripts/extract_keywords.py --full --reset-period
```

## Estructura del proyecto

```text
db/
  schema.sql                    # schema completo y definitivo
  000_create_database.sql       # referencia: crear base (no migración)
  001_create_radar_raw.sql
  002_create_processing_tables.sql
  003_create_keywords_tables.sql
  004_create_keyword_processing_state.sql
  005_create_monthly_aggregates.sql
  006_alter_affected_periods_add_consumed.sql
  007_create_source_aliases.sql

scripts/
  sync_trh_raw_to_radar.py
  detect_affected_periods.py
  extract_keywords.py
  build_monthly_aggregates.py
  proceso.py
  radar_common.py

web/
  SvelteKit v0.1
  src/routes/+page.server.ts
  src/routes/tema/[keyword]/+page.server.ts

config/
  keyword_dictionary.yml

tests/
  pytest suite

.env
.env.example
README.md
PLAN.md
requirements.txt
```

## Tests

El proyecto usa `pytest`. Para correr todos los tests:

```bash
python -m pytest tests/ -v
```

## Próximos pasos

- Ajustar `config/keyword_dictionary.yml` con keywords locales reales.
- Diseñar generación de clusters por mes usando embeddings.
- Iterar la UI/UX pública sobre los agregados MVP.
- Agregar CI en el momento que el equipo lo priorice.

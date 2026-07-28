# Radar TRH — Observatorio visual de agenda mediática

Radar TRH es un proyecto derivado de TRH que usa la base histórica de más de 50.000 noticias para mostrar, de forma visual y navegable, de qué se habla, de qué se habló y cómo cambia la agenda mediática con el tiempo.

La idea no es crear otro panel editorial, sino una experiencia pública/analítica: una página donde una persona pueda entender en pocos segundos qué temas dominaron un mes, qué medios cubrieron cada tema y cómo evolucionó la conversación.

## Decisión central

Construir un **observatorio mensual de agenda mediática** basado en:

- noticias históricas;
- fuentes;
- fechas de publicación;
- keywords;
- clusters;
- embeddings;
- categorías;
- métricas de tendencia.

Nombre recomendado: **Radar TRH**.

---

## Objetivo del producto

Responder preguntas como:

- ¿De qué se habló este mes?
- ¿Qué temas crecieron respecto al mes anterior?
- ¿Qué temas desaparecieron?
- ¿Qué medios hablaron más de cada tema?
- ¿Qué noticias representan mejor cada conversación?
- ¿Cómo se conecta un tema con otros temas similares?

---

## Público posible

| Usuario | Qué obtiene |
|---|---|
| Lector general | Un resumen visual de la agenda del mes. |
| Periodista/editor | Tendencias, cobertura por fuente y temas emergentes. |
| Investigador | Archivo histórico navegable por tema, fuente y período. |
| Medio local | Una forma de mostrar valor sobre su archivo de noticias. |

---

## MVP recomendado — versión 0.1

Primera versión simple, pero con impacto visual.

### Pantallas principales

1. **Home / Pulso del mes**
   - selector de mes;
   - total de noticias del mes;
   - nube de keywords;
   - top temas;
   - evolución diaria;
   - ranking de fuentes;
   - temas emergentes.

2. **Página de tema / keyword**
   - cantidad de noticias del tema;
   - evolución por día o semana;
   - fuentes que más lo cubrieron;
   - noticias representativas;
   - keywords relacionadas.

3. **Explorador mensual**
   - navegación por mes;
   - resumen de actividad;
   - comparación básica con mes anterior.

### Qué debe poder hacer el usuario

- Elegir un mes.
- Ver los temas más importantes.
- Hacer click en una keyword.
- Ver noticias relacionadas.
- Comparar actividad por fuente.

---

## Features por etapa

### v0.1 — Pulso mensual

Prioridad alta.

- Selector de mes.
- Total de noticias.
- Nube de keywords ponderada.
- Top 10 temas.
- Gráfico de noticias por día.
- Ranking de fuentes.
- Click en keyword para ver noticias.

Objetivo: que alguien entienda en 30 segundos la agenda del mes.

---

### v0.2 — Tendencias y comparación

- Comparación mes actual vs mes anterior.
- Temas emergentes.
- Temas en caída.
- Heatmap fuente × tema.
- Categorías dominantes.
- Resumen automático mensual con IA.

Ejemplo de salida:

> En mayo, la agenda estuvo marcada por seguridad, política provincial y educación. Seguridad tuvo picos los días 8, 14 y 22, mientras que turismo creció hacia fin de mes.

---

### v0.3 — Mapa semántico

Feature estrella.

Usar embeddings para construir un mapa visual de noticias/temas:

- reducción dimensional con UMAP o t-SNE;
- puntos agrupados por similitud;
- color por categoría o fuente;
- click en grupo para ver noticias;
- temas cercanos semánticamente.

Objetivo: mostrar el “mapa del discurso” de un mes.

---

## Datos disponibles desde TRH

La base actual de TRH ya tiene gran parte del valor necesario.

| Dato | Uso en Radar TRH |
|---|---|
| fuente | comparar cobertura por medio |
| título | mostrar noticias representativas |
| fecha_publicacion | agrupar por día, semana, mes |
| texto_completo | extracción/refuerzo de keywords |
| url_original | enlace a fuente original |
| url_imagen | previews visuales |
| embedding | similitud semántica y mapa 2D |
| noticia_hash | control de duplicados |
| cluster_id | agrupación de eventos relacionados |
| keywords | nube, rankings y navegación temática |

---

## Arquitectura sugerida

No modificar TRH directamente al principio.

Crear un proyecto separado:

```text
trh-radar/
```

Con conexión **read-only** a la base de datos de TRH.

### Capas

```text
DB TRH
  ↓
Agregaciones Radar
  ↓
API / backend liviano
  ↓
Frontend visual
```

### Agregaciones propias

Radar debería calcular y cachear:

- keywords por mes;
- cantidad de noticias por fuente y mes;
- ranking de temas;
- evolución diaria por keyword;
- temas emergentes;
- temas en caída;
- clusters destacados;
- relaciones semánticas por embedding.

---

## Modelo de datos inicial

Se puede empezar sin crear muchas tablas nuevas, pero conviene tener tablas/materializaciones de resumen.

### Posibles vistas o tablas agregadas

| Nombre | Propósito |
|---|---|
| `radar_monthly_topic_stats` | métricas por mes y keyword/tema |
| `radar_source_topic_stats` | cobertura por fuente y tema |
| `radar_daily_topic_stats` | evolución diaria de cada tema |
| `radar_featured_clusters` | clusters representativos por mes |
| `radar_topic_embeddings_2d` | coordenadas para mapa semántico |

---

## Visualizaciones recomendadas

| Visualización | Valor |
|---|---|
| Nube de tags ponderada | impacto inicial rápido |
| Barras top temas | lectura clara |
| Línea temporal diaria | muestra picos de cobertura |
| Ranking de fuentes | compara volumen |
| Heatmap fuente × tema | muestra sesgo o foco editorial |
| Mapa semántico 2D | feature diferencial |
| Cards de clusters | conecta datos con noticias concretas |

---

## Principios de diseño

1. **Primero claridad, después complejidad.**
2. **Cada gráfico debe responder una pregunta concreta.**
3. **La nube de tags no debe ser decoración; debe ser navegable.**
4. **El mes es la unidad principal de navegación.**
5. **Los embeddings se usan para descubrir relaciones, no para reemplazar métricas simples.**
6. **La base de TRH debe usarse en modo lectura al principio.**

---

## Qué no hacer al inicio

Evitar en la primera versión:

- dashboard gigante con demasiados gráficos;
- login/admin;
- edición editorial;
- publicación automática;
- mapas 3D;
- demasiados filtros;
- dependencia fuerte de IA para todo;
- tocar el pipeline central de TRH.

---

## Primera entrega recomendada

### Alcance

Una página funcional con:

- selector de mes;
- nube de keywords;
- top temas;
- gráfico diario;
- ranking de fuentes;
- detalle simple de keyword.

### Criterio de éxito

Una persona entra y entiende:

- de qué se habló ese mes;
- qué temas dominaron;
- qué medios participaron;
- qué noticias representan esos temas.

---

## Próximos pasos

1. Definir stack técnico.
2. Confirmar acceso read-only a la DB de TRH.
3. Inspeccionar esquema real de keywords, clusters y noticias.
4. Diseñar consultas SQL para métricas mensuales.
5. Crear wireframe de Home / Pulso del mes.
6. Implementar MVP v0.1.

---

## Preguntas abiertas

- ¿Radar TRH será público o interno primero?
- ¿Debe mostrar enlaces a las fuentes originales?
- ¿Debe usar marca TRH o una identidad separada?
- ¿El foco es Santiago/región o agenda general de medios?
- ¿Conviene generar un resumen mensual con IA desde el MVP o dejarlo para v0.2?
- ¿Se usará la misma base en vivo o una réplica/snapshot?

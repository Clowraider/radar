# Radar web

App web v0.1 de **Radar**. Muestra el Pulso mensual público usando los agregados ya calculados en PostgreSQL.

> Importante: acá **no hay `app.py`**. Esta parte no es FastAPI ni Flask. Es una app **SvelteKit/Node.js**. Se ejecuta con `npm run dev` en desarrollo o con `node build` en producción.

## Estado v0.1

**Radar web v0.1 está funcionalmente completa.**

Incluye:

- selector de mes;
- total de noticias del mes;
- keywords / temas principales clickeables;
- actividad diaria visible;
- ranking de fuentes con aliases públicos (`Fuente 1`, `Fuente 2`, ...);
- detalle de tema en `/tema/[keyword]?month=YYYY-MM`;
- actividad diaria del tema;
- cobertura del tema por fuentes alias;
- noticias relacionadas con título enlazado a la URL original;
- filtro de noticias por fuente alias;
- orden de noticias por más representativas o más recientes;
- footer público;
- página 404/error personalizada.

La base de datos conserva los nombres reales de las fuentes. La web solo debe mostrar aliases al público. En el detalle de tema, las noticias relacionadas se muestran como títulos enlazados a la URL original; no se renderiza el nombre real de la fuente como texto y no se cargan imágenes externas de los sitios fuente.

## Stack

- SvelteKit + TypeScript;
- Tailwind CSS;
- `@sveltejs/adapter-node`;
- PostgreSQL usando `pg`;
- sin FastAPI;
- sin nginx/Caddy obligatorio.

## Variables de entorno

Copiá el ejemplo:

```bash
cd web
cp radar-web.env.example radar-web.env
```

Después editá `radar-web.env`.

Tenés dos formas de configurar la conexión a DB.

### Opción A — Una sola URL

```env
DATABASE_URL=postgresql://usuario:clave@host:5432/radar_trh
```

Usá esta si preferís una sola línea.

### Opción B — Variables separadas

```env
RADAR_DB_HOST=127.0.0.1
RADAR_DB_PORT=5432
RADAR_DB_NAME=radar_trh
RADAR_DB_USER=radar_user
RADAR_DB_PASSWORD=change-me
RADAR_DB_POOL_MAX=10
```

Significado:

| Variable | Qué es |
| --- | --- |
| `RADAR_DB_HOST` | Host/IP donde está PostgreSQL. Si corre en el mismo LXC, suele ser `127.0.0.1`. |
| `RADAR_DB_PORT` | Puerto de PostgreSQL. Normalmente `5432`. |
| `RADAR_DB_NAME` | Nombre de la base Radar. En este proyecto: `radar_trh`. |
| `RADAR_DB_USER` | Usuario de PostgreSQL que leerá las tablas Radar. Idealmente read-only. |
| `RADAR_DB_PASSWORD` | Clave de ese usuario. No la subas al repo. |
| `RADAR_DB_POOL_MAX` | Máximo de conexiones abiertas por la app. `10` está bien para arrancar. |

### Puerto de la app

```env
HOST=0.0.0.0
PORT=3000
```

| Variable | Qué es |
| --- | --- |
| `HOST` | IP donde escucha la app. En LXC conviene `0.0.0.0`. |
| `PORT` | Puerto HTTP de Radar. Ejemplo: `3000`. |

## Ejecutar en desarrollo

```bash
cd web
npm install
npm run dev
```

Abrí la URL que imprime Vite. Si estás entrando desde otra máquina al LXC, probá:

```text
http://IP_DEL_LXC:5173
```

## Ejecutar como producción simple

```bash
cd web
npm install
npm run build
HOST=0.0.0.0 PORT=3000 node build
```

Después abrí:

```text
http://IP_DEL_LXC:3000
```

## Ejecutar con systemd en el LXC

`radar-web.service.example` es una **plantilla para Linux/systemd**. No es código de la app.

Sirve para que el LXC mantenga Radar encendido como servicio:

- arranca solo cuando prende el LXC;
- reinicia si se cae;
- se controla con `systemctl`;
- los logs se ven con `journalctl`.

Si solo querés probar la app, **no necesitás usar systemd**. Usá esto:

```bash
cd web
npm run dev
```

O producción manual:

```bash
cd web
npm run build
HOST=0.0.0.0 PORT=3000 node build
```

Usá `radar-web.service.example` recién cuando quieras dejarla funcionando permanente en el LXC.

Pasos típicos:

```bash
sudo mkdir -p /opt/radar
sudo cp -r web /opt/radar/web
cd /opt/radar/web
sudo cp radar-web.env.example radar-web.env
sudo nano radar-web.env
npm install
npm run build
sudo cp radar-web.service.example /etc/systemd/system/radar-web.service
sudo nano /etc/systemd/system/radar-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now radar-web
```

En el `sudo nano /etc/systemd/system/radar-web.service`, revisá especialmente:

```ini
User=radar
Group=radar
WorkingDirectory=/opt/radar/web
EnvironmentFile=/opt/radar/web/radar-web.env
ExecStart=/usr/bin/node build
```

Si tu usuario Linux no se llama `radar`, cambiá `User=` y `Group=`.

También verificá que el archivo termine con esta sección. Sin `[Install]`, `systemctl enable --now radar-web` falla porque systemd no sabe cómo habilitar el servicio al arranque:

```ini
[Install]
WantedBy=multi-user.target
```

Si `ExecStart=/usr/bin/node build` no funciona, confirmá la ruta de Node:

```bash
which node
```

y reemplazá `/usr/bin/node` por esa ruta.

Ver estado:

```bash
sudo systemctl status radar-web
```

Ver logs:

```bash
sudo journalctl -u radar-web -f
```

Reiniciar después de cambios:

```bash
sudo systemctl restart radar-web
```

Confirmar que arranca con el LXC:

```bash
systemctl is-enabled radar-web
```

Debe responder:

```text
enabled
```

## Comandos importantes

| Comando | Para qué sirve |
| --- | --- |
| `npm run dev` | Desarrollo con recarga automática. |
| `npm run build` | Compila la app para producción. |
| `node build` | Ejecuta la versión compilada. |
| `npm run start` | Ejecuta `node build` usando `HOST`/`PORT` por defecto. |

## Checklist v0.1

Estado validado: v0.1 fue probada en un LXC Ubuntu y quedó online usando producción Node/SvelteKit.

Antes de dar una instalación por lista:

- [ ] `npm install` ejecutado en `web/`.
- [ ] `npm run build` termina sin errores.
- [ ] La app levanta con `HOST=0.0.0.0 PORT=3000 node build`.
- [ ] Home carga rápido en PC, tablet y móvil.
- [ ] Selector de mes funciona.
- [ ] Keywords abren `/tema/[keyword]?month=YYYY-MM`.
- [ ] Página de tema muestra noticias relacionadas.
- [ ] Filtro por `Fuente N` funciona.
- [ ] Orden por representativas/recientes funciona.
- [ ] Rankings y métricas muestran aliases, no nombres reales de fuentes.
- [ ] No se cargan imágenes externas de sitios fuente.
- [ ] Links a noticias originales abren en pestaña nueva.
- [ ] Footer visible: `Powered by Sebastian Bergmann · ConectadIA.com © 2026`.
- [ ] Ruta inexistente muestra la página 404 personalizada.

## Notas

- No edites ni subas `radar-web.env` con credenciales reales.
- La app intenta cargar `web/radar-web.env`, luego `web/.env`, y luego el `.env` del proyecto padre.
- Para producción conviene un usuario PostgreSQL de solo lectura sobre las tablas que consume la web.

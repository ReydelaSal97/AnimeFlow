# AnimeFlow

Directorio de anime con frontend responsivo en modo oscuro, base de datos en
Supabase Cloud y un pipeline en Python que sincroniza metadatos desde la
**API pública Jikan v4** (MyAnimeList).

```
animeflow/
├── INICIAR-ANIMEFLOW.bat   ← Windows: doble clic y la web se abre sola
├── SINCRONIZAR-HOY.bat     ← Windows: actualización diaria programable
├── frontend/
│   ├── index.html          ← toda la web (HTML + Tailwind + JS vanilla, sin build)
│   ├── demo-player.html    ← reproductor de marcador para el modo demo
│   └── mock-data.json      ← dataset de ejemplo (se genera con generar_mock.py)
├── backend/
│   ├── sync_anime_supabase.py   ← CLI del pipeline
│   ├── jikan_client.py          ← cliente Jikan (rate limit, backoff, caché, traducciones)
│   ├── generar_mock.py          ← genera el JSON de demostración
│   ├── configurar_frontend.py   ← escribe las credenciales en index.html
│   ├── requirements.txt
│   └── .env.example
├── db/
│   └── schema.sql          ← ejecutar en el SQL Editor de Supabase
└── docs/
    └── ejemplo-consumo.md  ← forma exacta de cada respuesta JSON
```

---

## Windows: doble clic y listo

```
INICIAR-ANIMEFLOW.bat      ← empieza por aquí
SINCRONIZAR-HOY.bat        ← actualización diaria (Programador de tareas)
```

`INICIAR-ANIMEFLOW.bat` comprueba Python, genera los datos de demostración si
faltan, busca un puerto libre entre el 8000 y el 8020, levanta el servidor y
abre la web en el navegador. Después muestra un menú:

| Opción | Qué hace |
|---|---|
| 1 – 2 | Abrir la web · reiniciar el servidor |
| 3 | `pip install -r requirements.txt` |
| 4 | Crear y editar `backend\.env` (clave **service_role**) |
| 5 | Escribir la URL y la clave **anon** dentro de `index.html` |
| 6 | Carga inicial desde Jikan (`init`) |
| 7 | Actualizar «Capítulos de hoy» (`sync-today`) |
| 8 | Añadir un anime buscando por título |
| 9 – 10 | Regenerar datos demo · volver al modo demo |
| 0 | Detener el servidor y salir |

La opción 5 rechaza la clave `service_role` si la pegas por error: leería el
rol dentro del JWT y avisaría, porque esa clave en el navegador da acceso total
a la base de datos a cualquiera que mire el código fuente.

**Actualización diaria automática** — Programador de tareas → Crear tarea
básica → Diariamente 06:00 → Iniciar un programa → ruta de `SINCRONIZAR-HOY.bat`.

> Si Windows SmartScreen avisa al abrir el `.bat`: *Más información → Ejecutar
> de todas formas*. Es un archivo de texto sin firmar, puedes leerlo con el
> Bloc de notas antes de ejecutarlo.

---

## Puesta en marcha manual (macOS / Linux, o si prefieres la terminal)

### 1 · Ver la web ya mismo (modo demo, sin base de datos)

```bash
cd frontend
python3 -m http.server 8000
# abre http://localhost:8000
```

Sin credenciales de Supabase, el frontend lee `mock-data.json` y muestra un
aviso ámbar en la parte superior. Todo funciona: filtros, buscador, favoritos,
historial, reproductor y calendario.

### 2 · Crear la base de datos

1. Crea un proyecto en [supabase.com](https://supabase.com) (plan gratuito sirve).
2. Ve a **SQL Editor → New query**, pega el contenido de `db/schema.sql` y pulsa **Run**.

Eso crea las tablas `animes`, `episodios`, `servidores`, `emisiones_hoy`,
`generos` y `reportes`, más las vistas `v_catalogo`, `v_emisiones_hoy`,
`v_ultimos_episodios`, las funciones RPC (`buscar_animes`, `reportar_enlace`,
`incrementar_vistas`), los índices GIN/trigram y las políticas RLS
(lectura pública, escritura sólo con `service_role`).

### 3 · Poblar con datos reales

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # rellena SUPABASE_URL y SUPABASE_SERVICE_KEY

python sync_anime_supabase.py init        # carga inicial completa
```

Comandos disponibles:

| Comando | Qué hace |
|---|---|
| `init` | Carga inicial: temporada actual + top en emisión + agenda de hoy |
| `sync-season` | Temporada en curso (`/seasons/now`) |
| `sync-season --anio 2024 --estacion fall` | Una temporada concreta |
| `sync-today` | Regenera «Capítulos del Día» desde `/schedules` |
| `sync-id 52991 --episodios` | Un anime por MAL ID, con su lista de episodios |
| `sync-title "Frieren" --limite 3` | Búsqueda por título |
| `sync-top --filtro airing --destacar` | Top de MAL; `--destacar` alimenta el Hero Banner |
| `export-json --salida ../frontend/mock-data.json` | Vuelca el catálogo a JSON |

Modificadores globales: `--dry-run` (no escribe nada), `--sin-cache`,
`--intervalo 1.0`, `-v`.

**Automatización con cron:**

```cron
0 6 * * *   cd /ruta/backend && python sync_anime_supabase.py sync-today  >> sync.log 2>&1
0 4 * * 1   cd /ruta/backend && python sync_anime_supabase.py sync-season >> sync.log 2>&1
```

### 4 · Conectar el frontend

En `frontend/index.html`, bloque `CONFIG` (arriba del `<script>` principal):

```js
const CONFIG = {
  SUPABASE_URL:      'https://TU-PROYECTO.supabase.co',
  SUPABASE_ANON_KEY: 'eyJhbGciOi…',   // clave anon public, NUNCA la service_role
  MOCK_URL:          'mock-data.json',
  PAGINA: 24
};
```

El aviso de modo demo desaparece solo. Publícalo en Netlify, Vercel, Cloudflare
Pages o GitHub Pages arrastrando la carpeta `frontend/` — es estático.

---

## Cargar los enlaces de los servidores

Jikan aporta metadatos, **no** enlaces de vídeo. Los `embed_url` los cargas tú
en la tabla `servidores`:

```sql
insert into servidores (episodio_id, nombre, embed_url, audio, calidad, orden)
values
  ('<uuid-del-episodio>', 'Servidor 1 - Streamtape', 'https://…/e/XXXX/', 'SUB', 'FHD', 1),
  ('<uuid-del-episodio>', 'Servidor 2 - Mega',       'https://mega.nz/embed/XXXX', 'SUB', 'HD', 2);
```

El frontend genera automáticamente una pestaña por cada fila activa, recuerda
el servidor preferido del usuario y ofrece el botón de reporte.

> ⚠️ Indexa únicamente enlaces cuya distribución esté autorizada. El aviso legal
> del pie describe la naturaleza de la plataforma como índice, pero la
> responsabilidad sobre qué enlaces se cargan es de quien opera el sitio.

---

## Qué incluye el frontend

**Requisitos del enunciado**

- Modo oscuro `#0f0f13` / `#18181c` con acentos neón y navbar sticky con buscador, enlaces y menú de géneros.
- Grids responsivas con hover (zoom, calidad, audio, episodio actual, sinopsis).
- Hero banner con carrusel automático de los 5 destacados.
- Módulo «Capítulos de hoy» con hora local, episodio esperado/subido y estado de emisión.
- Directorio con filtros de género, año, temporada, estado, tipo y ordenamiento + paginación.
- Ficha técnica con portada, títulos, sinopsis, tags cliqueables, ficha de datos, tráiler y episodios agrupados en bloques de 12.
- Reproductor con pestañas de servidores, iframe responsive 16:9 y navegación Anterior / Lista / Siguiente.
- Buscador con autocompletado instantáneo (miniatura + título + metadatos).
- Favoritos e historial en LocalStorage, sin login.
- Botón de reportar enlace caído con motivos y comentario.
- Aviso legal en el footer.

**Mejoras añadidas (punto 5)**

1. **Continuar viendo** — fila con miniaturas y barra de progreso reconstruida desde el historial local; el botón «Ver ahora» retoma el último episodio en vez de empezar de cero.
2. **Progreso sobre la portada** — cada tarjeta del catálogo dibuja una barra fina con el porcentaje visto de la serie.
3. **Calendario semanal completo** — vista de 7 columnas con el día actual resaltado, más allá de las emisiones de hoy.
4. **Color de acento configurable** — 5 paletas (violeta, cian, azul, rosa, verde) mediante variables CSS; se guarda en LocalStorage.
5. **Modo cine** — atenúa navbar, footer e info alrededor del reproductor con la tecla `C`.
6. **Atajos de teclado** — `/` enfoca el buscador, `Esc` cierra modales, `←` `→` cambian de episodio, `R` abre un anime aleatorio.
7. **Botón aleatorio** — descubrimiento tipo ruleta para cuando no sabes qué ver.
8. **Exportar / importar Mi Lista** — descarga un `.json` con favoritos, historial y preferencias para migrar de navegador o dispositivo.
9. **Búsqueda tolerante a errores** — RPC con `pg_trgm` + `unaccent`: «frier», «atake a los titanes» o «shingeki» encuentran el mismo título.
10. **Skeleton loaders** en cada vista, en lugar de pantallas en blanco.
11. **Compartir nativo** — `navigator.share` en móvil, copiado al portapapeles en escritorio.
12. **URLs con estado** — los filtros del directorio viven en el hash, así que una búsqueda filtrada es enlazable y sobrevive al recargar.
13. **Autodesactivación de servidores caídos** — al acumular 15 reportes el servidor deja de mostrarse, sin intervención manual.
14. **Realtime opcional** — `episodios` y `emisiones_hoy` publicados en `supabase_realtime` para avisar de estrenos sin recargar.
15. **Degradación elegante** — sin credenciales el sitio funciona con datos de ejemplo; sin servidores para un episodio, el reproductor explica qué falta en vez de mostrar un iframe roto.

---

## Detalles del pipeline

- **Rate limiting**: 0,75 s entre peticiones (Jikan permite 3 req/s y 60 req/min).
- **Backoff exponencial** ante `429`, `5xx` y caídas de red, hasta 5 reintentos.
- **Caché en disco** de 12 h en `.jikan_cache/` para no machacar la API mientras desarrollas.
- **Traducción al español** de estados, estaciones, días, géneros, temas, demografías y fuentes.
- **Upsert por lotes** de 50 filas usando `mal_id` como clave de conflicto — reejecutable sin duplicar.
- **Estimación de episodio en emisión** por semanas transcurridas desde `fecha_estreno`, acotada al total.
- **Conversión horaria** de JST (UTC+9) a la zona de `TZ_OFFSET_HORAS`.

---

## Verificación realizada

- Normalización Jikan → Supabase probada contra un payload real (estado, estación, día, géneros, tema, demografía, fuente, slug, limpieza de sinopsis, conversión horaria y caso de anime sin datos).
- Frontend renderizado en Chromium (1440×900 y 390×844) sobre las 6 vistas: inicio, directorio con filtros, calendario, ficha, reproductor y favoritos. Sin errores de consola.
- Flujos interactivos verificados: buscador incremental, alta en Mi Lista con badge, filtro por género + orden A-Z, cambio de paleta y navegación entre episodios.

---

## Aviso legal

AnimeFlow es un **índice de enlaces embebidos alojados en servidores de
terceros**. No aloja, almacena ni transmite archivos de vídeo. Los metadatos
provienen de la API pública Jikan (MyAnimeList) y los derechos de títulos,
imágenes y obras pertenecen a sus respectivos propietarios.

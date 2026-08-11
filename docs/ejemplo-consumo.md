# Ejemplo de consumo: frontend ↔ Supabase

Cómo el `index.html` pide los datos y qué forma exacta tiene la respuesta.
El objeto `DB` del frontend implementa cada uno de estos métodos, así que si
cambias el esquema sólo tienes que tocar ese módulo.

---

## 0. Inicializar el cliente

```js
const SB = supabase.createClient(
  'https://TU-PROYECTO.supabase.co',
  'eyJhbGciOi...'          // clave anon public (nunca la service_role)
);
```

---

## 1. Hero Banner — animes destacados

```js
const { data } = await SB
  .from('animes')
  .select('*')
  .eq('destacado', true)
  .limit(5);
```

**Respuesta esperada**

```json
[
  {
    "id": "9f1c4b2e-77aa-4c31-9a1b-4d0a6f2ce881",
    "mal_id": 52991,
    "slug": "sousou-no-frieren",
    "titulo": "Sousou no Frieren",
    "titulo_espanol": "Frieren: Más allá del final del viaje",
    "titulo_japones": "葬送のフリーレン",
    "titulos_alt": ["Frieren at the Funeral"],
    "sinopsis": "Tras derrotar al Rey Demonio, la maga elfa Frieren…",
    "portada": "https://cdn.myanimelist.net/images/anime/1015/138006l.jpg",
    "portada_webp": "https://cdn.myanimelist.net/images/anime/1015/138006l.webp",
    "banner": "https://img.youtube.com/vi/qgUplyQ2ZOI/maxresdefault.jpg",
    "trailer_url": "https://www.youtube.com/embed/qgUplyQ2ZOI",
    "generos": ["Aventura", "Drama", "Fantasía"],
    "temas": ["Mitología"],
    "demografia": ["Shonen"],
    "estudio": "Madhouse",
    "estudios": ["Madhouse"],
    "fuente": "Manga",
    "estado": "Finalizado",
    "tipo": "TV",
    "clasificacion": "PG-13 - Teens 13 or older",
    "puntuacion": 9.31,
    "miembros": 1050000,
    "ranking": 1,
    "popularidad": 120,
    "episodios_total": 28,
    "duracion": "24 min per ep",
    "anio": 2023,
    "estacion": "Otoño",
    "fecha_estreno": "2023-09-29",
    "fecha_fin": "2024-03-22",
    "dia_emision": "viernes",
    "hora_emision": "23:00:00",
    "audio": "SUB",
    "calidad": "FHD",
    "destacado": true,
    "vistas": 184023,
    "activo": true
  }
]
```

---

## 2. Directorio con filtros combinados

Usa la vista `v_catalogo`, que ya trae `ultimo_episodio` calculado (evita el
problema N+1 de pedir los episodios de cada portada del grid).

```js
let q = SB.from('v_catalogo').select('*', { count: 'exact' });

q = q.contains('generos', ['Isekai']);          // array ⊇ ['Isekai']
q = q.eq('estado', 'En emisión');
q = q.eq('anio', 2026).eq('estacion', 'Verano');
q = q.order('puntuacion', { ascending: false, nullsFirst: false });

const { data, count } = await q.range(0, 23);   // paginación de 24 en 24
```

**Respuesta esperada**

```json
{
  "count": 87,
  "data": [
    {
      "id": "3c8e...", "mal_id": 58567, "slug": "kaiju-no-8",
      "titulo": "Kaiju No. 8", "titulo_espanol": "Kaiju No. 8",
      "portada": "https://cdn.myanimelist.net/images/anime/1370/140362l.jpg",
      "generos": ["Acción", "Sci-Fi"], "temas": ["Superpoderes"],
      "estado": "En emisión", "tipo": "TV", "puntuacion": 8.24,
      "episodios_total": 12, "anio": 2026, "estacion": "Verano",
      "audio": "SUB", "calidad": "FHD", "dia_emision": "lunes",
      "ultimo_episodio": 7,
      "episodios_disponibles": 7
    }
  ]
}
```

---

## 3. Módulo «Capítulos del Día»

```js
const { data } = await SB.from('v_emisiones_hoy').select('*');
```

**Respuesta esperada**

```json
[
  {
    "id": "b21f...",
    "anime_id": "3c8e...",
    "mal_id": 58567,
    "titulo": "Kaiju No. 8",
    "portada": "https://cdn.myanimelist.net/images/anime/1370/140362l.jpg",
    "slug": "kaiju-no-8",
    "dia": "lunes",
    "hora_emision": "23:00:00",
    "hora_local": "09:00",
    "episodio_esperado": 8,
    "episodio_subido": 7,
    "estado_emision": "Emitido",
    "fecha_snapshot": "2026-08-10",
    "generos": ["Acción", "Sci-Fi"],
    "puntuacion": 8.24,
    "estado": "En emisión"
  }
]
```

> `estado_emision` toma uno de: `Programado` · `Emitido` · `Subtitulado` · `Retrasado`.
> El script de Python lo calcula comparando `episodio_esperado` (semanas desde el
> estreno) con `episodio_subido` (máximo real en la tabla `episodios`).

---

## 4. Ficha técnica + episodios

```js
const { data: anime } = await SB
  .from('animes').select('*').eq('slug', 'kaiju-no-8').single();

const { data: episodios } = await SB
  .from('episodios').select('*')
  .eq('anime_id', anime.id).eq('publicado', true)
  .order('numero');
```

**Respuesta de `episodios`**

```json
[
  {
    "id": "e1a0...", "anime_id": "3c8e...", "numero": 1, "temporada": 1,
    "titulo": "El hombre que se convirtió en kaiju",
    "miniatura": null, "duracion_seg": 1440, "audio": "SUB",
    "fecha_emision": "2026-07-06T14:00:00+00:00",
    "filler": false, "recap": false, "vistas": 12043, "publicado": true
  }
]
```

---

## 5. Servidores del reproductor (pestañas)

```js
const { data: servidores } = await SB
  .from('servidores').select('*')
  .eq('episodio_id', episodio.id)
  .eq('activo', true)
  .order('orden');
```

**Respuesta esperada**

```json
[
  { "id": "s1...", "episodio_id": "e1a0...", "nombre": "Servidor 1 - Streamtape",
    "embed_url": "https://streamtape.com/e/XXXXXXXX/", "descarga_url": null,
    "audio": "SUB", "calidad": "FHD", "orden": 1, "activo": true, "reportes": 0 },

  { "id": "s2...", "episodio_id": "e1a0...", "nombre": "Servidor 2 - Mega",
    "embed_url": "https://mega.nz/embed/XXXXXXXX", "audio": "SUB",
    "calidad": "HD", "orden": 2, "activo": true, "reportes": 1 },

  { "id": "s3...", "episodio_id": "e1a0...", "nombre": "Servidor 4 - YourUpload",
    "embed_url": "https://www.yourupload.com/embed/XXXXXXXX", "audio": "DUB",
    "calidad": "HD", "orden": 4, "activo": true, "reportes": 0 }
]
```

El frontend lo pinta como pestañas y monta el iframe:

```html
<iframe src="{{ embed_url }}" allowfullscreen
        allow="autoplay; encrypted-media; picture-in-picture"
        referrerpolicy="origin"
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"></iframe>
```

---

## 6. Buscador en tiempo real (RPC)

```js
const { data } = await SB.rpc('buscar_animes', { q: 'frier', lim: 8 });
```

Tolera errores tipográficos y tildes gracias a `pg_trgm` + `unaccent`.

**Respuesta esperada**

```json
[
  { "id": "9f1c...", "mal_id": 52991, "slug": "sousou-no-frieren",
    "titulo": "Sousou no Frieren", "titulo_espanol": "Frieren: Más allá del final del viaje",
    "portada": "https://cdn.myanimelist.net/images/anime/1015/138006l.jpg",
    "anio": 2023, "tipo": "TV", "puntuacion": 9.31,
    "generos": ["Aventura","Drama","Fantasía"], "score": 0.52 }
]
```

---

## 7. Reportar enlace caído

```js
await SB.rpc('reportar_enlace', {
  p_servidor_id: 's2...',
  p_motivo:      'no_carga',      // no_carga | sin_subs | audio | otro
  p_comentario:  'Error 404 al pulsar play'
});
```

Devuelve `null` si todo fue bien. La función incrementa `servidores.reportes`
y desactiva automáticamente el servidor al llegar a 15 reportes.

---

## 8. Realtime: episodios nuevos sin recargar

```js
SB.channel('nuevos-episodios')
  .on('postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'episodios' },
      payload => toast(`¡Nuevo episodio ${payload.new.numero} disponible!`))
  .subscribe();
```

---

## 9. Contrato de datos locales (LocalStorage)

Sin backend ni login. Claves usadas por el frontend:

```jsonc
// af:favoritos
[{ "mal_id": 52991, "slug": "sousou-no-frieren", "titulo": "…",
   "portada": "…", "generos": ["…"], "puntuacion": 9.31,
   "episodios_total": 28, "agregado": 1754870400000 }]

// af:historial   (máx. 40 entradas, la más reciente primero)
[{ "mal_id": 58567, "slug": "kaiju-no-8", "titulo": "…", "portada": "…",
   "episodio": 7, "total": 12, "segundos": 0, "ts": 1754870400000 }]

// af:prefs
{ "tema": "violeta", "cine": false, "servidor": "Servidor 1 - Streamtape" }
```

El botón **Exportar Mi Lista** del footer genera exactamente esta estructura
envuelta en `{ version, exportado, favoritos, historial, prefs }`, de modo que
el usuario puede migrar sus datos entre navegadores o dispositivos.

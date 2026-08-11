-- ============================================================================
--  AnimeFlow · Esquema de base de datos para Supabase (PostgreSQL)
--  Ejecutar completo en:  Supabase Dashboard → SQL Editor → New query → Run
--  Es idempotente: se puede volver a ejecutar sin romper nada.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. Extensiones
-- ---------------------------------------------------------------------------
create extension if not exists "pg_trgm";      -- búsqueda difusa / autocompletado
create extension if not exists "unaccent";     -- búsquedas sin tildes
create extension if not exists "pgcrypto";     -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- 1. Tipos enumerados
-- ---------------------------------------------------------------------------
do $$ begin
  create type estado_anime as enum ('En emisión', 'Finalizado', 'Próximamente', 'Pausado', 'Cancelado');
exception when duplicate_object then null; end $$;

do $$ begin
  create type estacion_anime as enum ('Invierno', 'Primavera', 'Verano', 'Otoño');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tipo_audio as enum ('SUB', 'DUB', 'RAW');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- 2. Tabla principal: animes
--    mal_id es la clave natural (MyAnimeList) usada para el UPSERT desde Python
-- ---------------------------------------------------------------------------
create table if not exists public.animes (
    id                uuid primary key default gen_random_uuid(),
    mal_id            integer not null unique,          -- ← clave de conflicto para upsert
    slug              text unique,                      -- para URLs bonitas: /anime/frieren
    titulo            text not null,                    -- título principal (romaji)
    titulo_espanol    text,
    titulo_japones    text,
    titulos_alt       text[] default '{}',              -- sinónimos, para el buscador
    sinopsis          text,
    portada           text,                             -- imagen vertical alta resolución
    portada_webp      text,
    banner            text,                             -- imagen horizontal para el hero
    trailer_url       text,                             -- embed de YouTube
    generos           text[] default '{}',              -- desnormalizado: filtros instantáneos
    temas             text[] default '{}',              -- Jikan "themes": Escuela, Mecha, Isekai...
    demografia        text[] default '{}',              -- Shonen, Seinen, Josei, Shojo
    estudio           text,
    estudios          text[] default '{}',
    fuente            text,                             -- Manga, Light novel, Original...
    estado            estado_anime default 'Próximamente',
    tipo              text,                             -- TV, Movie, OVA, ONA, Special
    clasificacion     text,                             -- PG-13, R-17...
    puntuacion        numeric(4,2),                     -- 0.00 - 10.00
    miembros          integer default 0,                -- popularidad (MAL members)
    ranking           integer,
    popularidad       integer,
    episodios_total   integer,
    duracion          text,
    anio              integer,
    estacion          estacion_anime,
    fecha_estreno     date,
    fecha_fin         date,
    dia_emision       text,                             -- 'lunes', 'martes', ... (minúsculas)
    hora_emision      time,                             -- hora JST de emisión
    audio             tipo_audio default 'SUB',
    calidad           text default 'HD',                -- HD, FHD, 4K
    destacado         boolean default false,            -- aparece en el Hero Banner
    vistas            bigint default 0,
    activo            boolean default true,
    creado_en         timestamptz default now(),
    actualizado_en    timestamptz default now()
);

comment on table public.animes is 'Catálogo de metadatos sincronizado desde Jikan API v4 (MyAnimeList).';

-- ---------------------------------------------------------------------------
-- 3. Episodios
-- ---------------------------------------------------------------------------
create table if not exists public.episodios (
    id              uuid primary key default gen_random_uuid(),
    anime_id        uuid not null references public.animes(id) on delete cascade,
    numero          integer not null,
    temporada       integer default 1,
    titulo          text,
    descripcion     text,
    miniatura       text,
    duracion_seg    integer,
    audio           tipo_audio default 'SUB',
    fecha_emision   timestamptz,
    filler          boolean default false,
    recap           boolean default false,
    vistas          bigint default 0,
    publicado       boolean default true,
    creado_en       timestamptz default now(),
    actualizado_en  timestamptz default now(),
    unique (anime_id, temporada, numero)
);

-- ---------------------------------------------------------------------------
-- 4. Servidores (enlaces embebidos externos)
--    IMPORTANTE: aquí sólo se guardan URLs de reproductores de terceros.
--    La plataforma NO aloja archivos de video.
-- ---------------------------------------------------------------------------
create table if not exists public.servidores (
    id              uuid primary key default gen_random_uuid(),
    episodio_id     uuid not null references public.episodios(id) on delete cascade,
    nombre          text not null,                      -- 'Streamtape', 'Mega', 'YourUpload'...
    embed_url       text not null,                      -- URL del iframe
    descarga_url    text,
    audio           tipo_audio default 'SUB',
    calidad         text default 'HD',
    orden           smallint default 1,                 -- orden de las pestañas
    activo          boolean default true,
    reportes        integer default 0,                  -- contador de "enlace caído"
    ultimo_check    timestamptz,
    creado_en       timestamptz default now(),
    unique (episodio_id, nombre, audio)
);

-- ---------------------------------------------------------------------------
-- 5. Emisiones de hoy (snapshot diario, regenerado por el script de Python)
-- ---------------------------------------------------------------------------
create table if not exists public.emisiones_hoy (
    id                uuid primary key default gen_random_uuid(),
    anime_id          uuid references public.animes(id) on delete cascade,
    mal_id            integer not null,
    titulo            text not null,
    portada           text,
    dia               text not null,                    -- 'lunes' ... 'domingo'
    hora_emision      time,
    hora_local        text,                             -- ya convertida a la TZ configurada
    episodio_esperado integer,                          -- estimado por fecha de estreno
    episodio_subido   integer,                          -- último episodio realmente en la BD
    estado_emision    text default 'Programado',        -- Programado | Emitido | Subtitulado | Retrasado
    fecha_snapshot    date not null default current_date,
    actualizado_en    timestamptz default now(),
    unique (mal_id, fecha_snapshot)
);

-- ---------------------------------------------------------------------------
-- 6. Reportes de enlaces caídos (los envía el frontend, sin login)
-- ---------------------------------------------------------------------------
create table if not exists public.reportes (
    id            uuid primary key default gen_random_uuid(),
    servidor_id   uuid references public.servidores(id) on delete cascade,
    episodio_id   uuid references public.episodios(id) on delete cascade,
    motivo        text default 'no_carga',              -- no_carga | audio | sin_subs | otro
    comentario    text,
    user_agent    text,
    creado_en     timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- 7. Catálogo de géneros (para poblar el filtro del navbar)
-- ---------------------------------------------------------------------------
create table if not exists public.generos (
    id       serial primary key,
    mal_id   integer unique,
    nombre   text not null unique,
    slug     text unique,
    conteo   integer default 0
);

-- ---------------------------------------------------------------------------
-- 8. Índices de rendimiento
-- ---------------------------------------------------------------------------
create index if not exists idx_animes_generos      on public.animes using gin (generos);
create index if not exists idx_animes_temas        on public.animes using gin (temas);
create index if not exists idx_animes_titulo_trgm  on public.animes using gin (titulo gin_trgm_ops);
create index if not exists idx_animes_esp_trgm     on public.animes using gin (titulo_espanol gin_trgm_ops);
create index if not exists idx_animes_estado       on public.animes (estado);
create index if not exists idx_animes_anio_est     on public.animes (anio desc, estacion);
create index if not exists idx_animes_score        on public.animes (puntuacion desc nulls last);
create index if not exists idx_animes_destacado    on public.animes (destacado) where destacado = true;
create index if not exists idx_animes_dia          on public.animes (dia_emision);
create index if not exists idx_episodios_anime     on public.episodios (anime_id, temporada, numero desc);
create index if not exists idx_servidores_ep       on public.servidores (episodio_id) where activo = true;
create index if not exists idx_emisiones_fecha     on public.emisiones_hoy (fecha_snapshot, dia);

-- ---------------------------------------------------------------------------
-- 9. Trigger: mantener actualizado_en
-- ---------------------------------------------------------------------------
create or replace function public.touch_actualizado_en()
returns trigger language plpgsql as $$
begin
  new.actualizado_en = now();
  return new;
end $$;

drop trigger if exists trg_animes_touch on public.animes;
create trigger trg_animes_touch before update on public.animes
  for each row execute function public.touch_actualizado_en();

drop trigger if exists trg_episodios_touch on public.episodios;
create trigger trg_episodios_touch before update on public.episodios
  for each row execute function public.touch_actualizado_en();

-- ---------------------------------------------------------------------------
-- 10. Vistas de conveniencia para el frontend
-- ---------------------------------------------------------------------------

-- Catálogo con el último episodio disponible (evita N+1 en el grid)
create or replace view public.v_catalogo as
select
  a.id, a.mal_id, a.slug, a.titulo, a.titulo_espanol, a.sinopsis,
  a.portada, a.banner, a.generos, a.temas, a.demografia, a.estudio,
  a.estado, a.tipo, a.puntuacion, a.episodios_total, a.anio, a.estacion,
  a.audio, a.calidad, a.destacado, a.vistas, a.dia_emision, a.fecha_estreno,
  coalesce(max(e.numero), 0) as ultimo_episodio,
  count(e.id)                as episodios_disponibles
from public.animes a
left join public.episodios e on e.anime_id = a.id and e.publicado
where a.activo
group by a.id;

-- Emisiones del día actual, listas para pintar el módulo "Capítulos de Hoy"
create or replace view public.v_emisiones_hoy as
select
  eh.*,
  a.slug, a.generos, a.puntuacion, a.estado, a.tipo
from public.emisiones_hoy eh
left join public.animes a on a.id = eh.anime_id
where eh.fecha_snapshot = current_date
order by eh.hora_emision nulls last;

-- Últimos episodios subidos (fila "Novedades")
create or replace view public.v_ultimos_episodios as
select
  e.id as episodio_id, e.numero, e.temporada, e.titulo as titulo_episodio,
  e.miniatura, e.audio, e.creado_en,
  a.id as anime_id, a.mal_id, a.slug, a.titulo, a.portada, a.generos, a.calidad
from public.episodios e
join public.animes a on a.id = e.anime_id
where e.publicado and a.activo
order by e.creado_en desc
limit 60;

-- ---------------------------------------------------------------------------
-- 11. Funciones RPC (llamadas desde el frontend con supabase.rpc(...))
-- ---------------------------------------------------------------------------

-- Buscador con autocompletado tolerante a errores tipográficos y tildes
create or replace function public.buscar_animes(q text, lim int default 8)
returns table (
  id uuid, mal_id int, slug text, titulo text, titulo_espanol text,
  portada text, anio int, tipo text, puntuacion numeric, generos text[], score real
)
language sql stable as $$
  select a.id, a.mal_id, a.slug, a.titulo, a.titulo_espanol, a.portada,
         a.anio, a.tipo, a.puntuacion, a.generos,
         greatest(
           similarity(unaccent(lower(a.titulo)),                     unaccent(lower(q))),
           similarity(unaccent(lower(coalesce(a.titulo_espanol,''))), unaccent(lower(q)))
         ) as score
  from public.animes a
  where a.activo
    and (
      unaccent(lower(a.titulo))                     ilike '%' || unaccent(lower(q)) || '%'
      or unaccent(lower(coalesce(a.titulo_espanol,''))) ilike '%' || unaccent(lower(q)) || '%'
      or exists (
        select 1 from unnest(a.titulos_alt) t
        where unaccent(lower(t)) ilike '%' || unaccent(lower(q)) || '%'
      )
      or unaccent(lower(a.titulo)) % unaccent(lower(q))
    )
  order by score desc, a.miembros desc
  limit lim;
$$;

-- Incrementar vistas de forma atómica
create or replace function public.incrementar_vistas(p_anime_id uuid)
returns void language sql as $$
  update public.animes set vistas = vistas + 1 where id = p_anime_id;
$$;

-- Registrar un enlace caído + incrementar el contador del servidor
create or replace function public.reportar_enlace(
  p_servidor_id uuid, p_motivo text default 'no_carga', p_comentario text default null
) returns void language plpgsql security definer as $$
begin
  insert into public.reportes (servidor_id, episodio_id, motivo, comentario)
  select p_servidor_id, s.episodio_id, p_motivo, left(coalesce(p_comentario,''), 500)
  from public.servidores s where s.id = p_servidor_id;

  update public.servidores set reportes = reportes + 1 where id = p_servidor_id;

  -- auto-desactivación defensiva ante reportes masivos
  update public.servidores set activo = false where id = p_servidor_id and reportes >= 15;
end $$;

-- ---------------------------------------------------------------------------
-- 12. Row Level Security
--     · anon  → sólo LECTURA del catálogo + INSERT de reportes
--     · service_role (usado por el script de Python) → acceso total
-- ---------------------------------------------------------------------------
alter table public.animes       enable row level security;
alter table public.episodios    enable row level security;
alter table public.servidores   enable row level security;
alter table public.emisiones_hoy enable row level security;
alter table public.generos      enable row level security;
alter table public.reportes     enable row level security;

do $$
declare t text;
begin
  foreach t in array array['animes','episodios','servidores','emisiones_hoy','generos'] loop
    execute format('drop policy if exists "lectura publica %1$s" on public.%1$I', t);
    execute format('create policy "lectura publica %1$s" on public.%1$I for select using (true)', t);
  end loop;
end $$;

drop policy if exists "insertar reportes" on public.reportes;
create policy "insertar reportes" on public.reportes for insert with check (true);

-- ---------------------------------------------------------------------------
-- 13. Semilla de géneros (los del filtro del navbar)
-- ---------------------------------------------------------------------------
insert into public.generos (mal_id, nombre, slug) values
  (1,'Acción','accion'), (2,'Aventura','aventura'), (4,'Comedia','comedia'),
  (8,'Drama','drama'), (10,'Fantasía','fantasia'), (7,'Misterio','misterio'),
  (22,'Romance','romance'), (24,'Sci-Fi','sci-fi'), (36,'Slice of Life','slice-of-life'),
  (30,'Deportes','deportes'), (37,'Sobrenatural','sobrenatural'), (14,'Horror','horror'),
  (41,'Suspenso','suspenso'), (18,'Mecha','mecha'), (62,'Isekai','isekai'),
  (23,'Escolar','escolar'), (38,'Militar','militar'), (17,'Artes Marciales','artes-marciales'),
  (19,'Música','musica'), (40,'Psicológico','psicologico'),
  (27,'Shonen','shonen'), (42,'Seinen','seinen'), (25,'Shojo','shojo'), (43,'Josei','josei')
on conflict (nombre) do nothing;

-- ---------------------------------------------------------------------------
-- 14. Realtime (opcional): que el frontend reciba nuevos episodios en vivo
-- ---------------------------------------------------------------------------
do $$ begin
  alter publication supabase_realtime add table public.episodios;
exception when duplicate_object then null; when undefined_object then null; end $$;

do $$ begin
  alter publication supabase_realtime add table public.emisiones_hoy;
exception when duplicate_object then null; when undefined_object then null; end $$;

-- ============================================================================
--  FIN DEL ESQUEMA
-- ============================================================================

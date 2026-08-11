"""
jikan_client.py
===============
Cliente para la API pública de Jikan v4 (MyAnimeList) con:

  · Rate limiting real (3 req/s y 60 req/min son los límites de Jikan).
  · Reintentos con backoff exponencial ante 429 / 5xx / timeouts.
  · Caché en disco opcional (evita machacar la API durante el desarrollo).
  · Normalización de metadatos al español, lista para Supabase.

Docs: https://docs.api.jikan.moe/
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import requests

log = logging.getLogger("jikan")

JIKAN_BASE = os.getenv("JIKAN_BASE_URL", "https://api.jikan.moe/v4")

# Jikan permite 3 req/s y 60 req/min. Usamos un margen de seguridad.
REQ_INTERVAL = float(os.getenv("JIKAN_REQ_INTERVAL", "0.75"))   # segundos entre llamadas
MAX_RETRIES = int(os.getenv("JIKAN_MAX_RETRIES", "5"))
TIMEOUT = int(os.getenv("JIKAN_TIMEOUT", "25"))

CACHE_DIR = Path(os.getenv("JIKAN_CACHE_DIR", ".jikan_cache"))
CACHE_TTL_H = int(os.getenv("JIKAN_CACHE_TTL_HOURS", "12"))

# ---------------------------------------------------------------------------
# Diccionarios de traducción
# ---------------------------------------------------------------------------
ESTADOS = {
    "Currently Airing": "En emisión",
    "Finished Airing": "Finalizado",
    "Not yet aired": "Próximamente",
    "On Hiatus": "Pausado",
    "Discontinued": "Cancelado",
}

ESTACIONES = {"winter": "Invierno", "spring": "Primavera", "summer": "Verano", "fall": "Otoño"}

DIAS = {
    "Mondays": "lunes", "Tuesdays": "martes", "Wednesdays": "miércoles",
    "Thursdays": "jueves", "Fridays": "viernes", "Saturdays": "sábado",
    "Sundays": "domingo", "Other": "otro", "Unknown": "desconocido",
}
DIAS_PY = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

GENEROS = {
    "Action": "Acción", "Adventure": "Aventura", "Comedy": "Comedia", "Drama": "Drama",
    "Fantasy": "Fantasía", "Horror": "Horror", "Mystery": "Misterio", "Romance": "Romance",
    "Sci-Fi": "Sci-Fi", "Slice of Life": "Slice of Life", "Sports": "Deportes",
    "Supernatural": "Sobrenatural", "Suspense": "Suspenso", "Thriller": "Suspenso",
    "Ecchi": "Ecchi", "Award Winning": "Premiado", "Gourmet": "Gastronomía",
    "Avant Garde": "Vanguardia", "Boys Love": "Boys Love", "Girls Love": "Girls Love",
    "Erotica": "Erótico", "Hentai": "Hentai",
}

TEMAS = {
    "Isekai": "Isekai", "School": "Escolar", "Mecha": "Mecha", "Military": "Militar",
    "Martial Arts": "Artes Marciales", "Music": "Música", "Psychological": "Psicológico",
    "Super Power": "Superpoderes", "Historical": "Histórico", "Time Travel": "Viaje en el tiempo",
    "Vampire": "Vampiros", "Space": "Espacial", "Survival": "Supervivencia",
    "Gore": "Gore", "Detective": "Detectives", "Harem": "Harem", "Reverse Harem": "Harem inverso",
    "Mythology": "Mitología", "Video Game": "Videojuegos", "Team Sports": "Deportes de equipo",
    "Racing": "Carreras", "Adult Cast": "Reparto adulto", "Iyashikei": "Iyashikei",
    "Love Polygon": "Triángulo amoroso", "Organized Crime": "Crimen organizado",
    "Otaku Culture": "Cultura otaku", "Performing Arts": "Artes escénicas",
    "Pets": "Mascotas", "Reincarnation": "Reencarnación", "Samurai": "Samurái",
    "Strategy Game": "Juegos de estrategia", "Visual Arts": "Artes visuales",
    "Workplace": "Trabajo", "Anthropomorphic": "Antropomórfico", "CGDCT": "CGDCT",
    "Childcare": "Crianza", "Combat Sports": "Deportes de combate", "Delinquents": "Delincuentes",
    "Educational": "Educativo", "Gag Humor": "Humor absurdo", "High Stakes Game": "Juego mortal",
    "Idols (Female)": "Idols", "Idols (Male)": "Idols", "Magical Sex Shift": "Cambio mágico",
    "Medical": "Médico", "Memoir": "Memorias", "Parody": "Parodia", "Crossdressing": "Crossdressing",
    "Mahou Shoujo": "Magical Girl", "Romantic Subtext": "Subtexto romántico",
    "Showbiz": "Espectáculo", "Urban Fantasy": "Fantasía urbana", "Villainess": "Villana",
}

DEMOGRAFIAS = {
    "Shounen": "Shonen", "Seinen": "Seinen", "Shoujo": "Shojo",
    "Josei": "Josei", "Kids": "Infantil",
}

FUENTES = {
    "Manga": "Manga", "Light novel": "Novela ligera", "Original": "Original",
    "Novel": "Novela", "Visual novel": "Novela visual", "Game": "Videojuego",
    "Web manga": "Web manga", "4-koma manga": "Yonkoma", "Book": "Libro",
    "Card game": "Juego de cartas", "Music": "Música", "Picture book": "Libro ilustrado",
    "Radio": "Radio", "Web novel": "Novela web", "Mixed media": "Multimedia",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def slugify(texto: str) -> str:
    """'Sousou no Frieren: Beyond' → 'sousou-no-frieren-beyond'"""
    if not texto:
        return ""
    n = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    n = re.sub(r"[^\w\s-]", "", n).strip().lower()
    return re.sub(r"[-\s]+", "-", n)[:120]


def traducir(valores: Iterable[str], mapa: dict[str, str]) -> list[str]:
    return [mapa.get(v, v) for v in valores if v]


def _fecha(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Cliente HTTP
# ---------------------------------------------------------------------------
class JikanClient:
    """Cliente con throttling, backoff y caché en disco."""

    def __init__(self, usar_cache: bool = True, intervalo: float = REQ_INTERVAL):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AnimeFlow-Sync/1.0 (+https://github.com/)"})
        self.usar_cache = usar_cache
        self.intervalo = intervalo
        self._ultimo_req = 0.0
        if usar_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # -- caché -------------------------------------------------------------
    def _cache_path(self, url: str, params: dict | None) -> Path:
        clave = hashlib.md5(f"{url}{sorted((params or {}).items())}".encode()).hexdigest()
        return CACHE_DIR / f"{clave}.json"

    def _leer_cache(self, path: Path) -> dict | None:
        if not (self.usar_cache and path.exists()):
            return None
        if datetime.fromtimestamp(path.stat().st_mtime) < datetime.now() - timedelta(hours=CACHE_TTL_H):
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # -- request -----------------------------------------------------------
    def _throttle(self) -> None:
        espera = self.intervalo - (time.monotonic() - self._ultimo_req)
        if espera > 0:
            time.sleep(espera)
        self._ultimo_req = time.monotonic()

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        """GET con rate limit + reintentos exponenciales. Devuelve {} si falla."""
        url = f"{JIKAN_BASE}{endpoint}"
        cache_file = self._cache_path(url, params)

        cached = self._leer_cache(cache_file)
        if cached is not None:
            log.debug("cache hit  %s", endpoint)
            return cached

        for intento in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                r = self.session.get(url, params=params, timeout=TIMEOUT)

                if r.status_code == 200:
                    data = r.json()
                    if self.usar_cache:
                        try:
                            cache_file.write_text(json.dumps(data), encoding="utf-8")
                        except OSError:
                            pass
                    return data

                if r.status_code == 429:  # Rate limit
                    espera = min(60, 2 ** intento) + 1
                    log.warning("429 Rate limit en %s → esperando %ss (intento %d/%d)",
                                endpoint, espera, intento, MAX_RETRIES)
                    time.sleep(espera)
                    continue

                if r.status_code == 404:
                    log.warning("404 No encontrado: %s", endpoint)
                    return {}

                if 500 <= r.status_code < 600:
                    espera = 2 ** intento
                    log.warning("HTTP %d en %s → reintento en %ss", r.status_code, endpoint, espera)
                    time.sleep(espera)
                    continue

                log.error("HTTP %d inesperado en %s", r.status_code, endpoint)
                return {}

            except (requests.Timeout, requests.ConnectionError) as e:
                espera = 2 ** intento
                log.warning("Red caída (%s) en %s → reintento en %ss", type(e).__name__, endpoint, espera)
                time.sleep(espera)
            except json.JSONDecodeError:
                log.error("Respuesta no-JSON en %s", endpoint)
                return {}

        log.error("Agotados %d reintentos en %s", MAX_RETRIES, endpoint)
        return {}

    # -- endpoints ---------------------------------------------------------
    def anime_por_id(self, mal_id: int) -> dict | None:
        """GET /anime/{id}/full — metadatos completos."""
        return self.get(f"/anime/{mal_id}/full").get("data")

    def buscar(self, titulo: str, limite: int = 5, **extra) -> list[dict]:
        """GET /anime?q=... — búsqueda por título."""
        params = {"q": titulo, "limit": limite, "sfw": "true", **extra}
        return self.get("/anime", params).get("data", []) or []

    def temporada(self, anio: int, estacion: str, paginas: int = 1) -> list[dict]:
        """GET /seasons/{year}/{season} — catálogo de una temporada."""
        salida: list[dict] = []
        for p in range(1, paginas + 1):
            data = self.get(f"/seasons/{anio}/{estacion}", {"page": p, "sfw": "true"})
            salida.extend(data.get("data", []) or [])
            if not data.get("pagination", {}).get("has_next_page"):
                break
        return salida

    def temporada_actual(self, paginas: int = 2) -> list[dict]:
        """GET /seasons/now — animes en emisión esta temporada."""
        salida: list[dict] = []
        for p in range(1, paginas + 1):
            data = self.get("/seasons/now", {"page": p, "sfw": "true"})
            salida.extend(data.get("data", []) or [])
            if not data.get("pagination", {}).get("has_next_page"):
                break
        return salida

    def agenda(self, dia: str | None = None, paginas: int = 2) -> list[dict]:
        """GET /schedules?filter={day} — parrilla de emisión semanal."""
        params: dict[str, Any] = {"sfw": "true", "limit": 25}
        if dia:
            params["filter"] = dia          # monday, tuesday, ...
        salida: list[dict] = []
        for p in range(1, paginas + 1):
            data = self.get("/schedules", {**params, "page": p})
            salida.extend(data.get("data", []) or [])
            if not data.get("pagination", {}).get("has_next_page"):
                break
        return salida

    def episodios(self, mal_id: int, max_paginas: int = 5) -> list[dict]:
        """GET /anime/{id}/episodes — lista de episodios con títulos."""
        salida: list[dict] = []
        for p in range(1, max_paginas + 1):
            data = self.get(f"/anime/{mal_id}/episodes", {"page": p})
            salida.extend(data.get("data", []) or [])
            if not data.get("pagination", {}).get("has_next_page"):
                break
        return salida

    def top(self, filtro: str = "bypopularity", limite: int = 25) -> list[dict]:
        """GET /top/anime — 'airing' | 'upcoming' | 'bypopularity' | 'favorite'."""
        return self.get("/top/anime", {"filter": filtro, "limit": limite,
                                       "sfw": "true"}).get("data", []) or []


# ---------------------------------------------------------------------------
# Normalización → fila de la tabla `animes`
# ---------------------------------------------------------------------------
def normalizar_anime(a: dict) -> dict:
    """Convierte la respuesta cruda de Jikan en una fila lista para Supabase."""
    imgs = a.get("images", {}) or {}
    jpg, webp = imgs.get("jpg", {}) or {}, imgs.get("webp", {}) or {}

    portada = jpg.get("large_image_url") or jpg.get("image_url")
    portada_webp = webp.get("large_image_url") or webp.get("image_url")

    trailer = (a.get("trailer") or {}).get("embed_url")

    # Títulos alternativos (sinónimos, inglés, japonés) para el buscador
    alt = {t.get("title") for t in (a.get("titles") or []) if t.get("title")}
    alt.discard(a.get("title"))
    titulo_esp = a.get("title_english") or None

    broadcast = a.get("broadcast") or {}
    dia = DIAS.get(broadcast.get("day") or "", None)
    hora = broadcast.get("time") or None
    if hora and len(hora) == 5:
        hora = f"{hora}:00"

    aired = a.get("aired") or {}
    estudios = [s["name"] for s in (a.get("studios") or []) if s.get("name")]

    titulo = a.get("title") or a.get("title_english") or f"MAL-{a.get('mal_id')}"

    return {
        "mal_id": a.get("mal_id"),
        "slug": slugify(titulo) or f"anime-{a.get('mal_id')}",
        "titulo": titulo,
        "titulo_espanol": titulo_esp,
        "titulo_japones": a.get("title_japanese"),
        "titulos_alt": sorted(alt)[:12],
        "sinopsis": (a.get("synopsis") or "").replace("[Written by MAL Rewrite]", "").strip() or None,
        "portada": portada,
        "portada_webp": portada_webp,
        # Jikan no expone banner; usamos la miniatura del trailer de YouTube como fallback.
        "banner": (a.get("trailer") or {}).get("images", {}).get("maximum_image_url") or portada,
        "trailer_url": trailer,
        "generos": traducir([g["name"] for g in (a.get("genres") or [])], GENEROS),
        "temas": traducir([t["name"] for t in (a.get("themes") or [])], TEMAS),
        "demografia": traducir([d["name"] for d in (a.get("demographics") or [])], DEMOGRAFIAS),
        "estudio": estudios[0] if estudios else None,
        "estudios": estudios,
        "fuente": FUENTES.get(a.get("source") or "", a.get("source")),
        "estado": ESTADOS.get(a.get("status") or "", "Próximamente"),
        "tipo": a.get("type"),
        "clasificacion": a.get("rating"),
        "puntuacion": a.get("score"),
        "miembros": a.get("members") or 0,
        "ranking": a.get("rank"),
        "popularidad": a.get("popularity"),
        "episodios_total": a.get("episodes"),
        "duracion": a.get("duration"),
        "anio": a.get("year") or (int(aired["from"][:4]) if aired.get("from") else None),
        "estacion": ESTACIONES.get(a.get("season") or ""),
        "fecha_estreno": _fecha(aired.get("from")),
        "fecha_fin": _fecha(aired.get("to")),
        "dia_emision": dia,
        "hora_emision": hora,
        "activo": True,
    }


def normalizar_episodios(anime_id: str, eps: list[dict]) -> list[dict]:
    """Convierte /anime/{id}/episodes en filas de la tabla `episodios`."""
    filas = []
    for e in eps:
        num = e.get("mal_id")
        if not num:
            continue
        filas.append({
            "anime_id": anime_id,
            "numero": num,
            "temporada": 1,
            "titulo": e.get("title") or e.get("title_romanji") or f"Episodio {num}",
            "fecha_emision": e.get("aired"),
            "filler": bool(e.get("filler")),
            "recap": bool(e.get("recap")),
            "publicado": True,
        })
    return filas


def dia_actual(tz_offset_horas: int = 0) -> tuple[str, str]:
    """Devuelve (dia_es, dia_en) del día de hoy. tz_offset ajusta la zona horaria."""
    hoy = datetime.utcnow() + timedelta(hours=tz_offset_horas)
    idx = hoy.weekday()  # 0 = lunes
    en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][idx]
    return DIAS_PY[idx], en


def estimar_episodio_actual(fecha_estreno: str | None, total: int | None = None) -> int | None:
    """Estima el nº de episodio en emisión: semanas transcurridas desde el estreno."""
    if not fecha_estreno:
        return None
    try:
        inicio = date.fromisoformat(fecha_estreno[:10])
    except ValueError:
        return None
    semanas = (date.today() - inicio).days // 7 + 1
    if semanas < 1:
        return None
    return min(semanas, total) if total else semanas

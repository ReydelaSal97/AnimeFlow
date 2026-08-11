#!/usr/bin/env python3
"""
sync_anime_supabase.py
======================
Pipeline de sincronización  Jikan API v4  →  Supabase Cloud.

Uso
---
    # 1) Instalar dependencias
    pip install -r requirements.txt

    # 2) Copiar .env.example a .env y rellenar SUPABASE_URL / SUPABASE_KEY

    # 3) Comandos disponibles
    python sync_anime_supabase.py init                       # géneros + temporada actual + agenda
    python sync_anime_supabase.py sync-season                # temporada en curso (/seasons/now)
    python sync_anime_supabase.py sync-season --anio 2024 --estacion fall
    python sync_anime_supabase.py sync-today                 # ← ejecutar por cron cada día
    python sync_anime_supabase.py sync-id 52991              # un anime por MAL ID
    python sync_anime_supabase.py sync-title "Frieren" --episodios
    python sync_anime_supabase.py sync-top --filtro airing --limite 20 --destacar
    python sync_anime_supabase.py export-json --salida ../frontend/mock-data.json
    python sync_anime_supabase.py --dry-run sync-today       # sin escribir en Supabase

Cron sugerido (servidor):
    0 6 * * *   cd /ruta/backend && python sync_anime_supabase.py sync-today  >> sync.log 2>&1
    0 4 * * 1   cd /ruta/backend && python sync_anime_supabase.py sync-season >> sync.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from jikan_client import (
    ESTACIONES,
    JikanClient,
    dia_actual,
    estimar_episodio_actual,
    normalizar_anime,
    normalizar_episodios,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s │ %(levelname)-7s │ %(name)-8s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("sync.log", encoding="utf-8")],
)
log = logging.getLogger("sync")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
TZ_OFFSET = int(os.getenv("TZ_OFFSET_HORAS", "-5"))   # America/Bogota = UTC-5
LOTE = 50                                              # filas por upsert


# ---------------------------------------------------------------------------
# Capa de persistencia
# ---------------------------------------------------------------------------
class SupabaseRepo:
    """Wrapper fino sobre supabase-py con soporte de --dry-run."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.client = None
        if dry_run:
            log.warning("MODO DRY-RUN: no se escribirá nada en Supabase.")
            return
        if not (SUPABASE_URL and SUPABASE_KEY):
            log.error("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY en el archivo .env")
            sys.exit(1)
        try:
            from supabase import create_client
        except ImportError:
            log.error("Falta la librería: pip install supabase")
            sys.exit(1)
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
        log.info("Conectado a Supabase → %s", SUPABASE_URL)

    # -- helpers -----------------------------------------------------------
    def upsert(self, tabla: str, filas: list[dict], on_conflict: str) -> list[dict]:
        """Upsert por lotes. Devuelve las filas insertadas/actualizadas."""
        if not filas:
            return []
        if self.dry_run:
            log.info("[dry-run] upsert %-14s ← %3d filas (conflict=%s)", tabla, len(filas), on_conflict)
            log.debug("[dry-run] muestra: %s", json.dumps(filas[0], ensure_ascii=False, default=str)[:400])
            return filas

        resultado: list[dict] = []
        for i in range(0, len(filas), LOTE):
            lote = filas[i:i + LOTE]
            try:
                r = self.client.table(tabla).upsert(lote, on_conflict=on_conflict).execute()
                resultado.extend(r.data or [])
                log.info("upsert %-14s ← %3d filas  (lote %d)", tabla, len(lote), i // LOTE + 1)
            except Exception as e:                                   # noqa: BLE001
                log.error("Error al hacer upsert en %s: %s", tabla, e)
        return resultado

    def obtener_id(self, mal_id: int) -> str | None:
        """Devuelve el UUID interno de un anime a partir de su mal_id."""
        if self.dry_run or not self.client:
            return f"dry-run-uuid-{mal_id}"
        try:
            r = self.client.table("animes").select("id").eq("mal_id", mal_id).limit(1).execute()
            return r.data[0]["id"] if r.data else None
        except Exception as e:                                       # noqa: BLE001
            log.error("No se pudo resolver el UUID de mal_id=%s: %s", mal_id, e)
            return None

    def ultimo_episodio(self, anime_id: str) -> int:
        if self.dry_run or not self.client:
            return 0
        try:
            r = (self.client.table("episodios").select("numero")
                 .eq("anime_id", anime_id).order("numero", desc=True).limit(1).execute())
            return r.data[0]["numero"] if r.data else 0
        except Exception:                                            # noqa: BLE001
            return 0

    def limpiar_emisiones(self) -> None:
        """Borra snapshots de días anteriores para que la tabla no crezca sin control."""
        if self.dry_run or not self.client:
            return
        try:
            self.client.table("emisiones_hoy").delete().lt("fecha_snapshot", date.today().isoformat()).execute()
            log.info("Snapshots antiguos de emisiones_hoy eliminados.")
        except Exception as e:                                       # noqa: BLE001
            log.warning("No se pudieron limpiar emisiones antiguas: %s", e)

    def marcar_destacados(self, mal_ids: list[int]) -> None:
        """Deja como destacados (Hero Banner) sólo los mal_ids indicados."""
        if self.dry_run or not self.client or not mal_ids:
            log.info("[dry-run] destacados → %s", mal_ids)
            return
        try:
            self.client.table("animes").update({"destacado": False}).eq("destacado", True).execute()
            self.client.table("animes").update({"destacado": True}).in_("mal_id", mal_ids).execute()
            log.info("Hero Banner actualizado con %d animes destacados.", len(mal_ids))
        except Exception as e:                                       # noqa: BLE001
            log.error("Error al marcar destacados: %s", e)

    def exportar(self) -> dict:
        """Descarga el catálogo para generar el JSON de demo del frontend."""
        if self.dry_run or not self.client:
            return {}
        animes = self.client.table("v_catalogo").select("*").limit(500).execute().data or []
        hoy = self.client.table("v_emisiones_hoy").select("*").execute().data or []
        return {"animes": animes, "emisiones_hoy": hoy,
                "generado_en": datetime.now().isoformat()}


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def cmd_sync_season(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Sincroniza el catálogo de una temporada completa."""
    if args.anio and args.estacion:
        log.info("Sincronizando temporada %s %s…", args.estacion, args.anio)
        crudos = jk.temporada(args.anio, args.estacion, paginas=args.paginas)
    else:
        log.info("Sincronizando la temporada en emisión (/seasons/now)…")
        crudos = jk.temporada_actual(paginas=args.paginas)

    filas = [normalizar_anime(a) for a in crudos if a.get("mal_id")]
    # Deduplicar por mal_id (Jikan puede repetir entre páginas)
    filas = list({f["mal_id"]: f for f in filas}.values())
    log.info("%d animes normalizados.", len(filas))

    repo.upsert("animes", filas, on_conflict="mal_id")

    if args.episodios:
        sincronizar_episodios(jk, repo, [f["mal_id"] for f in filas][:args.limite_eps])

    log.info("✔ Temporada sincronizada: %d animes.", len(filas))


def cmd_sync_today(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Construye el módulo 'Capítulos del Día' consultando /schedules."""
    dia_es, dia_en = dia_actual(TZ_OFFSET)
    log.info("Hoy es %s → consultando /schedules?filter=%s", dia_es, dia_en)

    crudos = jk.agenda(dia_en, paginas=args.paginas)
    if not crudos:
        log.warning("La agenda vino vacía; usando /seasons/now como respaldo.")
        crudos = [a for a in jk.temporada_actual(paginas=2)
                  if (a.get("broadcast") or {}).get("day", "").lower().startswith(dia_en[:3])]

    animes = [normalizar_anime(a) for a in crudos if a.get("mal_id")]
    animes = list({a["mal_id"]: a for a in animes}.values())
    log.info("%d animes se emiten hoy.", len(animes))

    # 1) El catálogo primero (necesitamos los UUID para la FK)
    guardados = repo.upsert("animes", animes, on_conflict="mal_id")
    mapa_uuid = {g["mal_id"]: g["id"] for g in guardados if isinstance(g, dict) and "mal_id" in g}

    # 2) Snapshot del día
    repo.limpiar_emisiones()
    hoy_iso = date.today().isoformat()
    emisiones = []
    for a in animes:
        uuid = mapa_uuid.get(a["mal_id"]) or repo.obtener_id(a["mal_id"])
        esperado = estimar_episodio_actual(a["fecha_estreno"], a["episodios_total"])
        subido = repo.ultimo_episodio(uuid) if uuid else 0

        if subido and esperado and subido >= esperado:
            estado = "Subtitulado"
        elif esperado:
            estado = "Emitido" if subido else "Programado"
        else:
            estado = "Programado"

        emisiones.append({
            "anime_id": uuid,
            "mal_id": a["mal_id"],
            "titulo": a["titulo_espanol"] or a["titulo"],
            "portada": a["portada"],
            "dia": dia_es,
            "hora_emision": a["hora_emision"],
            "hora_local": convertir_hora_local(a["hora_emision"]),
            "episodio_esperado": esperado,
            "episodio_subido": subido,
            "estado_emision": estado,
            "fecha_snapshot": hoy_iso,
        })

    emisiones.sort(key=lambda e: e["hora_emision"] or "99:99:99")
    repo.upsert("emisiones_hoy", emisiones, on_conflict="mal_id,fecha_snapshot")

    log.info("✔ Emisiones de hoy (%s): %d títulos.", dia_es, len(emisiones))
    for e in emisiones[:10]:
        log.info("   %s  ep.%-4s %-45s [%s]",
                 e["hora_local"] or "--:--", e["episodio_esperado"] or "?",
                 e["titulo"][:45], e["estado_emision"])


def cmd_sync_id(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Sincroniza un anime concreto por su MAL ID."""
    for mal_id in args.mal_ids:
        crudo = jk.anime_por_id(mal_id)
        if not crudo:
            log.error("MAL ID %s no encontrado.", mal_id)
            continue
        fila = normalizar_anime(crudo)
        repo.upsert("animes", [fila], on_conflict="mal_id")
        log.info("✔ %s (%s)", fila["titulo"], fila["estado"])
        if args.episodios:
            sincronizar_episodios(jk, repo, [mal_id])


def cmd_sync_title(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Busca por título y sincroniza los N mejores resultados."""
    resultados = jk.buscar(args.titulo, limite=args.limite)
    if not resultados:
        log.error("Sin resultados para «%s».", args.titulo)
        return
    filas = [normalizar_anime(a) for a in resultados]
    repo.upsert("animes", filas, on_conflict="mal_id")
    for f in filas:
        log.info("✔ [%s] %s — %s %s", f["mal_id"], f["titulo"], f["estado"], f["puntuacion"] or "")
    if args.episodios:
        sincronizar_episodios(jk, repo, [f["mal_id"] for f in filas])


def cmd_sync_top(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Sincroniza el Top de MAL y opcionalmente alimenta el Hero Banner."""
    crudos = jk.top(args.filtro, args.limite)
    filas = [normalizar_anime(a) for a in crudos if a.get("mal_id")]
    repo.upsert("animes", filas, on_conflict="mal_id")
    if args.destacar:
        repo.marcar_destacados([f["mal_id"] for f in filas[:5]])
    log.info("✔ Top '%s': %d animes.", args.filtro, len(filas))


def cmd_init(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Carga inicial completa: temporada actual + top + agenda de hoy."""
    log.info("═══ Carga inicial de AnimeFlow ═══")
    args.anio = args.estacion = None
    args.paginas, args.episodios, args.limite_eps = 3, False, 0
    cmd_sync_season(jk, repo, args)

    args.filtro, args.limite, args.destacar = "airing", 12, True
    cmd_sync_top(jk, repo, args)

    args.paginas = 2
    cmd_sync_today(jk, repo, args)
    log.info("═══ Carga inicial terminada ═══")


def cmd_export(jk: JikanClient, repo: SupabaseRepo, args) -> None:
    """Vuelca el contenido de Supabase a un JSON para el modo demo del frontend."""
    datos = repo.exportar()
    if not datos:
        log.error("No hay datos que exportar (¿estás en --dry-run?).")
        return
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info("✔ Exportado a %s (%d animes)", salida, len(datos.get("animes", [])))


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------
def sincronizar_episodios(jk: JikanClient, repo: SupabaseRepo, mal_ids: list[int]) -> None:
    """Descarga la lista de episodios de cada anime y la guarda."""
    for mal_id in mal_ids:
        uuid = repo.obtener_id(mal_id)
        if not uuid:
            log.warning("Sin UUID para mal_id=%s; se omiten sus episodios.", mal_id)
            continue
        eps = jk.episodios(mal_id)
        if not eps:
            continue
        filas = normalizar_episodios(uuid, eps)
        repo.upsert("episodios", filas, on_conflict="anime_id,temporada,numero")
        log.info("   ↳ %d episodios para mal_id=%s", len(filas), mal_id)


def convertir_hora_local(hora_jst: str | None) -> str | None:
    """Convierte HH:MM:SS de Japón (UTC+9) a la zona configurada en TZ_OFFSET_HORAS."""
    if not hora_jst:
        return None
    try:
        h, m = int(hora_jst[:2]), int(hora_jst[3:5])
    except (ValueError, IndexError):
        return None
    total = (h * 60 + m) + (TZ_OFFSET - 9) * 60
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sincroniza metadatos de anime desde Jikan API v4 hacia Supabase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--dry-run", action="store_true", help="No escribe en Supabase, sólo muestra.")
    p.add_argument("--sin-cache", action="store_true", help="Ignora la caché en disco de Jikan.")
    p.add_argument("--intervalo", type=float, default=0.75, help="Segundos entre llamadas a Jikan.")
    p.add_argument("-v", "--verbose", action="store_true")

    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("init", help="Carga inicial completa.")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("sync-season", help="Sincroniza una temporada.")
    s.add_argument("--anio", type=int)
    s.add_argument("--estacion", choices=list(ESTACIONES.keys()))
    s.add_argument("--paginas", type=int, default=2)
    s.add_argument("--episodios", action="store_true", help="También descarga los episodios.")
    s.add_argument("--limite-eps", type=int, default=15, help="Máx. animes a los que bajar episodios.")
    s.set_defaults(func=cmd_sync_season)

    s = sub.add_parser("sync-today", help="Actualiza 'Capítulos del Día'.")
    s.add_argument("--paginas", type=int, default=2)
    s.set_defaults(func=cmd_sync_today)

    s = sub.add_parser("sync-id", help="Sincroniza uno o varios MAL ID.")
    s.add_argument("mal_ids", nargs="+", type=int)
    s.add_argument("--episodios", action="store_true")
    s.set_defaults(func=cmd_sync_id)

    s = sub.add_parser("sync-title", help="Busca por título y sincroniza.")
    s.add_argument("titulo")
    s.add_argument("--limite", type=int, default=3)
    s.add_argument("--episodios", action="store_true")
    s.set_defaults(func=cmd_sync_title)

    s = sub.add_parser("sync-top", help="Sincroniza el Top de MyAnimeList.")
    s.add_argument("--filtro", default="airing", choices=["airing", "upcoming", "bypopularity", "favorite"])
    s.add_argument("--limite", type=int, default=25)
    s.add_argument("--destacar", action="store_true", help="Marca los 5 primeros para el Hero Banner.")
    s.set_defaults(func=cmd_sync_top)

    s = sub.add_parser("export-json", help="Exporta el catálogo a JSON (modo demo).")
    s.add_argument("--salida", default="../frontend/mock-data.json")
    s.set_defaults(func=cmd_export)

    return p


def main() -> None:
    args = construir_parser().parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    inicio = datetime.now()
    jk = JikanClient(usar_cache=not args.sin_cache, intervalo=args.intervalo)
    repo = SupabaseRepo(dry_run=args.dry_run)

    try:
        args.func(jk, repo, args)
    except KeyboardInterrupt:
        log.warning("Interrumpido por el usuario.")
        sys.exit(130)
    finally:
        log.info("Tiempo total: %.1fs", (datetime.now() - inicio).total_seconds())


if __name__ == "__main__":
    main()

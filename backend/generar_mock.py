#!/usr/bin/env python3
"""
generar_mock.py
===============
Genera `frontend/mock-data.json`: un dataset de demostración con EXACTAMENTE
la misma forma que devuelve Supabase (vista v_catalogo + tablas relacionadas),
para que el frontend funcione sin base de datos.

    python generar_mock.py

Cuando ya tengas Supabase poblado, sustitúyelo por el volcado real:

    python sync_anime_supabase.py export-json --salida ../frontend/mock-data.json
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

random.seed(7)

SALIDA = Path(__file__).resolve().parent.parent / "frontend" / "mock-data.json"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Paletas por género principal → portadas SVG generadas (nunca dan 404)
PALETAS = {
    "Acción":      ("#7c3aed", "#db2777"), "Aventura":  ("#0ea5e9", "#22d3ee"),
    "Fantasía":    ("#8b5cf6", "#22d3ee"), "Romance":   ("#f43f5e", "#fb923c"),
    "Comedia":     ("#f59e0b", "#84cc16"), "Drama":     ("#6366f1", "#a855f7"),
    "Sci-Fi":      ("#06b6d4", "#3b82f6"), "Misterio":  ("#334155", "#6366f1"),
    "Deportes":    ("#10b981", "#a3e635"), "Sobrenatural": ("#a855f7", "#ec4899"),
    "Horror":      ("#18181b", "#dc2626"), "Suspenso":  ("#1e293b", "#0ea5e9"),
}


def portada_svg(titulo: str, genero: str, horizontal: bool = False) -> str:
    """Genera una portada SVG como data-URI (siempre carga, sin depender de CDN)."""
    c1, c2 = PALETAS.get(genero, ("#8b5cf6", "#22d3ee"))
    w, h = (960, 540) if horizontal else (300, 425)
    ini = "".join(p[0] for p in titulo.split()[:2]).upper()
    fs_ini = 150 if horizontal else 110
    palabras = titulo.split()
    lineas, actual = [], ""
    for p in palabras:
        if len(actual + " " + p) > 18:
            lineas.append(actual); actual = p
        else:
            actual = (actual + " " + p).strip()
    lineas.append(actual)
    lineas = lineas[:3]
    y0 = h - 34 - (len(lineas) - 1) * 20
    tspans = "".join(
        f'<tspan x="50%" y="{y0 + i * 20}">{l.replace("&", "&amp;").replace("<", "&lt;")}</tspan>'
        for i, l in enumerate(lineas)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/></linearGradient>
<radialGradient id="v" cx="50%" cy="35%" r="75%">
<stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity=".72"/></radialGradient>
<pattern id="p" width="26" height="26" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
<line x1="0" y1="0" x2="0" y2="26" stroke="#fff" stroke-opacity=".07" stroke-width="9"/></pattern>
</defs>
<rect width="100%" height="100%" fill="url(#g)"/>
<rect width="100%" height="100%" fill="url(#p)"/>
<rect width="100%" height="100%" fill="url(#v)"/>
<text x="50%" y="{h * 0.47:.0f}" font-family="Outfit,Arial,sans-serif" font-size="{fs_ini}" font-weight="800"
 fill="#fff" fill-opacity=".2" text-anchor="middle" dominant-baseline="middle">{ini}</text>
<text font-family="Outfit,Arial,sans-serif" font-size="17" font-weight="700" fill="#fff" text-anchor="middle">{tspans}</text>
</svg>'''
    return "data:image/svg+xml;utf8," + quote(svg)


# ---------------------------------------------------------------------------
# Catálogo de demostración (metadatos ficticios con estructura real)
# ---------------------------------------------------------------------------
CATALOGO = [
    # (título, título ES, géneros, temas, estudio, estado, tipo, score, eps, año, estación, día, hora, destacado)
    ("Sousou no Frieren", "Frieren: Más allá del final del viaje", ["Aventura","Drama","Fantasía"], ["Mitología"], "Madhouse", "Finalizado", "TV", 9.31, 28, 2023, "Otoño", "viernes", "09:00", True),
    ("Kaiju No. 8", "Kaiju No. 8", ["Acción","Sci-Fi"], ["Superpoderes"], "Production I.G", "En emisión", "TV", 8.24, 12, 2026, "Verano", "lunes", "10:30", True),
    ("Sakamoto Days", "Sakamoto Days", ["Acción","Comedia"], ["Crimen organizado"], "TMS Entertainment", "En emisión", "TV", 8.05, 24, 2026, "Verano", "lunes", "13:00", True),
    ("Boku no Hero Academia", "My Hero Academia", ["Acción","Aventura"], ["Escolar","Superpoderes"], "Bones", "Finalizado", "TV", 8.12, 25, 2016, "Primavera", "sábado", "17:30", False),
    ("Shingeki no Kyojin", "Ataque a los Titanes", ["Acción","Drama","Suspenso"], ["Militar","Supervivencia"], "Wit Studio", "Finalizado", "TV", 8.56, 25, 2013, "Primavera", "domingo", "01:58", True),
    ("Jujutsu Kaisen", "Jujutsu Kaisen", ["Acción","Sobrenatural"], ["Escolar"], "MAPPA", "Finalizado", "TV", 8.55, 24, 2020, "Otoño", "sábado", "01:25", False),
    ("Mushoku Tensei", "Mushoku Tensei: Jobless Reincarnation", ["Aventura","Drama","Fantasía"], ["Isekai","Reencarnación"], "Studio Bind", "En emisión", "TV", 8.36, 23, 2026, "Verano", "domingo", "00:00", False),
    ("Spy x Family", "Spy x Family", ["Acción","Comedia"], ["Escolar"], "Wit Studio", "Finalizado", "TV", 8.49, 25, 2022, "Primavera", "sábado", "23:00", False),
    ("Vinland Saga", "Vinland Saga", ["Acción","Aventura","Drama"], ["Histórico"], "Wit Studio", "Finalizado", "TV", 8.75, 24, 2019, "Verano", "lunes", "00:10", False),
    ("Kimetsu no Yaiba", "Guardianes de la Noche", ["Acción","Sobrenatural"], ["Histórico"], "ufotable", "En emisión", "TV", 8.44, 26, 2026, "Verano", "domingo", "23:15", True),
    ("Bocchi the Rock!", "Bocchi the Rock!", ["Comedia","Slice of Life"], ["Música","CGDCT"], "CloverWorks", "Finalizado", "TV", 8.75, 12, 2022, "Otoño", "sábado", "23:30", False),
    ("Oshi no Ko", "Oshi no Ko", ["Drama","Sobrenatural"], ["Espectáculo","Reencarnación"], "Doga Kobo", "En emisión", "TV", 8.61, 13, 2026, "Verano", "miércoles", "23:00", False),
    ("Dandadan", "Dandadan", ["Acción","Comedia","Sobrenatural"], ["Escolar"], "Science SARU", "En emisión", "TV", 8.48, 12, 2026, "Verano", "jueves", "00:26", False),
    ("Chainsaw Man", "Chainsaw Man", ["Acción","Sobrenatural"], ["Gore"], "MAPPA", "Finalizado", "TV", 8.53, 12, 2022, "Otoño", "martes", "00:00", False),
    ("Blue Lock", "Blue Lock", ["Deportes","Drama"], ["Deportes de equipo"], "8bit", "En emisión", "TV", 8.19, 24, 2026, "Verano", "sábado", "01:30", False),
    ("Steins;Gate", "Steins;Gate", ["Drama","Sci-Fi","Suspenso"], ["Viaje en el tiempo","Psicológico"], "White Fox", "Finalizado", "TV", 9.07, 24, 2011, "Primavera", "miércoles", "02:05", False),
    ("Violet Evergarden", "Violet Evergarden", ["Drama","Fantasía"], ["Militar"], "Kyoto Animation", "Finalizado", "TV", 8.67, 13, 2018, "Invierno", "miércoles", "00:00", False),
    ("Haikyuu!!", "Haikyu!!", ["Deportes","Comedia"], ["Escolar","Deportes de equipo"], "Production I.G", "Finalizado", "TV", 8.45, 25, 2014, "Primavera", "domingo", "01:25", False),
    ("Tensei shitara Slime Datta Ken", "Reencarné como una Slime", ["Aventura","Comedia","Fantasía"], ["Isekai","Reencarnación"], "8bit", "En emisión", "TV", 8.13, 24, 2026, "Verano", "viernes", "23:00", False),
    ("Cyberpunk: Edgerunners", "Cyberpunk: Edgerunners", ["Acción","Sci-Fi","Drama"], ["Videojuegos","Gore"], "Studio Trigger", "Finalizado", "ONA", 8.60, 10, 2022, "Otoño", "martes", "12:00", False),
    ("Hunter x Hunter", "Hunter x Hunter", ["Acción","Aventura","Fantasía"], ["Superpoderes"], "Madhouse", "Pausado", "TV", 9.04, 148, 2011, "Otoño", "domingo", "10:55", False),
    ("Monster", "Monster", ["Drama","Misterio","Suspenso"], ["Psicológico","Detectives"], "Madhouse", "Finalizado", "TV", 8.87, 74, 2004, "Primavera", "miércoles", "00:50", False),
    ("Made in Abyss", "Made in Abyss", ["Aventura","Drama","Fantasía"], ["Supervivencia"], "Kinema Citrus", "Finalizado", "TV", 8.68, 13, 2017, "Verano", "viernes", "22:00", False),
    ("Ranma ½ (2024)", "Ranma ½", ["Comedia","Romance"], ["Artes Marciales","Escolar"], "MAPPA", "En emisión", "TV", 7.98, 12, 2026, "Verano", "sábado", "00:00", False),
    ("Sakura Trick Zero", "Sakura Trick Zero", ["Romance","Slice of Life"], ["Escolar"], "Studio Deen", "Próximamente", "TV", None, 12, 2027, "Invierno", None, None, False),
    ("Ao no Exorcist", "Blue Exorcist", ["Acción","Fantasía"], ["Escolar","Sobrenatural"], "A-1 Pictures", "Finalizado", "TV", 7.51, 25, 2011, "Primavera", "domingo", "17:00", False),
]

SINOPSIS = (
    "En un mundo donde las fronteras entre lo cotidiano y lo extraordinario se difuminan, un grupo de "
    "personajes muy distintos entre sí descubre que sus destinos están entrelazados por algo mucho más "
    "grande que ellos mismos. Entre batallas trepidantes, silencios cargados de emoción y decisiones que "
    "no admiten vuelta atrás, cada capítulo profundiza en lo que significa pertenecer, perder y volver a "
    "empezar. Una historia sobre el peso del tiempo, la amistad y las promesas que se sostienen aunque "
    "todo lo demás se derrumbe."
)

SERVIDORES = [
    ("Servidor 1 - Streamtape", "SUB", "FHD", 1),
    ("Servidor 2 - Mega",       "SUB", "HD",  2),
    ("Servidor 3 - Fembed",     "SUB", "HD",  3),
    ("Servidor 4 - YourUpload", "DUB", "HD",  4),
]


def slugify(t: str) -> str:
    import re, unicodedata
    n = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", n).strip().lower())


def main() -> None:
    animes, episodios, servidores, emisiones = [], [], [], []
    hoy = DIAS[(datetime.now().weekday())]

    for i, (t, tes, gen, tem, est, estado, tipo, score, eps, anio, estacion, dia, hora, dest) in enumerate(CATALOGO):
        aid = str(uuid.uuid4())
        principal = gen[0]
        disponibles = eps if estado == "Finalizado" else (0 if estado == "Próximamente" else random.randint(3, max(4, eps - 2)))

        animes.append({
            "id": aid,
            "mal_id": 10000 + i,
            "slug": slugify(t),
            "titulo": t,
            "titulo_espanol": tes,
            "titulo_japones": None,
            "titulos_alt": [tes],
            "sinopsis": SINOPSIS,
            "portada": portada_svg(tes, principal),
            "banner": portada_svg(tes, principal, horizontal=True),
            "trailer_url": None,
            "generos": gen,
            "temas": tem,
            "demografia": ["Shonen"] if "Acción" in gen else [],
            "estudio": est,
            "fuente": "Manga",
            "estado": estado,
            "tipo": tipo,
            "clasificacion": "PG-13 - Teens 13 or older",
            "puntuacion": score,
            "miembros": random.randint(50_000, 3_000_000),
            "ranking": i + 1,
            "episodios_total": eps,
            "duracion": "24 min por ep.",
            "anio": anio,
            "estacion": estacion,
            "fecha_estreno": f"{anio}-{ {'Invierno':'01','Primavera':'04','Verano':'07','Otoño':'10'}[estacion] }-{random.randint(1,27):02d}",
            "dia_emision": dia,
            "hora_emision": f"{hora}:00" if hora else None,
            "hora_local": hora,
            "audio": "SUB",
            "calidad": random.choice(["HD", "FHD", "FHD", "4K"]),
            "destacado": dest,
            "vistas": random.randint(1_000, 900_000),
            "ultimo_episodio": disponibles,
            "episodios_disponibles": disponibles,
        })

        for n in range(1, disponibles + 1):
            eid = str(uuid.uuid4())
            episodios.append({
                "id": eid, "anime_id": aid, "numero": n, "temporada": 1,
                "titulo": f"Episodio {n}", "audio": "SUB", "filler": n % 9 == 0,
                "publicado": True,
                "fecha_emision": (date(anio, 1, 1) + timedelta(weeks=n)).isoformat(),
            })
            for nombre, audio, calidad, orden in SERVIDORES:
                if audio == "DUB" and random.random() < 0.55:
                    continue
                servidores.append({
                    "id": str(uuid.uuid4()), "episodio_id": eid, "nombre": nombre,
                    "embed_url": f"demo-player.html?s={quote(nombre)}&ep={n}&t=Episodio",
                    "audio": audio, "calidad": calidad, "orden": orden, "activo": True,
                })

        if dia == hoy and estado == "En emisión":
            emisiones.append({
                "id": str(uuid.uuid4()), "anime_id": aid, "mal_id": 10000 + i,
                "titulo": tes, "portada": portada_svg(tes, principal),
                "dia": dia, "hora_emision": f"{hora}:00", "hora_local": hora,
                "episodio_esperado": disponibles + 1, "episodio_subido": disponibles,
                "estado_emision": random.choice(["Programado", "Emitido", "Subtitulado"]),
                "fecha_snapshot": date.today().isoformat(),
                "slug": slugify(t), "generos": gen, "puntuacion": score, "estado": estado, "tipo": tipo,
            })

    datos = {
        "_meta": {
            "descripcion": "Dataset de demostración de AnimeFlow. Misma forma que devuelve Supabase.",
            "generado_en": datetime.now().isoformat(timespec="seconds"),
            "modo": "demo",
        },
        "animes": animes,
        "episodios": episodios,
        "servidores": servidores,
        "emisiones_hoy": emisiones,
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = SALIDA.stat().st_size / 1024
    print(f"✔ {SALIDA}")
    print(f"  {len(animes)} animes · {len(episodios)} episodios · {len(servidores)} servidores · "
          f"{len(emisiones)} emisiones hoy ({hoy}) · {kb:.0f} KB")


if __name__ == "__main__":
    main()

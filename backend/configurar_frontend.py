#!/usr/bin/env python3
"""
configurar_frontend.py
======================
Escribe las credenciales de Supabase dentro del bloque CONFIG de
`frontend/index.html`, sin tocar nada más. Hace una copia de seguridad antes.

    python configurar_frontend.py https://xxxx.supabase.co eyJhbGciOi...
    python configurar_frontend.py --mostrar     # ver la configuración actual
    python configurar_frontend.py --estado      # una sola línea (lo usa el .bat)
    python configurar_frontend.py --limpiar     # volver al modo demo
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

RE_URL = re.compile(r"(SUPABASE_URL:\s*)'[^']*'")
RE_KEY = re.compile(r"(SUPABASE_ANON_KEY:\s*)'[^']*'")


def leer() -> str:
    if not INDEX.exists():
        print(f"[ERROR] No se encuentra {INDEX}")
        sys.exit(1)
    return INDEX.read_text(encoding="utf-8")


def mostrar() -> None:
    html = leer()
    u = RE_URL.search(html)
    k = RE_KEY.search(html)
    url = re.search(r"SUPABASE_URL:\s*'([^']*)'", html)
    key = re.search(r"SUPABASE_ANON_KEY:\s*'([^']*)'", html)
    if not (u and k):
        print("[ERROR] No se encontro el bloque CONFIG en index.html")
        sys.exit(1)
    url_v = url.group(1) if url else ""
    key_v = key.group(1) if key else ""
    if url_v and key_v:
        print("Estado    : CONECTADO a Supabase")
        print(f"URL       : {url_v}")
        print(f"Anon key  : {key_v[:14]}...{key_v[-6:]}  ({len(key_v)} caracteres)")
    else:
        print("Estado    : MODO DEMO (lee mock-data.json)")
        print("            Aun no hay credenciales de Supabase configuradas.")


def estado_corto() -> None:
    """Una sola linea en ASCII, pensada para mostrarla desde el .bat."""
    html = leer()
    url = re.search(r"SUPABASE_URL:\s*'([^']*)'", html)
    key = re.search(r"SUPABASE_ANON_KEY:\s*'([^']*)'", html)
    if url and key and url.group(1) and key.group(1):
        host = url.group(1).replace("https://", "").rstrip("/")
        print(f"Supabase conectado ({host})")
    else:
        print("Modo demostracion (mock-data.json)")


def escribir(url: str, key: str) -> None:
    html = leer()

    if not RE_URL.search(html) or not RE_KEY.search(html):
        print("[ERROR] No se encontro el bloque CONFIG en index.html")
        sys.exit(1)

    if url and not url.startswith("https://"):
        print("[ERROR] La URL debe empezar por https://  (ej: https://abcd.supabase.co)")
        sys.exit(1)
    rol = _rol_jwt(key)
    if rol and rol != "anon":
        print(f"[ERROR] Esa clave tiene el rol '{rol}', no 'anon'.")
        print("        Usa la clave 'anon public' de Project Settings > API.")
        print("        La service_role NUNCA debe ir en el frontend: da acceso")
        print("        total a la base de datos a cualquiera que vea el codigo.")
        sys.exit(1)

    copia = INDEX.with_suffix(f".backup-{datetime.now():%Y%m%d-%H%M%S}.html")
    shutil.copy2(INDEX, copia)

    html = RE_URL.sub(lambda m: f"{m.group(1)}'{url}'", html, count=1)
    html = RE_KEY.sub(lambda m: f"{m.group(1)}'{key}'", html, count=1)
    INDEX.write_text(html, encoding="utf-8")

    print(f"[OK] index.html actualizado.  Copia de seguridad: {copia.name}")
    if url and key:
        print("     La web ya consultara Supabase en lugar de mock-data.json.")
    else:
        print("     Vuelto al modo demostracion.")


def _rol_jwt(jwt: str) -> str:
    """Extrae el claim `role` de un JWT de Supabase. Devuelve '' si no aplica."""
    import base64
    import json
    if not jwt or not jwt.startswith("eyJ") or jwt.count(".") != 2:
        return ""
    try:
        p = jwt.split(".")[1]
        p += "=" * (-len(p) % 4)
        datos = json.loads(base64.urlsafe_b64decode(p))
        return str(datos.get("role", ""))
    except Exception:
        return ""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    if args[0] == "--mostrar":
        return mostrar()
    if args[0] == "--estado":
        return estado_corto()
    if args[0] == "--limpiar":
        return escribir("", "")
    if len(args) < 2:
        print("[ERROR] Faltan argumentos. Uso: configurar_frontend.py <URL> <ANON_KEY>")
        sys.exit(1)
    escribir(args[0].strip(), args[1].strip())


if __name__ == "__main__":
    main()

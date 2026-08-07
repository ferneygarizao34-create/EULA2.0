"""
Eula - Control de Spotify (Fase 6b) - SIN necesidad de API/credenciales

Nota importante: desde febrero de 2026, Spotify exige que la cuenta
que registra una "app" de desarrollador tenga Premium activo, así que
la vía de la Web API (buscar y reproducir automáticamente) ya no es
viable con una cuenta gratis.

En su lugar, este módulo abre directamente la búsqueda en tu app de
Spotify usando su esquema de enlaces (spotify:search:...). Esto SÍ
funciona con cuenta gratis y no necesita ninguna credencial: solo
tienes que darle play al resultado que aparezca (no queda 100%
automático, pero es la opción que no cuesta nada).
"""

import webbrowser
import urllib.parse


def reproducir_cancion(nombre_cancion: str) -> str:
    """Abre la app de Spotify con la búsqueda de la canción lista.
    El usuario solo tiene que darle play al primer resultado."""
    if not nombre_cancion.strip():
        return "No entendí qué canción quieres poner."

    consulta = urllib.parse.quote(nombre_cancion)

    # El esquema spotify: abre la app de escritorio directamente si
    # está instalada. Si no la tiene abierta, la abre.
    uri_app = f"spotify:search:{consulta}"
    webbrowser.open(uri_app)

    return f"Te dejé la búsqueda de '{nombre_cancion}' lista en Spotify, dale play."

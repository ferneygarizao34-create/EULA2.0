"""
Eula - Módulo de comandos del sistema (Fase 3)

Contiene las acciones que Eula puede ejecutar directamente sobre tu
computadora: abrir aplicaciones, buscar archivos, decir la hora, etc.

Cada función de comando devuelve un string con lo que Eula debe decir
como resultado.
"""

import os
import sys
import subprocess
import webbrowser
import datetime
import glob

SISTEMA = sys.platform  # 'win32', 'darwin' (Mac), 'linux'

# Carpetas donde se buscan archivos, en orden de prioridad
CARPETAS_BUSQUEDA = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Escritorio"),
    os.path.expanduser("~/Documentos"),
    os.path.expanduser("~/Descargas"),
]

# Apps comunes: nombre que dices -> cómo abrirla en cada sistema
APPS = {
    "calculadora": {"win32": "calc.exe", "darwin": "Calculator", "linux": "gnome-calculator"},
    "bloc de notas": {"win32": "notepad.exe", "darwin": "TextEdit", "linux": "gedit"},
    "explorador de archivos": {"win32": "explorer.exe", "darwin": "Finder", "linux": "nautilus"},
    "word": {"win32": "winword.exe", "darwin": "Microsoft Word", "linux": "libreoffice --writer"},
    "excel": {"win32": "excel.exe", "darwin": "Microsoft Excel", "linux": "libreoffice --calc"},
    "spotify": {"win32": "spotify.exe", "darwin": "Spotify", "linux": "spotify"},
}


def abrir_aplicacion(nombre_app: str) -> str:
    """Intenta abrir una aplicación conocida por su nombre."""
    nombre_app = nombre_app.lower().strip()

    if nombre_app in APPS:
        comando = APPS[nombre_app].get(SISTEMA)
        if not comando:
            return f"No sé cómo abrir {nombre_app} en este sistema operativo."
        try:
            if SISTEMA == "win32":
                os.startfile(comando) if comando.endswith(".exe") else subprocess.Popen(comando, shell=True)
            elif SISTEMA == "darwin":
                subprocess.Popen(["open", "-a", comando])
            else:
                subprocess.Popen(comando.split())
            return f"Abriendo {nombre_app}."
        except Exception as error:
            return f"No pude abrir {nombre_app}. Error: {error}"

    # Si no está en la lista conocida, intenta abrirlo como programa genérico (Windows)
    if SISTEMA == "win32":
        try:
            os.startfile(nombre_app)
            return f"Intentando abrir {nombre_app}."
        except Exception:
            pass

    return f"No conozco la aplicación '{nombre_app}'. Puedo abrir: {', '.join(APPS.keys())}."


def abrir_navegador(sitio: str = "") -> str:
    """Abre el navegador, opcionalmente en un sitio/búsqueda específica."""
    if sitio:
        url = sitio if sitio.startswith("http") else f"https://www.google.com/search?q={sitio}"
        webbrowser.open(url)
        return f"Buscando {sitio} en el navegador."
    webbrowser.open("https://www.google.com")
    return "Abriendo el navegador."


def buscar_archivo(nombre: str, max_resultados: int = 5) -> str:
    """Busca un archivo por nombre (parcial) en las carpetas comunes."""
    nombre = nombre.lower().strip()
    encontrados = []

    for carpeta in CARPETAS_BUSQUEDA:
        if not os.path.isdir(carpeta):
            continue
        patron = os.path.join(carpeta, "**", f"*{nombre}*")
        encontrados.extend(glob.glob(patron, recursive=True))
        if len(encontrados) >= max_resultados:
            break

    if not encontrados:
        return f"No encontré ningún archivo que contenga '{nombre}' en tus carpetas principales."

    encontrados = encontrados[:max_resultados]
    lista = "; ".join(os.path.basename(f) for f in encontrados)
    return f"Encontré {len(encontrados)} archivo(s): {lista}."


def decir_hora() -> str:
    ahora = datetime.datetime.now().strftime("%I:%M %p")
    return f"Son las {ahora}."


def decir_fecha() -> str:
    hoy = datetime.datetime.now().strftime("%A %d de %B de %Y")
    return f"Hoy es {hoy}."


def abrir_carpeta(nombre_carpeta: str) -> str:
    """Abre una carpeta común (descargas, documentos, escritorio)."""
    mapa = {
        "descargas": ["~/Downloads", "~/Descargas"],
        "documentos": ["~/Documents", "~/Documentos"],
        "escritorio": ["~/Desktop", "~/Escritorio"],
    }
    nombre_carpeta = nombre_carpeta.lower().strip()

    for clave, rutas in mapa.items():
        if clave in nombre_carpeta:
            for ruta in rutas:
                ruta_completa = os.path.expanduser(ruta)
                if os.path.isdir(ruta_completa):
                    if SISTEMA == "win32":
                        os.startfile(ruta_completa)
                    elif SISTEMA == "darwin":
                        subprocess.Popen(["open", ruta_completa])
                    else:
                        subprocess.Popen(["xdg-open", ruta_completa])
                    return f"Abriendo la carpeta de {clave}."
    return f"No encontré la carpeta '{nombre_carpeta}'."


# ---------------------------------------------------------
# Interpretación de comandos: texto hablado -> acción
# ---------------------------------------------------------

def interpretar_comando(texto: str):
    """Revisa si el texto es un comando conocido. Si lo es, lo ejecuta
    y devuelve la respuesta (string). Si no es un comando, devuelve None
    (y el texto se manda a la IA como conversación normal)."""
    texto_normalizado = texto.lower().strip()

    if texto_normalizado.startswith("abre ") or texto_normalizado.startswith("abrir "):
        objetivo = texto_normalizado.split(" ", 1)[1].strip()
        if "carpeta de" in objetivo or objetivo in ("descargas", "documentos", "escritorio"):
            return abrir_carpeta(objetivo)
        if objetivo in ("el navegador", "navegador", "chrome", "internet"):
            return abrir_navegador()
        return abrir_aplicacion(objetivo)

    if texto_normalizado.startswith("busca ") and "archivo" in texto_normalizado:
        # ej: "busca el archivo presupuesto" -> nombre = "presupuesto"
        partes = texto_normalizado.replace("archivo", "").split(" ")
        nombre = " ".join(p for p in partes if p not in ("busca", "el", "la", "un", "una", ""))
        return buscar_archivo(nombre)

    if texto_normalizado.startswith("busca en internet") or texto_normalizado.startswith("busca en google"):
        consulta = texto_normalizado.split("google" if "google" in texto_normalizado else "internet", 1)[1].strip()
        return abrir_navegador(consulta)

    if texto_normalizado.startswith("pon ") and ("spotify" in texto_normalizado or "canción" in texto_normalizado or "cancion" in texto_normalizado):
        from spotify_control import reproducir_cancion
        cancion = texto_normalizado.replace("en spotify", "").replace("la canción", "").replace("la cancion", "")
        cancion = cancion.replace("pon ", "", 1).strip()
        return reproducir_cancion(cancion)

    if "qué hora es" in texto_normalizado or "que hora es" in texto_normalizado:
        return decir_hora()

    if "qué día es" in texto_normalizado or "que dia es" in texto_normalizado or "qué fecha es" in texto_normalizado:
        return decir_fecha()

    return None  # no es un comando, que lo maneje la IA

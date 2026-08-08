"""
Eula - Cerebro en la nube (Fase 9: Claude + Gemini de respaldo)

Eula ahora piensa principalmente con Claude (Anthropic), y si Claude
falla por cualquier motivo (se acaban los créditos gratis de prueba,
límite de uso, error de conexión, etc.) cae automáticamente a Gemini
(Google), que se mantiene como respaldo gratuito de por vida.

Desde esta versión, además de texto, Eula puede recibir imágenes y
documentos (PDF, TXT) adjuntos y "verlos"/"leerlos" gracias a que
Gemini es multimodal. Los adjuntos se mandan directo a Gemini (Claude
también soporta imágenes, pero para no duplicar esa lógica dos veces
se dejó centralizada ahí; si más adelante quieres que Claude también
vea imágenes, se puede agregar).

Gemini conserva la búsqueda de Google activada ("grounding"): antes
de responder, puede buscar en internet para verificar datos actuales
en vez de adivinar solo con lo que aprendió en su entrenamiento.

Requiere las variables de entorno:
  ANTHROPIC_API_KEY  -> tu clave de platform.claude.com
  GEMINI_API_KEY     -> tu clave de aistudio.google.com (respaldo)
"""

import os
import anthropic
from google import genai
from google.genai import types

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Modelo de Claude a usar. Haiku 4.5 es el más económico -> ideal
# mientras tengas créditos de prueba limitados. Si más adelante
# quieres más calidad y no te importa gastar más rápido, cambia a
# "claude-sonnet-5".
MODELO_CLAUDE = "claude-haiku-4-5-20251001"

# Modelo de Gemini de respaldo, vigente y gratuito (agosto 2026).
# Si en el futuro da 404, entra a aistudio.google.com y copia el
# nombre exacto del modelo Flash-Lite que te muestre ahí como
# disponible.
MODELO_GEMINI = "gemini-3.5-flash-lite"

# Tipos de archivo que Gemini puede interpretar de forma nativa.
MIME_SOPORTADOS = {
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
    "application/pdf", "text/plain",
}

_cliente_claude = None
_cliente_gemini = None


def _obtener_cliente_claude():
    global _cliente_claude
    if _cliente_claude is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("Falta la variable de entorno ANTHROPIC_API_KEY.")
        _cliente_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _cliente_claude


def _obtener_cliente_gemini():
    global _cliente_gemini
    if _cliente_gemini is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")
        _cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)
    return _cliente_gemini


def _consultar_claude(pregunta: str, personalidad: str) -> str:
    cliente = _obtener_cliente_claude()
    mensaje = cliente.messages.create(
        model=MODELO_CLAUDE,
        max_tokens=1024,
        system=personalidad,
        messages=[{"role": "user", "content": pregunta}],
    )
    partes_texto = [bloque.text for bloque in mensaje.content if bloque.type == "text"]
    return "".join(partes_texto).strip()


def _consultar_gemini(
    pregunta: str,
    personalidad: str,
    archivos: list[dict] | None,
    permitir_busqueda: bool,
) -> str:
    cliente = _obtener_cliente_gemini()

    partes: list = []
    for archivo in archivos or []:
        mime = archivo.get("mime", "application/octet-stream")
        partes.append(types.Part.from_bytes(data=archivo["datos"], mime_type=mime))

    texto_final = pregunta.strip() or "Describe u analiza el/los archivo(s) adjunto(s)."
    partes.append(texto_final)

    herramientas = [types.Tool(google_search=types.GoogleSearch())] if permitir_busqueda else None

    respuesta = cliente.models.generate_content(
        model=MODELO_GEMINI,
        contents=partes,
        config=types.GenerateContentConfig(
            system_instruction=personalidad,
            tools=herramientas,
        ),
    )
    return respuesta.text.strip()


def consultar_nube(
    pregunta: str,
    personalidad: str,
    archivos: list[dict] | None = None,
    permitir_busqueda: bool = True,
) -> str:
    """Manda la pregunta a Claude primero; si falla por lo que sea
    (créditos agotados, límite de uso, error de red, etc.) cae
    automáticamente a Gemini como respaldo, sin que el usuario note
    la diferencia salvo por el propio texto de la respuesta.

    Si hay archivos adjuntos, se salta Claude y va directo a Gemini
    (que ya tiene la lógica multimodal lista).

    'permitir_busqueda' solo aplica al respaldo de Gemini (Claude no
    tiene búsqueda propia en este código todavía).
    """
    if not pregunta.strip() and not archivos:
        raise ValueError("No hay ninguna pregunta ni archivo que mandar a la nube.")

    if archivos:
        return _consultar_gemini(pregunta, personalidad, archivos, permitir_busqueda)

    if ANTHROPIC_API_KEY:
        try:
            return _consultar_claude(pregunta, personalidad)
        except Exception as error:
            print(f"⚠️  Claude falló ({error!r}), usando Gemini de respaldo.")

    return _consultar_gemini(pregunta, personalidad, archivos, permitir_busqueda)

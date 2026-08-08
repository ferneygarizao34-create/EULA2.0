"""
Eula - Cerebro en la nube (Fase 8 + búsqueda en Google)

Este servidor ya NO usa un modelo local (Ollama/phi3): Eula piensa
enteramente con Gemini (Google), en la capa gratuita de Google AI
Studio (no pide tarjeta de crédito).

Desde esta versión, además de texto, Eula puede recibir imágenes y
documentos (PDF, TXT) adjuntos y "verlos"/"leerlos" gracias a que
Gemini es multimodal.

NOVEDAD: ahora Eula tiene activada la herramienta de búsqueda de
Google ("grounding"). Antes de responder, el modelo puede buscar en
internet para verificar datos actuales (resultados deportivos,
noticias, precios, fechas, etc.) en vez de adivinar solo con lo que
aprendió en su entrenamiento. Esto reduce mucho las respuestas
desactualizadas o inventadas.

Requiere la variable de entorno GEMINI_API_KEY.
"""

import os
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODELO_NUBE = "gemini-3.5-flash-lite"

# Tipos de archivo que Gemini puede interpretar de forma nativa.
# Cualquier otro tipo se manda igual, pero puede que Gemini no lo
# entienda bien (por ejemplo un .docx no es texto plano ni un formato
# nativo del modelo).
MIME_SOPORTADOS = {
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
    "application/pdf", "text/plain",
}

_cliente = None


def _obtener_cliente():
    global _cliente
    if _cliente is None:
        if not API_KEY:
            raise RuntimeError(
                "Falta la variable de entorno GEMINI_API_KEY. Consigue una "
                "gratis en aistudio.google.com y configúrala en tu hosting."
            )
        _cliente = genai.Client(api_key=API_KEY)
    return _cliente


def consultar_nube(
    pregunta: str,
    personalidad: str,
    archivos: list[dict] | None = None,
    permitir_busqueda: bool = True,
) -> str:
    """Manda la pregunta (con el contexto ya incluido como texto) a
    Gemini y devuelve la respuesta como texto.

    'archivos' es opcional: una lista de dicts con
      {"mime": "image/png", "datos": <bytes>, "nombre": "foto.png"}
    Solo se adjuntan en el turno actual (no se guardan en la memoria
    persistente en JSON para no inflar el archivo).

    'permitir_busqueda' activa la herramienta de Google Search para
    que el modelo verifique datos reales antes de responder. Se deja
    como parámetro (en vez de fijo) por si en algún caso puntual
    quieres desactivarla (por ejemplo, para ahorrar latencia en un
    saludo simple), pero por defecto siempre va activada.
    """
    if not pregunta.strip() and not archivos:
        raise ValueError("No hay ninguna pregunta ni archivo que mandar a la nube.")

    cliente = _obtener_cliente()

    partes: list = []
    for archivo in archivos or []:
        mime = archivo.get("mime", "application/octet-stream")
        partes.append(types.Part.from_bytes(data=archivo["datos"], mime_type=mime))

    texto_final = pregunta.strip() or "Describe u analiza el/los archivo(s) adjunto(s)."
    partes.append(texto_final)

    herramientas = [types.Tool(google_search=types.GoogleSearch())] if permitir_busqueda else None

    respuesta = cliente.models.generate_content(
        model=MODELO_NUBE,
        contents=partes,
        config=types.GenerateContentConfig(
            system_instruction=personalidad,
            tools=herramientas,
        ),
    )
    return respuesta.text.strip()

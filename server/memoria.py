"""
Eula - Memoria persistente multi-chat (Fase 9: chats separados)

Guarda TODAS las conversaciones en un único archivo memoria.json, cada
una identificada por un id único (uuid), con su propio título e
historial de mensajes. Así el navegador puede mostrar una lista de
chats guardados (como ChatGPT/Claude) y cambiar entre ellos.

Nota: en el plan gratuito de Render, el disco no es permanente — si el
servicio se reinicia o se redespliega, este archivo se borra. Para
memoria que sobreviva reinicios habría que usar una base de datos
externa; por ahora se mantiene igual que las fases anteriores (JSON
en disco), solo que ahora con varios chats en vez de uno.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

RUTA_MEMORIA = Path(__file__).parent / "memoria.json"
MAX_MENSAJES_CONTEXTO = 20  # cuántos mensajes recientes se mandan a Gemini como contexto
LARGO_TITULO = 40


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _leer_archivo() -> dict:
    if not RUTA_MEMORIA.exists():
        return {"chats": {}}
    try:
        with open(RUTA_MEMORIA, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "chats" not in data:
                data = {"chats": {}}
            return data
    except (json.JSONDecodeError, OSError):
        return {"chats": {}}


def _escribir_archivo(data: dict) -> None:
    with open(RUTA_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def listar_chats() -> list:
    """Devuelve todos los chats guardados (sin sus mensajes, solo el
    resumen), ordenados del más reciente al más viejo."""
    data = _leer_archivo()
    resumen = [
        {"id": chat_id, "titulo": chat.get("titulo", "Nuevo chat"), "actualizado": chat.get("actualizado", "")}
        for chat_id, chat in data["chats"].items()
    ]
    resumen.sort(key=lambda c: c["actualizado"], reverse=True)
    return resumen


def crear_chat() -> dict:
    """Crea un chat nuevo vacío y lo guarda. Devuelve {id, titulo}."""
    data = _leer_archivo()
    chat_id = uuid.uuid4().hex[:12]
    data["chats"][chat_id] = {
        "titulo": "Nuevo chat",
        "actualizado": _ahora(),
        "historial": [],
    }
    _escribir_archivo(data)
    return {"id": chat_id, "titulo": "Nuevo chat"}


def existe_chat(chat_id: str) -> bool:
    data = _leer_archivo()
    return chat_id in data["chats"]


def cargar_historial_chat(chat_id: str, mensaje_sistema: dict) -> list:
    """Carga el historial de un chat (con el mensaje de sistema al
    principio). Si el chat no existe todavía, lo crea vacío."""
    data = _leer_archivo()
    if chat_id not in data["chats"]:
        data["chats"][chat_id] = {"titulo": "Nuevo chat", "actualizado": _ahora(), "historial": []}
        _escribir_archivo(data)

    guardado = data["chats"][chat_id]["historial"]
    return [mensaje_sistema] + guardado


def guardar_historial_chat(chat_id: str, historial_completo: list) -> None:
    """Guarda el historial de un chat (recibe la lista completa,
    incluyendo el mensaje de sistema en la posición 0, que NO se
    guarda en disco)."""
    data = _leer_archivo()
    if chat_id not in data["chats"]:
        data["chats"][chat_id] = {"titulo": "Nuevo chat", "actualizado": _ahora(), "historial": []}

    data["chats"][chat_id]["historial"] = historial_completo[1:]  # sin el mensaje de sistema
    data["chats"][chat_id]["actualizado"] = _ahora()
    _escribir_archivo(data)


def renombrar_chat_si_es_nuevo(chat_id: str, primer_mensaje: str) -> Optional[str]:
    """Si el chat todavía tiene el título por defecto 'Nuevo chat', lo
    renombra usando el primer mensaje del usuario (recortado). Devuelve
    el título nuevo, o None si no hizo falta cambiarlo."""
    data = _leer_archivo()
    chat = data["chats"].get(chat_id)
    if not chat or chat.get("titulo") != "Nuevo chat":
        return None

    titulo = primer_mensaje.strip().replace("\n", " ")
    if len(titulo) > LARGO_TITULO:
        titulo = titulo[:LARGO_TITULO].rstrip() + "…"
    if not titulo:
        titulo = "Nuevo chat"

    chat["titulo"] = titulo
    _escribir_archivo(data)
    return titulo


def eliminar_chat(chat_id: str) -> None:
    data = _leer_archivo()
    data["chats"].pop(chat_id, None)
    _escribir_archivo(data)


def vaciar_chat(chat_id: str) -> None:
    """Borra los mensajes de un chat pero mantiene el chat (y su id)."""
    data = _leer_archivo()
    if chat_id in data["chats"]:
        data["chats"][chat_id]["historial"] = []
        data["chats"][chat_id]["actualizado"] = _ahora()
        _escribir_archivo(data)


def recortar_contexto(historial: list) -> list:
    """Si la conversación ya es muy larga, se queda solo con el
    mensaje de sistema + los últimos MAX_MENSAJES_CONTEXTO mensajes,
    para no mandarle a Gemini un contexto gigante innecesariamente."""
    if len(historial) <= MAX_MENSAJES_CONTEXTO + 1:
        return historial
    return [historial[0]] + historial[-MAX_MENSAJES_CONTEXTO:]

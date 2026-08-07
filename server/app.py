"""
Eula - Servidor en la nube (Fase 8: versión web)

Corre en un servidor (ej. Render) y expone:

- Una página web con chat + voz (Web Speech API del navegador) para
  hablar con Eula desde cualquier lado, incluyendo adjuntar imágenes
  y documentos.
- Un WebSocket (/ws/agente) para que el "agente local" que corre en
  tu PC reciba comandos del sistema y los ejecute ahí, ya que el
  servidor en la nube no tiene acceso a tu computadora.

Eula ahora piensa con Gemini (Google) en vez de un modelo local.
"""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cerebro_nube import consultar_nube
from memoria import cargar_historial, guardar_historial, recortar_contexto, olvidar_todo

NOMBRE_ASISTENTE = "Eula"
TOKEN_WEB = os.environ.get("EULA_TOKEN", "cambia-esto")
TOKEN_AGENTE = os.environ.get("EULA_AGENTE_TOKEN", "cambia-esto-tambien")

# Límite de tamaño por archivo adjunto (en bytes) antes de decodificar.
# Protege al servidor de mensajes gigantes; el frontend también valida.
MAX_BYTES_POR_ARCHIVO = 10 * 1024 * 1024  # 10 MB

PERSONALIDAD = f"""Eres {NOMBRE_ASISTENTE}, un asistente de IA personal
inspirado en JARVIS y Karen. Eres servicial, directo, un poco ingenioso,
y te diriges al usuario con confianza. Responde SIEMPRE de forma breve
(1 a 3 oraciones), porque tu respuesta puede leerse en voz alta. Si el
usuario adjunta una imagen o documento, coméntalo con naturalidad."""

MENSAJE_SISTEMA = {"role": "system", "content": PERSONALIDAD}

app = FastAPI(title="Eula")

# --- Estado del agente local conectado (soporta un usuario/agente) ---
agente_ws: Optional[WebSocket] = None
agente_respuestas: dict[str, asyncio.Future] = {}
_contador_peticiones = 0


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.websocket("/ws/agente")
async def ws_agente(websocket: WebSocket, token: str = Query(...)):
    """El agente local (tu PC) se conecta acá y se queda escuchando."""
    global agente_ws
    if token != TOKEN_AGENTE:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    agente_ws = websocket
    print("✅ Agente local conectado.")

    try:
        while True:
            data = await websocket.receive_json()
            id_peticion = data.get("id")
            futuro = agente_respuestas.pop(id_peticion, None)
            if futuro and not futuro.done():
                futuro.set_result(data)
    except WebSocketDisconnect:
        agente_ws = None
        print("⚠️  Agente local desconectado.")


async def pedir_al_agente(texto: str, tiempo_espera: float = 4.0) -> Optional[str]:
    """Le pregunta al agente local si el texto es un comando conocido.
    Devuelve el resultado (string) o None si no es un comando, si el
    agente no está conectado, o si no respondió a tiempo."""
    global _contador_peticiones

    if agente_ws is None:
        return None

    _contador_peticiones += 1
    id_peticion = str(_contador_peticiones)
    futuro = asyncio.get_event_loop().create_future()
    agente_respuestas[id_peticion] = futuro

    try:
        await agente_ws.send_json({"id": id_peticion, "texto": texto})
        data = await asyncio.wait_for(futuro, timeout=tiempo_espera)
    except Exception:
        agente_respuestas.pop(id_peticion, None)
        return None

    if data.get("tipo") == "comando":
        return data.get("resultado")
    return None


def _construir_prompt_con_contexto(historial: list) -> str:
    """Convierte el historial reciente en un texto plano que se le
    manda a Gemini junto con la personalidad como instrucción de
    sistema (así Eula recuerda lo hablado en la sesión)."""
    mensajes = recortar_contexto(historial)[1:]  # sin el mensaje de sistema
    lineas = []
    for m in mensajes:
        quien = "Usuario" if m["role"] == "user" else NOMBRE_ASISTENTE
        lineas.append(f"{quien}: {m['content']}")
    return "\n".join(lineas)


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, token: str = Query(...)):
    """El navegador se conecta acá para chatear/hablar con Eula.

    El navegador manda cada mensaje como JSON:
      {"texto": "...", "archivos": [{"nombre": "foto.png", "mime": "image/png", "datos": "<base64>"}]}
    ('archivos' es opcional). Por compatibilidad, si llega texto plano
    (no JSON), se trata como si fuera solo el campo 'texto'.
    """
    if token != TOKEN_WEB:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    historial = cargar_historial(MENSAJE_SISTEMA)

    try:
        while True:
            mensaje_crudo = await websocket.receive_text()

            try:
                data = json.loads(mensaje_crudo)
                if not isinstance(data, dict):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                data = {"texto": mensaje_crudo}

            texto_usuario = (data.get("texto") or "").strip()
            adjuntos_entrantes = data.get("archivos") or []

            if not texto_usuario and not adjuntos_entrantes:
                continue

            if texto_usuario.lower() in ("olvida todo", "borra la memoria"):
                olvidar_todo()
                historial = [MENSAJE_SISTEMA]
                await websocket.send_text("Listo, olvidé todo lo que hablamos antes.")
                continue

            # 1. ¿Es un comando de sistema? (solo aplica a mensajes de puro texto)
            if not adjuntos_entrantes:
                resultado_comando = await pedir_al_agente(texto_usuario)
                if resultado_comando is not None:
                    await websocket.send_text(resultado_comando)
                    continue

            # 2. Decodificar adjuntos (si los hay) para mandárselos a Gemini.
            archivos_para_gemini = []
            nombres_adjuntos = []
            for adjunto in adjuntos_entrantes:
                try:
                    datos_binarios = base64.b64decode(adjunto.get("datos", ""), validate=True)
                except Exception:
                    continue
                if len(datos_binarios) > MAX_BYTES_POR_ARCHIVO:
                    await websocket.send_text(
                        f"El archivo '{adjunto.get('nombre', 'sin nombre')}' pesa demasiado (máx. 10 MB)."
                    )
                    continue
                archivos_para_gemini.append({
                    "mime": adjunto.get("mime", "application/octet-stream"),
                    "datos": datos_binarios,
                    "nombre": adjunto.get("nombre", "archivo"),
                })
                nombres_adjuntos.append(adjunto.get("nombre", "archivo"))

            # 3. Conversación normal -> Gemini, con el historial como contexto.
            #    Los archivos solo se mandan en el turno actual: no se guardan
            #    en memoria.json para no inflar el historial persistente.
            texto_para_memoria = texto_usuario
            if nombres_adjuntos:
                etiqueta = f"[adjuntó: {', '.join(nombres_adjuntos)}]"
                texto_para_memoria = f"{texto_usuario} {etiqueta}".strip() if texto_usuario else etiqueta

            historial.append({"role": "user", "content": texto_para_memoria})
            try:
                prompt = _construir_prompt_con_contexto(historial)
                respuesta = consultar_nube(prompt, PERSONALIDAD, archivos_para_gemini or None)
            except Exception as error:
                respuesta = f"Tuve un problema para pensar la respuesta: {error}"

            historial.append({"role": "assistant", "content": respuesta})
            guardar_historial(historial)
            await websocket.send_text(respuesta)

    except WebSocketDisconnect:
        pass


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

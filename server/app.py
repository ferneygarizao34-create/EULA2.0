"""
Eula - Servidor en la nube (Fase 9: chats múltiples + agente local)

Corre en un servidor (ej. Render) y expone:

- Una página web con chat + voz para hablar con Eula desde cualquier
  lado, con varios chats guardados en paralelo (como ChatGPT/Claude).
- Un WebSocket (/ws/agente) para que el "agente local" que corre en
  tu PC reciba comandos del sistema y los ejecute ahí.
- Endpoints REST (/api/chats) para listar, crear y borrar chats.

Eula piensa con Gemini (Google).
"""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cerebro_nube import consultar_nube
from memoria import (
    listar_chats,
    crear_chat,
    cargar_historial_chat,
    guardar_historial_chat,
    renombrar_chat_si_es_nuevo,
    eliminar_chat,
    vaciar_chat,
    recortar_contexto,
)

NOMBRE_ASISTENTE = "Eula"
TOKEN_WEB = os.environ.get("EULA_TOKEN", "cambia-esto")
TOKEN_AGENTE = os.environ.get("EULA_AGENTE_TOKEN", "cambia-esto-tambien")

MAX_BYTES_POR_ARCHIVO = 10 * 1024 * 1024  # 10 MB por archivo adjunto

PERSONALIDAD = f"""Eres {NOMBRE_ASISTENTE}, un asistente de IA personal
inspirado en JARVIS y Karen. Eres servicial, directo, un poco ingenioso,
y te diriges al usuario con confianza. Responde SIEMPRE de forma breve
(1 a 3 oraciones), porque tu respuesta puede leerse en voz alta. Si el
usuario adjunta una imagen o documento, coméntalo con naturalidad."""

MENSAJE_SISTEMA = {"role": "system", "content": PERSONALIDAD}

app = FastAPI(title="Eula")

# --- Estado del agente local conectado ---
agente_ws: Optional[WebSocket] = None
agente_respuestas: dict[str, asyncio.Future] = {}
_contador_peticiones = 0


def _verificar_token_web(token: str) -> None:
    if token != TOKEN_WEB:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ---------------------------------------------------------
# API REST de chats (listar / crear / borrar / vaciar)
# ---------------------------------------------------------

@app.get("/api/chats")
def api_listar_chats(token: str):
    _verificar_token_web(token)
    return listar_chats()


@app.post("/api/chats")
def api_crear_chat(token: str):
    _verificar_token_web(token)
    return crear_chat()


@app.delete("/api/chats/{chat_id}")
def api_eliminar_chat(chat_id: str, token: str):
    _verificar_token_web(token)
    eliminar_chat(chat_id)
    return {"ok": True}


@app.post("/api/chats/{chat_id}/vaciar")
def api_vaciar_chat(chat_id: str, token: str):
    _verificar_token_web(token)
    vaciar_chat(chat_id)
    return {"ok": True}


# ---------------------------------------------------------
# WebSocket del agente local (comandos del sistema en tu PC)
# ---------------------------------------------------------

@app.websocket("/ws/agente")
async def ws_agente(websocket: WebSocket, token: str = Query(...)):
    global agente_ws
    if token != TOKEN_AGENTE:
        print(f"🚫 Agente rechazado: token incorrecto ({token!r}).")
        await websocket.close(code=4401)
        return

    await websocket.accept()
    agente_ws = websocket
    print("✅ Agente local conectado. (agente_ws asignado)")

    try:
        while True:
            data = await websocket.receive_json()
            print(f"📬 Respuesta recibida del agente local: {data}")
            id_peticion = data.get("id")
            futuro = agente_respuestas.pop(id_peticion, None)
            if futuro and not futuro.done():
                futuro.set_result(data)
            else:
                print(f"⚠️  No había ninguna petición esperando el id {id_peticion!r} (¿llegó tarde?).")
    except WebSocketDisconnect:
        agente_ws = None
        print("⚠️  Agente local desconectado. (agente_ws = None)")


async def pedir_al_agente(texto: str, tiempo_espera: float = 4.0) -> Optional[str]:
    global _contador_peticiones

    if agente_ws is None:
        print(f"⏭️  pedir_al_agente: no hay agente conectado para texto={texto!r}. Se manda directo a Gemini.")
        return None

    _contador_peticiones += 1
    id_peticion = str(_contador_peticiones)
    futuro = asyncio.get_event_loop().create_future()
    agente_respuestas[id_peticion] = futuro

    print(f"📤 Mandando al agente local -> id={id_peticion} texto={texto!r}")

    try:
        await agente_ws.send_json({"id": id_peticion, "texto": texto})
        data = await asyncio.wait_for(futuro, timeout=tiempo_espera)
    except Exception as error:
        print(f"⏱️  pedir_al_agente: sin respuesta a tiempo para id={id_peticion}: {error!r}")
        agente_respuestas.pop(id_peticion, None)
        return None

    print(f"📥 pedir_al_agente: respuesta del agente para id={id_peticion}: {data}")
    if data.get("tipo") == "comando":
        return data.get("resultado")
    return None


def _construir_prompt_con_contexto(historial: list) -> str:
    mensajes = recortar_contexto(historial)[1:]  # sin el mensaje de sistema
    lineas = []
    for m in mensajes:
        quien = "Usuario" if m["role"] == "user" else NOMBRE_ASISTENTE
        lineas.append(f"{quien}: {m['content']}")
    return "\n".join(lineas)


# ---------------------------------------------------------
# WebSocket del chat web (ahora con chat_id)
# ---------------------------------------------------------

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, token: str = Query(...), chat_id: str = Query(...)):
    """El navegador se conecta acá para chatear/hablar con Eula.

    Cada mensaje del navegador es JSON:
      {"texto": "...", "archivos": [{"nombre", "mime", "datos"}]}

    'chat_id' identifica a qué conversación guardada pertenece este
    WebSocket (el navegador se reconecta con un chat_id distinto cada
    vez que el usuario cambia de chat en la barra lateral).
    """
    if token != TOKEN_WEB:
        print(f"🚫 Chat rechazado: token incorrecto ({token!r}).")
        await websocket.close(code=4401)
        return

    await websocket.accept()
    print(f"✅ Navegador conectado a /ws/chat (chat_id={chat_id}).")
    historial = cargar_historial_chat(chat_id, MENSAJE_SISTEMA)

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

            print(f"💬 [{chat_id}] Mensaje del navegador: texto={texto_usuario!r} archivos={len(adjuntos_entrantes)} | agente conectado: {agente_ws is not None}")

            if not texto_usuario and not adjuntos_entrantes:
                continue

            if texto_usuario.lower() in ("olvida todo", "borra la memoria", "borra este chat"):
                vaciar_chat(chat_id)
                historial = [MENSAJE_SISTEMA]
                await websocket.send_text(json.dumps({"tipo": "texto", "texto": "Listo, borré esta conversación."}))
                continue

            # 1. ¿Es un comando de sistema? (solo si no hay archivos adjuntos)
            if not adjuntos_entrantes:
                resultado_comando = await pedir_al_agente(texto_usuario)
                if resultado_comando is not None:
                    historial.append({"role": "user", "content": texto_usuario})
                    historial.append({"role": "assistant", "content": resultado_comando})
                    guardar_historial_chat(chat_id, historial)
                    titulo_nuevo = renombrar_chat_si_es_nuevo(chat_id, texto_usuario)
                    await websocket.send_text(json.dumps({
                        "tipo": "texto", "texto": resultado_comando, "titulo_nuevo": titulo_nuevo,
                    }))
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
                    await websocket.send_text(json.dumps({
                        "tipo": "texto",
                        "texto": f"El archivo '{adjunto.get('nombre', 'sin nombre')}' pesa demasiado (máx. 10 MB).",
                    }))
                    continue
                archivos_para_gemini.append({
                    "mime": adjunto.get("mime", "application/octet-stream"),
                    "datos": datos_binarios,
                    "nombre": adjunto.get("nombre", "archivo"),
                })
                nombres_adjuntos.append(adjunto.get("nombre", "archivo"))

            # 3. Conversación normal -> Gemini, con el historial como contexto.
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
            guardar_historial_chat(chat_id, historial)
            titulo_nuevo = renombrar_chat_si_es_nuevo(chat_id, texto_usuario or "Archivo adjunto")

            await websocket.send_text(json.dumps({
                "tipo": "texto", "texto": respuesta, "titulo_nuevo": titulo_nuevo,
            }))

    except WebSocketDisconnect:
        print(f"⚠️  Navegador desconectado de /ws/chat (chat_id={chat_id}).")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

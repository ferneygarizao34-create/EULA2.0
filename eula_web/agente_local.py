"""
Eula - Agente local (Fase 8: versión web)

Este script corre en TU computadora (no en el servidor). Se conecta
al servidor web por WebSocket y se queda escuchando: cuando le llega
un texto desde el navegador, revisa si es un comando conocido
(usando comandos.py) y si lo es, lo ejecuta ahí mismo en tu PC y
manda el resultado de vuelta al servidor.

Así es como "abre calculadora" dicho desde el navegador termina
abriendo la calculadora de tu computadora real.

Requiere las variables de entorno:
  EULA_SERVIDOR_WS   -> ej. wss://tu-servidor.onrender.com/ws/agente
  EULA_AGENTE_TOKEN  -> el mismo valor que pusiste en Render

Requiere: pip install -r requirements_agente.txt
"""

import asyncio
import os
import sys
import websockets

from comandos import interpretar_comando

SERVIDOR_WS = os.environ.get("EULA_SERVIDOR_WS", "")
TOKEN = os.environ.get("EULA_AGENTE_TOKEN", "")

RECONEXION_SEGUNDOS = 5


def _validar_configuracion() -> None:
    faltantes = []
    if not SERVIDOR_WS:
        faltantes.append("EULA_SERVIDOR_WS")
    if not TOKEN:
        faltantes.append("EULA_AGENTE_TOKEN")
    if faltantes:
        print(f"⚠️  Faltan estas variables de entorno: {', '.join(faltantes)}")
        print("   Configúralas antes de correr el agente (ver README_WEB.md).")
        sys.exit(1)


async def _procesar_mensajes(conexion) -> None:
    async for mensaje_crudo in conexion:
        import json
        try:
            data = json.loads(mensaje_crudo)
        except json.JSONDecodeError:
            continue

        id_peticion = data.get("id")
        texto = data.get("texto", "")

        print(f"📩 Comando recibido: {texto}")

        try:
            resultado = interpretar_comando(texto)
        except Exception as error:
            resultado = f"Tuve un error ejecutando eso en tu PC: {error}"

        respuesta = {
            "id": id_peticion,
            "tipo": "comando" if resultado is not None else "no_comando",
            "resultado": resultado,
        }
        await conexion.send(__import__("json").dumps(respuesta))

        if resultado is not None:
            print(f"✅ Ejecutado: {resultado}")
        else:
            print("↪️  No era un comando de sistema, el servidor lo maneja con la IA.")


async def correr_agente() -> None:
    _validar_configuracion()
    url = f"{SERVIDOR_WS}?token={TOKEN}"

    while True:
        try:
            print("🔌 Conectando al servidor de Eula...")
            async with websockets.connect(url) as conexion:
                print("✅ Conectado. Esperando comandos desde el navegador...")
                await _procesar_mensajes(conexion)
        except (websockets.exceptions.ConnectionClosed, OSError) as error:
            print(f"⚠️  Se perdió la conexión ({error}). Reintentando en {RECONEXION_SEGUNDOS}s...")
            await asyncio.sleep(RECONEXION_SEGUNDOS)
        except KeyboardInterrupt:
            print("👋 Agente detenido.")
            break


if __name__ == "__main__":
    asyncio.run(correr_agente())

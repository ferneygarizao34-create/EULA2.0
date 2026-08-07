"""
Eula - Módulo de memoria persistente (Fase 4)

Guarda y carga el historial de conversación en un archivo JSON,
para que Eula recuerde lo hablado incluso después de cerrar el programa.
"""

import json
import os

ARCHIVO_MEMORIA = os.path.join(os.path.dirname(__file__), "memoria.json")

# Cuántos mensajes recientes se mandan a la IA como contexto.
# (menos mensajes = respuestas más rápidas, pero Eula "recuerda" menos
# de la conversación actual; con phi3 en equipos de 8GB, 8 es un buen balance)
MAX_MENSAJES_CONTEXTO = 8


def cargar_historial(mensaje_sistema: dict) -> list:
    """Carga el historial guardado, o crea uno nuevo si no existe."""
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                historial_guardado = json.load(f)
            # Siempre nos aseguramos de que el mensaje de sistema esté primero y actualizado
            sin_sistema = [m for m in historial_guardado if m.get("role") != "system"]
            return [mensaje_sistema] + sin_sistema
        except (json.JSONDecodeError, OSError):
            pass  # si el archivo está corrupto, empezamos de cero
    return [mensaje_sistema]


def guardar_historial(historial: list) -> None:
    """Guarda el historial completo en disco."""
    try:
        with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"⚠️  No pude guardar la memoria: {error}")


def recortar_contexto(historial: list) -> list:
    """Devuelve solo los últimos N mensajes (más el system) para mandarle
    a la IA, así no se vuelve lentísimo con meses de conversación."""
    mensaje_sistema = historial[0]
    resto = historial[1:]
    if len(resto) > MAX_MENSAJES_CONTEXTO:
        resto = resto[-MAX_MENSAJES_CONTEXTO:]
    return [mensaje_sistema] + resto


def olvidar_todo() -> None:
    """Borra la memoria guardada (para empezar de cero si se quiere)."""
    if os.path.exists(ARCHIVO_MEMORIA):
        os.remove(ARCHIVO_MEMORIA)

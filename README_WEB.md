# Eula en la nube — Fase 8 (versión web)

Eula ahora vive en un servidor web en vez de tu terminal, y piensa con
**Gemini** (ya no necesita Ollama ni un modelo local). Puedes chatear
y hablarle desde el navegador, desde cualquier dispositivo.

Como los comandos de sistema (abrir apps, buscar archivos) solo tienen
sentido en TU computadora, se mantiene un **agente local** pequeño que
corre en tu PC y se conecta al servidor para ejecutarlos.

```
Navegador (voz/texto) <--WebSocket--> Servidor en la nube (FastAPI + Gemini)
                                              |
                                       WebSocket
                                              |
                                     Agente local (tu PC)
                                     ejecuta comandos.py
```

## Estructura

```
eula_web/
├── server/                 # esto se despliega en la nube (Render)
│   ├── app.py               # servidor FastAPI (chat + WebSockets)
│   ├── cerebro_nube.py       # conexión con Gemini
│   ├── memoria.py            # memoria persistente (JSON)
│   ├── requirements.txt
│   └── static/
│       └── index.html        # la página web (chat + voz del navegador)
├── comandos.py              # esto se queda en TU PC
├── agente_local.py          # esto se queda en TU PC
├── requirements_agente.txt
└── render.yaml
```

## Paso 1 — Consigue tu API key de Gemini (gratis)

1. Entra a https://aistudio.google.com/apikey
2. Crea una API key gratuita (no pide tarjeta).
3. Guárdala, la necesitas en el paso 3.

## Paso 2 — Sube el proyecto a GitHub

Crea un repositorio nuevo y sube toda la carpeta `eula_web/` (o solo
`server/` si prefieres, pero deja `comandos.py` y `agente_local.py`
disponibles para descargarlos en tu PC después).

## Paso 3 — Despliega el servidor en Render (gratis)

1. Entra a https://render.com y crea una cuenta (gratis).
2. "New" → "Web Service" → conecta tu repositorio de GitHub.
3. Render debería detectar `render.yaml` automáticamente. Si no,
   configura a mano:
   - **Root directory:** `server`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. En la sección "Environment", agrega estas variables:
   - `GEMINI_API_KEY` → tu API key del paso 1
   - `EULA_TOKEN` → una contraseña que inventes (para entrar a la web)
   - `EULA_AGENTE_TOKEN` → otra contraseña distinta (para tu agente local)
5. Dale "Deploy". En unos minutos tendrás una URL tipo
   `https://eula-xxxx.onrender.com`.

> **Nota sobre el plan gratuito:** el servicio se "duerme" tras ~15
> minutos sin uso y tarda unos segundos en despertar la próxima vez
> que lo uses. Es normal, no es un error.

## Paso 4 — Abre Eula en tu navegador

Ve a `https://tu-servidor.onrender.com/?token=TU_EULA_TOKEN`
(usa el mismo valor que pusiste en `EULA_TOKEN`). Usa **Chrome**, que
es el navegador con mejor soporte para reconocimiento de voz.

Ya puedes escribirle o hablarle con el botón del micrófono — en este
punto Eula responde con Gemini, aunque todavía no puede ejecutar
comandos en tu PC (eso es el paso 5).

## Paso 5 — Corre el agente local en tu PC

Esto es lo que le da a Eula control sobre tu computadora otra vez.

1. En tu PC, en la carpeta con `agente_local.py` y `comandos.py`:
   ```bash
   pip install -r requirements_agente.txt
   ```
2. Configura las variables de entorno (cambia por tus valores reales):

   **Windows (PowerShell):**
   ```powershell
   $env:EULA_SERVIDOR_WS = "wss://tu-servidor.onrender.com/ws/agente"
   $env:EULA_AGENTE_TOKEN = "el-token-que-pusiste-en-render"
   python agente_local.py
   ```

   **Mac/Linux:**
   ```bash
   export EULA_SERVIDOR_WS="wss://tu-servidor.onrender.com/ws/agente"
   export EULA_AGENTE_TOKEN="el-token-que-pusiste-en-render"
   python agente_local.py
   ```
3. Deja esa ventana abierta. Mientras esté corriendo, si le dices a
   Eula "abre calculadora" o "qué hora es" desde la web, el agente lo
   ejecuta en tu PC y el resultado aparece/se dice en el navegador.

> Tip: crea un `.bat` (Windows) o `.sh` (Mac/Linux) parecido a
> `iniciar_eula.bat` de la versión anterior, pero que ponga las
> variables de entorno y corra `agente_local.py`, para no tener que
> escribir todo cada vez.

## Novedades de esta versión

- **Interfaz nueva** (`index.html`): una esfera futurista que cambia de
  color y ritmo según lo que Eula está haciendo (esperando, escuchando,
  pensando, hablando), con un layout de chat como el de Claude/ChatGPT.
- **Adjuntar imágenes y documentos**: con el botón del clip puedes
  mandarle a Eula una imagen (PNG/JPEG/WEBP) o un documento (PDF/TXT) y
  te comenta o analiza el contenido usando Gemini. Los archivos solo se
  usan en ese turno, no se guardan en `memoria.json`. Límite: 10 MB por
  archivo.
- Otros tipos de documento (por ejemplo `.docx`) se pueden adjuntar,
  pero Gemini puede no leerlos bien porque no son texto plano ni un
  formato nativo — para mejores resultados usa PDF, TXT o imágenes.

## Comandos especiales

- **"olvida todo"** o **"borra la memoria"** — borra la memoria guardada.

## Diferencias con la versión de terminal

- Ya no se usa Ollama/phi3 — Eula piensa 100% con Gemini.
- La voz ahora es la del navegador (Web Speech API), no Edge TTS ni
  pyttsx3 — es gratis pero suena un poco más robótica; si más adelante
  quieres la voz natural de Edge TTS, se puede agregar en el servidor.
- Ya no hay palabra de activación ("Eula, ...") porque en la web tú
  decides cuándo apretar el micrófono.
- El HUD visual (ventana flotante) no aplica en una versión web — la
  propia página hace ese rol mostrando el estado.

## Seguridad

`EULA_TOKEN` y `EULA_AGENTE_TOKEN` son lo único que evita que
cualquier persona en internet chatee con tu Eula o mande comandos a tu
PC. Trátalos como contraseñas: no los subas a GitHub, no los compartas,
y usa valores largos y difíciles de adivinar.

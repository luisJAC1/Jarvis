from flask import Flask, request, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
import gspread
import requests
import json
import os
import io

# Loads .env when running locally. Has no effect in Railway (vars set directly).
load_dotenv()

app = Flask(__name__)
# ProxyFix is required for ngrok and Railway — both sit behind a reverse proxy.
# Without it, request.url uses the wrong scheme (http) and Twilio validation fails.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# --- Environment variables ---
GEMINI_KEY          = os.environ.get("GEMINI_KEY")
GOOGLE_CREDS_JSON   = os.environ.get("GOOGLE_CREDS")
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
MI_NUMERO_WA        = os.environ.get("MI_NUMERO_WA")
TWILIO_WA_NUMBER    = os.environ.get("TWILIO_WA_NUMBER")

# --- Cached singletons ---
_sheets_spreadsheet = None
_gemini_client      = genai.Client(api_key=GEMINI_KEY)


# ─────────────────────────────────────────────
# GOOGLE SHEETS — connection + memory functions
# ─────────────────────────────────────────────

def get_sheets():
    global _sheets_spreadsheet
    if _sheets_spreadsheet is None:
        creds_json = json.loads(GOOGLE_CREDS_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        _sheets_spreadsheet = client.open("Memoria_Socio")
    return _sheets_spreadsheet


def guardar_en_sheet(categoria, dato):
    try:
        sheet = get_sheets()
        worksheet = sheet.worksheet(categoria.capitalize())
        existentes = worksheet.get_all_values()
        if any(dato.lower() in str(fila).lower() for fila in existentes):
            print(f"⚠️ El dato ya existe en {categoria}, saltando guardado.")
            return True
        worksheet.append_row([dato])
        return True
    except Exception as e:
        print(f"❌ Error en Google Sheets: {e}")
        return False


def eliminar_de_sheet(categoria, dato_a_borrar):
    try:
        sheet = get_sheets()
        worksheet = sheet.worksheet(categoria.capitalize())
        celda = worksheet.find(dato_a_borrar)
        if celda:
            worksheet.delete_rows(celda.row)
            return True
        return False
    except Exception as e:
        print(f"❌ Error al eliminar de Sheets: {e}")
        return False


def obtener_memoria_sheets():
    try:
        sheet = get_sheets()
        return {
            "perfil":  sheet.worksheet("Perfil").get_all_values(),
            "tareas":  sheet.worksheet("Tareas").get_all_values(),
            "eventos": sheet.worksheet("Eventos").get_all_values()
        }
    except Exception as e:
        print(f"Error leyendo Sheets: {e}")
        return {"perfil": [], "tareas": [], "eventos": []}


def actualizar_historial_sheets(rol, mensaje):
    try:
        sheet = get_sheets()
        sheet.worksheet("Historial").append_row([rol, mensaje])
    except Exception as e:
        print(f"Error al guardar historial: {e}")


def obtener_historial_reciente():
    try:
        sheet = get_sheets()
        filas = sheet.worksheet("Historial").get_all_values()
        ultimos = filas[-10:] if len(filas) > 10 else filas[1:]
        resultado = []
        for f in ultimos:
            role = "user" if f[0] in ("Alfaro", "Luis") else "model"
            resultado.append(types.Content(role=role, parts=[types.Part(text=f[1])]))
        return resultado
    except Exception as e:
        print(f"Error al obtener historial: {e}")
        return []


def formatear_memoria(memoria_datos):
    def filas_a_texto(filas):
        return [" ".join(c for c in fila if c).strip() for fila in filas if any(fila)]

    perfil  = filas_a_texto(memoria_datos.get("perfil", []))
    tareas  = filas_a_texto(memoria_datos.get("tareas", []))
    eventos = filas_a_texto(memoria_datos.get("eventos", []))

    return (
        "=== PERFIL (quién es Alfaro, gustos, amigos, instrucciones de personalidad) ===\n" +
        ("\n".join(f"- {p}" for p in perfil) if perfil else "(vacío)") +
        "\n\n=== TAREAS PENDIENTES ===\n" +
        ("\n".join(f"- {t}" for t in tareas) if tareas else "(vacío)") +
        "\n\n=== EVENTOS ===\n" +
        ("\n".join(f"- {e}" for e in eventos) if eventos else "(vacío)")
    )


def inferir_sheet(categoria_raw):
    c = categoria_raw.lower()
    if "tarea" in c or "pendiente" in c:
        return "Tareas"
    elif "evento" in c or "cita" in c or "agenda" in c:
        return "Eventos"
    elif "archivo" in c or "documento" in c or "imagen" in c or "foto" in c or "voz" in c:
        return "Archivos"
    elif "perfil" in c or "gusto" in c or "personalidad" in c or "amig" in c:
        return "Perfil"
    return "Perfil"


def log_archivo_en_sheets(tipo, nombre, descripcion):
    """Logs received media to the Archivos tab in Sheets."""
    try:
        sheet = get_sheets()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.worksheet("Archivos").append_row([timestamp, tipo, nombre, descripcion])
    except Exception as e:
        print(f"Error logging to Archivos sheet: {e}")


# ─────────────────────────────────────────────
# MEDIA PROCESSING — voice, images, documents
# ─────────────────────────────────────────────

def download_media_from_twilio(media_url):
    """
    Downloads bytes from a Twilio media URL.
    Requires HTTP Basic Auth — without it Twilio returns 401.
    """
    try:
        response = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=30
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None


def procesar_nota_de_voz(media_url, media_content_type):
    """Downloads a voice note and transcribes it with Gemini."""
    file_bytes = download_media_from_twilio(media_url)
    if not file_bytes:
        return "[Nota de voz recibida, pero no se pudo descargar]"

    transcripcion = "[transcripción no disponible]"
    try:
        audio_file = _gemini_client.files.upload(
            file=io.BytesIO(file_bytes),
            config={"mime_type": media_content_type, "display_name": "voicenote"}
        )
        trans_response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[audio_file, "Transcribe this voice note word for word. Reply with only the transcription, nothing else."]
        )
        transcripcion = trans_response.text.strip()
    except Exception as e:
        print(f"Error transcribing audio: {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_archivo_en_sheets("Nota de voz", f"voicenote_{timestamp}.ogg", transcripcion)

    return f"[Nota de voz recibida. Transcripción: '{transcripcion}']"


def procesar_imagen(media_url, media_content_type):
    """Downloads an image and describes it with Gemini."""
    file_bytes = download_media_from_twilio(media_url)
    if not file_bytes:
        return "[Imagen recibida, pero no se pudo descargar]"

    descripcion = "[descripción no disponible]"
    try:
        image_file = _gemini_client.files.upload(
            file=io.BytesIO(file_bytes),
            config={"mime_type": media_content_type, "display_name": "image"}
        )
        desc_response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[image_file, "Describe this image in detail in one paragraph."]
        )
        descripcion = desc_response.text.strip()
    except Exception as e:
        print(f"Error describing image: {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = media_content_type.split("/")[-1].split(";")[0]
    log_archivo_en_sheets("Imagen", f"image_{timestamp}.{ext}", descripcion)

    return f"[Imagen recibida. Descripción: '{descripcion}']"


def procesar_documento(media_url, media_content_type):
    """Logs a received document to Sheets."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = media_content_type.split("/")[-1].split(";")[0]
    filename = f"document_{timestamp}.{ext}"
    log_archivo_en_sheets("Documento", filename, "Documento recibido via WhatsApp")
    return f"[Documento recibido: '{filename}']"


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

def construir_system_prompt(memoria_datos, preferencias_personalidad):
    return f"""
Eres Jarvis, el asistente personal de Alfaro. Directo, capaz, y con un poco de humor seco.

LÍMITE DE RESPUESTA (obligatorio):
- Tus respuestas nunca deben superar 1500 caracteres. Sé conciso.
- Si el tema es complejo, da un resumen corto y ofrece profundizar si el usuario quiere más.
- Si ves que tu mensaje anterior en el historial termina con '_(respuesta larga — escríbeme 'más' si quieres que continúe)_', significa que fue cortado. Si Alfaro responde 'más' o 'continúa', retoma exactamente desde donde se cortó, sin repetir lo que ya dijiste.

REGLA DE IDIOMA (aplica a todo, sin excepción):
- Responde SIEMPRE en el mismo idioma en que Alfaro escribió.
- Si escribió en español → responde completamente en español.
- Si escribió en inglés → responde completamente en inglés.
- NUNCA mezcles los dos idiomas en una misma respuesta.
- Esta regla aplica a recordatorios, tareas, comandos y cualquier otra cosa.

PERSONALIDAD ACTUAL (lo que Alfaro ha pedido):
{preferencias_personalidad if preferencias_personalidad else "- Directo, conciso, un poco de humor seco. Como un asistente brillante que se toma el trabajo en serio pero no se toma a sí mismo demasiado en serio."}

REGLAS DE PERSONALIDAD:
- Eres proactivo: si Alfaro te da algo nuevo para guardar, pregunta detalles que falten (fecha, hora, plataforma, etc). No asumas lo que no sabes.
- "Fer" es Fernanda, su mejor amiga.
- No preguntes cosas que ya están en el historial.
- Cuando Alfaro pida cambiar cómo le hablas: GUARDAR: Perfil - Instrucción de Personalidad: [instrucción]

CONTEXTO DE MEDIOS:
- Si ves [Nota de voz recibida. Transcripción: '...'] → el usuario te mandó una nota de voz con ese contenido. Responde al contenido naturalmente.
- Si ves [Imagen recibida. Descripción: '...'] → el usuario te mandó una foto. Responde a lo que muestra.
- Si ves [Documento recibido: '...'] → el usuario te mandó un archivo que ya fue guardado en Drive.

════════════════════════════════
MEMORIA PERSISTENTE DE ALFARO:
════════════════════════════════
{formatear_memoria(memoria_datos)}
════════════════════════════════

SISTEMA DE COMANDOS (escríbelos exactamente así, en su propia línea):

GUARDAR: [Categoria] - [Detalle completo]
  - [Categoria] debe ser exactamente una de estas: Tareas | Eventos | Perfil | Archivos
  - Ejemplos:
      GUARDAR: Tareas - Estudiar para el examen de Derecho el viernes
      GUARDAR: Eventos - Boda de Fer el sábado 1 de marzo a las 5pm
      GUARDAR: Perfil - Le gusta el café americano sin azúcar
      GUARDAR: Perfil - Instrucción de Personalidad: háblame de tú
      GUARDAR: Archivos - Contrato PDF recibido el {datetime.now().strftime('%Y-%m-%d')}, guardado en Drive

ELIMINAR: [Categoria] - [Texto exacto que está guardado en memoria]
  - [Categoria] debe ser exactamente una de: Tareas | Eventos | Perfil
  - El texto después del guion debe ser IDÉNTICO al que aparece en la memoria de arriba.
  - Ejemplo: ELIMINAR: Tareas - Estudiar para el examen de Derecho el viernes

REGLAS DE COMANDOS:
- Escribe el comando en su propia línea, sin texto adicional en esa línea.
- Después del comando, en la SIGUIENTE línea, escribe tu respuesta normal.
- Solo usa GUARDAR si la info es nueva (no está ya en la memoria de arriba).
- Solo usa ELIMINAR cuando Alfaro confirme que algo ya está resuelto/terminado.

REGLAS DE CONSULTA:
- Si Alfaro pregunta por sus TAREAS: léele solo la sección TAREAS PENDIENTES de la memoria. Nada más.
- Si Alfaro pregunta por sus EVENTOS: léele solo la sección EVENTOS. Nada más.
- Si Alfaro pregunta por su PERFIL o GUSTOS: léele solo la sección PERFIL. Nada más.
- Si pregunta por TODO o su MEMORIA completa: léele las tres secciones.
- Nunca inventes ni generes un GUARDAR de algo que ya está en la memoria.
    """


# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/bot", methods=['POST'])
def bot():
    # Validate the request is actually from Twilio
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    signature = request.headers.get('X-Twilio-Signature', '')
    if not validator.validate(request.url, request.form, signature):
        return Response("Forbidden", status=403)

    # Parse the incoming message
    mensaje_texto = request.values.get('Body', '').strip()
    num_media     = int(request.values.get('NumMedia', 0))
    media_url     = request.values.get('MediaUrl0', None)
    media_type    = request.values.get('MediaContentType0', '')

    # Handle any attached media
    contexto_media = ""
    if num_media > 0 and media_url:
        if "audio" in media_type:
            contexto_media = procesar_nota_de_voz(media_url, media_type)
        elif "image" in media_type:
            contexto_media = procesar_imagen(media_url, media_type)
        else:
            contexto_media = procesar_documento(media_url, media_type)

    # Combine media context with any text the user also sent
    mensaje_completo = f"{contexto_media}\n{mensaje_texto}".strip()

    # If there's nothing to process (empty message with no media), return silently
    if not mensaje_completo:
        return Response(str(MessagingResponse()), mimetype='text/xml')

    # Load memory and conversation history from Sheets
    memoria_datos     = obtener_memoria_sheets()
    hilo_conversacion = obtener_historial_reciente()

    # Extract personality overrides stored in Perfil
    preferencias_personalidad = ""
    for fila in memoria_datos.get('perfil', []):
        fila_texto = " ".join(fila)
        if "Instrucción de Personalidad" in fila_texto:
            preferencias_personalidad += f"- {fila_texto}\n"

    # Add the user's message to the conversation thread
    hilo_conversacion.append(
        types.Content(role="user", parts=[types.Part(text=mensaje_completo)])
    )

    # Generate Jarvis's response
    instrucciones = construir_system_prompt(memoria_datos, preferencias_personalidad)
    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=instrucciones,
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
            contents=hilo_conversacion
        )
        # response.text can be None when the model uses the search tool internally.
        # Fall back to iterating through parts directly.
        respuesta_jarvis = response.text
        if not respuesta_jarvis and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    respuesta_jarvis = part.text
                    break
        if not respuesta_jarvis:
            finish = response.candidates[0].finish_reason if response.candidates else "no candidates"
            print(f"❌ response.text is None. finish_reason: {finish}")
            respuesta_jarvis = "No pude generar una respuesta, intenta de nuevo."
    except Exception as e:
        print(f"❌ Error generando respuesta: {e}")
        respuesta_jarvis = "Tuve un problema procesando eso. Intenta de nuevo."

    # Execute GUARDAR commands from Jarvis's response
    if "GUARDAR:" in respuesta_jarvis:
        try:
            for linea in respuesta_jarvis.split("\n"):
                if "GUARDAR:" in linea:
                    contenido = linea.split("GUARDAR:")[1].strip()
                    if "-" in contenido:
                        partes = contenido.split("-", 1)
                        target_sheet = inferir_sheet(partes[0].strip())
                        dato = partes[1].strip()
                    else:
                        target_sheet = "Perfil"
                        dato = contenido
                    guardar_en_sheet(target_sheet, dato)
                    print(f"✅ Guardado en {target_sheet}: {dato}")
        except Exception as e:
            print(f"❌ Error en lógica de guardado: {e}")

    # Execute ELIMINAR commands from Jarvis's response
    if "ELIMINAR:" in respuesta_jarvis:
        try:
            contenido_borrar = respuesta_jarvis.split("ELIMINAR:")[1].split("\n")[0].strip()
            if "-" in contenido_borrar:
                partes = contenido_borrar.split("-", 1)
                target_sheet = inferir_sheet(partes[0].strip())
                dato_a_borrar = partes[1].strip()
            else:
                target_sheet = None
                dato_a_borrar = contenido_borrar

            sheets_a_revisar = (
                [target_sheet] + [p for p in ["Tareas", "Eventos", "Perfil"] if p != target_sheet]
                if target_sheet else ["Tareas", "Eventos", "Perfil"]
            )
            for pestana in sheets_a_revisar:
                if eliminar_de_sheet(pestana, dato_a_borrar):
                    print(f"🗑️ Eliminado de {pestana}: {dato_a_borrar}")
                    break
        except Exception as e:
            print(f"❌ Error al intentar eliminar: {e}")

    # Truncate as a hard safety net — Twilio rejects messages over 1600 chars
    if len(respuesta_jarvis) > 1580:
        chunk = respuesta_jarvis[:1560]
        last_stop = max(chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
        if last_stop > 800:
            respuesta_jarvis = chunk[:last_stop + 1] + "\n\n_(respuesta larga — escríbeme 'más' si quieres que continúe)_"
        else:
            respuesta_jarvis = chunk + "..."

    # Save to Sheets AFTER truncation so history reflects what the user actually saw.
    # WHY: if Jarvis sees its own full response in history it won't know it was cut off.
    # GUARDAR/ELIMINAR parsing above already ran on the full text, so commands are safe.
    actualizar_historial_sheets("Alfaro", mensaje_completo)
    actualizar_historial_sheets("Jarvis", respuesta_jarvis)

    # Return the response to Twilio (which forwards it to WhatsApp)
    resp = MessagingResponse()
    resp.message(respuesta_jarvis)
    return Response(str(resp), mimetype='text/xml')


# Temporary test route — remove once everything is working
@app.route("/test_sheets")
def test_sheets():
    return str(obtener_memoria_sheets())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

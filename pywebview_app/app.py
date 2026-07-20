"""
LunaIA - Backend en Python, interfaz en HTML (pywebview)
-----------------------------------------------------------
La ventana es un navegador embebido que muestra gui.html
(ahí vive todo el CSS/Tailwind, igual que en la versión web).
Toda la lógica del chat vive aquí, en Python.

La API key se lee de la variable de entorno OPENROUTER_API_KEY
(nunca la escribas directo en este archivo).

Los chats y ajustes se guardan en la carpeta "data/", junto a
este archivo, como archivos JSON en tu propia computadora.
"""

import base64
import datetime
import json
import mimetypes
import os
import uuid

import webview
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHATS_FILE = os.path.join(DATA_DIR, "chats.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# OpenRouter también habla el "idioma" de la API de OpenAI,
# por eso usamos el mismo SDK apuntando a otra base_url.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Revisa openrouter.ai/qwen para confirmar el nombre exacto del
# modelo que quieres usar hoy. Este termina en ":free" — no
# consume crédito, pero tiene límite de mensajes por día.
QWEN_MODEL = "qwen/qwen3.6-plus:free"

# Los modelos gratis a veces se retiran sin avisar. Si el modelo de
# arriba deja de existir, usamos este router que elige automáticamente
# entre los modelos gratis que sí sigan disponibles ese día.
FALLBACK_MODEL = "openrouter/free"

# Tope de tokens por respuesta. Las cuentas gratis de OpenRouter no
# tienen crédito para el máximo del modelo (puede ser 60k+), así que
# lo bajamos a algo razonable para una respuesta de chat normal.
MAX_REPLY_TOKENS = 1024

SYSTEM_PROMPT = (
    "Eres LunaIA, una asistente de IA amigable, clara y concisa. "
    "Respondes en español salvo que te pidan otro idioma."
)

DEFAULT_SETTINGS = {"theme": "nebula", "profile_photo": None, "notifications_enabled": True}


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Api:
    """Puente entre el JavaScript de gui.html y Python.

    Cada método público de esta clase queda expuesto en el
    navegador como `window.pywebview.api.<metodo>(...)`, y
    se llama desde JS con await porque devuelve una Promise.
    """

    def __init__(self):
        api_key = os.environ.get("OPENROUTER_API_KEY")

        self._client = None
        self._init_error = None
        self._window = None  # se asigna en main(), lo necesita pick_profile_photo

        if not api_key:
            self._init_error = (
                "No encontré la variable de entorno OPENROUTER_API_KEY. "
                "Guarda tu llave con setx OPENROUTER_API_KEY \"sk-or-v1-tu-llave\" "
                "y abre una terminal nueva antes de correr la app."
            )
        else:
            self._client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://lunaia.local",
                    "X-Title": "LunaIA",
                },
            )

        # Todos los chats guardados en disco: {id: {title, updated_at, messages: [...]}}
        self._chats = _load_json(CHATS_FILE, {})
        self._settings = _load_json(SETTINGS_FILE, dict(DEFAULT_SETTINGS))

        # Conversación activa en memoria (incluye el system prompt al frente).
        self._current_id = str(uuid.uuid4())
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def send_message(self, text: str) -> str:
        if self._init_error:
            return self._init_error

        self._history.append({"role": "user", "content": text})

        try:
            response = self._client.chat.completions.create(
                model=QWEN_MODEL,
                messages=self._history,
                max_tokens=MAX_REPLY_TOKENS,
            )
            reply = response.choices[0].message.content
        except Exception as first_err:
            # Si el modelo ya no existe (404) o cambió de nombre,
            # reintentamos una vez con el router de respaldo.
            try:
                response = self._client.chat.completions.create(
                    model=FALLBACK_MODEL,
                    messages=self._history,
                    max_tokens=MAX_REPLY_TOKENS,
                )
                reply = response.choices[0].message.content
            except Exception:
                self._history.pop()
                return f"Ocurrió un error hablando con Qwen (vía OpenRouter): {first_err}"

        self._history.append({"role": "assistant", "content": reply})
        self._persist_current_chat()
        return reply

    def new_chat(self):
        """Se puede llamar desde JS para empezar una conversación nueva."""
        self._current_id = str(uuid.uuid4())
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]
        return True

    def _persist_current_chat(self):
        """Guarda la conversación activa en data/chats.json."""
        messages = [m for m in self._history if m["role"] != "system"]
        if not messages:
            return

        title = None
        for m in messages:
            if m["role"] == "user":
                title = m["content"][:42] + ("…" if len(m["content"]) > 42 else "")
                break

        self._chats[self._current_id] = {
            "title": title or "Nueva conversación",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "messages": messages,
        }
        _save_json(CHATS_FILE, self._chats)

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def list_chats(self):
        items = [
            {"id": cid, "title": c.get("title") or "Nueva conversación", "updated_at": c.get("updated_at", "")}
            for cid, c in self._chats.items()
            if c.get("messages")
        ]
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items

    def load_chat(self, chat_id: str):
        chat = self._chats.get(chat_id)
        if not chat:
            return []
        self._current_id = chat_id
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}] + chat["messages"]
        return chat["messages"]

    # ------------------------------------------------------------------
    # Ajustes (tema)
    # ------------------------------------------------------------------
    def get_settings(self):
        return self._settings

    def set_theme(self, theme_name: str):
        self._settings["theme"] = theme_name
        _save_json(SETTINGS_FILE, self._settings)
        return True

    def set_notifications(self, enabled: bool):
        self._settings["notifications_enabled"] = bool(enabled)
        _save_json(SETTINGS_FILE, self._settings)
        return True

    # ------------------------------------------------------------------
    # Perfil (foto)
    # ------------------------------------------------------------------
    def pick_profile_photo(self):
        """Abre el selector de archivos nativo y guarda la foto elegida
        como una URL de datos (base64) dentro de settings.json."""
        if self._window is None:
            return {"error": "La ventana todavía no está lista."}

        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=("Imágenes (*.png;*.jpg;*.jpeg;*.gif;*.webp)",),
            )
        except Exception as err:
            return {"error": str(err)}

        if not result:
            return None  # el usuario canceló el diálogo

        path = result[0]
        try:
            mime, _ = mimetypes.guess_type(path)
            mime = mime or "image/png"
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            data_url = f"data:{mime};base64,{encoded}"
        except Exception as err:
            return {"error": str(err)}

        self._settings["profile_photo"] = data_url
        _save_json(SETTINGS_FILE, self._settings)
        return data_url

    # ------------------------------------------------------------------
    # Notificaciones de escritorio
    # ------------------------------------------------------------------
    def notify(self, title: str, message: str):
        """Muestra una notificación nativa del sistema operativo.
        Se llama desde JS solo cuando la ventana no tiene el foco."""
        if not self._settings.get("notifications_enabled", True):
            return False
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message or "",
                app_name="LunaIA",
                timeout=6,
            )
        except Exception:
            # Si el sistema no soporta notificaciones (o falta el
            # backend de plyer), simplemente lo ignoramos sin tronar.
            pass
        return True


def main():
    api = Api()
    html_path = os.path.join(BASE_DIR, "gui.html")

    window = webview.create_window(
        "LunaIA",
        html_path,
        js_api=api,
        width=1200,
        height=760,
        min_size=(900, 600),
        background_color="#0a0b10",
    )
    api._window = window

    webview.start()


if __name__ == "__main__":
    main()

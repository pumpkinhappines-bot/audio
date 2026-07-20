# LunaIA

Chat de escritorio con interfaz en HTML/CSS (pywebview) y lógica en Python, conectado a Qwen a través de [OpenRouter](https://openrouter.ai).

## Requisitos

- Python 3.9 o más nuevo
- Una API key gratis de OpenRouter (cada persona necesita la suya, ver abajo)

## Instalación

```bash
git clone <url-de-tu-repo>
cd pywebview_app
pip install -r requirements.txt
```

## Configura tu propia API key (obligatorio, una sola vez)

LunaIA **no trae ninguna llave incluida** — por seguridad, cada quien usa la suya. Es gratis y toma un par de minutos:

1. Crea una cuenta en [openrouter.ai](https://openrouter.ai) (no pide tarjeta).
2. Ve a **API Keys** → **Create Key**. Copia la llave (empieza con `sk-or-v1-...`).
3. Guárdala como variable de entorno:

   **Windows (PowerShell):**
   ```powershell
   setx OPENROUTER_API_KEY "sk-or-v1-tu-llave-aqui"
   ```
   Cierra y abre una terminal nueva para que tome efecto.

   **macOS / Linux:**
   ```bash
   echo 'export OPENROUTER_API_KEY="sk-or-v1-tu-llave-aqui"' >> ~/.bashrc
   source ~/.bashrc
   ```

## Correr la app

```bash
python app.py
```

## Notas

- Los chats guardados, tu foto de perfil y el tema elegido se guardan localmente en la carpeta `data/` (no se sube a GitHub, está en `.gitignore`).
- El modelo usado es gratuito en OpenRouter (`qwen/qwen3.6-plus:free`, con un router de respaldo si ese deja de existir). Los modelos gratis tienen límite de mensajes por día — revisa [openrouter.ai/qwen](https://openrouter.ai/qwen) si algo deja de funcionar.
- Nunca subas tu propia API key al repositorio, ni la escribas directo en `app.py`.

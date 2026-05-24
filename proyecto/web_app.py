import csv
import io
import json
import os
import re
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, render_template, request, session, Response
from dotenv import load_dotenv

from src.scraper import run_scrape, validate_url

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_BASE_DIR, '..'))

env_path = os.path.join(_ROOT_DIR, '.env')
load_dotenv(dotenv_path=env_path)

SESSION_STATE_PATH = os.path.join(_ROOT_DIR, 'data', 'session_state.json')
os.makedirs(os.path.dirname(SESSION_STATE_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_ROOT_DIR, 'data', 'app.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

_IS_PRODUCTION = os.getenv("FLASK_ENV", "production") == "production"

app = Flask(__name__,
    static_folder=os.path.join(_BASE_DIR, 'static'),
    template_folder=os.path.join(_BASE_DIR, 'templates')
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

app.config.update(
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_IS_PRODUCTION,
    MAX_CONTENT_LENGTH=1024 * 1024,
)

MAX_URL_LENGTH = 500


def sanitize_html(text):
    return re.sub(r'<[^>]*>', '', text) if text else text


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def require_csrf(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
            if not token or token != session.get("_csrf_token"):
                logger.warning("CSRF inválido desde %s", request.remote_addr)
                return jsonify({"error": "Token CSRF inválido"}), 403
        return f(*args, **kwargs)
    return decorated


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


@app.context_processor
def inject_csrf():
    return dict(csrf_token=csrf_token())


@app.route("/")
def index():
    return render_template("index.html", tasks=session.get("tasks", []))


@app.route("/scrape", methods=["POST"])
@require_csrf
def scrape():
    url = request.form.get("url", "").strip()

    if not url:
        return jsonify({"error": "La URL es requerida"}), 400
    if len(url) > MAX_URL_LENGTH:
        return jsonify({"error": "URL demasiado larga"}), 400
    if not validate_url(url):
        logger.warning("URL bloqueada: %s", url[:80])
        return jsonify({"error": "URL no permitida. Solo enlaces de UNEMI."}), 400

    headless = request.form.get("headless", "true").lower() == "true"
    username = (request.form.get("username") or os.getenv("MOODLE_USERNAME") or "").strip()
    password = request.form.get("password") or os.getenv("MOODLE_PASSWORD") or ""

    logger.info("Scraping iniciado: %s", url[:60])

    try:
        result = run_scrape(url, username=username, password=password, headless=headless, storage_path=SESSION_STATE_PATH)

        if result is None:
            return jsonify({"error": "No se pudo extraer la información. Revisa la URL o las credenciales."}), 500

        for field in ["titulo", "materia", "tipo", "fecha_apertura", "fecha_entrega"]:
            if field in result:
                result[field] = sanitize_html(result[field])

        session.permanent = True
        tasks = session.get("tasks", [])
        tasks.insert(0, result)

        max_tasks = int(os.getenv("MAX_TASKS_PER_SESSION", "50"))
        session["tasks"] = tasks[:max_tasks]

        logger.info("Tarea extraída: %s - %s", result.get("materia", "?"), result.get("titulo", "?")[:50])
        return jsonify({"task": result, "count": len(session["tasks"])})

    except RuntimeError as e:
        logger.warning("Error de scraping: %s", str(e)[:100])
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error("Error inesperado: %s", str(e)[:200])
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/delete/<int:index>", methods=["POST"])
@require_csrf
def delete(index):
    tasks = session.get("tasks", [])
    if 0 <= index < len(tasks):
        tasks.pop(index)
        session["tasks"] = tasks
        return jsonify({"success": True, "count": len(tasks)})
    return jsonify({"error": "Índice inválido"}), 400


@app.route("/clear", methods=["POST"])
@require_csrf
def clear():
    session["tasks"] = []
    return jsonify({"success": True})


@app.route("/export")
def export_csv():
    tasks = session.get("tasks", [])
    if not tasks:
        return jsonify({"error": "No hay tareas para exportar"}), 400

    output = io.StringIO()
    fields = ["titulo", "descripcion", "fecha_entrega", "estado", "materia", "tipo", "fecha_apertura"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(tasks)

    filename = f"tareas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/upload-session", methods=["POST"])
@require_csrf
def upload_session():
    if "session_file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    file = request.files["session_file"]
    if file.filename == "" or not file.filename.endswith(".json"):
        return jsonify({"error": "Debe ser un archivo .json"}), 400
    try:
        content = file.read().decode("utf-8")
        json.loads(content)
        os.makedirs(os.path.dirname(SESSION_STATE_PATH), exist_ok=True)
        with open(SESSION_STATE_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Sesión subida correctamente desde %s", request.remote_addr)
        return jsonify({"success": True, "message": "Sesión cargada correctamente"})
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"error": "El archivo no es un JSON válido"}), 400


@app.route("/session-status")
def session_status():
    exists = os.path.exists(SESSION_STATE_PATH)
    return jsonify({
        "has_session": exists,
        "message": "Sesión activa" if exists else "No hay sesión guardada"
    })


@app.route("/delete-session", methods=["POST"])
@require_csrf
def delete_session():
    if os.path.exists(SESSION_STATE_PATH):
        os.remove(SESSION_STATE_PATH)
        logger.info("Sesión eliminada por %s", request.remote_addr)
    return jsonify({"success": True, "message": "Sesión eliminada"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Solicitud demasiado grande"}), 413


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Error interno del servidor"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)

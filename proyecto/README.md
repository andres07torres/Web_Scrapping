# Web Scrapping Tareas

![Estado](https://img.shields.io/badge/Estado-Completado-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000?style=for-the-badge&logo=flask&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Aplicación web para automatizar la extracción de actividades, tareas y evaluaciones desde la plataforma **Moodle UNEMI**. Desarrollada con **Flask** y **Playwright**.

## Características

- **Extracción automática** — Obtiene título, materia, tipo (tarea/test/foro) y fechas de apertura/entrega desde cualquier URL de Moodle.
- **Sesión persistente** — Guarda cookies para evitar login repetitivo.
- **Exportación CSV** — Archivos listos para importar a base de datos SQL.
- **Modo headless** — Playwright ejecuta Chromium sin ventana.
- **Validación de seguridad** — Solo permite URLs del dominio UNEMI.
- **Dockerizado** — Listo para desplegar en Render o cualquier servidor.

## Tecnologías

- **Backend**: Python, Flask, Gunicorn
- **Scraping**: Playwright (Chromium)
- **Frontend**: HTML, CSS, JavaScript vanilla
- **Infraestructura**: Docker, Render

## Seguridad

- **Headers de seguridad** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy y Permissions-Policy.
- **Protección CSRF** — Token único por sesión validado en todas las rutas POST.
- **Sesión segura** — Cookies HTTP-only, SameSite=Lax, timeout de 2 horas.
- **Validación de URLs** — Solo se permite el dominio `aulagradob.unemi.edu.ec` con prefijo HTTPS.
- **Sanitización de entrada** — Se elimina HTML/scripts de todos los inputs del usuario.
- **Sanitización de salida** — Escape de caracteres HTML en el frontend para prevenir XSS.
- **Playwright seguro** — Navegador lanzado con `--no-sandbox`, `--disable-dev-shm-usage`, user-agent fijo y timeouts acotados.
- **Logging** — Registro de actividad (scraping, CSRF inválidos, errores) en archivo y consola.
- **Límite de datos** — Máximo 50 tareas por sesión y 500 caracteres por URL.
- **Sin exposición de errores** — Los errores internos no muestran stack traces al usuario.

## Instalación y uso

### Local

```bash
cd proyecto
pip install -r requirements.txt
playwright install chromium
python web_app.py
```

Abrir `http://localhost:5000`

### Docker

```bash
cd proyecto
docker compose up --build
```

### Render

```bash
# El render.yaml está en la raíz, apunta a proyecto/
# Solo conectar el repo en Render Dashboard
```

## Estructura del proyecto

```
Scrapping/
├── .env                     # Credenciales (fuera del proyecto)
├── data/                    # Datos de ejecución
├── render.yaml              # Config para Render
├── proyecto/
│   ├── src/
│   │   └── scraper.py       # Lógica de scraping con Playwright
│   ├── web_app.py            # Servidor Flask (punto de entrada)
│   ├── templates/
│   │   └── index.html       # Interfaz de usuario
│   ├── static/
│   │   └── style.css        # Estilos
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── render.yaml
│   └── requirements.txt
└── .gitignore
```

## Configuración

Crear archivo `.env` en la raíz del proyecto:

```env
MOODLE_USERNAME=tu_usuario
MOODLE_PASSWORD=tu_contraseña
FLASK_SECRET_KEY=clave-segura-para-sesiones
```

## Reglas de Git

- Trabajar en ramas `develop_[nombre]`
- No hacer push directo a `main`
- Siempre hacer `git pull` antes de empezar a editar

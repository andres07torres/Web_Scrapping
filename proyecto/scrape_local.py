"""
Scrapea URLs de Moodle desde tu PC y envía los datos a Render.

Uso:
  cd proyecto
  python scrape_local.py https://aulagradob.unemi.edu.ec/mod/assign/view.php?id=70708
  python scrape_local.py urls.txt  (una URL por línea)

Requiere las variables en .env:
  RENDER_API_URL=https://web-scrapping-fr20.onrender.com/api/tasks
  RENDER_API_KEY=clave_que_definas_en_Render
"""
import os
import sys
import json
import asyncio
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from src.scraper import run_scrape, validate_url

SESSION_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'session_state.json')
API_URL = os.getenv("RENDER_API_URL", "https://web-scrapping-fr20.onrender.com/api/tasks")
API_KEY = os.getenv("RENDER_API_KEY", "")


def load_urls():
    if len(sys.argv) < 2:
        print("Uso: python scrape_local.py <url1> <url2> ... | python scrape_local.py urls.txt")
        sys.exit(1)

    if len(sys.argv) == 2 and os.path.isfile(sys.argv[1]):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return sys.argv[1:]


def send_to_render(tasks):
    if not tasks:
        print("⚠️  No hay tareas para enviar.")
        return

    if not API_KEY:
        print("⚠️  RENDER_API_KEY no configurada. Las tareas solo se guardan localmente.")
        return

    data = json.dumps(tasks).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Enviadas {result.get('added', 0)} tareas a Render (total: {result.get('total', 0)})")
    except Exception as e:
        print(f"❌ Error al enviar a Render: {e}")


async def main():
    urls = load_urls()
    print(f"🔍 Scrapeando {len(urls)} URL(s)...\n")

    results = []
    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not validate_url(url):
            print(f"  [{i}/{len(urls)}] ⚠️  URL inválida (no es UNEMI): {url[:60]}")
            continue

        print(f"  [{i}/{len(urls)}] Extrayendo: {url[:70]}...", end=" ")
        try:
            task = run_scrape(url,
                              username=os.getenv("MOODLE_USERNAME"),
                              password=os.getenv("MOODLE_PASSWORD"),
                              headless=True,
                              storage_path=SESSION_PATH)
            if task:
                results.append(task)
                print(f"✅ {task.get('titulo', '?')[:50]}")
            else:
                print("❌ Sin resultado")
        except Exception as e:
            print(f"❌ {str(e)[:60]}")

    print(f"\n📊 Total: {len(results)}/{len(urls)} tareas extraídas")

    if results:
        send_to_render(results)

        # Guardar local como respaldo
        local_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'tareas_export.json')
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"📁 Backup local: {local_path}")


if __name__ == "__main__":
    asyncio.run(main())

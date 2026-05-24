import os
import sys
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
SESSION_PATH = os.path.join(DATA_DIR, 'session_state.json')
os.makedirs(DATA_DIR, exist_ok=True)


async def main():
    print("=" * 60)
    print("Capturador de sesi\u00f3n Moodle")
    print("=" * 60)
    print("Se abrir\u00e1 una ventana del navegador.")
    print("1. Inicia sesi\u00f3n MANUALMENTE (resuelve el CAPTCHA si aparece)")
    print("2. Despu\u00e9s de entrar, vuelve a esta terminal y presiona ENTER")
    print("3. Las cookies se guardar\u00e1n autom\u00e1ticamente")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
        )
        context = await browser.new_context(
            no_viewport=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(
            "https://aulagradob.unemi.edu.ec/login/index.php",
            wait_until="networkidle"
        )

        input("Presiona ENTER despu\u00e9s de iniciar sesi\u00f3n... ")

        await context.storage_state(path=SESSION_PATH)
        await browser.close()

    print("\u2705 Sesion guardada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())

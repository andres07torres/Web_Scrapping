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
    print("Capturador de sesión Moodle - Aula Grado B")
    print("=" * 60)
    print("Se abrirá una ventana del navegador de Aula Grado B.")
    print("1. Inicia sesión MANUALMENTE (resuelve el CAPTCHA si aparece)")
    print("2. Después de entrar, vuelve a esta terminal y presiona ENTER")
    print("3. Las cookies se guardarán automáticamente")
    print("=" * 60)

    login_url = "https://aulagradob.unemi.edu.ec/login/index.php"
    session_path = os.path.join(DATA_DIR, 'session_state_aulagradob.json')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        await page.goto(
            login_url,
            wait_until="networkidle"
        )

        input("\nPresiona ENTER después de iniciar sesión... ")

        await context.storage_state(path=session_path)
        await browser.close()

    print("\n✅ Sesión de Aula Grado B guardada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())

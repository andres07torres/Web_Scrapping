"""
Genera data/session_state.json autenticándose manualmente en Moodle.

Uso:
  cd proyecto
  python get_session.py

Resuelve el CAPTCHA en el navegador que se abre y luego
sube data/session_state.json a Render desde la web.
"""
import os
import json
import asyncio

from playwright.async_api import async_playwright

LOGIN_URL = "https://aulagradob.unemi.edu.ec/login/index.php"
VERIFY_URL = "https://aulagradob.unemi.edu.ec/my/"


async def main():
    session_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'session_state.json')
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("🔓 Navegador abierto. Ve al login de Moodle...")
        print("⚠️  Si aparece CAPTCHA, resuélvelo manualmente.")
        print("⏳ Esperando que inicies sesión...\n")

        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)

        try:
            # Esperar hasta que desaparezca el formulario de login
            await page.wait_for_function(
                "!document.querySelector('#username') && !document.querySelector('input[name=\"username\"]')",
                timeout=300000
            )
            print("✅ Inicio de sesión detectado (login ya no visible).")

            # Verificar navegando a una página protegida
            await page.goto(VERIFY_URL, wait_until="networkidle", timeout=60000)
            logged_in = await page.locator("#username, input[name='username']").is_visible()
            if logged_in:
                print("⚠️  La sesión no es válida. Intenta de nuevo.")
                await browser.close()
                return

            print("✅ Sesión verificada. Guardando cookies...\n")

            # Guardar la sesión
            await context.storage_state(path=session_path)

            # Mostrar resumen del archivo
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies_count = len(data.get("cookies", []))
            origins_count = len(data.get("origins", []))

            print(f"📁 Archivo: {session_path}")
            print(f"🍪 Cookies: {cookies_count}")
            print(f"🌐 Orígenes: {origins_count}")
            print()

            if cookies_count > 0:
                print("✅ Sesión guardada correctamente.")
                print("📤 Súbela a Render:")
                print("   1. Abre https://web-scrapping-fr20.onrender.com/")
                print("   2. Haz clic en 'Subir session_state.json'")
                print("   3. Selecciona este archivo")
                print("   4. Verás '● Sesión activa' en verde ✅")
            else:
                print("❌ No se encontraron cookies. La sesión no es válida.")

        except Exception as e:
            print(f"❌ Error: No se detectó inicio de sesión en 5 minutos.")
            print("   Ejecuta de nuevo e inicia sesión más rápido.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

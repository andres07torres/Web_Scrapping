"""
Genera data/session_state.json autenticándose manualmente en Moodle.
"""
import os
import json
import asyncio

from playwright.async_api import async_playwright

LOGIN_URL = "https://aulagradob.unemi.edu.ec/login/index.php"
TARGET_URL = "https://aulagradob.unemi.edu.ec/mod/assign/view.php?id=70708"


async def main():
    session_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'session_state.json')
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print("")
        print("⚠️  ⚠️  ⚠️  ATENCIÓN ⚠️  ⚠️  ⚠️")
        print("Se abrirá una ventana de CHROME NUEVA.")
        print("NO es tu navegador normal. Debes iniciar sesión AHÍ.")
        print("Si cierras la ventana sin loguearte, no funcionará.")
        print("⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️")
        print("")
        print()

        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)

        print("⏳ Esperando que inicies sesión en la ventana de Playwright...")
        print("   - Ingresa tus credenciales")
        print("   - Resuelve el CAPTCHA si aparece")
        print("   - La sesión se guardará automáticamente\n")

        try:
            await page.wait_for_function(
                "!document.querySelector('#username')",
                timeout=300000
            )
            print("✅ Login detectado. Esperando que terminen las redirecciones...")
            await asyncio.sleep(5)

            if await page.locator("#username").is_visible():
                print("❌ El login sigue visible. Algo salió mal.")
                await browser.close()
                return

            print("✅ Navegando a una actividad para consolidar la sesión...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            if await page.locator("#username").is_visible():
                print("❌ La sesión no es válida (redirigió al login).")
                await browser.close()
                return

            print("✅ Sesión verificada en la actividad. Guardando cookies...")
            await context.storage_state(path=session_path)

            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            moodle_cookies = [c for c in cookies if "unemi" in c.get("domain", "")]
            session_cookies = [c for c in cookies if "MoodleSession" in c.get("name", "")]

            print(f"\n📊 Resumen de cookies guardadas:")
            print(f"   Total: {len(cookies)}")
            print(f"   Dominio unemi: {len(moodle_cookies)}")
            print(f"   MoodleSession: {len(session_cookies)}")
            print()

            if session_cookies:
                print(f"✅ LISTO. Archivo guardado en: {session_path}")
                print(f"📤 Súbelo a Render desde la web.")
            else:
                print("❌ No se encontró la cookie MoodleSession.")
                print("   La sesión no es válida. Intenta de nuevo.")

        except Exception:
            print("❌ Tiempo de espera agotado (5 min). Ejecuta de nuevo.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

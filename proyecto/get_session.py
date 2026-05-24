"""
Genera data/session_state.json usando las cookies de tu CHROME real.

Si ya estás logueado en Moodle en tu Chrome, este script usará
ESA misma sesión — no necesitas loguearte de nuevo.

Uso:
  cd proyecto
  python get_session.py
"""
import os
import json
import sys
import asyncio

from playwright.async_api import async_playwright

CHECK_URL = "https://aulagradob.unemi.edu.ec/my/"
EXPORT_URL = "https://aulagradob.unemi.edu.ec/mod/assign/view.php?id=70708"


async def main():
    session_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'session_state.json')
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    async with async_playwright() as p:
        print("🔓 Abriendo Chrome (tu perfil real)...")
        print("   Si ya estás logueado en Moodle, las cookies se heredarán.\n")

        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(CHECK_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        needs_login = await page.locator("#username, input[name='username']").is_visible()

        if needs_login:
            print("⚠️  No estás logueado en Moodle en este perfil.")
            print("👉 Inicia sesión en la ventana de Chrome que se abrió.")
            print("⏳ Esperando login...\n")

            try:
                await page.wait_for_function(
                    "!document.querySelector('#username')",
                    timeout=300000
                )
                print("✅ Login detectado.")
                await asyncio.sleep(3)
            except Exception:
                print("❌ Tiempo agotado. Intenta de nuevo.")
                await browser.close()
                return
        else:
            print("✅ Ya estás logueado en Moodle. Usando sesión existente.\n")

        await page.goto(EXPORT_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        if await page.locator("#username, input[name='username']").is_visible():
            print("❌ La sesión no es válida (redirigió al login en Moodle).")
            await browser.close()
            return

        print("✅ Sesión verificada. Guardando cookies...")
        await context.storage_state(path=session_path)

        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cookies = data.get("cookies", [])
        session_cookies = [c for c in cookies if "MoodleSession" in c.get("name", "")]
        unemi_cookies = [c for c in cookies if "unemi" in c.get("domain", "")]

        print(f"\n📊 Cookies guardadas: {len(cookies)} total, {len(unemi_cookies)} de unemi, {len(session_cookies)} MoodleSession")

        if session_cookies:
            print(f"✅ Sesión válida guardada en: {session_path}")
            print(f"📤 Súbela a Render desde la web → 'Subir session_state.json'")
        else:
            print("❌ No hay MoodleSession. La sesión no sirve.")
            print("   Asegúrate de estar logueado en la pestaña que se abrió.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

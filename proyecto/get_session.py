"""
Genera data/session_state.json autenticándose manualmente en Moodle.

Uso:
  cd proyecto
  python get_session.py

Resuelve el CAPTCHA en el navegador que se abre.
Luego sube data/session_state.json a Render desde la web.
"""
import os
import sys
import asyncio

from playwright.async_api import async_playwright

TARGET_URL = "https://aulagradob.unemi.edu.ec/"

async def main():
    session_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'session_state.json')
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("🔓 Navegador abierto. Inicia sesión en Moodle...")
        print("⚠️  Resuelve el CAPTCHA si aparece.")
        print("⏳ La sesión se guardará automáticamente al detectar el login.\n")

        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        try:
            await page.wait_for_selector(".usermenu, .breadcrumb-item, #region-main", timeout=300000)
            print("✅ Inicio de sesión detectado.")
            await context.storage_state(path=session_path)
            print(f"✅ Sesión guardada en: {session_path}")
            print("📤 Súbela a Render desde la interfaz web → 'Subir session_state.json'")
        except Exception:
            print("❌ Tiempo de espera agotado. No se detectó el inicio de sesión.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

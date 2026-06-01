import asyncio
import os
import re
from datetime import datetime

from playwright.async_api import async_playwright

_MAX_SCRAPE_TIMEOUT = 120000
_MAX_URL_LENGTH = 500

_cached_browser = None
_cached_playwright = None


def _validate_url_strict(url):
    if not url or not isinstance(url, str):
        return False
    if len(url) > _MAX_URL_LENGTH:
        return False
    return True


def format_to_sql_date(date_str):
    if not date_str or date_str == "N/A":
        return datetime.now().strftime("%Y-%m-%d")
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }
    try:
        date_lower = date_str.lower()
        year_match = re.search(r"\d{4}", date_str)
        year = year_match.group(0) if year_match else str(datetime.now().year)
        day_matches = re.findall(r"\b\d{1,2}\b", date_str)
        day = day_matches[0].zfill(2) if day_matches else "01"
        month = "01"
        for m_name, m_num in meses.items():
            if m_name in date_lower:
                month = m_num
                break
        return f"{year}-{month}-{day}"
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def validate_url(url):
    if not _validate_url_strict(url):
        return False
    return url.startswith("https://aulagradob.unemi.edu.ec") or url.startswith("https://aulagrado.unemi.edu.ec")


def _sanitize_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    return text.strip()[:500]


def _get_launch_args():
    return [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-accelerated-2d-canvas",
        "--disable-background-networking",
        "--disable-sync",
        "--no-first-run",
        "--mute-audio",
        "--disable-blink-features=AutomationControlled",
    ]


async def _get_browser(headless=True):
    global _cached_browser, _cached_playwright
    if _cached_browser is None or not _cached_browser.is_connected():
        if _cached_playwright is None:
            _cached_playwright = await async_playwright().start()
        pw = _cached_playwright
        _cached_browser = await pw.chromium.launch(
            headless=headless,
            args=_get_launch_args(),
            timeout=30000,
        )
    return _cached_browser


async def scrape_task(target_url, username, password, headless=True, storage_path=None):
    if not validate_url(target_url):
        raise ValueError("URL no válida o no permitida")

    pw = await async_playwright().start()
    
    # Launch headed but offscreen when headless=True to completely bypass headless detection, Client Hints, and fingerprints
    launch_headless = False
    launch_args = _get_launch_args()
    if headless:
        launch_args = launch_args + ["--window-position=-2000,-2000", "--window-size=1024,768"]
    else:
        launch_args = launch_args + ["--window-size=1024,768"]

    browser = await pw.chromium.launch(
        headless=launch_headless,
        args=launch_args,
        timeout=30000,
    )
    storage = storage_path if storage_path and os.path.exists(storage_path) else None
    context = await browser.new_context(
        storage_state=storage,
        no_viewport=True,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.set_default_timeout(15000)

    try:
        # Use domcontentloaded for significantly faster scraping (does not wait for images/external assets)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=_MAX_SCRAPE_TIMEOUT)
        
        # Wait for either the main content or the login fields to load
        try:
            await page.wait_for_selector("#region-main, #username, input[name='username']", timeout=5000)
        except Exception:
            pass

        if await page.locator("#username, input[name='username']").is_visible():
            from urllib.parse import urlparse
            parsed = urlparse(target_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            await page.goto(f"{base_url}/login/index.php", wait_until="domcontentloaded")

            await page.wait_for_selector("#username", timeout=10000)
            await page.wait_for_selector("#password", timeout=10000)

            safe_user = _sanitize_text(username) if username else ""
            if safe_user and password:
                await page.fill("#username", safe_user)
                await page.wait_for_timeout(500)
                await page.fill("#password", password)
                await page.wait_for_timeout(500)
                try:
                    await page.click("#loginbtn")
                except Exception:
                    try:
                        await page.click("button[type='submit']")
                    except Exception:
                        pass

                try:
                    # Wait up to 15s for the login form to disappear (indicating successful navigation)
                    await page.wait_for_selector("#username", state="hidden", timeout=15000)
                except Exception:
                    pass

            if await page.locator("#username").is_visible():
                try:
                    screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "login_failure.png")
                    await page.screenshot(path=screenshot_path)
                    print(f"[DEBUG] Screenshot saved to {screenshot_path}")
                except Exception as e_ss:
                    print(f"[DEBUG] Failed to save screenshot: {e_ss}")
                raise RuntimeError(
                    "Se requiere resolver un CAPTCHA. "
                    "Intenta más tarde o verifica tus credenciales."
                )

            try:
                # Reduce timeout to 15s so it fails fast if blocked or credentials are invalid
                await page.wait_for_selector(".usermenu, .breadcrumb-item, #region-main", timeout=15000)
            except Exception:
                raise RuntimeError("Tiempo de espera agotado para el inicio de sesión.")

            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector("#region-main, .breadcrumb-item", timeout=10000)

        await page.wait_for_timeout(500)

        title = "Sin título"
        try:
            selectors = [
                ".page-header-headings h2",
                "#region-main h2",
                "h2.h2",
                "h2"
            ]
            for selector in selectors:
                element = page.locator(selector).first
                if await element.is_visible():
                    text = await element.inner_text()
                    if text.strip() and "Bloques" not in text and "Navegación" not in text:
                        title = text.strip()
                        break

            if title == "Sin título" or "Entrar" in title or "Grado B" in title:
                page_title = await page.title()
                title = page_title.split("|")[0].split(":")[-1].strip()
        except Exception:
            pass

        materia = "Desconocida"
        try:
            breadcrumbs = page.locator(".breadcrumb-item a")
            count = await breadcrumbs.count()
            if count >= 3:
                materia = await breadcrumbs.nth(2).inner_text()
                materia = re.split(r"[,\[\-]", materia)[0].strip()
        except Exception:
            pass

        tipo = "tarea"
        if "quiz" in target_url or "cuestionario" in target_url:
            tipo = "test"
        elif "forum" in target_url or "foro" in target_url:
            tipo = "foro"

        apertura = "N/A"
        entrega = "N/A"

        try:
            text = await page.inner_text("body")
        except Exception:
            text = ""

        if text:
            ap_patterns = [
                r"(?:Apertura|Abri[oó]|Abre|Abierto|Disponible desde|Desde el)\s*(?:el|desde)?\s*[:\-]?\s*([^.]{10,100}?\d{2}:\d{2})",
                r"Este cuestionario no estar[aá] disponible hasta el\s*([^.]{10,100}?\d{2}:\d{2})",
                r"Este cuestionario se abri[oó] el\s*([^.]{10,100}?\d{2}:\d{2})"
            ]
            ci_patterns = [
                r"(?:Cierre|Cierra|Vencimiento|Fecha de entrega|Hasta el|Vence el)\s*(?:el|hasta)?\s*[:\-]?\s*([^.]{10,100}?\d{2}:\d{2})",
                r"Este cuestionario se cerrar[aá] el\s*([^.]{10,100}?\d{2}:\d{2})"
            ]
            for p_in in ap_patterns:
                match = re.search(p_in, text, re.IGNORECASE)
                if match:
                    apertura = match.group(1).strip()
                    break
            for p_in in ci_patterns:
                match = re.search(p_in, text, re.IGNORECASE)
                if match:
                    entrega = match.group(1).strip()
                    break

        if storage_path:
            try:
                await context.storage_state(path=storage_path)
            except Exception:
                pass

        return {
            "titulo": _sanitize_text(title) or "Sin título",
            "descripcion": "",
            "fecha_entrega": format_to_sql_date(entrega),
            "estado": "pendiente",
            "materia": _sanitize_text(materia) or "Desconocida",
            "tipo": tipo,
            "fecha_apertura": format_to_sql_date(apertura),
        }
    finally:
        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass


def run_scrape(target_url, username=None, password=None, headless=True, storage_path=None):
    if not _validate_url_strict(target_url):
        raise ValueError("URL inválida")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            scrape_task(target_url, username, password, headless=headless, storage_path=storage_path)
        )
        return result
    finally:
        loop.close()


def cleanup_scraper():
    global _cached_browser, _cached_playwright
    try:
        if _cached_browser:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_cached_browser.close())
            loop.close()
            _cached_browser = None
        if _cached_playwright:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_cached_playwright.stop())
            loop.close()
            _cached_playwright = None
    except Exception:
        pass


def clean_session_file(session_path):
    import json
    from datetime import datetime, timezone
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        now = datetime.now(timezone.utc).timestamp()
        # Keep session cookies (expires < 0 or expires = -1) and unexpired cookies
        valid = [c for c in cookies if not c.get("expires") or c["expires"] < 0 or c["expires"] > now]
        if len(valid) != len(cookies):
            data["cookies"] = valid
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
    except Exception:
        pass

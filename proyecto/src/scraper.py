import asyncio
import os
import re
from datetime import datetime

from playwright.async_api import async_playwright

_MAX_SCRAPE_TIMEOUT = 120000
_MAX_URL_LENGTH = 500


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
    return url.startswith("https://aulagradob.unemi.edu.ec")


def _sanitize_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    return text.strip()[:500]


async def scrape_task(target_url, username, password, headless=True, storage_path=None):
    if not validate_url(target_url):
        raise ValueError("URL no válida o no permitida")

    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-accelerated-2d-canvas",
        "--disable-background-networking",
        "--disable-sync",
        "--no-first-run",
        "--mute-audio",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
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

        try:
            await page.goto(target_url, wait_until="networkidle", timeout=_MAX_SCRAPE_TIMEOUT)

            if await page.locator("#username, input[name='username']").is_visible():
                await page.goto("https://aulagradob.unemi.edu.ec/login/index.php")

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
                        await page.wait_for_timeout(3000)
                    except Exception:
                        try:
                            await page.click("button[type='submit']")
                            await page.wait_for_timeout(3000)
                        except Exception:
                            pass

                if await page.locator("#username").is_visible():
                    raise RuntimeError(
                        "Se requiere resolver un CAPTCHA. "
                        "Intenta más tarde o verifica tus credenciales."
                    )

                try:
                    await page.wait_for_selector(".usermenu, .breadcrumb-item, #region-main", timeout=180000)
                except Exception:
                    raise RuntimeError("Tiempo de espera agotado para el inicio de sesión.")

                await page.goto(target_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_selector("#region-main, .breadcrumb-item", timeout=30000)

            await page.wait_for_timeout(2000)

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

            content = " ".join(re.sub('<.*?>', ' ', await page.content()).split())
            apertura = "N/A"
            entrega = "N/A"

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
                match = re.search(p_in, content, re.IGNORECASE)
                if match:
                    apertura = match.group(1).strip()
                    break

            for p_in in ci_patterns:
                match = re.search(p_in, content, re.IGNORECASE)
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
            await browser.close()


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

import asyncio
from pathlib import Path
import traceback
from quart import current_app, request
from pyppeteer import launch, connect
from pyppeteer.page import Page
from pyppeteer.errors import PageError
import aiohttp

with open(Path.cwd() / "flag", mode="r") as f:
    flag = f.read().strip()


async def get_ws_url(endpoint: str):
    async with aiohttp.ClientSession() as session:
        res = await session.get(endpoint + "/json/version")
        res_json = await res.json()
        return res_json["webSocketDebuggerUrl"]


async def get_browser():
    if not hasattr(current_app, "browser"):
        if browser_url := current_app.config.get("BROWSER_URL"):
            ws_url = await get_ws_url(browser_url)
            current_app.browser = await connect(browserWSEndpoint=ws_url)
        else:
            current_app.browser = await launch(headless=False)
    return current_app.browser


def verify_url(url: str):
    for domain in current_app.config.get("VERIFIED_DOMAIN", []):
        if domain in url:
            return True
    return False


async def goto_url(page: Page, url: str):
    """Go to said url, and log in if we see a login page
    that is on our verified domain"""
    await page.goto(url)
    await asyncio.sleep(1)

    is_login_page = await page.querySelector("#loginForm")
    if verify_url(url) and is_login_page:
        username_field = await page.querySelector("#username")
        await username_field.type("bob")

        password_field = await page.querySelector("#password")
        await password_field.type(flag)

        login_btn = await page.querySelector("#loginBtn")
        await login_btn.click()
        await page.waitForNavigation()


async def validate_url(url: str, job_id: int):
    """Validates url if it can be accessed or not"""
    browser = await get_browser()
    page = await browser.newPage()

    # We don't want javascript, thanks
    await page.setJavaScriptEnabled(False)

    # Go to the page
    current_app.logger.info("Accessing page")
    try:
        await goto_url(page, url)
        status = 2
        current_app.logger.info("Success, mark as valid")
    except PageError:
        traceback.print_exc()
        # Seems like page isn't working
        current_app.logger.info("Page errored, mark as invalid")
        status = 0

    # Go to admin panel
    await goto_url(page, current_app.config["HOST"] + "/admin")

    # Let's submit
    current_app.logger.info("Finding form")
    form = await page.querySelector(f"#form{job_id}")

    current_app.logger.info("Finding radio status button")
    radio = await form.querySelector(f'input[value="{status}"')
    await radio.click()

    current_app.logger.info("Finding submit button and submit")
    submit = await form.querySelector("button")
    await submit.click()

    await page.waitForNavigation()
    # We don't need the page anymore, let's just close the page
    await page.close()

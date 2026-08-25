import config

# ═══════════════════════════════════════════
# UNICODE HELPERS
# ═══════════════════════════════════════════
_SMALL_CAPS = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'q', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
}


def fancy(text: str) -> str:
    """Convert text to Unicode small-caps style."""
    return ''.join(_SMALL_CAPS.get(c, c) for c in text)


def fmt_num(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def pct(part: int, total: int) -> str:
    """Percentage string."""
    if total == 0:
        return "0.0%"
    return f"{(part / total * 100):.1f}%"


def dev_footer() -> str:
    return f"╰─ ◆ \U0001f468\u200d\U0001f4bc <i>DEV: {config.DEV_CREDIT}</i>"


# ═══════════════════════════════════════════
# PROGRESS BAR
# ═══════════════════════════════════════════
_BAR_LEN = 20


def progress_bar(current: int, total: int, width: int = _BAR_LEN) -> str:
    """ASCII progress bar."""
    if total == 0:
        return "[" + " " * width + "]"
    filled = int(width * current / total)
    return "[" + "■" * filled + "□" * (width - filled) + "]"


# ═══════════════════════════════════════════
# CHECKING PROGRESS MESSAGE
# ═══════════════════════════════════════════
def checking_progress_msg(
    checked: int,
    total: int,
    hits: int,
    free: int,
    bad: int,
    retry: int,
    proxy_errors: int,
    cps: float,
    eta: str,
) -> str:
    """Build the live checking progress message."""
    bar = progress_bar(checked, total)
    p = pct(checked, total)
    return (
        f"╭─ ⟡ {fancy('Checking')}\n"
        f"├─ {bar} {p}\n"
        f"├─ ✓ <b>{fancy('Progress')}</b>: {fmt_num(checked)} / {fmt_num(total)} ({p})\n"
        f"├─ ⏱ <b>{fancy('Speed')}</b>: {cps:.1f}/s\n"
        f"├─ ⏳ <b>{fancy('ETA')}</b>: {eta}\n"
        f"├─ ☆ <b>{fancy('Hits')}</b>: {fmt_num(hits)}\n"
        f"├─ ○ <b>{fancy('Free')}</b>: {fmt_num(free)}\n"
        f"├─ ✕ <b>{fancy('Bad')}</b>: {fmt_num(bad)}\n"
        f"├─ ⚠ <b>{fancy('Retry')}</b>: {fmt_num(retry)}\n"
        f"├─ ⚠ <b>{fancy('Proxy Errors')}</b>: {fmt_num(proxy_errors)}\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# HIT MESSAGE
# ═══════════════════════════════════════════
def hit_message(
    email: str,
    password: str,
    info: dict,
    checker_name: str,
    checker_id: int,
    checker_plan: str,
) -> str:
    """Build a hit notification message."""
    role = checker_plan
    if checker_id in config.ADMIN_IDS:
        role = "root"
    name_link = f"[{checker_name}](tg://user?id={checker_id})"
    return (
        f"╭─ ☆ {fancy('Premium Hit Found')}\n"
        f"├─ ▸ <b>{fancy('Checker')}</b>: {name_link} ({role})\n"
        f"├─ ▸ <b>{fancy('Email')}</b>: <code>{email}</code>\n"
        f"├─ ▸ <b>{fancy('Pass')}</b>: <code>{password}</code>\n"
        f"├─ ▸ <b>{fancy('User')}</b>: {info.get('user', '?')}\n"
        f"├─ ▸ <b>{fancy('Plan')}</b>: {info.get('plan', '?')}\n"
        f"├─ ▸ <b>{fancy('Expires')}</b>: {info.get('expires', '?')}\n"
        f"├─ ▸ <b>{fancy('Renew')}</b>: {info.get('renew', '?')}\n"
        f"├─ ▸ <b>{fancy('Streams')}</b>: {info.get('streams', '?')}\n"
        f"├─ ▸ <b>{fancy('Country')}</b>: {info.get('country', '?')}\n"
        f"├─ ▸ <b>{fancy('Payment')}</b>: {info.get('payment', '?')}\n"
        f"├─ ▸ <b>{fancy('Verified')}</b>: {info.get('verified', '?')}\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# JOB SUMMARY
# ═══════════════════════════════════════════
def job_summary_msg(ctx) -> str:
    """Build the final job summary message."""
    elapsed = ctx.elapsed()
    m, s = divmod(int(elapsed), 60)
    status_icon = "✓" if ctx.status == "completed" else ("⊘" if ctx.status == "cancelled" else "✕")
    return (
        f"╭─ {status_icon} {fancy('Job ' + ctx.status.title())}\n"
        f"├─ ▸ <b>{fancy('Job ID')}</b>: <code>{ctx.job_id}</code>\n"
        f"├─ ▸ <b>{fancy('Duration')}</b>: {m}m {s}s\n"
        f"├─ ▸ <b>{fancy('Total')}</b>: {fmt_num(ctx.checked)} / {fmt_num(ctx.total)}\n"
        f"├─ ▸ ☆ <b>{fancy('Hits')}</b>: {fmt_num(ctx.hits)}\n"
        f"├─ ▸ ○ <b>{fancy('Free')}</b>: {fmt_num(ctx.free)}\n"
        f"├─ ▸ ✕ <b>{fancy('Bad')}</b>: {fmt_num(ctx.bad)}\n"
        f"├─ ▸ ⚠ <b>{fancy('Retry')}</b>: {fmt_num(ctx.retry)}\n"
        f"├─ ▸ ⚠ <b>{fancy('Proxy Errors')}</b>: {fmt_num(ctx.proxy_errors)}\n"
        f"├─ ▸ <b>{fancy('Average Speed')}</b>: {ctx.cpm():.0f} CPM\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# MAIN MENU
# ═══════════════════════════════════════════
def main_menu_msg(user: dict, bot_config: dict) -> str:
    """Build the main menu message."""
    plan = user.get("plan", "free")
    plan_label = config.PLANS.get(plan, config.PLANS["free"])["label"]
    tid = user.get("telegram_id", 0)
    name = user.get("first_name", "") or user.get("username", "User")
    username = user.get("username", "")
    uname = f"@{username}" if username else name

    plan_expires = user.get("plan_expires_at", "")
    expires_str = ""
    if plan_expires:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(plan_expires)
            expires_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            expires_str = str(plan_expires)

    lines = [
        f"╭─ ⟡ {fancy('Welcome')}",
        f"├─ ▸ <b>{fancy('User')}</b>: {uname}",
        f"├─ ▸ <b>{fancy('ID')}</b>: <code>{tid}</code>",
        f"├─ ▸ <b>{fancy('Plan')}</b>: {plan_label}",
    ]
    if expires_str:
        lines.append(f"├─ ▸ <b>{fancy('Expires')}</b>: {expires_str}")
    lines.append(f"├─ ════════════════════════")
    lines.append(f"├─ ▸ <b>{fancy('Session')}</b>: {fmt_num(user.get('session_checked', 0))} checked")
    lines.append(f"├─   ☆ Hits: {fmt_num(user.get('session_hits', 0))}")
    lines.append(f"├─   ○ Free: {fmt_num(user.get('session_free', 0))}")
    lines.append(f"├─   ✕ Bad: {fmt_num(user.get('session_bad', 0))}")
    lines.append(f"├─ ════════════════════════")
    lines.append(f"├─ ▸ <b>{fancy('All Time')}</b>: {fmt_num(user.get('total_checked', 0))} checked")
    lines.append(f"├─   ☆ Hits: {fmt_num(user.get('total_hits', 0))}")
    lines.append(f"├─   ○ Free: {fmt_num(user.get('total_free', 0))}")
    lines.append(f"├─   ✕ Bad: {fmt_num(user.get('total_bad', 0))}")
    lines.append(f"├─ ════════════════════════")
    lines.append(f"├─ ▸ /check - {fancy('Check single account')}")
    lines.append(f"├─ ▸ /bulk - {fancy('Bulk check from file')}")
    lines.append(f"├─ ▸ /cancel - {fancy('Cancel current job')}")
    lines.append(f"├─ ▸ /plan - {fancy('View plan info')}")
    lines.append(f"├─ ▸ /redeem - {fancy('Redeem premium key')}")
    lines.append(f"├─ ▸ /proxies - {fancy('Proxy management')}")
    lines.append(f"{dev_footer()}")
    return "\n".join(lines)


# ═══════════════════════════════════════════
# PLAN INFO
# ═══════════════════════════════════════════
def plan_info_msg(current_plan: str = "free") -> str:
    """Build plan information message."""
    current_label = config.PLANS.get(current_plan, config.PLANS["free"])["label"]
    free = config.PLANS["free"]
    prem = config.PLANS["premium"]
    return (
        f"╭─ ⟡ {fancy('Plan Information')}\n"
        f"├─ ════════════════════════\n"
        f"├─ ▸ <b>{fancy('Current Plan')}</b>: {current_label}\n"
        f"├─ ════════════════════════\n"
        f"│\n"
        f"├─ ○ <b>{fancy('Free Plan')}</b>\n"
        f"│  ├─ Max per session: {fmt_num(free['max_combo'])}\n"
        f"│  ├─ Max concurrent jobs: {free['max_concurrent_jobs']}\n"
        f"│  └─ Speed limit: {free['speed_limit']} concurrent\n"
        f"│\n"
        f"├─ ☆ <b>{fancy('Premium Plan')}</b>\n"
        f"│  ├─ Max per session: {fmt_num(prem['max_combo'])}\n"
        f"│  ├─ Max concurrent jobs: {prem['max_concurrent_jobs']}\n"
        f"│  └─ Speed limit: {prem['speed_limit']} concurrent\n"
        f"│\n"
        f"├─ ════════════════════════\n"
        f"├─ ▸ Use /redeem <code>&lt;key&gt;</code> to upgrade\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# ADMIN STATS
# ═══════════════════════════════════════════
def admin_stats_msg(stats: dict) -> str:
    """Build admin statistics message."""
    return (
        f"╭─ ⟡ {fancy('Bot Statistics')}\n"
        f"├─ ════════════════════════\n"
        f"├─ ▸ <b>{fancy('Users')}</b>: {fmt_num(stats.get('total_users', 0))} total\n"
        f"│  ├─ Free: {fmt_num(stats.get('free_users', 0))}\n"
        f"│  ├─ Premium: {fmt_num(stats.get('premium_users', 0))}\n"
        f"│  └─ Banned: {fmt_num(stats.get('banned_users', 0))}\n"
        f"├─ ════════════════════════\n"
        f"├─ ▸ <b>{fancy('Checks')}</b>: {fmt_num(stats.get('total_checked', 0))} total\n"
        f"│  ├─ ☆ Hits: {fmt_num(stats.get('total_hits', 0))}\n"
        f"│  ├─ ○ Free: {fmt_num(stats.get('total_free', 0))}\n"
        f"│  └─ ✕ Bad: {fmt_num(stats.get('total_bad', 0))}\n"
        f"├─ ════════════════════════\n"
        f"├─ ▸ <b>{fancy('Proxies')}</b>: {fmt_num(stats.get('alive_proxies', 0))} / {fmt_num(stats.get('total_proxies', 0))} alive\n"
        f"├─ ▸ <b>{fancy('Jobs')}</b>: {stats.get('active_jobs', 0)} active / {fmt_num(stats.get('total_jobs', 0))} total\n"
        f"├─ ▸ <b>{fancy('Keys')}</b>: {stats.get('available_keys', 0)} available / {fmt_num(stats.get('total_keys', 0))} total\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# PROXY TEST PROGRESS
# ═══════════════════════════════════════════
def proxy_test_progress_msg(
    alive: int, dead: int, total: int, current: int
) -> str:
    bar = progress_bar(current, total)
    p = pct(current, total)
    return (
        f"╭─ ⟡ {fancy('Testing Proxies')}\n"
        f"├─ {bar} {p}\n"
        f"├─ ▸ <b>{fancy('Progress')}</b>: {fmt_num(current)} / {fmt_num(total)}\n"
        f"├─ ✓ <b>{fancy('Alive')}</b>: {fmt_num(alive)}\n"
        f"├─ ✕ <b>{fancy('Dead')}</b>: {fmt_num(dead)}\n"
        f"{dev_footer()}"
    )


# ═══════════════════════════════════════════
# ERROR MESSAGES
# ═══════════════════════════════════════════
def error_msg(title: str, detail: str = "") -> str:
    return (
        f"╭─ ✕ {fancy(title)}\n"
        f"├─ ▸ {detail}\n"
        f"{dev_footer()}"
    )


def success_msg(title: str, detail: str = "") -> str:
    return (
        f"╭─ ✓ {fancy(title)}\n"
        f"├─ ▸ {detail}\n"
        f"{dev_footer()}"
    )

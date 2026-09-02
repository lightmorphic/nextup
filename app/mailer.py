"""The morning email.

Once a day, a short message listing what has become watchable. What counts
as watchable is the same rule the rest of the app uses, so if you have said
a programme is only really available the day after it airs, it appears in
the following morning's email rather than that morning's.

The SMTP password is typed into the Settings page and stored encrypted,
never in an environment file.
"""
import smtplib
import ssl
import threading
import time
from datetime import date, datetime, time as clock_time, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from . import db, queries, secretstore

SITE_URL = "https://lightmorphic.com"

# Email clients only reliably understand inline styles and tables, so the
# colours live here rather than in a stylesheet.
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
BRAND = "#fbc711"
ON_BRAND = "#645007"
INK = "#111827"
MUTED = "#6e6e77"
LINE = "#e4e4e7"
WASH = "#f7f7f8"

DEFAULT_PORT = 587
DEFAULT_HOUR = 8
DEFAULT_TIME = "08:00"
SECURITIES = ("starttls", "ssl", "none")
CLOCKS = ("24", "12")


def clock_format():
    """Whether times are shown on a 24 hour clock or with am and pm."""
    return "12" if secretstore.get("clock_format", "24") == "12" else "24"


def send_time():
    """When the morning email should go out, as a time of day."""
    raw = secretstore.get("daily_email_time")
    if not raw:
        # Older installs stored only an hour.
        legacy = secretstore.get("daily_email_hour")
        raw = f"{_int(legacy, DEFAULT_HOUR, 0, 23):02d}:00" if legacy else DEFAULT_TIME
    return parse_time(raw) or parse_time(DEFAULT_TIME)


def parse_time(raw):
    """Read "HH:MM". Returns None if it is not a real time."""
    if not raw or ":" not in str(raw):
        return None
    hours, _, minutes = str(raw).partition(":")
    if not (hours.strip().isdigit() and minutes.strip().isdigit()):
        return None
    hour, minute = int(hours), int(minutes)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return clock_time(hour=hour, minute=minute)


def format_time(value, clock=None):
    """A time written the way the user has asked to read it."""
    clock = clock or clock_format()
    if clock == "12":
        hour = value.hour % 12 or 12
        return f"{hour}:{value.minute:02d} {'am' if value.hour < 12 else 'pm'}"
    return f"{value.hour:02d}:{value.minute:02d}"


class MailError(RuntimeError):
    pass


def config():
    """Everything the mailer needs, with the password left out."""
    when = send_time()
    clock = clock_format()
    return {
        "host": secretstore.get("smtp_host", "") or "",
        "port": _int(secretstore.get("smtp_port", str(DEFAULT_PORT)), DEFAULT_PORT),
        "security": secretstore.get("smtp_security", "starttls") or "starttls",
        "username": secretstore.get("smtp_username", "") or "",
        "has_password": bool(secretstore.get("smtp_password")),
        "from_address": secretstore.get("mail_from", "") or "",
        "from_name": secretstore.get("mail_from_name", "Nextup") or "Nextup",
        "to_address": secretstore.get("mail_to", "") or "",
        "enabled": secretstore.get("daily_email_enabled", "0") == "1",
        "time": when,
        "time_value": f"{when.hour:02d}:{when.minute:02d}",
        "time_display": format_time(when, clock),
        "hour_24": when.hour,
        "hour_12": when.hour % 12 or 12,
        "minute": when.minute,
        "meridiem": "am" if when.hour < 12 else "pm",
        "clock": clock,
        "last_sent": secretstore.get("daily_email_last_sent", "") or "",
    }


def _int(value, fallback, low=None, high=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    if low is not None and number < low:
        return fallback
    if high is not None and number > high:
        return fallback
    return number


def is_configured():
    settings = config()
    return bool(settings["host"] and settings["from_address"] and settings["to_address"])


def _connect(settings):
    password = secretstore.get("smtp_password", "")
    try:
        if settings["security"] == "ssl":
            server = smtplib.SMTP_SSL(
                settings["host"], settings["port"], timeout=30,
                context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(settings["host"], settings["port"], timeout=30)
            if settings["security"] == "starttls":
                server.starttls(context=ssl.create_default_context())
        server.ehlo()
        if settings["username"] and password:
            server.login(settings["username"], password)
        return server
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError("The mail server rejected that username and password.") from exc
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise MailError(f"Could not reach the mail server: {exc}") from exc


def send(subject, text_body, html_body=None):
    settings = config()
    if not is_configured():
        raise MailError("Fill in the mail server, the from address and the to address first.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings["from_name"], settings["from_address"]))
    message["To"] = settings["to_address"]
    message["Date"] = formatdate(localtime=True)
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    server = _connect(settings)
    try:
        server.send_message(message)
    except smtplib.SMTPException as exc:
        raise MailError(f"The mail server refused the message: {exc}") from exc
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001 - closing is best effort
            pass


def send_test():
    offset = queries.available_after_days()
    when = "the day it airs" if offset == 0 else f"{offset} day{'s' if offset != 1 else ''} after it airs"
    at = format_time(send_time())
    text = (
        "This is a test from Nextup.\n\n"
        "If you are reading it, the mail settings work and the morning email "
        f"will go out from here at {at}.\n\n"
        f"At the moment Nextup treats a programme as watchable {when}.\n\n"
        f"Made by Lightmorphic. {SITE_URL}\n"
    )
    html = _html_shell(
        "It works",
        f"<p style=\"margin:0;font:400 15px/1.6 {FONT};color:{MUTED}\">"
        "If you are reading this, the mail settings are right and the morning "
        f"email will go out from here at <strong style=\"color:{INK}\">{_esc(at)}</strong>."
        "</p>"
        f"<p style=\"margin:14px 0 0;font:400 15px/1.6 {FONT};color:{MUTED}\">"
        f"Nextup currently treats a programme as watchable {_esc(when)}.</p>",
    )
    send("Nextup test message", text, html)


def _episode_line(row):
    code = f"S{row['season_number']:02d}E{row['episode_number']:02d}"
    name = row["name"] or f"Episode {row['episode_number']}"
    watched = " (already ticked off)" if row["watched"] else ""
    return f"{row['show_name']} {code} - {name}{watched}"


def build_digest():
    """The message body, or None when there is nothing worth sending."""
    today = queries.available_today()
    episodes, films = today["episodes"], today["films"]
    if not episodes and not films:
        return None

    when = date.fromisoformat(today["date"]).strftime("%A %-d %B")
    counts = []
    if episodes:
        counts.append(f"{len(episodes)} episode{'s' if len(episodes) != 1 else ''}")
    if films:
        counts.append(f"{len(films)} film{'s' if len(films) != 1 else ''}")
    subject = "Ready to watch: " + " and ".join(counts)

    lines = [f"Available to watch now, from {when}.", ""]
    if episodes:
        lines.append("Television")
        lines += [f"  {_episode_line(row)}" for row in episodes]
        lines.append("")
    if films:
        lines.append("Films")
        for row in films:
            services = queries.provider_names(row)
            where = f" - on {', '.join(services)}" if services else ""
            lines.append(f"  {row['title']}{where}")
        lines.append("")
    lines.append("Sent by Nextup, running on your own server.")
    lines.append(f"Made by Lightmorphic. {SITE_URL}")
    text = "\n".join(lines)

    return subject, text, _html_digest(when, episodes, films)


def _esc(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_shell(heading, inner, standfirst=""):
    """The frame every Nextup email sits in: the name at the top, the credit at
    the bottom, and whatever the message is in between."""
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nextup</title></head>
<body style="margin:0;padding:0;background:{WASH};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{WASH};padding:28px 12px">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;max-width:600px;background:#ffffff;border:1px solid {LINE};
                  border-radius:18px;overflow:hidden">
      <tr><td style="padding:26px 32px 4px 32px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="background:{BRAND};border-radius:9px;width:34px;height:34px;
                     text-align:center;vertical-align:middle;
                     font:700 17px/34px {FONT};color:{ON_BRAND}">N</td>
          <td style="padding-left:11px;font:800 21px/1.2 {FONT};letter-spacing:-.03em;
                     color:{INK}">Nextup</td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:16px 32px 0 32px">
        <p style="margin:0;font:700 20px/1.3 {FONT};letter-spacing:-.02em;color:{INK}">
          {heading}</p>
        {standfirst}
      </td></tr>
      <tr><td style="padding:16px 32px 24px 32px">{inner}</td></tr>
      <tr><td style="padding:16px 32px 22px 32px;border-top:1px solid {LINE};
                     background:{WASH}">
        <p style="margin:0;font:400 13px/1.6 {FONT};color:{MUTED}">
          Made by <a href="{SITE_URL}" style="color:{INK};font-weight:700;
          text-decoration:none">Lightmorphic</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _html_section(title, rows):
    """One headed block of the email, as table rows."""
    out = [
        '<tr><td style="padding:26px 32px 10px 32px">'
        f'<p style="margin:0;font:600 12px/1.4 {FONT};letter-spacing:.09em;'
        f'text-transform:uppercase;color:{MUTED}">{_esc(title)}</p></td></tr>'
    ]
    for i, (headline, detail) in enumerate(rows):
        border = "" if i == 0 else f"border-top:1px solid {LINE};"
        out.append(
            f'<tr><td style="padding:0 32px"><table role="presentation" width="100%" '
            'cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td style="{border}padding:12px 0">'
            f'<p style="margin:0;font:600 16px/1.45 {FONT};color:{INK}">{_esc(headline)}</p>'
            + (
                f'<p style="margin:3px 0 0;font:400 14px/1.45 {FONT};color:{MUTED}">'
                f"{_esc(detail)}</p>"
                if detail
                else ""
            )
            + "</td></tr></table></td></tr>"
        )
    return "".join(out)


def _html_digest(when, episodes, films):
    """A plain, readable email. Tables and inline styles, because that is what
    mail clients understand, and no images, because nothing here is on the
    public internet to load them from."""
    tv_rows = []
    for row in episodes:
        code = f"S{row['season_number']:02d}E{row['episode_number']:02d}"
        name = row["name"] or f"Episode {row['episode_number']}"
        detail = f"{code} · {name}"
        if row["network"]:
            detail += f" · {row['network']}"
        if row["watched"]:
            detail += " · already ticked off"
        tv_rows.append((row["show_name"], detail))

    film_rows = []
    for row in films:
        services = queries.provider_names(row)
        detail = "On " + ", ".join(services) if services else "Out for home viewing"
        if row["runtime"]:
            detail += f" · {row['runtime']} min"
        film_rows.append((row["title"], detail))

    body = ""
    if tv_rows:
        body += _html_section("Television", tv_rows)
    if film_rows:
        body += _html_section("Films", film_rows)

    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nextup</title></head>
<body style="margin:0;padding:0;background:{WASH};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">
Available to watch now, from {_esc(when)}.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{WASH};padding:28px 12px">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;max-width:600px;background:#ffffff;border:1px solid {LINE};
                  border-radius:18px;overflow:hidden">

      <tr><td style="padding:26px 32px 4px 32px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="background:{BRAND};border-radius:9px;width:34px;height:34px;
                     text-align:center;vertical-align:middle;
                     font:700 17px/34px {FONT};color:{ON_BRAND}">N</td>
          <td style="padding-left:11px;font:800 21px/1.2 {FONT};letter-spacing:-.03em;
                     color:{INK}">Nextup</td>
        </tr></table>
      </td></tr>

      <tr><td style="padding:16px 32px 0 32px">
        <p style="margin:0;font:700 20px/1.3 {FONT};letter-spacing:-.02em;color:{INK}">
          Ready to watch</p>
        <p style="margin:6px 0 0;font:400 15px/1.5 {FONT};color:{MUTED}">
          Everything below became available on {_esc(when)}.</p>
      </td></tr>

      {body}

      <tr><td style="padding:20px 32px 26px 32px">
        <p style="margin:0;font:400 13px/1.6 {FONT};color:{MUTED}">
          Sent by Nextup, running on your own server. To change when this arrives,
          or to stop it, open the Settings page.</p>
      </td></tr>

      <tr><td style="padding:16px 32px 22px 32px;border-top:1px solid {LINE};
                     background:{WASH}">
        <p style="margin:0;font:400 13px/1.6 {FONT};color:{MUTED}">
          Made by <a href="{SITE_URL}" style="color:{INK};font-weight:700;
          text-decoration:none">Lightmorphic</a></p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>"""


def send_daily(force=False):
    """Send this morning's email. Returns a short line saying what happened."""
    settings = config()
    if not settings["enabled"] and not force:
        return "The morning email is switched off."
    if not is_configured():
        return "The mail settings are not complete."

    today = date.today().isoformat()
    if not force and settings["last_sent"] == today:
        return "Already sent today."

    digest = build_digest()
    if digest is None:
        # Record the attempt so an empty day does not retry every ten minutes.
        secretstore.set("daily_email_last_sent", today)
        return "Nothing became available today, so no email was sent."

    subject, text, html = digest
    send(subject, text, html)
    secretstore.set("daily_email_last_sent", today)
    return f"Sent: {subject}"


def start_background(app):
    """Check every ten minutes whether this morning's email is due."""

    def loop():
        time.sleep(40)
        while True:
            with app.app_context():
                try:
                    settings = config()
                    if settings["enabled"] and is_configured():
                        now = datetime.now()
                        due = now.time() >= settings["time"]
                        if due and settings["last_sent"] != now.date().isoformat():
                            app.logger.info("Nextup: %s", send_daily())
                except Exception:  # keep the thread alive whatever happens
                    app.logger.exception("The morning email failed")
            time.sleep(120)

    thread = threading.Thread(target=loop, name="nextup-mail", daemon=True)
    thread.start()
    return thread

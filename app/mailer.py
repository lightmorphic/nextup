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
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from . import db, queries, secretstore

DEFAULT_PORT = 587
DEFAULT_HOUR = 8
SECURITIES = ("starttls", "ssl", "none")


class MailError(RuntimeError):
    pass


def config():
    """Everything the mailer needs, with the password left out."""
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
        "hour": _int(secretstore.get("daily_email_hour", str(DEFAULT_HOUR)), DEFAULT_HOUR, 0, 23),
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
    send(
        "Nextup test message",
        "This is a test from Nextup.\n\n"
        "If you are reading it, the mail settings work and the morning email "
        "will go out from here.\n\n"
        f"At the moment Nextup treats a programme as watchable {when}.\n",
    )


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
    lines.append("Sent by Nextup, from your own server.")
    text = "\n".join(lines)

    def esc(value):
        return (
            str(value or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    html = [
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
        'font-size:16px;line-height:1.6;color:#111827;max-width:600px">',
        f'<p style="margin:0 0 18px">Available to watch now, from {esc(when)}.</p>',
    ]
    if episodes:
        html.append('<h2 style="font-size:15px;text-transform:uppercase;letter-spacing:.05em;'
                    'color:#6e6e77;margin:0 0 8px">Television</h2>')
        html.append('<ul style="margin:0 0 22px;padding-left:20px">')
        html += [f'<li style="margin-bottom:6px">{esc(_episode_line(row))}</li>' for row in episodes]
        html.append("</ul>")
    if films:
        html.append('<h2 style="font-size:15px;text-transform:uppercase;letter-spacing:.05em;'
                    'color:#6e6e77;margin:0 0 8px">Films</h2>')
        html.append('<ul style="margin:0 0 22px;padding-left:20px">')
        for row in films:
            services = queries.provider_names(row)
            where = f' <span style="color:#6e6e77">on {esc(", ".join(services))}</span>' if services else ""
            html.append(f'<li style="margin-bottom:6px">{esc(row["title"])}{where}</li>')
        html.append("</ul>")
    html.append('<p style="color:#6e6e77;font-size:13px;margin:0">'
                "Sent by Nextup, from your own server.</p></div>")

    return subject, text, "".join(html)


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
                        due = now.hour >= settings["hour"]
                        if due and settings["last_sent"] != now.date().isoformat():
                            app.logger.info("Nextup: %s", send_daily())
                except Exception:  # keep the thread alive whatever happens
                    app.logger.exception("The morning email failed")
            time.sleep(600)

    thread = threading.Thread(target=loop, name="nextup-mail", daemon=True)
    thread.start()
    return thread

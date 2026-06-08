"""
Watchlist Notifier — sends notifications when watchlist matches are found.
Supports Discord, Telegram, Email, and console output.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
import json

from config import settings

logger = logging.getLogger(__name__)


class WatchlistNotifier:
    """Send notifications when watchlist matches are found."""

    def notify_matches(self, matches: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Send notifications for all watchlist matches via configured channels.

        Returns dict with channel -> notification_count
        """
        if not matches:
            logger.info("No matches to notify")
            return {}

        stats: Dict[str, int] = {}

        # Group matches by watchlist
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for m in matches:
            wl_name = m["watchlist"]["name"]
            if wl_name not in grouped:
                grouped[wl_name] = []
            grouped[wl_name].append(m)

        # Always log to console
        stats["console"] = self._notify_console(grouped)

        # Discord
        if settings.discord_webhook:
            try:
                stats["discord"] = self._notify_discord(grouped)
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")

        # Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                stats["telegram"] = self._notify_telegram(grouped)
            except Exception as e:
                logger.error(f"Telegram notification failed: {e}")

        # Email
        if settings.email_to and settings.email_smtp_server:
            try:
                stats["email"] = self._notify_email(grouped)
            except Exception as e:
                logger.error(f"Email notification failed: {e}")

        logger.info(f"Notifications sent: {stats}")
        return stats

    def _notify_console(self, grouped: Dict[str, List[Dict[str, Any]]]) -> int:
        """Print matches to console."""
        count = 0
        print(f"\n{'='*70}")
        print(f"  WATCHLIST MATCHES FOUND!")
        print(f"{'='*70}")

        for wl_name, items in grouped.items():
            print(f"\n  >>> {wl_name} ({len(items)} matches)")
            print(f"  {'-'*50}")

            for item in items[:5]:  # Top 5 per watchlist
                v = item["vehicle"]
                print(f"  {v['brand']} {v['model']} ({v['year']})")
                print(f"    Price: €{v['price']:,.2f} | Est: €{v['estimated_value']:,.2f}")
                if v.get("deal_score"):
                    print(f"    Score: {v['deal_score']:.1f}/10 | Profit: €{v['profit_potential']:,.2f}")
                print(f"    {v['url']}")
                count += 1

            if len(items) > 5:
                print(f"    ... and {len(items) - 5} more matches")

        print(f"\n  Total: {count} matches across {len(grouped)} watchlists")
        print(f"{'='*70}\n")
        return count

    def _notify_discord(self, grouped: Dict[str, List[Dict[str, Any]]]) -> int:
        """Send notifications to Discord webhook."""
        import requests

        count = 0
        for wl_name, items in grouped.items():
            top = items[:5]
            message = f"**🔔 Watchlist Alert: {wl_name}**\n"
            message += f"Found {len(items)} matching vehicle(s):\n\n"

            for item in top:
                v = item["vehicle"]
                message += f"**{v['brand']} {v['model']} ({v['year']})**\n"
                message += f"> Price: €{v['price']:,.2f} | Score: {v.get('deal_score', 'N/A')}\n"
                message += f"> Profit: €{v.get('profit_potential', 0):,.2f} | KM: {v.get('km', 'N/A')}\n"
                message += f"> {v['url']}\n\n"
                count += 1

            if len(items) > 5:
                message += f"... and {len(items) - 5} more matches\n"

            try:
                resp = requests.post(
                    settings.discord_webhook,
                    json={"content": message[:2000]},  # Discord limit
                    timeout=10,
                )
                if resp.status_code == 204:
                    logger.info(f"Discord notification sent for '{wl_name}'")
            except Exception as e:
                logger.error(f"Discord webhook failed: {e}")

        return count

    def _notify_telegram(self, grouped: Dict[str, List[Dict[str, Any]]]) -> int:
        """Send notifications via Telegram bot."""
        import requests

        count = 0
        token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"

        for wl_name, items in grouped.items():
            top = items[:3]
            text = f"🔔 *Watchlist: {wl_name}*\n{len(items)} matches found\n\n"

            for item in top:
                v = item["vehicle"]
                text += f"• *{v['brand']} {v['model']}* ({v['year']})\n"
                text += f"  €{v['price']:,.2f} | Score: {v.get('deal_score', 'N/A')}\n"
                text += f"  Profit: €{v.get('profit_potential', 0):,.2f}\n\n"
                count += 1

            try:
                resp = requests.post(
                    api_url,
                    json={
                        "chat_id": chat_id,
                        "text": text[:4096],
                        "parse_mode": "Markdown",
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.info(f"Telegram notification sent for '{wl_name}'")
            except Exception as e:
                logger.error(f"Telegram notification failed: {e}")

        return count

    def _notify_email(self, grouped: Dict[str, List[Dict[str, Any]]]) -> int:
        """Send notifications via email."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        count = 0
        if not all([settings.email_smtp_server, settings.email_smtp_user, settings.email_smtp_password]):
            return 0

        subject = f"AutoDeal Watchlist: {count} matches found"
        body_html = "<h2>Watchlist Matches Found</h2>\n"

        for wl_name, items in grouped.items():
            body_html += f"<h3>{wl_name} ({len(items)} matches)</h3><ul>\n"
            for item in items[:5]:
                v = item["vehicle"]
                body_html += (
                    f"<li><strong>{v['brand']} {v['model']} ({v['year']})</strong><br>"
                    f"Price: €{v['price']:,.2f} | "
                    f"Score: {v.get('deal_score', 'N/A')}<br>"
                    f"<a href='{v['url']}'>View Listing</a></li>\n"
                )
                count += 1
            body_html += "</ul>\n"

        try:
            msg = MIMEMultipart()
            msg["From"] = settings.email_smtp_user
            msg["To"] = settings.email_to
            msg["Subject"] = subject
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(settings.email_smtp_server, settings.email_smtp_port) as server:
                server.starttls()
                server.login(settings.email_smtp_user, settings.email_smtp_password)
                server.send_message(msg)
            logger.info("Email notification sent")
        except Exception as e:
            logger.error(f"Email notification failed: {e}")

        return count
"""
Daily job scheduler for automated scraping, analysis, and watchlist checking
"""
from __future__ import annotations
import logging
import asyncio
from datetime import datetime, time, timezone
from typing import Dict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from core.settings import settings
from scrapers.olx_scraper import OLXScraper
from scrapers.standvirtual_scraper import StandvirtualScraper
from scrapers.autosapo_scraper import AutoSapoScraper
from valuation.predict import update_vehicle_valuations
from ai_agent.deal_finder import DealFinder
from database.db import init_db
from alerts.watchlist_matcher import WatchlistMatcher
from alerts.watchlist_notifier import WatchlistNotifier

logger = logging.getLogger(__name__)

# Default timezone for scheduler
SCHEDULER_TZ = "Europe/Lisbon"


class DailyJob:
    """Daily automated job for scraping, analysis, and watchlist monitoring"""
    
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
        self.olx_scraper = OLXScraper()
        self.standvirtual_scraper = StandvirtualScraper()
        self.autosapo_scraper = AutoSapoScraper()
        self.deal_finder = DealFinder()
        self.watchlist_matcher = WatchlistMatcher()
        self.watchlist_notifier = WatchlistNotifier()
    
    async def run(self) -> Dict[str, object]:
        """Async entry point for scheduler tests (does not run full scrape loop)."""
        return {"status": "ok", "job": "daily"}

    def run_scraping_job(self) -> None:
        """Run complete scraping pipeline"""
        logger.info("=" * 60)
        logger.info("Starting daily scraping job")
        logger.info("=" * 60)
        
        try:
            # Initialize database
            init_db()

            async def _run_async_scraping() -> None:
                from database.db import get_db_context
                from database.models import Vehicle, Source
                from sqlalchemy import select

                def save_deduped(listings, source_name, vehicle_type):
                    """Save listings with deduplication by source + source_id"""
                    if not listings:
                        return 0
                    added = 0
                    updated = 0
                    with get_db_context() as db:
                        for listing in listings:
                            source_id = listing.get("source_id") or listing.get("id")
                            if not source_id:
                                continue
                            existing = db.execute(
                                select(Vehicle).where(
                                    Vehicle.source == Source(source_name),
                                    Vehicle.source_id == str(source_id)
                                )
                            ).scalar_one_or_none()
                            if existing:
                                # Update price and last_seen
                                existing.price = listing.get("price", existing.price)
                                existing.last_seen = datetime.now(timezone.utc)
                                existing.scrape_count = (existing.scrape_count or 1) + 1
                                
                                # Update detailed fields if available
                                if listing.get("horsepower") is not None:
                                    existing.horsepower = listing.get("horsepower")
                                if listing.get("engine_size") is not None:
                                    existing.engine_size = listing.get("engine_size")
                                if listing.get("doors") is not None:
                                    existing.doors = listing.get("doors")
                                if listing.get("color"):
                                    existing.color = listing.get("color")
                                if listing.get("description"):
                                    existing.description = listing.get("description")
                                if listing.get("fuel_type"):
                                    existing.fuel_type = listing.get("fuel_type")
                                if listing.get("transmission"):
                                    existing.transmission = listing.get("transmission")
                                if listing.get("images"):
                                    existing.images = listing.get("images")
                                
                                updated += 1
                            else:
                                vehicle = Vehicle(
                                    source=Source(source_name),
                                    source_id=str(source_id),
                                    url=listing.get("url", ""),
                                    vehicle_type=vehicle_type,
                                    brand=listing.get("brand", "Unknown"),
                                    model=listing.get("model", "Unknown"),
                                    year=listing.get("year"),
                                    km=listing.get("km"),
                                    price=listing.get("price", 0),
                                    title=listing.get("title", ""),
                                    location=listing.get("location"),
                                    description=listing.get("description"),
                                    images=listing.get("images"),
                                    fuel_type=listing.get("fuel_type"),
                                    transmission=listing.get("transmission"),
                                    horsepower=listing.get("horsepower"),
                                    engine_size=listing.get("engine_size"),
                                    doors=listing.get("doors"),
                                    color=listing.get("color"),
                                    seller_name=listing.get("seller_name"),
                                    seller_type=listing.get("seller_type"),
                                    extras=listing.get("extras"),
                                )
                                db.add(vehicle)
                                added += 1
                        db.commit()
                    logger.info(f"[{source_name}] Adicionados: {added}, Atualizados: {updated}")
                    return added + updated

                scraper_failures = []

                def record_source(name, listings, saved):
                    if not listings:
                        scraper_failures.append(name)
                        logger.error("[%s] devolveu 0 anúncios; ciclo marcado como falhado", name)
                    logger.info("[%s] encontrados=%d persistidos=%d", name, len(listings or []), saved)

                logger.info("Scraping OLX...")
                olx_listings = await self.olx_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("OLX:carros", olx_listings, save_deduped(olx_listings, "OLX", "carros"))

                olx_motos = await self.olx_scraper.scrape_listings("motos", max_listings=30, scrape_details=True)
                record_source("OLX:motos", olx_motos, save_deduped(olx_motos, "OLX", "motos"))

                logger.info("Scraping Standvirtual...")
                sv_listings = await self.standvirtual_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("STANDVIRTUAL", sv_listings, save_deduped(sv_listings, "STANDVIRTUAL", "carros"))

                logger.info("Scraping AutoSapo...")
                as_listings = await self.autosapo_scraper.scrape_listings("carros", max_listings=50, scrape_details=True)
                record_source("AUTOSAPO", as_listings, save_deduped(as_listings, "AUTOSAPO", "carros"))
                if scraper_failures:
                    raise RuntimeError("Fontes sem anúncios ou bloqueadas: " + ", ".join(scraper_failures))

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_run_async_scraping())
            else:
                raise RuntimeError("run_scraping_job não pode ser chamado dentro de um event loop ativo")
            
            # Update valuations
            logger.info("Updating vehicle valuations...")
            update_vehicle_valuations(batch_size=200)
            
            # Find and analyze best deals
            logger.info("Finding best deals...")
            best_deals = self.deal_finder.run_daily_analysis()
            
            # Send notifications
            if best_deals:
                logger.info(f"Sending notifications for {len(best_deals)} deals")
                self.send_notifications(best_deals)
            
            logger.info("Daily scraping job completed successfully")
            
        except Exception as e:
            logger.error(f"Error in daily scraping job: {e}")
            raise
    
    def run_analysis_job(self) -> None:
        """Run AI analysis on existing vehicles"""
        logger.info("Starting AI analysis job")
        
        try:
            # Update valuations
            update_vehicle_valuations(batch_size=100)
            
            # Find best deals
            best_deals = self.deal_finder.run_daily_analysis()
            
            # Send notifications
            if best_deals:
                self.send_notifications(best_deals)
            
            logger.info("AI analysis job completed")
            
        except Exception as e:
            logger.error(f"Error in AI analysis job: {e}")
    
    def run_watchlist_checker(self) -> None:
        """Check all watchlists for matching vehicles"""
        logger.info("=" * 40)
        logger.info("Running watchlist checker")
        logger.info("=" * 40)
        
        try:
            matches = self.watchlist_matcher.check_all_watchlists()
            
            if matches:
                logger.info(f"Found {len(matches)} watchlist matches — sending notifications")
                self.watchlist_notifier.notify_matches(matches)
            else:
                logger.info("No watchlist matches found")
                
        except Exception as e:
            logger.error(f"Error in watchlist checker: {e}")

    # ── Re-treino periódico controlado ───────────────────────────────────────
    RETRAIN_STATE_PATH = "models/retrain_state.json"
    RETRAIN_MIN_NEW_LISTINGS = 500  # só re-treina com pelo menos este volume novo

    def run_retrain_job(self) -> None:
        """Re-treino semanal CONTROLADO do modelo de avaliação.

        Só re-treina se houver >= RETRAIN_MIN_NEW_LISTINGS anúncios novos desde
        o último treino (evita re-treinos vazios e oscilação do modelo).
        Ordem: treino segmentado (LOW/FULL) -> treino HIGH -> ligação do routing
        HIGH aos metadados -> re-avaliação -> métricas de observabilidade.
        """
        import json
        import subprocess
        import sys
        from pathlib import Path

        logger.info("=" * 60)
        logger.info("Re-treino periódico controlado — verificação")
        logger.info("=" * 60)

        try:
            from database.db import get_db_context
            from database.models import Vehicle

            state_path = Path(self.RETRAIN_STATE_PATH)
            state = {}
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except Exception:
                    state = {}

            with get_db_context() as db:
                current_n = db.query(Vehicle).filter(Vehicle.is_active == True).count()  # noqa: E712

            last_n = int(state.get("n_listings_at_train", 0))
            new_since = current_n - last_n
            logger.info("Anúncios ativos: %d | no último treino: %d | novos: %d",
                        current_n, last_n, new_since)

            if last_n > 0 and new_since < self.RETRAIN_MIN_NEW_LISTINGS:
                logger.info("Re-treino adiado: apenas %d novos (< %d mínimo)",
                            new_since, self.RETRAIN_MIN_NEW_LISTINGS)
                return

            py = sys.executable
            for script in ("scripts/train_segmented.py", "scripts/train_high.py"):
                logger.info("A correr %s ...", script)
                proc = subprocess.run([py, "-u", script], capture_output=True, text=True)
                if proc.returncode != 0:
                    logger.error("Falha em %s:\n%s", script, proc.stderr[-2000:])
                    return
                logger.info("%s OK", script)

            # Ligar modelo HIGH aos metadados de produção
            mdir = Path(settings.models_dir)
            meta = json.loads((mdir / "best_model_carros.json").read_text(encoding="utf-8"))
            high_meta = json.loads((mdir / "model_carros_high.meta.json").read_text(encoding="utf-8"))
            meta.update({
                "high_model_path": "model_carros_high.json",
                "high_threshold": high_meta["high_threshold"],
                "high_log_target": high_meta["high_log_target"],
                "high_cat_features": high_meta["high_cat_features"],
                "high_metrics_true_ge_20k": high_meta["metrics_true_ge_20k_after"],
            })
            (mdir / "best_model_carros.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            # Re-avaliação incremental (só quem não tem a versão atual)
            total = 0
            while True:
                n = update_vehicle_valuations(batch_size=300)
                total += n
                if n == 0:
                    break
            logger.info("Re-avaliados %d anúncios", total)

            # Métricas de observabilidade
            subprocess.run([py, "-u", "scripts/valuation_metrics.py"],
                           capture_output=True, text=True)

            state_path.write_text(json.dumps({
                "n_listings_at_train": current_n,
                "trained_at": datetime.now().isoformat(),
                "r2": meta.get("metrics", {}).get("r2"),
                "mape_pct": meta.get("metrics", {}).get("mape_pct"),
            }, indent=2), encoding="utf-8")
            logger.info("Re-treino controlado concluído (R²=%s)",
                        meta.get("metrics", {}).get("r2"))

        except Exception as e:
            logger.error(f"Error in retrain job: {e}")
    
    def send_notifications(self, deals: list[dict[str, object]]) -> None:
        """Send notifications via configured channels"""
        # Discord
        if settings.discord_webhook:
            self.send_discord_notification(deals)

        # Email
        if settings.email_to:
            self.send_email_notification(deals)

        # Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            self.send_telegram_notification(deals)
    
    def send_discord_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification to Discord webhook"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Discord notification")
            return

        if not settings.discord_webhook:
            return
        
        # Build message
        message = f"**🚗 Top {len(deals)} Auto Deals Found**\n\n"
        
        for deal in deals:
            message += f"\n**{deal.get('brand')} {deal.get('model')} ({deal.get('year')})**\n"
            message += f"Price: €{deal.get('price')}\n"
            message += f"Score: {deal.get('deal_score')}\n"
            message += f"Profit: €{deal.get('profit_potential')}\n"
            if deal.get('ai_review'):
                message += f"Review: {str(deal.get('ai_review'))[:200]}...\n"
            message += f"{deal.get('url')}\n\n"
        
        data = {"content": message}

        try:
            response = requests.post(settings.discord_webhook, json=data, timeout=10)
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(f"Discord notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    def send_email_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification via email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
        except ImportError:
            logger.warning("Email libraries not available, skipping email notification")
            return

        if not all([settings.email_smtp_server, settings.email_smtp_user, settings.email_smtp_password, settings.email_from]):
            return
        
        # Build email content
        subject = f"Top {len(deals)} Auto Deals Found - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"<h2>Top {len(deals)} Auto Deals Found</h2>\n"
        
        for i, deal in enumerate(deals[:10], 1):
            body += f"""
            <h3>{i}. {deal.get('brand')} {deal.get('model')} ({deal.get('year')})</h3>
            <ul>
                <li><strong>Price:</strong> €{deal.get('price'):,}</li>
                <li><strong>Estimated Value:</strong> €{deal.get('estimated_value'):,}</li>
                <li><strong>Profit:</strong> €{deal.get('profit_potential'):,}</li>
                <li><strong>Profit %:</strong> {deal.get('profit_percentage'):.1f}%</li>
                <li><strong>Score:</strong> {deal.get('deal_score'):.1f}/10</li>
                <li><strong>URL:</strong> <a href="{deal.get('url')}">View Listing</a></li>
            </ul>
            <hr>
            """
        
        msg = MIMEMultipart()
        msg['From'] = settings.email_from
        recipients = settings.email_to
        if isinstance(recipients, list):
            msg['To'] = ", ".join(recipients)
        else:
            msg['To'] = recipients
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(settings.email_smtp_server, settings.email_smtp_port) as server:
                server.starttls()
                server.login(settings.email_smtp_user, settings.email_smtp_password)
                server.send_message(msg)
            logger.info("Email notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    def send_telegram_notification(self, deals: list[dict[str, object]]) -> None:
        """Send notification via Telegram"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Telegram notification")
            return

        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return
        
        # Build message
        message = f"🚗 *Top {len(deals)} Auto Deals Found*\n\n"
        
        for i, deal in enumerate(deals[:10], 1):
            message += (
                f"*{i}. {deal.get('brand')} {deal.get('model')} ({deal.get('year')})*\n"
                f"💰 Price: €{deal.get('price'):,} | Est: €{deal.get('estimated_value'):,}\n"
                f"📈 Profit: €{deal.get('profit_potential'):,} ({deal.get('profit_percentage'):.1f}%)\n"
                f"⭐ Score: {deal.get('deal_score'):.1f}/10\n"
                f"🔗 {deal.get('url')}\n\n"
            )
        
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
            else:
                logger.warning(f"Telegram notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    def start(self) -> None:
        """Start the scheduler"""
        logger.info("Starting scheduler")

        # Parse scraping time
        hour, minute = settings.daily_scraping_time.split(":")

        # Add daily scraping job
        self.scheduler.add_job(
            self.run_scraping_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_scraping',
            name='Daily Scraping Job',
            replace_existing=True
        )

        # Add periodic analysis job (every 6 hours)
        self.scheduler.add_job(
            self.run_analysis_job,
            trigger='interval',
            hours=settings.scraping_interval_hours if hasattr(settings, 'scraping_interval_hours') else settings.scrape_interval_hours,
            id='periodic_analysis',
            name='Periodic Analysis Job',
            replace_existing=True
        )
        
        # Add watchlist checker job (every hour)
        self.scheduler.add_job(
            self.run_watchlist_checker,
            trigger='interval',
            hours=1,
            id='watchlist_checker',
            name='Watchlist Match Checker',
            replace_existing=True
        )

        # Re-treino semanal controlado (domingo de madrugada, minuto fora da hora cheia)
        self.scheduler.add_job(
            self.run_retrain_job,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=17),
            id='weekly_retrain',
            name='Weekly Controlled Model Retrain',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


def run_scheduler() -> None:
    """Run the scheduler (blocking)"""
    job = DailyJob()
    job.start()
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        job.stop()


if __name__ == "__main__":
    # Run scheduler
    run_scheduler()

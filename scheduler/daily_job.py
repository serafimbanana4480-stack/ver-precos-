"""
Daily job scheduler for automated scraping and analysis
"""
import logging
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import (
    SCRAPING_INTERVAL_HOURS, DAILY_SCRAPING_TIME, SCHEDULER_TIMEZONE,
    DISCORD_WEBHOOK_URL, EMAIL_TO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
from scrapers.olx_scraper import OLXScraper
from scrapers.standvirtual_scraper import StandvirtualScraper
from scrapers.autosapo_scraper import AutoSapoScraper
from valuation.predict import update_vehicle_valuations
from ai_agent.deal_finder import DealFinder
from database.db import init_db

logger = logging.getLogger(__name__)


class DailyJob:
    """Daily automated job for scraping and analysis"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=SCHEDULER_TIMEZONE)
        self.olx_scraper = OLXScraper()
        self.standvirtual_scraper = StandvirtualScraper()
        self.autosapo_scraper = AutoSapoScraper()
        self.deal_finder = DealFinder()
    
    def run_scraping_job(self):
        """Run complete scraping pipeline"""
        logger.info("=" * 60)
        logger.info("Starting daily scraping job")
        logger.info("=" * 60)
        
        try:
            # Initialize database
            init_db()
            
            # Scrape OLX
            logger.info("Scraping OLX...")
            olx_listings = self.olx_scraper.scrape_listings("carros", max_listings=50)
            if olx_listings:
                self.olx_scraper.save_to_database(olx_listings, "carros")
            
            olx_motos = self.olx_scraper.scrape_listings("motos", max_listings=30)
            if olx_motos:
                self.olx_scraper.save_to_database(olx_motos, "motos")
            
            # Scrape Standvirtual
            logger.info("Scraping Standvirtual...")
            sv_listings = self.standvirtual_scraper.scrape_listings("carros", max_listings=50)
            if sv_listings:
                self.standvirtual_scraper.save_to_database(sv_listings, "carros")
            
            # Scrape AutoSapo
            logger.info("Scraping AutoSapo...")
            as_listings = self.autosapo_scraper.scrape_listings("carros", max_listings=50)
            if as_listings:
                self.autosapo_scraper.save_to_database(as_listings, "carros")
            
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
    
    def run_analysis_job(self):
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
    
    def send_notifications(self, deals):
        """Send notifications via configured channels"""
        # Discord
        if DISCORD_WEBHOOK_URL:
            self.send_discord_notification(deals)
        
        # Email
        if EMAIL_TO:
            self.send_email_notification(deals)
        
        # Telegram
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self.send_telegram_notification(deals)
    
    def send_discord_notification(self, deals):
        """Send notification to Discord webhook"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Discord notification")
            return
        
        if not DISCORD_WEBHOOK_URL:
            return
        
        # Build message
        message = f"**🚗 Top {len(deals)} Auto Deals Found**\n\n"
        
        for i, deal in enumerate(deals[:10], 1):
            summary = self.deal_finder.get_deal_summary(deal)
            message += (
                f"**{i}. {summary['brand']} {summary['model']} ({summary['year']})**\n"
                f"   💰 Price: €{summary['price']:,} | Est: €{summary['estimated_value']:,}\n"
                f"   📈 Profit: €{summary['profit_potential']:,} ({summary['profit_percentage']:.1f}%)\n"
                f"   ⭐ Score: {summary['deal_score']:.1f}/10\n"
                f"   🔗 {summary['url']}\n\n"
            )
        
        data = {"content": message}
        
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(f"Discord notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    def send_email_notification(self, deals):
        """Send notification via email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
        except ImportError:
            logger.warning("Email libraries not available, skipping email notification")
            return
        
        from config import (
            EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_USER,
            EMAIL_SMTP_PASSWORD, EMAIL_FROM
        )
        
        if not all([EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD, EMAIL_FROM]):
            return
        
        # Build email content
        subject = f"Top {len(deals)} Auto Deals Found - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"<h2>Top {len(deals)} Auto Deals Found</h2>\n"
        
        for i, deal in enumerate(deals[:10], 1):
            summary = self.deal_finder.get_deal_summary(deal)
            body += f"""
            <h3>{i}. {summary['brand']} {summary['model']} ({summary['year']})</h3>
            <ul>
                <li><strong>Price:</strong> €{summary['price']:,}</li>
                <li><strong>Estimated Value:</strong> €{summary['estimated_value']:,}</li>
                <li><strong>Potential Profit:</strong> €{summary['profit_potential']:,} ({summary['profit_percentage']:.1f}%)</li>
                <li><strong>Deal Score:</strong> {summary['deal_score']:.1f}/10</li>
                <li><strong>Location:</strong> {summary['location']}</li>
                <li><strong>Source:</strong> {summary['source']}</li>
                <li><strong>Link:</strong> <a href="{summary['url']}">View Listing</a></li>
            </ul>
            <hr>
            """
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = ", ".join(EMAIL_TO)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        try:
            with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
                server.send_message(msg)
            logger.info("Email notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    def send_telegram_notification(self, deals):
        """Send notification via Telegram"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not installed, skipping Telegram notification")
            return
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        # Build message
        message = f"🚗 *Top {len(deals)} Auto Deals Found*\n\n"
        
        for i, deal in enumerate(deals[:10], 1):
            summary = self.deal_finder.get_deal_summary(deal)
            message += (
                f"*{i}. {summary['brand']} {summary['model']} ({summary['year']})*\n"
                f"💰 Price: €{summary['price']:,} | Est: €{summary['estimated_value']:,}\n"
                f"📈 Profit: €{summary['profit_potential']:,} ({summary['profit_percentage']:.1f}%)\n"
                f"⭐ Score: {summary['deal_score']:.1f}/10\n"
                f"🔗 {summary['url']}\n\n"
            )
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
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
    
    def start(self):
        """Start the scheduler"""
        logger.info("Starting scheduler")
        
        # Add daily scraping job
        self.scheduler.add_job(
            self.run_scraping_job,
            trigger=CronTrigger.from_crontab(f"0 {DAILY_SCRAPING_TIME} * * *"),
            id='daily_scraping',
            name='Daily Scraping Job',
            replace_existing=True
        )
        
        # Add periodic analysis job (every 6 hours)
        self.scheduler.add_job(
            self.run_analysis_job,
            trigger='interval',
            hours=SCRAPING_INTERVAL_HOURS,
            id='periodic_analysis',
            name='Periodic Analysis Job',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


def run_scheduler():
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

"""
AutoDeal IA Hunter - Main Entry Point
Intelligent vehicle deal finder for Portugal
"""
from __future__ import annotations
import sys
import argparse
import logging
import json
import asyncio
import inspect
from pathlib import Path
from typing import Union

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from utils.logging_config import setup_logging
from utils.health_check import get_system_health
from utils.production_safeguards import setup_signal_handlers, validate_environment, get_health_check_summary
from utils.request_queue import initialize_queue, shutdown_queue
from database.db import init_db
from validation.cli_models import ScrapeArgs, TrainArgs, FindDealsArgs, ValuateArgs, DashboardArgs

# Initialize Sentry if DSN is configured
if settings.sentry_dsn:
    import sentry_sdk

    def filter_sentry_event(event: dict[str, object], hint: dict[str, object]) -> dict[str, object]:
        """Filter sensitive data from Sentry events"""
        if 'request' in event:
            request_obj = event.get('request')
            if isinstance(request_obj, dict):
                # Filter headers
                if 'headers' in request_obj:
                    headers = request_obj.get('headers')
                    if isinstance(headers, dict):
                        sensitive_keys = ['authorization', 'api-key', 'x-api-key', 'password']
                        for key in list(headers.keys()):
                            if isinstance(key, str) and key.lower() in sensitive_keys:
                                headers[key] = '***REDACTED***'

        # Filter environment variables
        if 'extra' in event:
            extra_obj = event.get('extra')
            if isinstance(extra_obj, dict):
                if 'env' in extra_obj:
                    env = extra_obj.get('env')
                    if isinstance(env, dict):
                        sensitive_keys = ['api_key', 'password', 'token', 'secret']
                        for key in list(env.keys()):
                            if isinstance(key, str) and key.lower() in sensitive_keys:
                                env[key] = '***REDACTED***'

        return event
    
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        sample_rate=settings.sentry_sample_rate,
        before_send=filter_sentry_event
    )


def main():
    """Main entry point with production safeguards"""
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Validate environment on startup (temporarily disabled for testing)
    # from utils.production_safeguards import validate_environment
    # env_check = validate_environment()
    # if env_check['issues']:
    #     print("CRITICAL: Environment validation failed:")
    #     for issue in env_check['issues']:
    #         print(f"  - {issue}")
    #     sys.exit(1)
    # if env_check['warnings']:
    #     print("WARNINGS:")
    #     for warning in env_check['warnings']:
    #         print(f"  - {warning}")
    
    parser = argparse.ArgumentParser(description='AutoDeal IA Hunter')
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers")
    scrape_parser.add_argument("--source", choices=["olx", "standvirtual", "autosapo", "all"], 
                              default="all", help="Source to scrape")
    scrape_parser.add_argument("--vehicle-type", choices=["carros", "motos", "all"],
                              default="all", help="Vehicle type to scrape")
    scrape_parser.add_argument("--max-listings", type=int, default=50,
                              help="Maximum listings to scrape per source")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train ML model")
    train_parser.add_argument("--force", action="store_true", 
                             help="Force retraining even if model exists")
    
    # Valuate command
    valuate_parser = subparsers.add_parser("valuate", help="Update vehicle valuations")
    valuate_parser.add_argument("--batch-size", type=int, default=100,
                               help="Number of vehicles to process")
    
    # Find-deals command
    deals_parser = subparsers.add_parser("find-deals", help="Find best deals")
    deals_parser.add_argument("--limit", type=int, default=20,
                             help="Number of deals to find")
    deals_parser.add_argument("--min-profit", type=float, default=None,
                             help="Minimum profit potential")
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser("scheduler", help="Run scheduler")
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start Streamlit dashboard")
    dashboard_parser.add_argument("--port", type=int, default=8501,
                                  help="Dashboard port")
    
    # Health check command
    health_parser = subparsers.add_parser("health-check", help="Check system health")
    
    args = parser.parse_args()

    if args.command == 'health-check':
        health_summary = get_health_check_summary()
        print(json.dumps(health_summary, indent=2))
        sys.exit(0 if health_summary['overall_status'] == 'healthy' else 1)

    # Validate CLI arguments using pydantic models
    if args.command == "scrape":
        try:
            ScrapeArgs.from_argparse(args)
        except Exception as e:
            print(f"Invalid arguments: {e}")
            sys.exit(1)
    elif args.command == "train":
        try:
            TrainArgs.from_argparse(args)
        except Exception as e:
            print(f"Invalid arguments: {e}")
            sys.exit(1)
    elif args.command == "find-deals":
        try:
            FindDealsArgs.from_argparse(args)
        except Exception as e:
            print(f"Invalid arguments: {e}")
            sys.exit(1)
    elif args.command == "valuate":
        try:
            ValuateArgs.from_argparse(args)
        except Exception as e:
            print(f"Invalid arguments: {e}")
            sys.exit(1)
    elif args.command == "dashboard":
        try:
            DashboardArgs.from_argparse(args)
        except Exception as e:
            print(f"Invalid arguments: {e}")
            sys.exit(1)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    if not settings.validate_config():
        logger.error("Configuration validation failed. Please check your .env file.")
        sys.exit(1)
    
    # Execute command
    if args.command == "init":
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully!")
    
    elif args.command == "scrape":
        logger.info(f"Starting scraping: {args.source}, {args.vehicle_type}")
        
        async def run_scraping():
            from scrapers import OLXScraper, StandvirtualScraper, AutoSapoScraper

            olx_scraper = OLXScraper()
            sv_scraper = StandvirtualScraper()
            as_scraper = AutoSapoScraper()

            sources_to_scrape: list[tuple[str, Union[OLXScraper, StandvirtualScraper, AutoSapoScraper]]] = []
            if args.source in ["olx", "all"]:
                sources_to_scrape.append(("OLX", olx_scraper))
            if args.source in ["standvirtual", "all"]:
                sources_to_scrape.append(("Standvirtual", sv_scraper))
            if args.source in ["autosapo", "all"]:
                sources_to_scrape.append(("AutoSapo", as_scraper))
            
            vehicle_types = ["carros", "motos"] if args.vehicle_type == "all" else [args.vehicle_type]
            
            for source_name, scraper in sources_to_scrape:
                for vtype in vehicle_types:
                    logger.info(f"Scraping {source_name} - {vtype}")
                    
                    # All scrapers are now async - await directly
                    listings = await scraper.scrape_listings(vtype, max_listings=args.max_listings)
                        
                    if listings:
                        scraper.save_to_database(listings, vtype)
                        logger.info(f"Saved {len(listings)} listings from {source_name}")
            
            logger.info("Scraping completed!")
        
        asyncio.run(run_scraping())
    
    elif args.command == "train":
        logger.info("Training ML model...")
        from valuation.train_model import train_model
        model = train_model(force_retrain=args.force)
        if model:
            logger.info("Model trained successfully!")
        else:
            logger.error("Model training failed")
            return
    
    elif args.command == "valuate":
        logger.info("Updating vehicle valuations...")
        from valuation.predict import update_vehicle_valuations
        update_vehicle_valuations(batch_size=args.batch_size)
        logger.info("Valuations updated!")
    
    elif args.command == "find-deals":
        logger.info("Finding best deals...")
        from ai_agent.deal_finder import DealFinder
        finder = DealFinder()
        deals = finder.find_best_deals(limit=args.limit, min_profit=args.min_profit)
        
        print(f"\n{'='*60}")
        print(f"Top {len(deals)} Deals Found")
        print(f"{'='*60}\n")
        
        for i, summary in enumerate(deals, 1):
            print(f"{i}. {summary['brand']} {summary['model']} ({summary['year']})")
            print(f"   Price: €{summary['price']:,} | Est: €{summary['estimated_value']:,}")
            print(f"   Profit: €{summary['profit_potential']:,} ({summary['profit_percentage']:.1f}%)")
            print(f"   Score: {summary['deal_score']:.1f}/10")
            print(f"   Location: {summary['location']}")
            print(f"   URL: {summary['url']}")
            print()
    
    elif args.command == "scheduler":
        logger.info("Starting scheduler...")
        from scheduler.daily_job import run_scheduler
        run_scheduler()
    
    elif args.command == "dashboard":
        logger.info(f"Starting dashboard on port {args.port}...")
        import subprocess
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
            "--server.port", str(args.port),
            "--server.address", "0.0.0.0"
        ])
    
    
    else:
        parser.print_help()
        print("\nQuick Start:")
        print("  python main.py init              # Initialize database")
        print("  python main.py scrape            # Run scrapers")
        print("  python main.py train             # Train ML model")
        print("  python main.py valuate           # Update valuations")
        print("  python main.py find-deals        # Find best deals")
        print("  python main.py scheduler         # Run scheduler")
        print("  python main.py dashboard         # Start dashboard")
        print("  python main.py health-check      # Check system health")


if __name__ == "__main__":
    main()

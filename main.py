"""
AutoDeal IA Hunter - Main Entry Point
Intelligent vehicle deal finder for Portugal
"""
import argparse
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.logging_config import setup_logging
from utils.health_check import get_system_health
from database.db import init_db
from validation.cli_models import ScrapeArgs, TrainArgs, FindDealsArgs, ValuateArgs, DashboardArgs

# Initialize Sentry if DSN is configured
if config.sentry_dsn:
    import sentry_sdk
    
    def filter_sentry_event(event, hint):
        """Filter sensitive data from Sentry events"""
        if 'request' in event:
            # Filter headers
            if 'headers' in event['request']:
                headers = event['request']['headers']
                sensitive_keys = ['authorization', 'api-key', 'x-api-key', 'password']
                for key in list(headers.keys()):
                    if key.lower() in sensitive_keys:
                        headers[key] = '***REDACTED***'
        
        # Filter extra data
        if 'extra' in event:
            for key in list(event['extra'].keys()):
                if any(s in key.lower() for s in ['api_key', 'password', 'token', 'secret']):
                    event['extra'][key] = '***REDACTED***'
        
        return event
    
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        environment=config.sentry_environment,
        sample_rate=config.sentry_sample_rate,
        before_send=filter_sentry_event
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AutoDeal IA Hunter - Intelligent Vehicle Deal Finder"
    )
    
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
    if not config.validate():
        logger.error("Configuration validation failed. Please check your .env file.")
        sys.exit(1)
    
    # Execute command
    if args.command == "init":
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully!")
    
    elif args.command == "scrape":
        logger.info(f"Starting scraping: {args.source}, {args.vehicle_type}")
        
        from scrapers.olx_scraper import OLXScraper
        from scrapers.standvirtual_scraper import StandvirtualScraper
        from scrapers.autosapo_scraper import AutoSapoScraper
        
        olx_scraper = OLXScraper()
        sv_scraper = StandvirtualScraper()
        as_scraper = AutoSapoScraper()
        
        sources_to_scrape = []
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
                listings = scraper.scrape_listings(vtype, max_listings=args.max_listings)
                if listings:
                    scraper.save_to_database(listings, vtype)
                    logger.info(f"Saved {len(listings)} listings from {source_name}")
        
        logger.info("Scraping completed!")
    
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
        import sys
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
            "--server.port", str(args.port),
            "--server.address", "0.0.0.0"
        ])
    
    elif args.command == "health-check":
        import json
        health = get_system_health()
        print(json.dumps(health, indent=2))
        
        # Exit with error code if unhealthy
        if health["status"] != "healthy":
            sys.exit(1)
    
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

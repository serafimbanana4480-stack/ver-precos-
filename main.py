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

from core.settings import settings
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
    
    # Production: enforce environment validation before any command
    if settings.is_production:
        env_check = validate_environment()
        if env_check["issues"]:
            print("CRITICAL: Environment validation failed:")
            for issue in env_check["issues"]:
                print(f"  - {issue}")
            sys.exit(1)
        if env_check["warnings"]:
            print("WARNINGS:")
            for warning in env_check["warnings"]:
                print(f"  - {warning}")
    
    parser = argparse.ArgumentParser(description='AutoDeal IA Hunter')
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers")
    scrape_parser.add_argument("--source", choices=["olx", "standvirtual", "autosapo", "custojusto", "piscapisca", "carplus", "autopt", "autoscout24", "all"], 
                              default="all", help="Source to scrape")
    scrape_parser.add_argument("--vehicle-type", choices=["carros", "motos", "all"],
                              default="all", help="Vehicle type to scrape")
    scrape_parser.add_argument("--max-listings", type=int, default=50,
                              help="Maximum listings to scrape per source")
    scrape_parser.add_argument("--scrape-details", action="store_true",
                              help="Scrape detailed info from each listing (slower but more complete)")
    
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
    
    # Auction scrape command - for collecting REAL transaction prices
    auction_parser = subparsers.add_parser("auction", help="Scrape auction sites for real transaction prices")
    auction_parser.add_argument("--source", choices=["vpauto", "leilosoc", "manheim", "autorola", "bca", "all"],
                               default="all", help="Auction source to scrape")
    auction_parser.add_argument("--max-listings", type=int, default=50,
                               help="Maximum listings per source")
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser("scheduler", help="Run scheduler")
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start Streamlit dashboard")
    dashboard_parser.add_argument("--port", type=int, default=8501,
                                  help="Dashboard port")
    
    # Health check command
    health_parser = subparsers.add_parser("health-check", help="Check system health")
    
    # Agent command - Multi-Agent System
    agent_parser = subparsers.add_parser("agent", help="Run multi-agent system")
    agent_sub = agent_parser.add_subparsers(dest="agent_command", help="Agent commands")
    
    agent_run = agent_sub.add_parser("run", help="Run improvement cycle")
    agent_run.add_argument("--target", default=".", help="Target directory")
    
    agent_watch = agent_sub.add_parser("watch", help="Start continuous improvement watcher")
    agent_watch.add_argument("--target", default=".", help="Target directory")
    
    agent_status = agent_sub.add_parser("status", help="Show agent system status")
    
    agent_generate = agent_sub.add_parser("generate", help="Generate new project")
    agent_generate.add_argument("spec", help="Project specification")
    agent_generate.add_argument("--output", default="./generated_project", help="Output directory")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search for specific vehicles")
    search_parser.add_argument("--brand", help="Brand (e.g., Honda, Yamaha)")
    search_parser.add_argument("--model", help="Model (e.g., CB 600F, MT-07)")
    search_parser.add_argument("--query", help="Free-text search across brand/model/title")
    search_parser.add_argument("--vehicle-type", choices=["carros", "motos"], help="Vehicle type filter")
    search_parser.add_argument("--min-price", type=float, help="Minimum price in EUR")
    search_parser.add_argument("--max-price", type=float, help="Maximum price in EUR")
    search_parser.add_argument("--min-year", type=int, help="Minimum year")
    search_parser.add_argument("--max-year", type=int, help="Maximum year")
    search_parser.add_argument("--max-km", type=int, help="Maximum kilometers")
    search_parser.add_argument("--fuel-type", help="Fuel type (gasolina, diesel, etc.)")
    search_parser.add_argument("--location", help="Location (partial match)")
    search_parser.add_argument("--district", help="District filter")
    search_parser.add_argument("--source", choices=["olx", "standvirtual", "autosapo", "custojusto", "piscapisca", "carplus"], help="Source filter")
    search_parser.add_argument("--min-score", type=float, help="Minimum deal score (0-10)")
    search_parser.add_argument("--sort-by", default="deal_score",
                             choices=["price", "year", "km", "deal_score", "profit_potential", "first_seen"],
                             help="Sort field")
    search_parser.add_argument("--asc", action="store_true", help="Sort ascending")
    search_parser.add_argument("--limit", type=int, default=20, help="Max results")
    search_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Watchlist commands
    watchlist_parser = subparsers.add_parser("watchlist", help="Manage vehicle watchlists")
    wl_sub = watchlist_parser.add_subparsers(dest="wl_command", help="Watchlist subcommands")
    
    wl_add = wl_sub.add_parser("add", help="Add a new watchlist")
    wl_add.add_argument("--name", required=True, help="Watchlist name")
    wl_add.add_argument("--brand", help="Brand filter")
    wl_add.add_argument("--model", help="Model filter")
    wl_add.add_argument("--vehicle-type", choices=["carros", "motos"], help="Vehicle type")
    wl_add.add_argument("--min-year", type=int, help="Minimum year")
    wl_add.add_argument("--max-year", type=int, help="Maximum year")
    wl_add.add_argument("--min-price", type=float, help="Minimum price")
    wl_add.add_argument("--max-price", type=float, help="Maximum price")
    wl_add.add_argument("--max-km", type=int, help="Maximum kilometers")
    wl_add.add_argument("--min-profit", type=float, help="Minimum profit potential")
    wl_add.add_argument("--fuel-type", help="Fuel type filter")
    wl_add.add_argument("--no-notify", action="store_true", help="Disable notifications")
    
    wl_list = wl_sub.add_parser("list", help="List all watchlists")
    wl_list.add_argument("--all", action="store_true", dest="wl_all", help="Show inactive too")
    
    wl_check = wl_sub.add_parser("check", help="Check watchlists for matches now")
    wl_check.add_argument("--id", type=int, help="Check specific watchlist ID")
    wl_check.add_argument("--notify", action="store_true", help="Send notifications for matches")
    
    wl_delete = wl_sub.add_parser("delete", help="Delete a watchlist")
    wl_delete.add_argument("--id", type=int, required=True, help="Watchlist ID to delete")
    
    # Market intelligence command
    stats_parser = subparsers.add_parser("stats", help="Market intelligence and statistics")
    stats_sub = stats_parser.add_subparsers(dest="stats_command", help="Stats subcommands")
    
    st_demand = stats_sub.add_parser("demand", help="Analyze demand for a vehicle")
    st_demand.add_argument("--brand", required=True, help="Brand name")
    st_demand.add_argument("--model", help="Model name")
    st_demand.add_argument("--vehicle-type", choices=["carros", "motos"], help="Vehicle type")
    st_demand.add_argument("--json", action="store_true", help="Output as JSON")
    
    st_market = stats_sub.add_parser("market", help="Market stats for brand/model")
    st_market.add_argument("--brand", required=True, help="Brand name")
    st_market.add_argument("--model", required=True, help="Model name")
    st_market.add_argument("--vehicle-type", choices=["carros", "motos"], help="Vehicle type")
    
    st_saturation = stats_sub.add_parser("saturation", help="Market saturation by brand")
    st_saturation.add_argument("--vehicle-type", choices=["carros", "motos"], help="Vehicle type")
    st_saturation.add_argument("--json", action="store_true", help="Output as JSON")
    
    st_trends = stats_sub.add_parser("trends", help="Price trends for a model")
    st_trends.add_argument("--brand", required=True, help="Brand name")
    st_trends.add_argument("--model", help="Model name")
    st_trends.add_argument("--days", type=int, default=90, help="Days of history")
    
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
    
    elif args.command == 'scrape':
        logger.info(f"Starting scraping: {args.source}, {args.vehicle_type}")
        
        async def run_scraping():
            from scrapers import OLXScraper, StandvirtualScraper, AutoSapoScraper, AutoPtScraper
            from scrapers.custojusto_scraper import CustoJustoScraper
            from scrapers.piscapisca_scraper import PiscaPiscaScraper
            from scrapers.carplus_scraper import CarplusScraper
            from scrapers.autoscout24_scraper import AutoScout24Scraper
            from scrapers.browser_pool import get_browser_pool
            from processing.pipeline import production_pipeline

            pool = get_browser_pool()
            logger.info(f"[BROWSER_POOL] Initialized: {pool.get_stats()}")

            olx_scraper = OLXScraper()
            sv_scraper = StandvirtualScraper()
            as_scraper = AutoSapoScraper()
            cj_scraper = CustoJustoScraper()
            pp_scraper = PiscaPiscaScraper()
            cp_scraper = CarplusScraper()
            apt_scraper = AutoPtScraper()
            as24_scraper = AutoScout24Scraper()

            sources_to_scrape = []
            scraper_map = {
                "olx": ("OLX", olx_scraper), "standvirtual": ("Standvirtual", sv_scraper),
                "autosapo": ("AutoSapo", as_scraper), "custojusto": ("CustoJusto", cj_scraper),
                "piscapisca": ("PiscaPisca", pp_scraper), "carplus": ("Carplus", cp_scraper),
                "autopt": ("AutoPt", apt_scraper), "autoscout24": ("AutoScout24", as24_scraper),
            }
            if args.source == "all":
                sources_to_scrape = list(scraper_map.values())
            elif args.source in scraper_map:
                sources_to_scrape = [scraper_map[args.source]]
            
            vehicle_types = ["carros", "motos"] if args.vehicle_type == "all" else [args.vehicle_type]
            
            all_listings = []
            
            # SCRAPE ALL SOURCES IN PARALLEL for massive speedup
            async def scrape_source(source_name: str, scraper, vtype: str) -> List[Dict[str, object]]:
                logger.info(f"[CONCURRENT] Starting {source_name} - {vtype}")
                start_time = asyncio.get_event_loop().time()
                
                use_details = args.scrape_details if hasattr(args, 'scrape_details') else (source_name != "OLX")
                
                try:
                    listings = await scraper.scrape_listings(
                        vtype,
                        max_listings=args.max_listings,
                        scrape_details=use_details,
                    )
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if listings:
                        logger.info(f"[CONCURRENT] {source_name} - {vtype}: {len(listings)} listings in {elapsed:.1f}s")
                    else:
                        logger.warning(f"[CONCURRENT] {source_name} - {vtype}: 0 listings in {elapsed:.1f}s")
                    return listings or []
                except Exception as e:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.error(f"[CONCURRENT] {source_name} - {vtype} FAILED after {elapsed:.1f}s: {e}")
                    return []
            
            # Build all tasks for parallel execution
            all_tasks = []
            for source_name, scraper in sources_to_scrape:
                for vtype in vehicle_types:
                    all_tasks.append(scrape_source(source_name, scraper, vtype))
            
            # Run all scrapers concurrently
            logger.info(f"[PARALLEL] Running {len(all_tasks)} scraper tasks concurrently")
            parallel_start = asyncio.get_event_loop().time()
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            parallel_elapsed = asyncio.get_event_loop().time() - parallel_start
            
            for result in results:
                if isinstance(result, list):
                    all_listings.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"[PARALLEL] Scraper exception: {result}")
            
            logger.info(f"[PARALLEL] All scrapers completed in {parallel_elapsed:.1f}s")
            logger.info(f"Scraping completed! Total listings: {len(all_listings)}")
            
            # Close browser pool
            try:
                await pool.close_all()
                logger.info("[BROWSER_POOL] Closed")
            except Exception as e:
                logger.warning(f"[BROWSER_POOL] Close error: {e}")
            
            # Process listings through production pipeline
            if getattr(settings, 'fast_scrape_mode', False) or (
                not getattr(settings, 'enable_pipeline_llm', True) and not getattr(settings, 'enable_pipeline_vision', True)
            ):
                logger.info("Fast scrape: skipping LLM/vision in pipeline")
            else:
                logger.info("Running production pipeline with AI enrichment")

            results = production_pipeline.process_batch(all_listings)
            
            logger.info(f"Pipeline completed!")
            logger.info(f"  Total: {results['total']}")
            logger.info(f"  Success: {results['success']}")
            logger.info(f"  Errors: {results['error']}")
            logger.info(f"  Avg Score: {results['avg_score']:.2f}/10")
            logger.info(f"  Processing Time: {results['processing_time']:.2f}s")
        
        asyncio.run(run_scraping())
    
    elif args.command == "train":
        logger.info("Training ML models (vehicle-type-aware)...")
        from valuation.train import train_all_models
        results = train_all_models(force_retrain=args.force)
        for vtype, meta in results.items():
            if meta:
                metrics = meta.get("metrics", {})
                logger.info(f"  {vtype}: {meta['model_type']} R²={metrics.get('r2', 'N/A'):.4f}, "
                            f"MAE=€{metrics.get('mae', 'N/A'):.0f}, n={meta.get('n_samples', 0)}")
            else:
                logger.warning(f"  {vtype}: training failed or insufficient data")
    
    elif args.command == "valuate":
        logger.info("Updating vehicle valuations (statistical)...")
        from valuation.statistical_pricer import update_all_valuations
        n = update_all_valuations()
        logger.info(f"Valuations updated for {n} vehicles!")
    
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
            price = summary.get('price') or 0
            est_value = summary.get('estimated_value') or 0
            profit = summary.get('profit_potential') or 0
            profit_pct = summary.get('profit_percentage') or 0
            
            print(f"   Price: €{price:,.2f} | Est: €{est_value:,.2f}")
            print(f"   Profit: €{profit:,.2f} ({profit_pct:.1f}%)")
            print(f"   Score: {(summary.get('deal_score') or 0):.1f}/10")
            print(f"   Location: {summary.get('location')}")
            print(f"   URL: {summary.get('url')}")
            print()
    
    elif args.command == "search":
        from search.search_service import SearchService
        searcher = SearchService()
        
        if args.query:
            results = searcher.quick_search(args.query, vehicle_type=args.vehicle_type, limit=args.limit)
        else:
            results = searcher.search(
                brand=args.brand,
                model=args.model,
                vehicle_type=args.vehicle_type,
                min_price=args.min_price,
                max_price=args.max_price,
                min_year=args.min_year,
                max_year=args.max_year,
                max_km=args.max_km,
                fuel_type=args.fuel_type,
                location=args.location,
                district=args.district,
                source=args.source,
                min_deal_score=args.min_score,
                sort_by=args.sort_by,
                sort_desc=not args.asc,
                limit=args.limit,
                offset=args.offset,
            )
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            if not results:
                print("No vehicles found matching your criteria.")
            else:
                print(f"\n{'='*70}")
                print(f"  Search Results ({len(results)} found)")
                print(f"{'='*70}\n")
                for i, v in enumerate(results, 1):
                    print(f"{i}. {v['brand']} {v['model']} ({v['year']})")
                    print(f"   Price: €{v['price']:,.2f} | Est: €{v['estimated_value']:,.2f}" if v.get('estimated_value') else f"   Price: €{v['price']:,.2f}")
                    if v.get('deal_score'):
                        print(f"   Deal Score: {v['deal_score']:.1f}/10 | Profit: €{v['profit_potential']:,.2f}")
                    print(f"   KM: {v.get('km', 'N/A')} | Fuel: {v.get('fuel_type', 'N/A')}")
                    print(f"   Location: {v.get('location', 'N/A')} | Source: {v.get('source', 'N/A')}")
                    print(f"   {v['url']}")
                    print()
    
    elif args.command == "watchlist":
        from database.db import get_db_context
        from database.models import Watchlist, VehicleType as VT, FuelType as FT
        
        if args.wl_command == "add":
            with get_db_context() as db:
                wl = Watchlist(
                    name=args.name,
                    brand=args.brand,
                    model=args.model,
                    vehicle_type=VT(args.vehicle_type) if args.vehicle_type else None,
                    min_year=args.min_year,
                    max_year=args.max_year,
                    min_price=args.min_price,
                    max_price=args.max_price,
                    max_km=args.max_km,
                    min_profit=args.min_profit,
                    fuel_type=FT(args.fuel_type) if args.fuel_type else None,
                    notify_on_match=not args.no_notify,
                )
                db.add(wl)
                db.commit()
                print(f"Watchlist '{args.name}' created successfully (ID: {wl.id})")
        
        elif args.wl_command == "list":
            with get_db_context() as db:
                query = db.query(Watchlist)
                if not args.wl_all:
                    query = query.filter(Watchlist.is_active == True)  # noqa: E712
                watchlists = query.all()
                
                if not watchlists:
                    print("No watchlists found.")
                else:
                    print(f"\n{'='*60}")
                    print(f"  Your Watchlists ({len(watchlists)})")
                    print(f"{'='*60}")
                    for wl in watchlists:
                        print(f"\n  [{wl.id}] {wl.name} {'(inactive)' if not wl.is_active else ''}")
                        if wl.brand:
                            print(f"      Brand: {wl.brand}")
                        if wl.model:
                            print(f"      Model: {wl.model}")
                        if wl.vehicle_type:
                            print(f"      Type: {wl.vehicle_type.value}")
                        if wl.min_year or wl.max_year:
                            print(f"      Year: {wl.min_year or 'any'} - {wl.max_year or 'any'}")
                        if wl.min_price or wl.max_price:
                            print(f"      Price: €{wl.min_price or 0:,.0f} - €{wl.max_price or 'any'}")
                        if wl.max_km:
                            print(f"      Max KM: {wl.max_km:,}")
                        if wl.min_profit:
                            print(f"      Min Profit: €{wl.min_profit:,.0f}")
                        if wl.fuel_type:
                            print(f"      Fuel: {wl.fuel_type.value}")
                        if wl.last_notified:
                            print(f"      Last notified: {wl.last_notified.strftime('%Y-%m-%d %H:%M')}")
                    print()
        
        elif args.wl_command == "check":
            from alerts.watchlist_matcher import WatchlistMatcher
            from alerts.watchlist_notifier import WatchlistNotifier
            
            matcher = WatchlistMatcher()
            if args.id:
                matches = matcher.check_single_watchlist(args.id)
            else:
                matches = matcher.check_all_watchlists()
            
            if not matches:
                print("No matches found for your watchlists.")
            else:
                print(f"\nFound {len(matches)} matches across your watchlists!")
                if args.notify:
                    notifier = WatchlistNotifier()
                    notifier.notify_matches(matches)
        
        elif args.wl_command == "delete":
            with get_db_context() as db:
                wl = db.query(Watchlist).filter(Watchlist.id == args.id).first()
                if wl:
                    wl.is_active = False
                    db.commit()
                    print(f"Watchlist '{wl.name}' (ID: {args.id}) deactivated.")
                else:
                    print(f"Watchlist ID {args.id} not found.")
        else:
            watchlist_parser.print_help()
    
    elif args.command == "stats":
        if args.stats_command == "demand":
            from intelligence.demand_analyzer import DemandAnalyzer
            analyzer = DemandAnalyzer()
            result = analyzer.get_demand_score(
                brand=args.brand, model=args.model, vehicle_type=args.vehicle_type
            )
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"\n{'='*60}")
                print(f"  Demand Analysis: {args.brand} {args.model or ''}")
                print(f"{'='*60}")
                print(f"  Demand Score: {result['demand_score']:.1f}/10 ({result['demand_level']})")
                print(f"  Active Listings: {result['total_listings']}")
                print(f"  Avg Days on Market: {result['avg_days_on_market']}")
                print(f"  Avg Price: €{result['avg_price']:,.2f}")
                print(f"  Price Range: €{result['min_price']:,.2f} - €{result['max_price']:,.2f}")
                print(f"  Avg Deal Score: {result['avg_deal_score']:.1f}/10")
                print(f"  Good Deals Available: {result['good_deals_count']}")
                print(f"  30-Day Price Trend: {result['price_trend_30d_pct']}% ({result['price_trend_direction']})")
                print()
        
        elif args.stats_command == "market":
            from search.search_service import SearchService
            searcher = SearchService()
            result = searcher.get_market_stats(
                brand=args.brand, model=args.model, vehicle_type=args.vehicle_type
            )
            if result.get("total", 0) == 0:
                print(f"No vehicles found for {args.brand} {args.model}")
            else:
                print(f"\n{'='*60}")
                print(f"  Market Stats: {args.brand} {args.model}")
                print(f"{'='*60}")
                print(f"  Total Listings: {result['total']}")
                print(f"  Avg Price: €{result['avg_price']:,.2f}")
                print(f"  Price Range: €{result['min_price']:,.2f} - €{result['max_price']:,.2f}")
                print(f"  Avg Year: {result['avg_year']}")
                print(f"  Avg KM: {result['avg_km']:,.0f}")
                print(f"  Avg Deal Score: {result['avg_deal_score']:.1f}/10")
                if result.get("top_deals"):
                    print(f"\n  Top Deals:")
                    for d in result["top_deals"][:5]:
                        print(f"    €{d['price']:,.2f} | Score: {d['deal_score']:.1f} | {d['url']}")
                print()
        
        elif args.stats_command == "saturation":
            from intelligence.demand_analyzer import DemandAnalyzer
            analyzer = DemandAnalyzer()
            results = analyzer.get_market_saturation(vehicle_type=args.vehicle_type)
            if args.json:
                print(json.dumps(results, indent=2, default=str))
            else:
                print(f"\n{'='*60}")
                print(f"  Market Saturation by Brand")
                print(f"{'='*60}")
                print(f"  {'Brand':<20} {'Listings':>8} {'Avg Price':>12} {'Avg Score':>10}")
                print(f"  {'-'*50}")
                for r in results:
                    print(f"  {r['brand']:<20} {r['listings']:>8} €{r['avg_price']:>10,.0f} {r['avg_deal_score']:>9.1f}")
                print()
        
        elif args.stats_command == "trends":
            from intelligence.demand_analyzer import DemandAnalyzer
            analyzer = DemandAnalyzer()
            results = analyzer.get_price_trends(
                brand=args.brand, model=args.model, days=args.days
            )
            if not results:
                print(f"No trend data available for {args.brand} {args.model or ''}")
            else:
                print(f"\n{'='*60}")
                print(f"  Price Trends: {args.brand} {args.model or ''} (last {args.days} days)")
                print(f"{'='*60}")
                print(f"  {'Week':<12} {'Avg Price':>12} {'Min':>10} {'Max':>10} {'Count':>6}")
                print(f"  {'-'*50}")
                for r in results:
                    print(f"  {r['week']:<12} €{r['avg_price']:>10,.0f} €{r['min_price']:>8,.0f} €{r['max_price']:>8,.0f} {r['count']:>6}")
                print()
        else:
            stats_parser.print_help()

    elif args.command == "auction":
        logger.info(f"Scraping auction sites for real transaction prices...")
        
        async def run_auction_scraping():
            from scrapers.auction_scraper import scrape_all_auctions as scrape_legacy_auctions
            from scrapers.auction_multi_scraper import scrape_all_auctions as scrape_new_auctions
            
            aggregate: Dict[str, object] = {}
            
            if args.source in ["vpauto", "leilosoc", "all"]:
                legacy = await scrape_legacy_auctions(max_per_source=args.max_listings)
                aggregate.update(legacy)
            
            if args.source in ["manheim", "autorola", "bca", "all"]:
                new_results = await scrape_new_auctions(max_per_source=args.max_listings)
                aggregate.update(new_results)
            
            logger.info("Auction scraping completed!")
            if aggregate:
                for source, count in aggregate.items():
                    logger.info(f"  {source}: {count} transactions saved")
            else:
                logger.warning("No auction data collected - sites may be blocking or structure changed")
        
        asyncio.run(run_auction_scraping())
    
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
    
    elif args.command == "agent":
        from agents import AgentOrchestrator, ContinuousImprovementAgent
        
        orchestrator = AgentOrchestrator(project_root=Path(args.target) if hasattr(args, 'target') else Path.cwd())
        
        if args.agent_command == "run" or args.agent_command is None:
            logger.info("[AGENT] Starting improvement cycle...")
            summary = orchestrator.run_continuous_improvement_cycle()
            print(json.dumps(summary, indent=2, default=str))
        
        elif args.agent_command == "watch":
            logger.info("[AGENT] Starting continuous improvement watcher...")
            ci_agent = ContinuousImprovementAgent(orchestrator.ai, Path(args.target) if hasattr(args, 'target') else Path.cwd())
            import threading
            def watch_loop():
                while True:
                    try:
                        from agents.orchestrator import AgentTask, AgentRole
                        result = ci_agent.run(AgentTask(
                            id="watch_batch",
                            role=AgentRole.CONTINUOUS_IMPROVEMENT,
                            description="Batch analysis",
                            context={"mode": "batch"},
                        ))
                        logger.info(f"[AGENT] Watch cycle completed: {len(result.suggestions)} suggestions")
                    except Exception as e:
                        logger.error(f"[AGENT] Watch cycle error: {e}")
                    import time
                    time.sleep(300)  # 5 minutos
            
            watcher = threading.Thread(target=watch_loop, daemon=True)
            watcher.start()
            print("[AGENT] Watcher started. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[AGENT] Watcher stopped.")
        
        elif args.agent_command == "status":
            status = orchestrator.get_status()
            print(json.dumps(status, indent=2, default=str))
        
        elif args.agent_command == "generate":
            logger.info(f"[AGENT] Generating project: {args.spec}")
            result = orchestrator.generate_project(args.spec, Path(args.output))
            print(result.output)
            if result.artifacts:
                print(json.dumps(result.artifacts, indent=2, default=str))
    
    else:
        parser.print_help()
        print("\nQuick Start:")
        print("  python main.py init              # Initialize database")
        print("  python main.py scrape            # Run scrapers")
        print("  python main.py search            # Search for vehicles")
        print("  python main.py watchlist add     # Add watchlist criteria")
        print("  python main.py watchlist list    # List your watchlists")
        print("  python main.py watchlist check   # Check for matches")
        print("  python main.py train             # Train ML models")
        print("  python main.py valuate           # Update valuations")
        print("  python main.py find-deals        # Find best deals")
        print("  python main.py stats demand      # Analyze demand")
        print("  python main.py stats market      # Market statistics")
        print("  python main.py scheduler         # Run scheduler")
        print("  python main.py dashboard         # Start dashboard")
        print("  python main.py health-check      # Check system health")


if __name__ == "__main__":
    main()

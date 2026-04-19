"""
Streamlit Dashboard for AutoDeal IA Hunter
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from typing import Optional

# Configure page
st.set_page_config(
    page_title="AutoDeal IA Hunter",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stDataFrame {
        background-color: #1e2130;
    }
    .metric-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Database imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from valuation.predict import calculate_deal_score, calculate_profit_potential
from utils.helpers import format_price, format_km, calculate_age


@st.cache_data(ttl=300)
def load_vehicles(filters: Optional[dict[str, object]] = None) -> pd.DataFrame:
    """Load vehicles from database with optional comprehensive filters"""
    with get_db_context() as db:
        query = db.query(Vehicle).filter(Vehicle.is_active == True)

        if filters:
            # Vehicle type
            if filters.get("vehicle_type"):
                v_type = filters["vehicle_type"]
                if isinstance(v_type, str):
                    v_type_lower = v_type.lower()
                    if v_type_lower == "carros":
                        query = query.filter(Vehicle.vehicle_type == VehicleType.CAR)  # type: ignore[arg-type]
                    elif v_type_lower == "motos":
                        query = query.filter(Vehicle.vehicle_type == VehicleType.MOTO)  # type: ignore[arg-type]

            # Brand
            if filters.get("brand"):
                brand = filters["brand"]
                if isinstance(brand, str):
                    query = query.filter(Vehicle.brand.ilike(f"%{brand}%"))

            # Price range
            if filters.get("min_price"):
                min_price = filters["min_price"]
                if isinstance(min_price, (int, float)):
                    query = query.filter(Vehicle.price >= min_price)
            if filters.get("max_price"):
                max_price = filters["max_price"]
                if isinstance(max_price, (int, float)):
                    query = query.filter(Vehicle.price <= max_price)

            # Year range
            if filters.get("min_year"):
                min_year = filters["min_year"]
                if isinstance(min_year, (int, float)):
                    query = query.filter(Vehicle.year >= int(min_year))
            if filters.get("max_year"):
                max_year = filters["max_year"]
                if isinstance(max_year, (int, float)):
                    query = query.filter(Vehicle.year <= int(max_year))

            # KM range
            if filters.get("min_km"):
                min_km = filters["min_km"]
                if isinstance(min_km, (int, float)):
                    query = query.filter(Vehicle.km >= min_km)
            if filters.get("max_km"):
                max_km = filters["max_km"]
                if isinstance(max_km, (int, float)):
                    query = query.filter(Vehicle.km <= max_km)

            # Fuel type
            if filters.get("fuel_type"):
                fuel = filters["fuel_type"]
                if isinstance(fuel, str):
                    fuel_map = {
                        "gasolina": FuelType.GASOLINE,
                        "diesel": FuelType.DIESEL,
                        "elétrico": FuelType.ELECTRIC,
                        "eléctrico": FuelType.ELECTRIC,
                        "híbrido": FuelType.HYBRID,
                        "gpl": FuelType.GPL
                    }
                    if fuel.lower() in fuel_map:
                        query = query.filter(Vehicle.fuel_type == fuel_map[fuel.lower()])  # type: ignore[arg-type]

            # Transmission
            if filters.get("transmission"):
                trans = filters["transmission"]
                if isinstance(trans, str):
                    trans_map = {
                        "manual": Transmission.MANUAL,
                        "automático": Transmission.AUTOMATIC,
                        "automatico": Transmission.AUTOMATIC,
                        "semi-automático": Transmission.SEMI_AUTOMATIC,
                        "semi-automatico": Transmission.SEMI_AUTOMATIC
                    }
                    if trans.lower() in trans_map:
                        query = query.filter(Vehicle.transmission == trans_map[trans.lower()])  # type: ignore[arg-type]

            # Location
            if filters.get("location"):
                location = filters["location"]
                if isinstance(location, str):
                    query = query.filter(Vehicle.location.ilike(f"%{location}%"))

            # Deal score
            if filters.get("min_deal_score"):
                min_deal_score = filters["min_deal_score"]
                if isinstance(min_deal_score, (int, float)):
                    query = query.filter(Vehicle.deal_score >= min_deal_score)

            # Source
            if filters.get("source"):
                source = filters["source"]
                if isinstance(source, str):
                    query = query.filter(Vehicle.source == Source[source.upper()])  # type: ignore[arg-type]

            # Seller type
            if filters.get("seller_type"):
                seller = filters["seller_type"]
                if isinstance(seller, str):
                    query = query.filter(Vehicle.seller_type.ilike(f"%{seller}%"))

            # AI approval
            if filters.get("ai_approved") is not None:
                ai_approved = filters["ai_approved"]
                if isinstance(ai_approved, bool):
                    query = query.filter(Vehicle.ai_approved == ai_approved)

        vehicles = query.all()

        # Convert to DataFrame
        data = [v.to_dict() for v in vehicles]
        return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_top_deals(limit: int = 20) -> pd.DataFrame:
    """Get top deals by deal score and profit potential"""
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.is_active == True,
            Vehicle.deal_score.isnot(None)
        ).order_by(
            Vehicle.deal_score.desc(),
            Vehicle.profit_potential.desc()
        ).limit(limit).all()
        
        data = [v.to_dict() for v in vehicles]
        return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_price_history(brand: str, model: str, days: int = 30) -> pd.DataFrame:
    """Get price history for a specific model"""
    from database.models import PriceHistory
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    with get_db_context() as db:
        # Get vehicles matching brand/model
        vehicles = db.query(Vehicle).filter(
            Vehicle.brand.ilike(f"%{brand}%"),
            Vehicle.model.ilike(f"%{model}%")
        ).all()
        
        vehicle_ids = [v.id for v in vehicles]
        
        # Get price history
        history = db.query(PriceHistory).filter(
            PriceHistory.vehicle_id.in_(vehicle_ids),
            PriceHistory.recorded_at >= cutoff_date
        ).order_by(PriceHistory.recorded_at).all()
        
        data = [{
            "date": h.recorded_at,
            "price": h.price,
            "vehicle_id": h.vehicle_id
        } for h in history]
        
        return pd.DataFrame(data)


def render_metrics(df: pd.DataFrame) -> None:
    """Render key metrics including data freshness"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_vehicles = len(df)
        st.metric(
            label="Total Vehicles",
            value=f"{total_vehicles:,}",
            delta="Active listings"
        )

    with col2:
        avg_deal_score = df["deal_score"].mean() if not df["deal_score"].isna().all() else 0
        st.metric(
            label="Avg Deal Score",
            value=f"{avg_deal_score:.1f}/10",
            delta="Overall quality"
        )

    with col3:
        total_profit = df["profit_potential"].sum() if not df["profit_potential"].isna().all() else 0
        st.metric(
            label="Total Profit Potential",
            value=format_price(total_profit),
            delta="If all purchased"
        )

    with col4:
        avg_price = df["price"].mean() if not df["price"].isna().all() else 0
        st.metric(
            label="Avg Price",
            value=format_price(avg_price),
            delta="Market average"
        )

    # Data freshness indicators
    st.markdown("---")
    st.subheader("📅 Data Freshness")

    with get_db_context() as db:
        from database.models import ScrapingLog

        sources = ["OLX", "Standvirtual", "AutoSapo"]
        freshness_data = []

        for source_name in sources:
            try:
                source_enum = Source[source_name.upper()]
                latest_log = db.query(ScrapingLog).filter(
                    ScrapingLog.source == source_enum  # type: ignore[arg-type]
                ).order_by(ScrapingLog.finished_at.desc()).first()

                if latest_log and latest_log.finished_at:
                    time_diff = datetime.now(timezone.utc) - latest_log.finished_at
                    hours_ago = time_diff.total_seconds() / 3600
                    freshness_data.append({
                        "source": source_name,
                        "last_update": latest_log.finished_at.strftime("%Y-%m-%d %H:%M"),
                        "hours_ago": f"{hours_ago:.1f}h ago",
                        "listings": latest_log.listings_found or 0,
                        "status": latest_log.status
                    })
                else:
                    freshness_data.append({
                        "source": source_name,
                        "last_update": "Never",
                        "hours_ago": "N/A",
                        "listings": 0,
                        "status": "No data"
                    })
            except Exception:
                freshness_data.append({
                    "source": source_name,
                    "last_update": "Error",
                    "hours_ago": "N/A",
                    "listings": 0,
                    "status": "Error"
                })

    freshness_df = pd.DataFrame(freshness_data)
    st.dataframe(
        freshness_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "source": st.column_config.TextColumn("Source"),
            "last_update": st.column_config.TextColumn("Last Update"),
            "hours_ago": st.column_config.TextColumn("Time Ago"),
            "listings": st.column_config.NumberColumn("Listings Found"),
            "status": st.column_config.TextColumn("Status")
        }
    )


def render_deals_table(df: pd.DataFrame) -> None:
    """Render deals table with sorting"""
    st.subheader("📊 Vehicle Listings")
    
    # Format columns for display
    display_df = df.copy()
    
    if "price" in display_df.columns:
        display_df["price"] = display_df["price"].apply(format_price)
    
    if "estimated_value" in display_df.columns:
        display_df["estimated_value"] = display_df["estimated_value"].apply(lambda x: format_price(x) if pd.notna(x) else "N/A")
    
    if "profit_potential" in display_df.columns:
        display_df["profit_potential"] = display_df["profit_potential"].apply(lambda x: format_price(x) if pd.notna(x) else "N/A")
    
    if "km" in display_df.columns:
        display_df["km"] = display_df["km"].apply(format_km)
    
    if "deal_score" in display_df.columns:
        display_df["deal_score"] = display_df["deal_score"].apply(lambda x: f"{x:.1f}/10" if pd.notna(x) else "N/A")
    
    # Select columns to display
    display_cols = [
        "brand", "model", "year", "km", "price", 
        "estimated_value", "profit_potential", "deal_score",
        "location", "source"
    ]
    
    display_cols = [col for col in display_cols if col in display_df.columns]
    
    st.dataframe(
        display_df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "brand": st.column_config.TextColumn("Brand", width="medium"),
            "model": st.column_config.TextColumn("Model", width="medium"),
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "km": st.column_config.TextColumn("KM", width="small"),
            "price": st.column_config.TextColumn("Price", width="small"),
            "estimated_value": st.column_config.TextColumn("Est. Value", width="small"),
            "profit_potential": st.column_config.TextColumn("Profit", width="small"),
            "deal_score": st.column_config.TextColumn("Score", width="small"),
            "location": st.column_config.TextColumn("Location", width="medium"),
            "source": st.column_config.TextColumn("Source", width="small"),
        }
    )


def render_price_charts(df: pd.DataFrame) -> None:
    """Render price distribution charts"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Price Distribution")
        if "price" in df.columns and not df["price"].isna().all():
            fig = px.histogram(
                df, 
                x="price", 
                nbins=30,
                title="Price Distribution",
                color_discrete_sequence=["#00ff88"]
            )
            fig.update_layout(
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="white"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📈 Deal Score Distribution")
        if "deal_score" in df.columns and not df["deal_score"].isna().all():
            fig = px.histogram(
                df,
                x="deal_score",
                nbins=20,
                title="Deal Score Distribution",
                color_discrete_sequence=["#00ccff"]
            )
            fig.update_layout(
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="white"
            )
            st.plotly_chart(fig, use_container_width=True)


def render_top_deals() -> None:
    """Render top deals section"""
    st.subheader("🏆 Top Deals")
    
    df = get_top_deals(limit=10)
    
    if df.empty:
        st.info("No deals available yet. Run the scraper to populate data.")
        return
    
    for idx, row in df.iterrows():
        with st.expander(f"{row['brand']} {row['model']} ({row['year']}) - {format_price(row['price'])}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**KM:** {format_km(row['km'])}")
                st.write(f"**Location:** {row['location']}")
                st.write(f"**Source:** {row['source']}")
            
            with col2:
                st.write(f"**Est. Value:** {format_price(row['estimated_value'])}")
                st.write(f"**Profit Potential:** {format_price(row['profit_potential'])}")
                st.write(f"**Profit %:** {row['profit_percentage']:.1f}%")
            
            with col3:
                st.write(f"**Deal Score:** {row['deal_score']:.1f}/10")
                st.write(f"**Condition:** {row['condition_score']:.1f}/10" if pd.notna(row['condition_score']) else "**Condition:** N/A")
                st.write(f"**AI Approved:** {'✅ Yes' if row['ai_approved'] else '❌ No'}")
            
            if row['ai_review']:
                st.write(f"**AI Review:** {row['ai_review'][:300]}...")
            
            st.markdown(f"[🔗 View Listing]({row['url']})")


def render_filters() -> dict[str, object]:
    """Render filter sidebar with comprehensive filtering options"""
    st.sidebar.header("🔍 Filters")

    filters: dict[str, object] = {}

    # Vehicle type
    vehicle_type = st.sidebar.selectbox("Vehicle Type", ["All", "Carros", "Motos"])
    if vehicle_type != "All":
        filters["vehicle_type"] = vehicle_type

    # Brand filter
    brand = st.sidebar.text_input("Brand (e.g., BMW, Volkswagen)")
    if brand:
        filters["brand"] = brand

    # Price range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_price = st.sidebar.number_input("Min Price (€", min_value=0, value=0)
    with col2:
        max_price = st.sidebar.number_input("Max Price (€", min_value=0, value=100000)

    if min_price > 0:
        filters["min_price"] = min_price
    if max_price > 0:
        filters["max_price"] = max_price

    # Year range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_year = st.sidebar.number_input("Min Year", min_value=2000, value=2015)
    with col2:
        max_year = st.sidebar.number_input("Max Year", min_value=2000, value=2024)

    filters["min_year"] = min_year
    filters["max_year"] = max_year

    # KM range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_km = st.sidebar.number_input("Min KM", min_value=0, value=0, step=1000)
    with col2:
        max_km = st.sidebar.number_input("Max KM", min_value=0, value=300000, step=10000)

    if min_km > 0:
        filters["min_km"] = min_km
    if max_km > 0:
        filters["max_km"] = max_km

    # Fuel type
    fuel_type = st.sidebar.selectbox("Fuel Type", ["All", "Gasolina", "Diesel", "Elétrico", "Híbrido", "GPL"])
    if fuel_type != "All":
        filters["fuel_type"] = fuel_type

    # Transmission
    transmission = st.sidebar.selectbox("Transmission", ["All", "Manual", "Automático", "Semi-Automático"])
    if transmission != "All":
        filters["transmission"] = transmission

    # Location
    location = st.sidebar.text_input("Location (e.g., Lisboa, Porto)")
    if location:
        filters["location"] = location

    # Deal score
    min_deal_score = st.sidebar.slider("Min Deal Score", 0.0, 10.0, 5.0, 0.5)
    filters["min_deal_score"] = min_deal_score

    # Source
    source = st.sidebar.selectbox("Source", ["All", "OLX", "Standvirtual", "AutoSapo"])
    if source != "All":
        filters["source"] = source

    # Seller type
    seller_type = st.sidebar.selectbox("Seller Type", ["All", "Particular", "Profissional"])
    if seller_type != "All":
        filters["seller_type"] = seller_type

    # AI approval
    ai_approved = st.sidebar.selectbox("AI Approved", ["All", "Yes", "No"])
    if ai_approved == "Yes":
        filters["ai_approved"] = True
    elif ai_approved == "No":
        filters["ai_approved"] = False

    return filters


def export_data(df: pd.DataFrame, format: str = "csv") -> bytes | None:
    """Export data to file"""
    if format == "csv":
        return df.to_csv(index=False).encode('utf-8')  # type: ignore[no-any-return]
    elif format == "excel":
        return df.to_excel(index=False, engine='openpyxl')  # type: ignore[no-any-return]
    return None


def run_scrapers(vehicle_type: str = "carros", max_listings: int = 100) -> dict[str, object]:
    """Run all scrapers via subprocess to avoid Playwright event loop conflicts with Streamlit"""
    import subprocess
    import sys
    import json

    results: dict[str, object] = {
        "olx": 0,
        "standvirtual": 0,
        "autosapo": 0,
        "total": 0,
        "errors": []
    }

    try:
        # Run scrapers via main.py in subprocess
        cmd = [
            sys.executable,
            "main.py",
            "scrape",
            "--source", "all",
            "--vehicle-type", vehicle_type,
            "--max-listings", str(max_listings)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            # Parse output to count listings
            # Since we can't easily parse the output, we'll return success
            results["olx"] = "Success"
            results["standvirtual"] = "Success"
            results["autosapo"] = "Success"
            results["total"] = "Success"
        else:
            if isinstance(results["errors"], list):
                results["errors"].append(f"Scraping failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        if isinstance(results["errors"], list):
            results["errors"].append("Scraping timed out after 5 minutes")
    except Exception as e:
        if isinstance(results["errors"], list):
            results["errors"].append(f"Error running scrapers: {str(e)}")

    return results


def main() -> None:
    """Main dashboard function"""
    st.title("🚗 AutoDeal IA Hunter")
    st.markdown("### Intelligent Vehicle Deal Finder for Portugal")

    # Scraper control section
    st.markdown("---")
    st.subheader("🔄 Scraping Control")

    col1, col2, col3 = st.columns(3)
    with col1:
        vehicle_type = st.selectbox("Vehicle Type", ["carros", "motos"], key="scraper_vehicle_type")
    with col2:
        max_listings = st.number_input("Max Listings per Source", min_value=10, max_value=500, value=100, key="scraper_max_listings")
    with col3:
        if st.button("🚀 Run All Scrapers", type="primary", key="run_scrapers"):
            with st.spinner("Scraping in progress... This may take several minutes."):
                if isinstance(vehicle_type, str) and isinstance(max_listings, (int, float)):
                    results = run_scrapers(vehicle_type, int(max_listings))
                    st.success(f"Scraping completed! Total listings: {results['total']}")
                    st.info(f"OLX: {results['olx']} | Standvirtual: {results['standvirtual']} | AutoSapo: {results['autosapo']}")
                    if isinstance(results["errors"], list) and results["errors"]:
                        st.error(f"Errors: {', '.join(str(e) for e in results['errors'])}")
                    # Clear cache to refresh data
                    st.cache_data.clear()

    st.markdown("---")

    # Sidebar
    filters = render_filters()

    # Page navigation
    page = st.sidebar.radio(
        "Navigate",
        ["📊 Dashboard", "🏆 Top Deals", "📈 Analytics", "⚙️ Settings"]
    )
    
    if page == "📊 Dashboard":
        # Load data
        df = load_vehicles(filters)
        
        if df.empty:
            st.warning("No data available. Run the scraper to populate the database.")
            return
        
        # Metrics
        render_metrics(df)
        
        st.markdown("---")
        
        # Charts
        render_price_charts(df)
        
        st.markdown("---")
        
        # Table
        render_deals_table(df)
        
        # Export
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            csv = export_data(df, "csv")
            if csv is not None:
                st.download_button(
                    label="📥 Export CSV",
                    data=csv,
                    file_name=f"vehicles_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        with col2:
            st.download_button(
                label="📥 Export Top Deals PDF",
                data="PDF export requires additional setup",
                disabled=True,
                help="PDF export requires reportlab configuration"
            )
    
    elif page == "🏆 Top Deals":
        render_top_deals()
    
    elif page == "📈 Analytics":
        st.subheader("📈 Price Analytics")
        
        # Brand/Model selection
        with get_db_context() as db:
            brands = db.query(Vehicle.brand).distinct().all()
            brand_list = [b[0] for b in brands if b[0]]
        
        selected_brand = st.selectbox("Select Brand", brand_list)
        
        if selected_brand:
            with get_db_context() as db:
                models = db.query(Vehicle.model).filter(
                    Vehicle.brand == selected_brand
                ).distinct().all()
                model_list = [m[0] for m in models if m[0]]
            
            selected_model = st.selectbox("Select Model", model_list)
            
            if selected_model:
                days = st.slider("Time Period (Days)", 7, 90, 30)
                history_df = get_price_history(selected_brand, selected_model, days)
                
                if not history_df.empty:
                    fig = px.line(
                        history_df,
                        x="date",
                        y="price",
                        title=f"Price History: {selected_brand} {selected_model}",
                        color_discrete_sequence=["#00ff88"]
                    )
                    fig.update_layout(
                        plot_bgcolor="#0e1117",
                        paper_bgcolor="#0e1117",
                        font_color="white"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No price history available for this vehicle.")
    
    elif page == "⚙️ Settings":
        st.subheader("⚙️ Settings")
        
        st.write("Configuration settings would go here.")
        st.write("This section can be extended with:")
        st.write("- API key configuration")
        st.write("- Scraper scheduling")
        st.write("- Notification preferences")
        st.write("- Database management")


if __name__ == "__main__":
    main()

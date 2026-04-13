"""
Streamlit Dashboard for AutoDeal IA Hunter
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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
from database.models import Vehicle, Source, VehicleType
from valuation.predict import calculate_deal_score, calculate_profit_potential
from utils.helpers import format_price, format_km, calculate_age


@st.cache_data(ttl=300)
def load_vehicles(filters: Optional[dict] = None) -> pd.DataFrame:
    """Load vehicles from database with optional filters"""
    with get_db_context() as db:
        query = db.query(Vehicle).filter(Vehicle.is_active == True)
        
        if filters:
            if filters.get("brand"):
                query = query.filter(Vehicle.brand.ilike(f"%{filters['brand']}%"))
            if filters.get("min_price"):
                query = query.filter(Vehicle.price >= filters["min_price"])
            if filters.get("max_price"):
                query = query.filter(Vehicle.price <= filters["max_price"])
            if filters.get("min_year"):
                query = query.filter(Vehicle.year >= filters["min_year"])
            if filters.get("max_year"):
                query = query.filter(Vehicle.year <= filters["max_year"])
            if filters.get("min_deal_score"):
                query = query.filter(Vehicle.deal_score >= filters["min_deal_score"])
            if filters.get("source"):
                query = query.filter(Vehicle.source == Source[filters["source"].upper()])
        
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
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
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


def render_metrics(df: pd.DataFrame):
    """Render key metrics"""
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


def render_deals_table(df: pd.DataFrame):
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


def render_price_charts(df: pd.DataFrame):
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


def render_top_deals():
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


def render_filters():
    """Render filter sidebar"""
    st.sidebar.header("🔍 Filters")
    
    filters = {}
    
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
    
    # Deal score
    min_deal_score = st.sidebar.slider("Min Deal Score", 0.0, 10.0, 5.0, 0.5)
    filters["min_deal_score"] = min_deal_score
    
    # Source
    source = st.sidebar.selectbox("Source", ["All", "OLX", "Standvirtual", "AutoSapo"])
    if source != "All":
        filters["source"] = source
    
    return filters


def export_data(df: pd.DataFrame, format: str = "csv"):
    """Export data to file"""
    if format == "csv":
        return df.to_csv(index=False).encode('utf-8')
    elif format == "excel":
        return df.to_excel(index=False, engine='openpyxl')
    return None


def main():
    """Main dashboard function"""
    st.title("🚗 AutoDeal IA Hunter")
    st.markdown("### Intelligent Vehicle Deal Finder for Portugal")
    
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
            st.download_button(
                label="📥 Export CSV",
                data=csv,
                file_name=f"autodeal_export_{datetime.now().strftime('%Y%m%d')}.csv",
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

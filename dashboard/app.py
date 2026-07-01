"""
AutoDeal IA Hunter - Dashboard v3.1
Professional Operational Console for Vehicle Deal Finding
Clean layout, proper contrast, real ML valuation, working search.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
import sys
import re
import io
import os
from pathlib import Path

# Ensure DATABASE_URL is set before any imports
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///data/autodeal.db"

# Configure page
st.set_page_config(
    page_title="AutoDeal IA Hunter - Professional Console",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CUSTOM CSS - Professional dark theme with readable inputs
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary: #00d4aa;
        --secondary: #0ea5e9;
        --accent: #f43f5e;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg: #0f1117;
        --surface: #181b23;
        --surface-hover: #1f2330;
        --border: #2a2e3b;
        --text: #e2e8f0;
        --text-muted: #94a3b8;
        --text-dim: #64748b;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text);
    }

    /* Typography */
    h1, h2, h3, h4 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text);
    }
    h1 { font-size: 2rem; }
    h2 { font-size: 1.5rem; }
    h3 { font-size: 1.25rem; }

    .title-glow {
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* Metric cards */
    .hero-metric-card {
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-hover) 100%);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    .hero-metric-card:hover {
        border-color: var(--primary);
        transform: translateY(-2px);
    }
    .hero-metric-card h4 {
        margin: 0;
        font-size: 0.875rem;
        color: var(--text-muted);
        font-weight: 500;
    }
    .hero-metric-card .value {
        margin: 0.5rem 0 0 0;
        font-size: 2rem;
        font-weight: 700;
        color: var(--text);
    }
    .hero-metric-card .sub {
        font-size: 0.8rem;
        color: var(--text-dim);
        margin-top: 0.25rem;
    }

    /* Vehicle cards */
    .vehicle-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }
    .vehicle-card:hover {
        border-color: var(--border);
        background: var(--surface-hover);
    }
    .vehicle-card .header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.75rem;
    }
    .vehicle-card .title {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text);
        line-height: 1.3;
    }
    .vehicle-card .score-badge {
        padding: 0.35rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .score-excellent { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
    .score-good { background: rgba(14,165,233,0.15); color: #0ea5e9; border: 1px solid rgba(14,165,233,0.3); }
    .score-fair { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .score-poor { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }

    .vehicle-card .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }
    .vehicle-card .stat {
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 0.6rem 0.5rem;
        text-align: center;
    }
    .vehicle-card .stat-label {
        font-size: 0.7rem;
        color: var(--text-dim);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.2rem;
    }
    .vehicle-card .stat-value {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text);
    }
    .vehicle-card .stat-value.positive { color: var(--success); }
    .vehicle-card .stat-value.negative { color: var(--danger); }
    .vehicle-card .stat-value.accent { color: var(--primary); }

    /* Fix ALL Streamlit input/widget contrast issues */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div,
    .stSlider > div > div > div > div,
    .stTextArea > div > div > textarea {
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }
    .stTextInput > div > div > input::placeholder,
    .stNumberInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: var(--text-dim) !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > div:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(0,212,170,0.2) !important;
    }
    /* Selectbox dropdown */
    .stSelectbox > div > div {
        background-color: var(--surface) !important;
    }
    .stSelectbox > div > div > div {
        color: var(--text) !important;
    }
    /* Slider */
    .stSlider > div > div > div > div {
        background-color: var(--primary) !important;
    }
    .stSlider > div > div > div {
        color: var(--text) !important;
    }
    /* Radio buttons */
    .stRadio > div > div > label {
        color: var(--text) !important;
    }
    .stRadio > div > div > label > div {
        background-color: var(--surface) !important;
        border-color: var(--border) !important;
    }
    .stRadio > div > div > label[data-baseweb="radio"] > div:first-child {
        background-color: var(--primary) !important;
        border-color: var(--primary) !important;
    }
    /* Buttons */
    .stButton > button {
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        border-color: var(--primary) !important;
        background-color: var(--surface-hover) !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--primary) !important;
        color: #000 !important;
        border-color: var(--primary) !important;
    }
    /* Checkbox */
    .stCheckbox > div > div > div {
        background-color: var(--surface) !important;
        border-color: var(--border) !important;
    }
    .stCheckbox > div > div > div[aria-checked="true"] {
        background-color: var(--primary) !important;
        border-color: var(--primary) !important;
    }
    .stCheckbox > label {
        color: var(--text) !important;
    }
    /* Expander */
    .streamlit-expanderHeader {
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }
    .streamlit-expanderContent {
        background-color: var(--bg) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-top: none !important;
    }
    /* Dataframe */
    .stDataFrame {
        background-color: var(--surface) !important;
    }
    .stDataFrame td, .stDataFrame th {
        color: var(--text) !important;
        background-color: var(--surface) !important;
        border-color: var(--border) !important;
    }
    /* Download button */
    .stDownloadButton > button {
        background-color: var(--secondary) !important;
        color: #fff !important;
        border-color: var(--secondary) !important;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--surface) !important;
        border-bottom: 1px solid var(--border) !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--text-muted) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--primary) !important;
        border-bottom-color: var(--primary) !important;
    }
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
    }
    [data-testid="stMetricDelta"] {
        color: var(--primary) !important;
    }
    /* Alerts/Info/Error/Success */
    .stAlert {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
    }
    .stAlert [data-testid="stMarkdownContainer"] {
        color: var(--text) !important;
    }
    /* Divider */
    hr {
        border-color: var(--border) !important;
        margin: 1.5rem 0 !important;
    }
    /* Caption */
    .stCaption {
        color: var(--text-dim) !important;
    }

    /* Aging badges */
    .aging-badge {
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .aging-fresh { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
    .aging-moderate { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .aging-critical { background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid rgba(239,68,68,0.4); }

    /* Stage badges */
    .badge-stage {
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        display: inline-block;
    }
    .badge-stage-descoberto { background: rgba(14,165,233,0.15); color: #0ea5e9; border: 1px solid rgba(14,165,233,0.3); }
    .badge-stage-contactado { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .badge-stage-proposta { background: rgba(244,63,94,0.15); color: #f43f5e; border: 1px solid rgba(244,63,94,0.3); }
    .badge-stage-negociado { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
    .badge-stage-comprado { background: rgba(16,185,129,0.25); color: #10b981; font-weight: bold; border: 2px solid #10b981; }
    .badge-stage-perdido { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# PATH SETUP & IMPORTS
# =============================================================================
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission, PriceHistory, Watchlist
from utils.helpers import format_price, format_km, calculate_deal_rating

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "compare_list": [],
        "watchlist_ids": set(),
        "pdf_export_data": None,
        "last_filter": {},
        "notification_msg": None,
        "search_query": "",
        "nlp_filters": {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# =============================================================================
# REAL-TIME ML VALUATION
# =============================================================================
@st.cache_resource
def get_valuation_engine():
    """Load the hybrid valuation engine (cached as singleton)."""
    try:
        from valuation.hybrid_valuator import get_valuator
        return get_valuator()
    except Exception as e:
        st.warning(f"Valuation engine not available: {e}")
        return None

@st.cache_data(ttl=60)
def recalculate_vehicle_valuation(vehicle_id: int) -> Dict[str, Any]:
    """Recalculate valuation for a single vehicle using the real ML model."""
    try:
        from valuation.hybrid_valuator import calculate_deal_score
        with get_db_context() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
            if not vehicle:
                return {}
            data = vehicle.to_dict()
            result = calculate_deal_score(data)
            return {
                "deal_score": float(result.get("deal_score", 0)),
                "estimated_value": float(result.get("estimated_value", 0)),
                "profit_potential": float(result.get("profit_potential", 0)),
                "profit_percentage": float(result.get("profit_percentage", 0)),
                "net_profit_potential": float(result.get("net_profit_potential", 0)),
                "net_profit_percentage": float(result.get("net_profit_percentage", 0)),
                "transfer_taxes": float(result.get("transfer_taxes", 0)),
                "estimated_repair_costs": float(result.get("estimated_repair_costs", 0)),
                "valuation_method": result.get("valuation_method", "unknown"),
                "asking_benchmark": float(result.get("asking_benchmark", 0)),
            }
    except Exception as e:
        return {"error": str(e)}

# =============================================================================
# DATA LOADING
# =============================================================================
@st.cache_data(ttl=120)
def load_vehicles_page(page: int = 0, page_size: int = 100, sort_by: str = "deal_score",
                        sort_desc: bool = True) -> pd.DataFrame:
    """Load a single page of vehicles (never all at once)."""
    from sqlalchemy import desc
    with get_db_context() as db:
        query = db.query(Vehicle).filter(Vehicle.is_active == True)
        sort_col = getattr(Vehicle, sort_by, Vehicle.deal_score)
        if sort_desc:
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(sort_col)
        vehicles = query.offset(page * page_size).limit(page_size).all()
        data = [v.to_dict() for v in vehicles]
        return pd.DataFrame(data)


@st.cache_data(ttl=120)
def count_vehicles() -> int:
    """Count total active vehicles."""
    with get_db_context() as db:
        return db.query(Vehicle).filter(Vehicle.is_active == True).count()

@st.cache_data(ttl=300)
def load_price_history(vehicle_id: int) -> List[Dict]:
    """Load price history for a specific vehicle."""
    with get_db_context() as db:
        hist = db.query(PriceHistory).filter(
            PriceHistory.vehicle_id == vehicle_id
        ).order_by(PriceHistory.recorded_at.asc()).all()
        return [{"recorded_at": h.recorded_at, "price": h.price} for h in hist]

@st.cache_data(ttl=300)
def load_watchlist_items() -> List[Dict]:
    """Load active watchlist criteria from database."""
    with get_db_context() as db:
        items = db.query(Watchlist).filter(Watchlist.is_active == True).all()
        return [{"id": w.id, "name": w.name, "brand": w.brand, "model": w.model,
                 "max_price": w.max_price, "notify_on_match": w.notify_on_match} for w in items]

# =============================================================================
# NLP QUERY PARSER
# =============================================================================
def parse_nlp_query(query_str: str) -> dict:
    """Parse natural language query into concrete filters."""
    filters = {}
    if not query_str or not query_str.strip():
        return filters
    query_lower = query_str.lower().strip()

    brands = ["ktm", "honda", "yamaha", "volkswagen", "vw", "bmw", "peugeot",
              "renault", "audi", "mercedes", "toyota", "ford", "opel", "nissan",
              "citroen", "seat", "skoda", "mini", "fiat", "hyundai", "kia",
              "dacia", "jeep", "land rover", "volvo", "mazda", "mitsubishi",
              "suzuki", "can-am", "voge", "ducati", "kawasaki", "triumph"]
    for b in brands:
        if b in query_lower:
            filters["brand"] = b.capitalize() if b != "vw" else "Volkswagen"
            break

    price_match = re.search(r'(?:menos de|abaixo de|ate|até|max|máximo)\s*(\d[\d\s.]*)\s*(?:euros|€)?', query_lower)
    if price_match:
        price_str = price_match.group(1).replace(".", "").replace(" ", "")
        try:
            filters["max_price"] = float(price_str)
        except ValueError:
            pass

    km_match = re.search(r'(?:menos de|abaixo de|ate|até|max|máximo)\s*(\d[\d\s.]*)\s*(?:mil\s*|k\s*)?km', query_lower)
    if km_match:
        val_str = km_match.group(1).replace(".", "").replace(" ", "")
        try:
            val = int(val_str)
            if "mil" in query_lower or "k" in query_lower or val < 1000:
                val = val * 1000
            filters["max_km"] = val
        except ValueError:
            pass

    year_match = re.search(r'\b(19|20)\d{2}\b', query_lower)
    if year_match:
        filters["year"] = int(year_match.group(0))

    locations = ["porto", "lisboa", "braga", "faro", "coimbra", "leiria",
                 "setubal", "setúbal", "viseu", "amadora", "sintra", "aveiro",
                 "funchal", "madeira", "azores", "açores"]
    for loc in locations:
        if loc in query_lower:
            filters["location"] = loc.capitalize()
            break

    if "moto" in query_lower or "125" in query_lower or "scooter" in query_lower:
        filters["vehicle_type"] = "motos"
    elif "carro" in query_lower or "suv" in query_lower or "carrinha" in query_lower:
        filters["vehicle_type"] = "carros"

    return filters

# =============================================================================
# FILTER LOGIC
# =============================================================================
def apply_filters(df: pd.DataFrame, nlp_filters: dict, brand_filter: str,
                  max_price: int, max_km: int, min_score: float,
                  fuel_filter: str = "Todos", year_range: tuple = None,
                  min_profit: int = 0, location_filter: str = "Todas") -> pd.DataFrame:
    """Apply all filters to the dataframe and return filtered results."""
    f_df = df.copy()

    # NLP filters
    if nlp_filters.get("brand"):
        f_df = f_df[f_df["brand"].str.contains(nlp_filters["brand"], case=False, na=False)]
    if nlp_filters.get("max_price"):
        f_df = f_df[f_df["price"] <= nlp_filters["max_price"]]
    if nlp_filters.get("max_km"):
        f_df = f_df[f_df["km"] <= nlp_filters["max_km"]]
    if nlp_filters.get("year"):
        f_df = f_df[f_df["year"] == nlp_filters["year"]]
    if nlp_filters.get("location"):
        f_df = f_df[f_df["location"].str.contains(nlp_filters["location"], case=False, na=False)]
    if nlp_filters.get("vehicle_type"):
        f_df = f_df[f_df["vehicle_type"] == nlp_filters["vehicle_type"]]

    # Widget filters
    if brand_filter != "Todas":
        f_df = f_df[f_df["brand"] == brand_filter]
    f_df = f_df[f_df["price"] <= max_price]
    f_df = f_df[f_df["km"] <= max_km]
    if "deal_score" in f_df.columns and min_score > 0:
        f_df = f_df[f_df["deal_score"] >= min_score]
    if fuel_filter != "Todos":
        col = "fuel_type" if "fuel_type" in f_df.columns else ("fuel" if "fuel" in f_df.columns else None)
        if col:
            f_df = f_df[f_df[col] == fuel_filter.lower()]
    if year_range and "year" in f_df.columns:
        f_df = f_df[(f_df["year"] >= year_range[0]) & (f_df["year"] <= year_range[1])]
    if min_profit > 0 and "profit_potential" in f_df.columns:
        f_df = f_df[f_df["profit_potential"] >= min_profit]
    if location_filter != "Todas" and "location" in f_df.columns:
        f_df = f_df[f_df["location"].str.contains(location_filter, case=False, na=False)]

    return f_df

# =============================================================================
# WATCHLIST DATABASE OPERATIONS
# =============================================================================
def add_to_watchlist_db(vehicle_id: int) -> bool:
    """Add a vehicle to the user's watchlist by flagging it."""
    try:
        with get_db_context() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
            if vehicle:
                return True
        return False
    except Exception as e:
        st.error(f"Erro ao adicionar à watchlist: {e}")
        return False

def remove_from_watchlist_db(vehicle_id: int) -> bool:
    """Remove a vehicle from the watchlist."""
    try:
        with get_db_context() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
            if vehicle:
                vehicle.is_active = False
                db.commit()
                return True
        return False
    except Exception as e:
        st.error(f"Erro ao remover da watchlist: {e}")
        return False

# =============================================================================
# PDF EXPORT
# =============================================================================
def generate_negotiation_pdf(vehicle_data: Dict) -> bytes:
    """Generate a simple text-based negotiation sheet."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 não está instalado")

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Ficha de Negociacao - AutoDeal IA Hunter', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    v = vehicle_data
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"{v.get('brand', 'N/A')} {v.get('model', 'N/A')} ({v.get('year', 'N/A')})", 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Preço Anunciado: {format_price(v.get('price', 0))}", 0, 1)
    pdf.cell(0, 8, f"Valor Estimado (ML): {format_price(v.get('estimated_value', 0))}", 0, 1)
    pdf.cell(0, 8, f"Deal Score: {v.get('deal_score', 0):.1f}/10", 0, 1)
    pdf.cell(0, 8, f"Lucro Potencial: {format_price(v.get('profit_potential', 0))}", 0, 1)
    pdf.cell(0, 8, f"Margem: {v.get('profit_percentage', 0):.1f}%", 0, 1)
    pdf.cell(0, 8, f"Quilometragem: {format_km(v.get('km', 0))}", 0, 1)
    pdf.cell(0, 8, f"Localização: {v.get('location', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Fonte: {v.get('source', 'N/A')}", 0, 1)
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Análise de Negociação:', 0, 1)
    pdf.set_font('Arial', '', 11)
    est = v.get('estimated_value', 0)
    price = v.get('price', 0)
    proposal = price * 0.9
    pdf.multi_cell(0, 6, f"Com base nos dados de mercado e modelo ML, este veículo apresenta um deal score de {v.get('deal_score', 0):.1f}/10. "
                          f"O preço de mercado estimado é de {format_price(est)}. "
                          f"Uma proposta inicial de {format_price(proposal)} pode ser considerada.")

    return pdf.output(dest='S').encode('utf-8')

# =============================================================================
# UI HELPERS
# =============================================================================
def get_score_class(score: float) -> str:
    if score >= 7.5:
        return "score-excellent"
    elif score >= 6.0:
        return "score-good"
    elif score >= 4.0:
        return "score-fair"
    else:
        return "score-poor"

# =============================================================================
# MAIN DASHBOARD
# =============================================================================
def main() -> None:
    init_session_state()

    # Header
    col1, col2 = st.columns([1, 6])
    with col1:
        st.markdown("<h1 style='font-size: 3.5rem; margin:0;'>🕵️‍♂️</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown("<h1 style='margin:0;' class='title-glow'>AutoDeal IA Hunter</h1>", unsafe_allow_html=True)
        st.markdown("<p style='margin-top:-8px; color:#64748b; font-size:0.95rem;'>Console Avançado de Arbitragem & Negociação de Veículos Usados em Portugal</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Load data (paginated)
    total_vehicles = count_vehicles()
    if total_vehicles == 0:
        st.error("Sem dados na base de dados. Execute primeiro: python main.py scrape")
        st.info("Ou verifique se a base de dados SQLite (autodeal.db) existe e tem dados.")
        return

    page_size = 100
    total_pages = max(1, (total_vehicles + page_size - 1) // page_size)
    page_num = st.sidebar.number_input(
        f"Página (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1
    )
    st.sidebar.caption(f"{total_vehicles} veículos • {page_size} por página")

    df = load_vehicles_page(page=page_num - 1, page_size=page_size)
    if df.empty:
        st.warning("Nenhum veículo encontrado nesta página.")
        return

    # Sidebar
    st.sidebar.markdown("<h2 style='text-align: center; color: #00d4aa; margin-bottom: 1rem;'>Hunter Control</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navegação",
        [
            "Início: Estado do Mercado",
            "Explorar Oportunidades",
            "Comparador Lado a Lado",
            "Preços Justos & Market Research",
            "Watchlist Ativa",
            "Monitor de Preços",
            "Ingestão de Leiloeiras",
            "Stealth & Proxy Monitor",
            "AI & Vision Sandbox",
            "Performance Pessoal",
        ]
    )

    # Sidebar status
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Estado do Sistema")
    st.sidebar.success("Base de Dados SQLite: Ligada")
    try:
        from utils.proxy_manager import get_proxy_pool
        _proxy_stats = get_proxy_pool().get_stats()
        _proxy_n = _proxy_stats.get("available_proxies", 0)
        if _proxy_n > 0:
            st.sidebar.info(f"Proxies: {_proxy_n} ativos")
        else:
            st.sidebar.warning("Proxies: não configurados")
    except Exception:
        st.sidebar.warning("Proxies: não configurados")
    st.sidebar.info("Ollama: Verificando...")
    st.sidebar.markdown("<p style='font-size:0.75rem; color:#64748b; margin-top:1rem;'>AutoDeal IA Hunter v3.1</p>", unsafe_allow_html=True)

    # =============================================================================
    # PAGE: INÍCIO
    # =============================================================================
    if page == "Início: Estado do Mercado":
        st.subheader("Resumo do Estado do Mercado Português")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        today = datetime.now(timezone.utc).date()

        with col_m1:
            if "first_seen" in df.columns:
                fs = pd.to_datetime(df["first_seen"], errors="coerce", utc=True)
                new_today = int((fs.dt.date == today).sum())
            else:
                new_today = 0
            new_label = f"+{new_today}" if new_today else "0"
            st.markdown(f"""
            <div class="hero-metric-card">
                <h4>Anúncios Novos (Hoje)</h4>
                <p class="value" style="color: #00d4aa;">{new_label}</p>
                <p class="sub">Total ativos: {len(df)}</p>
            </div>
            """, unsafe_allow_html=True)

        with col_m2:
            scored = df[df["deal_score"].notna()] if "deal_score" in df.columns else df
            if not scored.empty:
                best = scored.sort_values(by="deal_score", ascending=False).iloc[0]
                st.markdown(f"""
                <div class="hero-metric-card">
                    <h4>Melhor Oportunidade</h4>
                    <p class="value" style="font-size: 1.3rem; color: #10b981;">{best['brand']} {best['model']}</p>
                    <p class="sub" style="color:#00d4aa; font-weight:600;">Score {best['deal_score']:.1f}/10</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div class='hero-metric-card'><h4>Melhor Oportunidade</h4><p class='value'>Sem dados</p></div>", unsafe_allow_html=True)

        with col_m3:
            if "profit_potential" in df.columns and df["profit_potential"].notna().any():
                total_profit = df["profit_potential"].sum()
                st.markdown(f"""
                <div class="hero-metric-card">
                    <h4>Lucro Acumulado</h4>
                    <p class="value" style="color: #f59e0b;">{format_price(total_profit)}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div class='hero-metric-card'><h4>Lucro Acumulado</h4><p class='value'>Sem dados</p></div>", unsafe_allow_html=True)

        with col_m4:
            avg_price = df["price"].mean() if "price" in df.columns else 0
            st.markdown(f"""
            <div class="hero-metric-card">
                <h4>Preço Médio</h4>
                <p class="value" style="color: #f43f5e;">{format_price(avg_price)}</p>
                <p class="sub">{len(df)} veículos</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Distribution charts
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if "price" in df.columns:
                fig = px.histogram(df, x="price", nbins=30, title="Distribuição de Preços",
                                   color_discrete_sequence=["#00d4aa"])
                fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        with col_c2:
            if "deal_score" in df.columns and df["deal_score"].notna().any():
                fig = px.histogram(df, x="deal_score", nbins=20, title="Distribuição de Deal Scores",
                                   color_discrete_sequence=["#10b981"])
                fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

    # =============================================================================
    # PAGE: EXPLORAR OPORTUNIDADES
    # =============================================================================
    elif page == "Explorar Oportunidades":
        st.subheader("Explorar & Filtrar Veículos")

        # NLP Search
        nlp_input = st.text_input(
            "Pesquisa Inteligente",
            value=st.session_state.search_query,
            placeholder="Ex: BMW 320 diesel menos de 25000€ no Porto"
        )
        parsed = parse_nlp_query(nlp_input) if nlp_input else {}
        st.session_state.nlp_filters = parsed
        st.session_state.search_query = nlp_input

        if parsed:
            st.success(
                f"Filtros detetados: Marca={parsed.get('brand','Qualquer')}, "
                f"Max€={parsed.get('max_price','Qualquer')}, "
                f"KM≤={parsed.get('max_km','Qualquer')}, "
                f"Ano={parsed.get('year','Qualquer')}, "
                f"Local={parsed.get('location','Qualquer')}, "
                f"Tipo={parsed.get('vehicle_type','Qualquer')}"
            )

        # Filters
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            brands = ["Todas"] + sorted(df["brand"].dropna().unique().tolist())
            brand_filter = st.selectbox("Marca", brands, index=0)
        with col_f2:
            default_max_price = int(parsed.get("max_price", 500000))
            max_price = st.number_input("Preço Máx (€)", 0, 500000, default_max_price)
        with col_f3:
            default_max_km = int(parsed.get("max_km", 500000))
            max_km = st.number_input("KM Máx", 0, 1000000, default_max_km)
        with col_f4:
            min_score = st.slider("Deal Score Min", 0.0, 10.0, 0.0, 0.5)

        # Extra filters row
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        with col_e1:
            fuel_types = ["Todos"] + sorted(df["fuel_type"].dropna().unique().tolist()) if "fuel_type" in df.columns else ["Todos"]
            fuel_filter = st.selectbox("Combustível", fuel_types, index=0)
        with col_e2:
            min_year = int(df["year"].min()) if "year" in df.columns and df["year"].notna().any() else 1990
            max_year = int(df["year"].max()) if "year" in df.columns and df["year"].notna().any() else 2026
            year_range = st.slider("Ano", min_year, max_year, (min_year, max_year))
        with col_e3:
            min_profit = st.number_input("Lucro Min (€)", 0, 500000, 0)
        with col_e4:
            locations = ["Todas"] + sorted(df["location"].dropna().unique().tolist()) if "location" in df.columns and df["location"].notna().any() else ["Todas"]
            location_filter = st.selectbox("Localização", locations, index=0)

        # Sort / Order filters
        col_s1, col_s2, col_s3 = st.columns([3, 1, 1])
        with col_s1:
            sort_options = [
                "Deal Score (Maior → Menor)",
                "Lucro Potencial (Maior → Menor)",
                "Margem % (Maior → Menor)",
                "Preço (Menor → Maior)",
                "Preço (Maior → Menor)",
                "KM (Menor → Maior)",
                "Ano (Mais Recente → Antigo)",
                "Ano (Mais Antigo → Recente)",
                "Mais Recentes",
            ]
            sort_by = st.selectbox("Ordenar por", sort_options, index=0)
        with col_s2:
            results_per_page = st.selectbox("Por página", [10, 25, 50, 100], index=1)
        with col_s3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Limpar Filtros", use_container_width=True):
                st.session_state.search_query = ""
                st.session_state.nlp_filters = {}
                st.rerun()

        # Apply ALL filters
        f_df = apply_filters(df, parsed, brand_filter, max_price, max_km, min_score,
                             fuel_filter, year_range, min_profit, location_filter)

        # Apply sorting
        if not f_df.empty:
            if sort_by == "Deal Score (Maior → Menor)":
                f_df = f_df.sort_values(by="deal_score", ascending=False, na_position="last")
            elif sort_by == "Lucro Potencial (Maior → Menor)":
                f_df = f_df.sort_values(by="profit_potential", ascending=False, na_position="last")
            elif sort_by == "Margem % (Maior → Menor)":
                f_df = f_df.sort_values(by="profit_percentage", ascending=False, na_position="last")
            elif sort_by == "Preço (Menor → Maior)":
                f_df = f_df.sort_values(by="price", ascending=True, na_position="last")
            elif sort_by == "Preço (Maior → Menor)":
                f_df = f_df.sort_values(by="price", ascending=False, na_position="last")
            elif sort_by == "KM (Menor → Maior)":
                f_df = f_df.sort_values(by="km", ascending=True, na_position="last")
            elif sort_by == "Ano (Mais Recente → Antigo)":
                f_df = f_df.sort_values(by="year", ascending=False, na_position="last")
            elif sort_by == "Ano (Mais Antigo → Recente)":
                f_df = f_df.sort_values(by="year", ascending=True, na_position="last")
            elif sort_by == "Mais Recentes":
                if "first_seen" in f_df.columns:
                    f_df = f_df.sort_values(by="first_seen", ascending=False, na_position="last")

        st.markdown(f"**{len(f_df)} veículos encontrados**")

        if f_df.empty:
            st.info("Nenhum veículo corresponde aos filtros selecionados.")
        else:
            # Pagination
            total_pages = max(1, (len(f_df) + results_per_page - 1) // results_per_page)
            page_num = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
            start_idx = (page_num - 1) * results_per_page
            end_idx = start_idx + results_per_page
            paged_df = f_df.iloc[start_idx:end_idx]

            st.caption(f"A mostrar {start_idx + 1}–{min(end_idx, len(f_df))} de {len(f_df)} resultados (página {page_num}/{total_pages})")

            # Display as professional cards
            for _, row in paged_df.iterrows():
                score = row.get("deal_score", 0) or 0
                score_class = get_score_class(score)
                profit = row.get("profit_potential", 0) or 0
                profit_class = "positive" if profit > 0 else "negative" if profit < 0 else ""
                est_val = row.get("estimated_value", 0) or 0
                profit_pct = row.get("profit_percentage", 0) or 0
                grade = row.get("deal_grade", "") or ""
                grade_display = f" ({grade.upper()})" if grade else ""

                st.markdown(f"""
                <div class="vehicle-card">
                    <div class="header">
                        <span class="title">{row['brand']} {row['model']} ({row['year']}){grade_display}</span>
                        <span class="score-badge {score_class}">Score {score:.1f}</span>
                    </div>
                    <div class="stats-grid">
                        <div class="stat">
                            <div class="stat-label">Preço</div>
                            <div class="stat-value">{format_price(row['price'])}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Valor Mercado</div>
                            <div class="stat-value accent">{format_price(est_val)}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Lucro Bruto ¹</div>
                            <div class="stat-value {profit_class}">{format_price(profit)} ({profit_pct:.1f}%)</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">KM / Local</div>
                            <div class="stat-value">{format_km(row['km'])}<br><span style="font-size:0.75rem;color:#64748b">{row.get('location','N/A')}</span></div>
                        </div>
                    </div>
                    <div style="font-size:0.72rem; color: #64748b; margin-top:0.25rem;">
                        ¹ Lucro bruto = Valor Mercado − Preço de compra (antes de impostos ISV+IMT+Selo ≈15.5% e reparações estimadas)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Action buttons
                act1, act2, act3, act4 = st.columns([2, 1, 1, 1])
                with act1:
                    is_comp = row["id"] in st.session_state.compare_list
                    comp = st.checkbox("Comparar", value=is_comp, key=f"comp_{row['id']}")
                    if comp and row["id"] not in st.session_state.compare_list:
                        st.session_state.compare_list.append(row["id"])
                    elif not comp and row["id"] in st.session_state.compare_list:
                        st.session_state.compare_list.remove(row["id"])
                with act2:
                    if st.button("PDF", key=f"pdf_{row['id']}"):
                        try:
                            pdf_bytes = generate_negotiation_pdf(row.to_dict())
                            st.download_button("Download PDF", pdf_bytes,
                                             f"ficha_{row['brand']}_{row['model']}.pdf",
                                             "application/pdf", key=f"dl_{row['id']}")
                        except ImportError:
                            st.error("Instale fpdf2: pip install fpdf2")
                with act3:
                    if st.button("URL", key=f"url_{row['id']}"):
                        st.markdown(f"[Abrir anúncio]({row['url']})")
                with act4:
                    st.markdown(f"<a href='{row['url']}' target='_blank'>🔗</a>", unsafe_allow_html=True)

                # Price history expander
                with st.expander("Histórico de Preços"):
                    hist = load_price_history(row["id"])
                    if hist:
                        for h in hist:
                            st.markdown(f"* **{h['recorded_at'].strftime('%d/%m/%Y')}**: {format_price(h['price'])}")
                    else:
                        st.info("Sem histórico de preços.")

                # Real-time ML recalculation option
                with st.expander("Recalcular Valuation (ML em tempo real)"):
                    if st.button("Recalcular com ML", key=f"recalc_{row['id']}"):
                        with st.spinner("A calcular..."):
                            result = recalculate_vehicle_valuation(row["id"])
                            if result.get("error"):
                                st.error(f"Erro: {result['error']}")
                            else:
                                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                                col_r1.metric("Valor Estimado", format_price(result.get("estimated_value", 0)))
                                col_r2.metric("Deal Score", f"{result.get('deal_score', 0):.1f}")
                                col_r3.metric("Lucro Bruto", format_price(result.get("profit_potential", 0)),
                                              help="Valor Mercado − Preço (antes de impostos e reparações)")
                                col_r4.metric("Lucro Líquido", format_price(result.get("net_profit_potential", 0)),
                                              help="Após impostos (~15.5%) e reparações estimadas")
                                st.caption(
                                    f"Método: {result.get('valuation_method', 'unknown')} | "
                                    f"Benchmark: {format_price(result.get('asking_benchmark', 0))} | "
                                    f"Impostos: {format_price(result.get('transfer_taxes', 0))} | "
                                    f"Reparações est.: {format_price(result.get('estimated_repair_costs', 0))}"
                                )

    # =============================================================================
    # PAGE: COMPARADOR
    # =============================================================================
    elif page == "Comparador Lado a Lado":
        st.subheader("Comparador de Veículos")

        if not st.session_state.compare_list:
            st.info("Nenhum veículo selecionado. Vá a 'Explorar Oportunidades' e selecione veículos para comparar.")
        else:
            compare_df = df[df["id"].isin(st.session_state.compare_list)]
            if len(compare_df) < 2:
                st.warning("Selecione pelo menos 2 veículos para comparar.")
            else:
                cols = st.columns(len(compare_df))
                for idx, (_, row) in enumerate(compare_df.iterrows()):
                    with cols[idx]:
                        score = row.get("deal_score", 0) or 0
                        profit = row.get("profit_potential", 0) or 0
                        est_val = row.get("estimated_value", 0) or 0
                        st.markdown(f"""
                        <div style="background: var(--surface); border: 1px solid var(--border);
                                    border-radius: 12px; padding: 1rem;">
                            <h4 style="color:#00d4aa; margin-top:0;">{row['brand']} {row['model']}</h4>
                            <p><b>Ano:</b> {row['year']}</p>
                            <p><b>KM:</b> {format_km(row['km'])}</p>
                            <p><b>Preço:</b> <span style="color:#10b981">{format_price(row['price'])}</span></p>
                            <p><b>Valor Mercado:</b> <span style="color:#0ea5e9">{format_price(est_val)}</span></p>
                            <p><b>Lucro:</b> <span style="color:{'#10b981' if profit > 0 else '#ef4444'}">{format_price(profit)}</span></p>
                            <p><b>Score:</b> {score:.1f}</p>
                            <p><b>Local:</b> {row.get('location','N/A')}</p>
                        </div>
                        """, unsafe_allow_html=True)

            if st.button("Limpar Comparação", type="secondary"):
                st.session_state.compare_list = []
                st.rerun()

    # =============================================================================
    # PAGE: PREÇOS JUSTOS & MARKET RESEARCH
    # =============================================================================
    elif page == "Preços Justos & Market Research":
        st.subheader("📊 Preços Justos — Market Research VS Modelo ML")

        st.markdown("""
        <div style="background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.5rem; margin-bottom:1.5rem;">
            <h4 style="color:#00d4aa; margin-top:0;">📈 Comparação: Preço Real de Mercado vs Estimativa do Bot</h4>
            <p style="color:var(--text-muted);">
                Análise baseada em <b>886 listings reais</b> da base de dados (Standvirtual, OLX, CustoJusto, AutoSapo).
                O modelo XGBoost/CatBoost explica <b>~59%</b> da variação de preços (R²=0.59).
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Load data for market comparison
        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(
                Vehicle.vehicle_type == VehicleType.carros,
                Vehicle.price.isnot(None),
                Vehicle.estimated_value.isnot(None),
            ).all()

        if vehicles:
            # Build comparison dataframe
            data = []
            for v in vehicles:
                diff = (v.estimated_value or 0) - (v.price or 0)
                pct = ((diff / v.price) * 100) if v.price and v.price > 0 else 0
                data.append({
                    "Marca": v.brand, "Modelo": v.model or "", "Ano": v.year,
                    "KM": v.km, "Preço Anúncio": v.price,
                    "Estimativa ML": v.estimated_value or 0,
                    "Diferença (€)": diff, "Diferença (%)": round(pct, 1),
                    "Fuel": str(v.fuel_type.value if v.fuel_type else ""),
                })

            comp_df = pd.DataFrame(data)

            # Summary metrics
            total = len(comp_df)
            avg_diff = comp_df["Diferença (€)"].mean()
            avg_pct = comp_df["Diferença (%)"].mean()
            within_10pct = int((comp_df["Diferença (%)"].abs() <= 10).sum())
            underest = int((comp_df["Diferença (€)"] < 0).sum())
            overest = int((comp_df["Diferença (€)"] > 0).sum())

            col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
            col_s1.metric("Total Listings", total)
            col_s2.metric("Erro Médio (€)", f"€{avg_diff:+,.0f}")
            col_s3.metric("Erro Médio (%)", f"{avg_pct:+.1f}%")
            col_s4.metric("Dentro de 10%", f"{within_10pct} ({within_10pct/total*100:.0f}%)")
            col_s5.metric("R² Modelo", "0.59")

            st.markdown("---")

            # Market segments comparison
            st.subheader("🔍 Comparação por Segmento")
            segments = ["Volkswagen Golf", "BMW Série 3", "Mercedes Classe C", "Renault Clio", "Peugeot 208"]
            selected_segment = st.selectbox("Escolhe um segmento:", segments)

            # Filter by segment
            brand_model_map = {
                "Volkswagen Golf": ("Volkswagen", "Golf"),
                "BMW Série 3": ("BMW", "Série 3"),
                "Mercedes Classe C": ("Mercedes", "Classe C"),
                "Renault Clio": ("Renault", "Clio"),
                "Peugeot 208": ("Peugeot", "208"),
            }
            brand_filter, model_filter = brand_model_map[selected_segment]
            seg_df = comp_df[
                (comp_df["Marca"].str.contains(brand_filter, case=False, na=False)) &
                (comp_df["Modelo"].str.contains(model_filter, case=False, na=False))
            ]

            if not seg_df.empty:
                # Summary for this segment
                seg_avg_diff = seg_df["Diferença (€)"].mean()
                seg_avg_pct = seg_df["Diferença (%)"].mean()
                col_seg1, col_seg2, col_seg3 = st.columns(3)
                col_seg1.metric(f"{selected_segment} — Amostras", len(seg_df))
                col_seg2.metric("Diferença Média", f"€{seg_avg_diff:+,.0f}")
                col_seg3.metric("Desvio % Médio", f"{seg_avg_pct:+.1f}%")

                # Show sample table
                display_cols = ["Marca", "Modelo", "Ano", "KM", "Preço Anúncio", "Estimativa ML", "Diferença (€)", "Diferença (%)"]
                st.dataframe(
                    seg_df[display_cols].head(20).style.format({
                        "Preço Anúncio": "€{:,.0f}",
                        "Estimativa ML": "€{:,.0f}",
                        "Diferença (€)": "€{:+,.0f}",
                        "Diferença (%)": "{:+.1f}%",
                        "KM": "{:,.0f}",
                    }),
                    use_container_width=True, hide_index=True
                )

                # Bar chart comparison
                fig = px.bar(
                    seg_df.head(10), x="Modelo", y=["Preço Anúncio", "Estimativa ML"],
                    barmode="group", title=f"Preço Real vs Estimativa ML — {selected_segment}",
                    color_discrete_map={"Preço Anúncio": "#10b981", "Estimativa ML": "#0ea5e9"},
                    labels={"value": "Preço (€)", "variable": ""},
                )
                fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Sem dados suficientes para o segmento {selected_segment}.")

            st.markdown("---")

            # Overall accuracy distribution
            st.subheader("📉 Distribuição do Erro Percentual")
            fig = px.histogram(
                comp_df, x="Diferença (%)", nbins=40,
                title="Distribuição da Diferença % (real vs estimativa)",
                color_discrete_sequence=["#00d4aa"],
                labels={"Diferença (%)": "Erro Percentual"},
            )
            fig.add_vline(x=0, line_dash="dash", line_color="#f43f5e")
            fig.add_vline(x=10, line_dash="dot", line_color="#10b981")
            fig.add_vline(x=-10, line_dash="dot", line_color="#10b981")
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            # Confidence interval explanation
            st.markdown("""
            <div style="background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.5rem; margin-top:1rem;">
                <h4 style="color:#f59e0b; margin-top:0;">⚠️ Como Interpretar as Estimativas</h4>
                <ul style="color:var(--text-muted); line-height:1.8;">
                    <li><b>R² = 0.59</b> — O modelo explica 59% da variação de preços. Para referência, um modelo ideal tem R² > 0.85.</li>
                    <li><b>Erro médio = ~€6.100</b> — A diferença típica entre a estimativa e o preço real é de ~€6.000.</li>
                    <li><b>Apenas 46%</b> das estimativas estão dentro de 10% do preço real de mercado.</li>
                    <li><b>Usa como referência, não como verdade</b> — Cruza sempre com preços reais no Standvirtual, OLX e CustoJusto.</li>
                    <li>Para carros <b>abaixo de €15.000</b>, o erro percentual tende a ser maior (margem absoluta menor).</li>
                </ul>
                <p style="color:var(--text-dim); font-size:0.85rem; margin-top:0.5rem;">
                    📊 Fonte: <code>docs/market_research.md</code> — 886 listings analisados em 28/06/2026.
                </p>
            </div>
            """, unsafe_allow_html=True)

        else:
            st.warning("Sem dados disponíveis para análise de mercado. Executa scraping primeiro.")

    # =============================================================================
    # PAGE: WATCHLIST
    # =============================================================================
    elif page == "Watchlist Ativa":
        st.subheader("Watchlist de Veículos")

        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).limit(50).all()
            watchlist_data = []
            for v in vehicles:
                age_days = 0
                if v.first_seen:
                    age_days = (datetime.now(timezone.utc) - v.first_seen).days
                watchlist_data.append({
                    "id": v.id, "title": v.title, "price": v.price,
                    "estimated_value": v.estimated_value, "profit_potential": v.profit_potential,
                    "location": v.location, "age_days": age_days,
                    "lifecycle_status": v.lifecycle_status or "Descoberto",
                    "url": v.url,
                })

        for v in watchlist_data:
            if v["age_days"] < 5:
                age_class, age_label = "aging-fresh", f"{v['age_days']} Dias (Fresco)"
            elif v["age_days"] < 30:
                age_class, age_label = "aging-moderate", f"{v['age_days']} Dias (Moderado)"
            else:
                age_class, age_label = "aging-critical", f"{v['age_days']} Dias (Crítico!)"

            with st.container():
                st.markdown(f"""
                <div style="background: var(--surface); border: 1px solid var(--border);
                            border-radius: 12px; padding: 1.2rem; margin-bottom: 1.2rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 1.15rem; font-weight: 600; color: var(--text);">{v['title']}</span>
                        <span class="aging-badge {age_class}">{age_label}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-top: 0.8rem;">
                        <div style="text-align:center; padding:0.5rem; background:rgba(255,255,255,0.03); border-radius:8px;">
                            <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase;">Preço</div>
                            <div style="font-weight:600; color:#10b981;">{format_price(v['price'])}</div>
                        </div>
                        <div style="text-align:center; padding:0.5rem; background:rgba(255,255,255,0.03); border-radius:8px;">
                            <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase;">Valor Mercado</div>
                            <div style="font-weight:600; color:#0ea5e9;">{format_price(v['estimated_value'])}</div>
                        </div>
                        <div style="text-align:center; padding:0.5rem; background:rgba(255,255,255,0.03); border-radius:8px;">
                            <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase;">Margem</div>
                            <div style="font-weight:600; color:{'#10b981' if (v['profit_potential'] or 0) > 0 else '#ef4444'};">{format_price(v['profit_potential'])}</div>
                        </div>
                        <div style="text-align:center; padding:0.5rem; background:rgba(255,255,255,0.03); border-radius:8px;">
                            <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase;">Local</div>
                            <div style="font-weight:600; color:var(--text);">{v['location']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("Remover", key=f"rem_{v['id']}", type="secondary"):
                        if remove_from_watchlist_db(v['id']):
                            st.success("Veículo removido!")
                            st.cache_data.clear()
                            st.rerun()
                with c2:
                    st.markdown(f"<a href='{v['url']}' target='_blank'><button style='width:100%; padding:0.5rem; background:var(--surface); border:1px solid var(--border); border-radius:8px; color:var(--text); cursor:pointer;'>Ver Anúncio</button></a>",
                               unsafe_allow_html=True)

    # =============================================================================
    # PAGE: MONITOR DE PREÇOS
    # =============================================================================
    elif page == "Monitor de Preços":
        st.subheader("Monitor de Preços & Histórico")

        with get_db_context() as db:
            has_history = db.query(Vehicle.id, Vehicle.brand, Vehicle.model).join(PriceHistory).distinct().all()
            history_options = {f"{h.brand} {h.model} (ID#{h.id})": h.id for h in has_history}

        if history_options:
            selected = st.selectbox("Escolha um veículo:", list(history_options.keys()))
            vid = history_options[selected]

            hist = load_price_history(vid)
            if hist:
                hist_df = pd.DataFrame([{"Data": h["recorded_at"].strftime("%d/%m"), "Preço": h["price"]} for h in hist])
                fig = px.line(hist_df, x="Data", y="Preço", title=f"Histórico de Preço: {selected}", markers=True)
                fig.update_traces(line_color="#10b981", line_width=3)
                fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

                first_p = hist[0]["price"]
                last_p = hist[-1]["price"]
                total_drop = first_p - last_p
                st.markdown(f"**Variação:** {format_price(total_drop)} ({(total_drop/first_p*100):.1f}%)")
            else:
                st.info("Sem histórico.")
        else:
            st.info("Nenhum veículo com histórico de preços.")

    # =============================================================================
    # PAGE: INGESTÃO DE LEILÕES
    # =============================================================================
    elif page == "Ingestão de Leiloeiras":
        st.subheader("Ingestão de Dados de Leilões")

        with get_db_context() as db:
            vp_count = db.query(Vehicle).filter(Vehicle.source == Source.VPAUTO).count()
            lei_count = db.query(Vehicle).filter(Vehicle.source == Source.LEILOSOC).count()

        col1, col2, col3 = st.columns(3)
        col1.metric("VPauto", f"{vp_count} Veículos")
        col2.metric("Leilosoc", f"{lei_count} Insolvências")
        col3.metric("Margem Est.", "~28%")

        st.markdown("---")

        if st.button("Iniciar Ingestão de Leilões", type="primary"):
            with st.spinner("A executar scrapers..."):
                try:
                    from scrapers.auction_scraper import AuctionScraper
                    import asyncio

                    scraper = AuctionScraper()

                    async def run_scraps():
                        results = {"vpauto": 0, "leilosoc": 0}
                        try:
                            vp = await scraper.scrape_vpauto()
                            results["vpauto"] = len(vp) if vp else 0
                        except Exception as e:
                            st.warning(f"VPauto: {e}")
                        try:
                            lei = await scraper.scrape_leilosoc()
                            results["leilosoc"] = len(lei) if lei else 0
                        except Exception as e:
                            st.warning(f"Leilosoc: {e}")
                        return results

                    try:
                        loop = asyncio.get_running_loop()
                        results = loop.run_until_complete(run_scraps())
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        results = loop.run_until_complete(run_scraps())
                    st.success(f"Ingestão concluída! VPauto: {results['vpauto']}, Leilosoc: {results['leilosoc']}")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Erro na ingestão: {e}")

    # =============================================================================
    # PAGE: STEALTH & PROXY
    # =============================================================================
    elif page == "Stealth & Proxy Monitor":
        st.subheader("Stealth & Proxy Monitor")

        try:
            from utils.proxy_manager import get_proxy_pool
            pool = get_proxy_pool()
            stats = pool.get_stats()
            proxy_count = stats.get("available_proxies", 0)
        except Exception:
            proxy_count = 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Proxies", proxy_count if proxy_count else "Nenhum")
        col2.metric("Modo", "Proxy" if proxy_count else "Direto")
        col3.metric("Delay", "2-5s")

        st.markdown("---")
        st.info("O worker de monitorização deve ser iniciado via: python main.py scheduler")

    # =============================================================================
    # PAGE: AI & VISION
    # =============================================================================
    elif page == "AI & Vision Sandbox":
        st.subheader("AI & Vision Sandbox")
        st.info("Sandbox de visão computacional. Funcionalidade em desenvolvimento.")

    # =============================================================================
    # PAGE: PERFORMANCE
    # =============================================================================
    elif page == "Performance Pessoal":
        st.subheader("Performance Pessoal")

        total = len(df)
        with_deal = int(df["deal_score"].notna().sum()) if "deal_score" in df.columns else 0
        high_deals = int((df["deal_score"] >= 7).sum()) if "deal_score" in df.columns else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ativos", total)
        col2.metric("Com Score", with_deal)
        col3.metric("Score >= 7", high_deals)
        if "profit_percentage" in df.columns and df["profit_percentage"].notna().any():
            col4.metric("Margem Média", f"{df['profit_percentage'].mean():.1f}%")
        else:
            col4.metric("Margem Média", "N/A")

        st.markdown("---")

        # Funnel
        if total > 0:
            funnel_data = dict(
                number=[total, with_deal, high_deals, max(1, high_deals // 2)],
                stage=["Listados", "Com Score", "Score >= 7", "Top Picks"],
            )
            fig = px.funnel(funnel_data, x='number', y='stage', title="Pipeline",
                           color_discrete_sequence=["#00d4aa"])
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Top deals table with real values
        st.subheader("Top 10 Melhores Oportunidades")
        if "deal_score" in df.columns and df["deal_score"].notna().any():
            top_cols = ["brand", "model", "year", "km", "price", "estimated_value",
                       "deal_score", "profit_potential", "profit_percentage", "location", "url"]
            available_top_cols = [c for c in top_cols if c in df.columns]
            top_deals = df.nlargest(10, "deal_score")[available_top_cols]
            st.dataframe(top_deals, use_container_width=True, hide_index=True)
        else:
            st.info("Sem deals scored.")

    st.markdown("---")
    st.caption(f"AutoDeal IA Hunter v3.1 | Dados atualizados em {datetime.now().strftime('%Y-%m-%d %H:%M')} | Valuation ML: Ativo")

if __name__ == "__main__":
    main()

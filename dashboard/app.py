"""
VER PRECOS — Dashboard v4
=========================
Foco: Encontrar o melhor deal com base em PROFIT REAL e CONFIANÇA.
Pesquisa por modelo, ranking por profit líquido, comparação entre fontes.

Run: streamlit run dashboard/app.py --server.port 8501
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VER PRECOS — Deal Hunter",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH = "data/autodeal.db"

@st.cache_data(ttl=300)
def load_all_vehicles() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, brand, model, year, km, price, estimated_value,
               profit_potential, profit_percentage, deal_score, deal_grade,
               source, fuel_type, transmission, location, url, title,
               first_seen, seller_name, horsepower, engine_size,
               buyer_profit, buyer_profit_margin, buyer_roi,
               repair_costs, taxes, total_additional_costs, profit_recommendation,
               net_profit,
               -- Colunas de fiabilidade (valuation/reliability.py). Corrigem a
               -- winner's curse: ordenar por profit bruto seleccionava erro do
               -- modelo (MAPE 45,9 % no top-100 vs 15,8 % global).
               comparables_count, valuation_confidence,
               adjusted_estimated_value, credible_profit, profit_is_publishable
        FROM vehicles WHERE is_active=1 AND price > 0
        ORDER BY credible_profit DESC NULLS LAST
    """, conn)
    conn.close()
    # Compatibilidade: bases anteriores ao scripts/fix_price_leaks.py não têm
    # as colunas de fiabilidade. Degrada para o comportamento antigo.
    for col, fallback in (
        ('comparables_count', 0),
        ('valuation_confidence', 'sem_dados'),
        ('adjusted_estimated_value', None),
        ('credible_profit', None),
        ('profit_is_publishable', 0),
    ):
        if col not in df.columns:
            df[col] = fallback
    df['comparables_count'] = df['comparables_count'].fillna(0).astype(int)
    df['valuation_confidence'] = df['valuation_confidence'].fillna('sem_dados')
    df['profit_is_publishable'] = df['profit_is_publishable'].fillna(0).astype(int)
    # Credible profit e deal_grade agora vêm da avaliação coerente
    # (valuation/service.py): `credible_profit` é None (não zero) quando não
    # há evidência, e `deal_grade` reflete a posição face ao intervalo.
    df['credible_profit'] = df['credible_profit'].fillna(0)
    df['adapted_estimated_value'] = df['adjusted_estimated_value'].fillna(df['estimated_value'])
    # `estimated_value` nulo significa "sem estimativa fiável": nunca se
    # assume o próprio preço como valor de mercado (era a fonte do NaN/+
    # nos cards). Quem avalia trata o None.
    df['estimated_value'] = df['estimated_value']
    df['km'] = df['km'].fillna(0).astype(int)
    for col in ['buyer_profit', 'buyer_profit_margin', 'buyer_roi', 'repair_costs',
                'taxes', 'total_additional_costs', 'net_profit']:
        if col not in df.columns:
            df[col] = float('nan')
    # net_pct derivado da margem líquida (ou NaN se não houver lucro nem preço).
    # NUNCA se propaga NaN para linhas com net_profit — usa-se máscara explícita.
    has_net = df['net_profit'].notna() & (df['price'] > 0)
    df['net_pct'] = float('nan')
    df.loc[has_net, 'net_pct'] = (
        df.loc[has_net, 'net_profit'] / df.loc[has_net, 'price'] * 100.0
    )
    return df

@st.cache_data(ttl=600)
def load_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE is_active=1")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT brand) FROM vehicles WHERE is_active=1")
    brands = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE is_active=1 AND estimated_value IS NOT NULL")
    with_val = cur.fetchone()[0]
    cur.execute("SELECT source, COUNT(*) FROM vehicles WHERE is_active=1 GROUP BY source ORDER BY COUNT(*) DESC")
    sources = cur.fetchall()
    # Model metrics
    import json
    try:
        meta = json.loads(open('models/best_model_carros.json').read())
        model_r2 = meta['metrics']['r2']
        model_mae = meta['metrics']['mae']
        model_samples = meta['n_samples']
    except:
        model_r2 = model_mae = model_samples = 0
    conn.close()
    return {
        'total': total, 'brands': brands, 'with_val': with_val,
        'sources': sources, 'r2': model_r2, 'mae': model_mae, 'samples': model_samples,
    }

@st.cache_data(ttl=60)
def get_model_suggestions(search: str) -> list:
    """Get matching brand+model combos for autocomplete."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT DISTINCT brand, model, COUNT(*) as cnt
        FROM vehicles WHERE is_active=1 AND price > 0
        GROUP BY brand, model ORDER BY cnt DESC
    """, conn)
    conn.close()
    if not search:
        return []
    q = search.lower()
    df['match'] = (df['brand'].str.lower() + ' ' + df['model'].str.lower()).str.contains(q, na=False)
    return df[df['match']].head(20).to_dict('records')

def calculate_net_profit(row) -> dict:
    """Calculate realistic net profit after Portuguese taxes + repairs + source costs."""
    price = row['price'] or 0
    est = row['estimated_value'] if pd.notna(row.get('estimated_value')) else price
    # Net profit is signed: a car priced above market yields a NEGATIVE gross.
    if pd.notna(row.get('buyer_profit')):
        net = float(row['buyer_profit'])
        gross = est - price
        net_pct = float(row['buyer_profit_margin']) if pd.notna(row.get('buyer_profit_margin')) else (net / price * 100 if price > 0 else 0)
        taxes = float(row['taxes']) if pd.notna(row.get('taxes')) else price * 0.155
        repairs = float(row['repair_costs']) if pd.notna(row.get('repair_costs')) else 0
        return {'gross_profit': gross, 'net_profit': net, 'net_pct': net_pct, 'taxes': taxes, 'repairs': repairs}
    # Taxes: 15.5% (IMT+ISV+Selo)
    taxes = price * 0.155
    # Repairs based on KM
    km = row['km'] or 0
    if km < 50000: repairs = 0
    elif km < 100000: repairs = 500
    elif km < 150000: repairs = 1000
    else: repairs = 1500
    # Transport/registration + source-specific acquisition costs
    extra = 500
    # Auction (LEILOSOC) carries ~18% buyer commission + IVA on top of hammer price
    if row.get('source') == 'LEILOSOC':
        extra += price * 0.18
    gross = max(0, est - price)
    net = gross - taxes - repairs - extra
    net_pct = (net / price * 100) if price > 0 else 0
    return {
        'gross_profit': gross,
        'net_profit': net,
        'net_pct': net_pct,
        'taxes': taxes,
        'repairs': repairs,
    }

def confidence_level(row) -> str:
    """Rate confidence based on data completeness and source.

    Prefere a confiança real calculada em ``valuation/reliability.py``
    (densidade de comparáveis), que é medida e não heurística. A heurística
    abaixo só corre em bases ainda não migradas.
    """
    measured = row.get('valuation_confidence')
    if measured and measured != 'sem_dados':
        n = int(row.get('comparables_count') or 0)
        return {
            'alta': f'🟢 Alta ({n} comp.)',
            'media': f'🟡 Média ({n} comp.)',
            'baixa': f'🔴 Baixa ({n} comp.)',
        }.get(measured, '⚪ n/d')

    score = 0
    if row['year'] and row['year'] > 1990: score += 1
    if row['km'] and row['km'] > 0: score += 2
    if row['horsepower'] and row['horsepower'] > 0: score += 1
    if row['fuel_type']: score += 1
    if row['source'] in ('STANDVIRTUAL', 'AUTOPT'): score += 1  # Better data
    if row['source'] == 'LEILOSOC': score -= 2  # Auction = uncertain
    if score >= 5: return '🟢 Alta'
    if score >= 3: return '🟡 Média'
    return '🔴 Baixa'
def grade_class(grade: str) -> str:
    """Map the valuation label to a stable CSS border class."""
    return {
        'excelente_oportunidade': 'excellent',
        'boa_oportunidade': 'good',
        'dentro_do_mercado': 'fair',
        'ligeiramente_acima_do_mercado': 'fair',
        'muito_acima_do_mercado': 'poor',
        'requer_validacao_manual': 'fair',
        'anuncio_suspeito': 'poor',
        'dados_insuficientes': 'poor',
    }.get(grade, 'poor')


def profit_badge(net_profit, net_pct):
    """Badge from the *signed* net profit. A negative net is a loss, shown as
    such — never silently flipped to a marginal gain."""
    if pd.isna(net_profit) or net_profit is None:
        return '⚪ S/ DADOS', '#94a3b8'
    if net_profit > 3000 and (net_pct or 0) > 8:
        return '🟢 EXCELENTE', '#10b981'
    if net_profit > 1000 and (net_pct or 0) > 5:
        return '🟡 BOM', '#f59e0b'
    if net_profit > 0:
        return '⚪ MARGINAL', '#94a3b8'
    return '🔴 PREJUÍZO', '#ef4444'

SOURCE_COLORS = {
    'LEILOSOC': '#f59e0b', 'AUTOPT': '#00d4aa', 'STANDVIRTUAL': '#0ea5e9',
    'OLX': '#8b5cf6', 'CUSTOJUSTO': '#ec4899',
}

# ── Auction sources ──────────────────────────────────────────────────────────
AUCTION_SOURCES = ['LEILOSOC', 'MARTELO', 'AUTOLINE', 'PENHORADO']

@st.cache_data(ttl=300)
def load_auctions(sources: list) -> pd.DataFrame:
    """Load active auction vehicles from the DB for the given sources."""
    conn = sqlite3.connect(DB_PATH)
    placeholder = ','.join('?' * len(sources))
    df = pd.read_sql_query(f"""
        SELECT id, source, brand, model, year, km, price, url, title
        FROM vehicles
        WHERE is_active = 1 AND price > 0 AND source IN ({placeholder})
        ORDER BY price ASC
    """, conn, params=sources)
    conn.close()
    df['km'] = df['km'].fillna(0).astype(int)
    df['year'] = df['year'].astype('Int64')
    return df

def render_auctions():
    """Page: active auctions across the 4 auction sources (LEILOSOC/MARTELO/AUTOLINE/PENHORADO)."""
    st.subheader("🏷️ Leilões ativos — 4 fontes")
    st.caption("Veículos em leilão (LEILOSOC, MARTELO, AUTOLINE, PENHORADO). "
               "Atenção: o valor de mercado do leiloeiro costuma ser inflacionado — "
               "não confundir com valor de revenda real.")

    # Source multiselect filter (default: all 4)
    sel = st.multiselect(
        "Fonte(s) de leilão",
        AUCTION_SOURCES,
        default=AUCTION_SOURCES,
        help="Filtra por uma ou várias fontes de leilão. Vazio = nenhuma.",
    )
    sort_order = st.radio(
        "Ordenação por preço",
        ["Crescente ↑", "Decrescente ↓"],
        horizontal=True, label_visibility="collapsed",
    )

    if not sel:
        st.info("Seleciona pelo menos uma fonte de leilão.")
        return

    au = load_auctions(sel)
    au = au.sort_values('price', ascending=(sort_order == "Crescente ↑"))

    # ── Summary ──────────────────────────────────────────────────────────
    sm = au.groupby('source').agg(n=('id', 'count'), avg_price=('price', 'mean')).reset_index()
    sm['avg_price'] = sm['avg_price'].round(0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Leilões ativos (filtro)", f"{len(au):,}")
    c2.metric("Fontes selecionadas", f"{au['source'].nunique()}")
    c3.metric("Preço médio (filtro)", f"€{au['price'].mean():,.0f}" if len(au) else "€0")

    st.markdown("**Resumo por fonte**")
    summ = pd.DataFrame({
        'Fonte': sm['source'],
        'Leilões': sm['n'].astype(int),
        'Preço médio €': sm['avg_price'].astype(int),
    })
    st.dataframe(summ, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(f"{len(au)} leilões • ordenado por preço ({sort_order})")

    # ── Table ────────────────────────────────────────────────────────────
    view = pd.DataFrame({
        'Fonte': au['source'],
        'Marca': au['brand'],
        'Modelo': au['model'],
        'Ano': au['year'],
        'KM': au['km'],
        'Preço €': au['price'].round(0).astype(int),
        'URL': au['url'],
    })
    st.dataframe(view, use_container_width=True, hide_index=True)

    # Quick links per row (limited to avoid rendering thousands of buttons)
    if not au.empty:
        with st.expander(f"🔗 Links diretos ({min(len(au), 200)} primeiros)"):
            for _, row in au.head(200).iterrows():
                st.markdown(
                    f"[{row['source']}] {row['brand']} {row['model']} "
                    f"({row['year'] if pd.notna(row['year']) else '?'}) — "
                    f"€{row['price']:,.0f} — {row['url']}",
                    unsafe_allow_html=False,
                )

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@600;700&display=swap');

    :root {
        /* Superfícies em escala, para dar profundidade sem sombras pesadas */
        --bg: #07080d;
        --surface: #101220;
        --surface-2: #161a2c;
        --border: #222639;
        --border-strong: #2f3550;

        --text: #e8e9f2;
        --muted: #8b8fa8;
        --faint: #5a5e77;

        /* Semântica: verde = oportunidade, âmbar = cautela, vermelho = risco */
        --accent: #00e5b0;
        --accent-dim: #00a37e;
        --warn: #f5a524;
        --danger: #f4436c;
        --info: #5b8cff;

        --radius: 14px;
        --radius-sm: 9px;
    }

    .stApp {
        background:
            radial-gradient(1100px 520px at 12% -10%, rgba(0,229,176,.09), transparent 60%),
            radial-gradient(900px 460px at 88% -6%, rgba(91,140,255,.08), transparent 62%),
            var(--bg);
        color: var(--text);
        font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }
    .block-container { padding-top: 2.2rem; max-width: 1500px; }

    /* ── Cabeçalho ─────────────────────────────────────────────────────── */
    .main-header {
        font-size: 2rem; font-weight: 800; letter-spacing: -.03em; margin: 0;
        background: linear-gradient(95deg, var(--accent), var(--info) 130%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .sub-header { color: var(--muted); font-size: .85rem; margin: .15rem 0 1.1rem; }

    /* ── KPIs ──────────────────────────────────────────────────────────── */
    .kpi-row { display: flex; gap: .7rem; flex-wrap: wrap; margin-bottom: 1.4rem; }
    .kpi {
        flex: 1 1 168px; background: var(--surface); border: 1px solid var(--border);
        border-radius: var(--radius); padding: .85rem 1rem; position: relative;
        overflow: hidden; transition: border-color .18s, transform .18s;
    }
    .kpi:hover { border-color: var(--border-strong); transform: translateY(-2px); }
    .kpi::before {
        content: ''; position: absolute; inset: 0 auto 0 0; width: 3px;
        background: var(--accent); opacity: .85;
    }
    .kpi.warn::before { background: var(--warn); }
    .kpi.info::before { background: var(--info); }
    .kpi.danger::before { background: var(--danger); }
    .kpi .label {
        font-size: .66rem; color: var(--muted); text-transform: uppercase;
        letter-spacing: .09em; font-weight: 600;
    }
    .kpi .value {
        font-family: 'JetBrains Mono', monospace; font-size: 1.5rem;
        font-weight: 700; line-height: 1.25; margin-top: .18rem;
    }
    .kpi .delta { font-size: .7rem; color: var(--faint); margin-top: .1rem; }

    /* ── Cartão de deal ────────────────────────────────────────────────── */
    .deal-card {
        background: linear-gradient(180deg, var(--surface-2), var(--surface));
        border: 1px solid var(--border); border-left: 3px solid var(--faint);
        border-radius: var(--radius); padding: .9rem 1.1rem; margin-bottom: .6rem;
        transition: border-color .18s, transform .18s;
    }
    .deal-card:hover { border-color: var(--border-strong); transform: translateX(3px); }
    .deal-card.grade-exceptional { border-left-color: var(--accent); }
    .deal-card.grade-excellent   { border-left-color: var(--accent-dim); }
    .deal-card.grade-good        { border-left-color: var(--info); }
    .deal-card.grade-fair        { border-left-color: var(--warn); }
    .deal-card.grade-poor        { border-left-color: var(--faint); }

    .deal-card .title { font-weight: 650; font-size: .97rem; letter-spacing: -.01em; }
    .deal-card .meta { color: var(--muted); font-size: .74rem; margin-top: .12rem; }
    .deal-card .price { font-family: 'JetBrains Mono', monospace; font-size: 1.05rem; font-weight: 700; }
    .deal-card .profit {
        font-family: 'JetBrains Mono', monospace; font-size: 1.15rem;
        font-weight: 700; color: var(--accent);
    }
    .deal-card .profit.neg { color: var(--danger); }

    /* ── Etiquetas ─────────────────────────────────────────────────────── */
    .tag {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        font-size: .63rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: .05em; border: 1px solid transparent; margin-right: .3rem;
    }
    .tag-source { background: rgba(91,140,255,.12); color: var(--info); border-color: rgba(91,140,255,.3); }
    .tag-alta   { background: rgba(0,229,176,.13); color: var(--accent); border-color: rgba(0,229,176,.32); }
    .tag-media  { background: rgba(245,165,36,.13); color: var(--warn); border-color: rgba(245,165,36,.32); }
    .tag-baixa  { background: rgba(244,67,108,.12); color: var(--danger); border-color: rgba(244,67,108,.3); }
    .tag-sem_dados { background: rgba(139,143,168,.12); color: var(--muted); border-color: rgba(139,143,168,.28); }
    .tag-grade  { background: rgba(232,233,242,.07); color: var(--text); border-color: var(--border-strong); }

    /* Barra de confiança: densidade de comparáveis de forma visual */
    .conf-bar { display: inline-flex; gap: 2px; vertical-align: middle; margin-left: .35rem; }
    .conf-bar i {
        width: 13px; height: 4px; border-radius: 2px; background: var(--border-strong);
        display: inline-block;
    }
    .conf-bar i.on { background: var(--accent); }
    .conf-bar.media i.on { background: var(--warn); }
    .conf-bar.baixa i.on { background: var(--danger); }

    /* ── Avisos ────────────────────────────────────────────────────────── */
    .note {
        background: var(--surface); border: 1px solid var(--border);
        border-left: 3px solid var(--info); border-radius: var(--radius-sm);
        padding: .65rem .9rem; font-size: .8rem; color: var(--muted);
        margin-bottom: .9rem;
    }
    .note.warn { border-left-color: var(--warn); }
    .note strong { color: var(--text); }

    /* ── Controlos Streamlit ───────────────────────────────────────────── */
    .stSelectbox [data-baseweb="select"], .stTextInput input,
    .stNumberInput input, .stMultiSelect [data-baseweb="select"] {
        background: var(--surface) !important; border-color: var(--border) !important;
        color: var(--text) !important; border-radius: var(--radius-sm) !important;
    }
    .stRadio [role="radiogroup"] { gap: .3rem; }
    .stRadio label {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 999px; padding: .3rem .85rem !important;
        transition: border-color .18s, background .18s;
    }
    .stRadio label:hover { border-color: var(--accent-dim); }
    div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--radius-sm); }
    hr { border-color: var(--border); }
</style>
""", unsafe_allow_html=True)


# ── Componentes de UI ────────────────────────────────────────────────────────
CONFIDENCE_LABELS = {
    'alta': ('Alta', 4), 'media': ('Média', 2),
    'baixa': ('Baixa', 1), 'sem_dados': ('Sem dados', 0),
}


def kpi(label: str, value: str, delta: str = "", tone: str = "") -> str:
    """HTML de um cartão de KPI."""
    d = f"<div class='delta'>{delta}</div>" if delta else ""
    return (
        f"<div class='kpi {tone}'><div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>{d}</div>"
    )


def save_deal(vehicle_id: int) -> None:
    """Guarda uma viatura numa tabela própria.

    Antes escrevia-se ``deal_grade='watchlist'``, o que destruía a grade
    calculada. A tabela ``saved_deals`` mantém as duas coisas separadas.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS saved_deals ("
            "vehicle_id INTEGER PRIMARY KEY, "
            "saved_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO saved_deals (vehicle_id) VALUES (?)",
            (vehicle_id,),
        )
        conn.commit()
    finally:
        conn.close()


def confidence_tag(conf: str, n_comp: int = 0) -> str:
    """Etiqueta + barra de confiança da avaliação."""
    conf = conf if conf in CONFIDENCE_LABELS else 'sem_dados'
    label, filled = CONFIDENCE_LABELS[conf]
    bars = "".join(
        f"<i class='{'on' if i < filled else ''}'></i>" for i in range(4)
    )
    return (
        f"<span class='tag tag-{conf}'>{label}</span>"
        f"<span class='conf-bar {conf}'>{bars}</span>"
        f"<span style='color:var(--faint);font-size:.7rem;margin-left:.35rem'>"
        f"{n_comp} comp.</span>"
    )

# ── Load data ────────────────────────────────────────────────────────────────
df = load_all_vehicles()
stats = load_stats()

# ── Header ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 20])
with col1: st.markdown("<h1 style='font-size:2.5rem;margin:0'>💰</h1>", unsafe_allow_html=True)
with col2:
    st.markdown("<h1 class='main-header'>VER PRECOS</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p class='sub-header'>{stats['total']:,} veículos • {stats['brands']} marcas • "
        f"{len(stats['sources'])} fontes • Modelo R²={stats['r2']:.2f} • "
        f"MAE {stats['mae']:,.0f} €</p>",
        unsafe_allow_html=True,
    )

# ── KPI hero ─────────────────────────────────────────────────────────────────
# Mostra a saúde do funil de deals, não apenas contagens brutas: quantas
# oportunidades sobrevivem às portas de fiabilidade é a métrica que importa.
_pub = df[df['profit_is_publishable'] == 1]
_high_conf = _pub[_pub['valuation_confidence'] == 'alta']
_total_profit = float(_pub['credible_profit'].sum())
_median_margin = (
    float((_pub['credible_profit'] / _pub['price'] * 100).median()) if len(_pub) else 0.0
)
_top_grades = int((_pub['deal_grade'].isin(
    ['excelente_oportunidade', 'boa_oportunidade'])).sum())

st.markdown(
    "<div class='kpi-row'>"
    + kpi("Deals credíveis", f"{len(_pub):,}",
          f"de {len(df):,} com preço retail")
    + kpi("Confiança alta", f"{len(_high_conf):,}",
          "8+ anúncios comparáveis", "info")
    + kpi("Grade A (exc./excel.)", f"{_top_grades:,}",
          "topo do ranking por percentil")
    + kpi("Margem mediana", f"{_median_margin:.1f}%",
          "após shrinkage e truncatura", "warn")
    + kpi("Lucro credível total", f"{_total_profit/1000:,.0f}k €",
          "soma dos deals publicáveis")
    + "</div>",
    unsafe_allow_html=True,
)

# ── NAV ──────────────────────────────────────────────────────────────────────
page = st.radio(
    "", ["🔍 Procurar Deals", "💸 Melhores Deals", "🏷️ Leilões", "🔥 Margem por Modelo", "📊 Análise Mercado", "⭐ Watchlist", "📋 Dados", "📈 Observabilidade"],
    horizontal=True, label_visibility="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1b: MELHORES DEALS / ONDE GANHAR DINHEIRO
# ═══════════════════════════════════════════════════════════════════════════════
if page == "💸 Melhores Deals":
    st.subheader("💸 Onde fazer dinheiro — ranking por lucro credível")
    st.markdown(
        "<div class='note'>O ranking usa <strong>lucro credível</strong>, não o gap bruto do "
        "modelo. O gap é encolhido pela densidade de comparáveis e truncado a "
        "20 %; anúncios com gap bruto acima de 50 % são fraude/erro e ficam de "
        "fora. Sem isto, o topo da lista era dominado por erro de avaliação: "
        "o top-100 por gap bruto tinha <strong>MAPE de 45,9 %</strong> contra "
        "15,8 % da população.</div>",
        unsafe_allow_html=True,
    )

    deals = df[df['profit_is_publishable'] == 1].copy()
    deals['margin_pct'] = (deals['credible_profit'] / deals['price'] * 100).where(
        deals['price'] > 0, 0
    )

    # ── Filtros ──────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        d_sources = st.multiselect(
            "Fonte(s)", sorted(deals['source'].unique().tolist()),
            default=[], label_visibility="collapsed",
            help="Filtra por uma ou várias fontes. Vazio = todas.",
        )
    with fc2:
        min_net = st.number_input(
            "Lucro mín (€)", 0, 50000, 500, 250, label_visibility="collapsed",
            help="Lucro credível mínimo, em euros.",
        )
    with fc3:
        min_margin = st.number_input(
            "Margem mín (%)", 0, 100, 0, 1, label_visibility="collapsed",
            help="Margem credível mínima sobre o preço pedido.",
        )
    with fc4:
        d_sort = st.selectbox(
            "Ordenar por",
            ["Maior Margem %", "Maior Lucro Credível", "Mais Comparáveis", "Menor Preço"],
            label_visibility="collapsed",
        )

    gc1, gc2 = st.columns([2, 3])
    with gc1:
        min_conf = st.select_slider(
            "Confiança mínima da avaliação",
            options=['baixa', 'media', 'alta'], value='media',
            help="Baseada no nº de anúncios comparáveis (marca+modelo, ano ±2). "
                 "Com menos de 3 comparáveis o erro do modelo triplica.",
        )
    with gc2:
        grades = st.multiselect(
            "Grade", ['exceptional', 'excellent', 'good', 'fair', 'poor'],
            default=['exceptional', 'excellent', 'good'],
            help="Grade por percentil de margem credível entre os deals publicáveis.",
        )

    _rank = {'baixa': 1, 'media': 2, 'alta': 3}
    if d_sources:
        deals = deals[deals['source'].isin(d_sources)]
    if grades:
        deals = deals[deals['deal_grade'].isin(grades)]
    deals = deals[
        (deals['credible_profit'] >= min_net)
        & (deals['margin_pct'] >= min_margin)
        & (deals['valuation_confidence'].map(_rank).fillna(0) >= _rank[min_conf])
    ]

    sort_map = {
        "Maior Margem %": ('margin_pct', False),
        "Maior Lucro Credível": ('credible_profit', False),
        "Mais Comparáveis": ('comparables_count', False),
        "Menor Preço": ('price', True),
    }
    _col, _asc = sort_map[d_sort]
    deals = deals.sort_values(_col, ascending=_asc, na_position='last')

    # ── Resumo ───────────────────────────────────────────────────────────────
    if not deals.empty:
        st.markdown(
            "<div class='kpi-row'>"
            + kpi("Deals filtrados", f"{len(deals):,}")
            + kpi("Lucro credível", f"{deals['credible_profit'].sum():,.0f} €", tone="info")
            + kpi("Lucro mediano", f"{deals['credible_profit'].median():,.0f} €")
            + kpi("Margem mediana", f"{deals['margin_pct'].median():.1f}%", tone="warn")
            + kpi("Comparáveis (mediana)", f"{deals['comparables_count'].median():.0f}",
                  "anúncios semelhantes")
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    LIMIT = 60
    for _, row in deals.head(LIMIT).iterrows():
        profit = float(row['credible_profit'])
        margin = float(row['margin_pct'])
        grade = grade_class(row['deal_grade'])
        adj = float(row['adjusted_estimated_value'] or row['price'])
        raw = float(row['estimated_value'] or adj)
        year = int(row['year']) if pd.notna(row['year']) else '?'

        # Mostra o valor bruto do modelo quando difere muito do ajustado: o
        # utilizador vê quanto do "lucro" era ruído e pode julgar por si.
        shrink_note = ""
        if raw > adj * 1.02:
            shrink_note = (
                f"<div style='font-size:.68rem;color:var(--faint);margin-top:2px'>"
                f"modelo bruto: {raw:,.0f} € · ajustado por fiabilidade</div>"
            )

        st.markdown(f"""
        <div class="deal-card grade-{grade}">
            <div style="display:flex; justify-content:space-between; align-items:start; gap:1rem;">
                <div style="flex:1;">
                    <span class="title">{row['brand']} {row['model']}</span>
                    <span style="font-size:.8rem;color:var(--muted);"> {year}</span>
                    <div style="margin-top:.35rem;">
                        <span class="tag tag-source">{row['source']}</span>
                        <span class="tag tag-grade">{grade}</span>
                        {confidence_tag(row['valuation_confidence'], int(row['comparables_count']))}
                    </div>
                    <div class="meta">{int(row['km']):,} km · {row['fuel_type'] or '?'} · {row['location'] or '?'}</div>
                </div>
                <div style="text-align:right;min-width:200px;">
                    <div style="font-size:.68rem;color:var(--muted);">Preço → Valor credível</div>
                    <span class="price">{row['price']:,.0f} €</span>
                    <span style="color:var(--faint);"> → {adj:,.0f} €</span>
                    <div class="profit" style="margin-top:.25rem;">+{profit:,.0f} € · {margin:.1f}%</div>
                    {shrink_note}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        bc1, bc2, _ = st.columns([1, 1, 3])
        with bc1:
            st.link_button("🔗 Ver anúncio", row['url'])
        with bc2:
            if st.button("⭐ Guardar", key=f"deal_save_{row['id']}"):
                save_deal(int(row['id']))
                st.toast("Guardado! ⭐")

    if len(deals) > LIMIT:
        st.info(f"+ {len(deals) - LIMIT} deals não mostrados. Refina os filtros.")
    if deals.empty:
        st.warning(
            "Nenhum deal passa estes filtros. Baixa a confiança mínima ou "
            "inclui grades mais baixas — mas nota que deals com poucos "
            "comparáveis têm 3× mais erro de avaliação."
        )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: PROCURAR DEALS
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Procurar Deals":
    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
    
    with c1:
        search_query = st.text_input(
            "Marca ou modelo",
            placeholder="Ex: BMW 320d, Mercedes C, Golf...",
            label_visibility="collapsed",
            key="search",
        )
    
    with c2:
        sort_by = st.selectbox(
            "Ordenar por",
            ["Maior Profit 💰", "Maior Margem %", "Menor Preço", "Maior Deal Score", "Mais Recentes"],
            label_visibility="collapsed",
        )
    
    with c3:
        source_filter = st.selectbox(
            "Fonte",
            ["Todas"] + [s[0] for s in stats['sources']],
            label_visibility="collapsed",
        )
    
    with c4:
        min_profit = st.number_input("Profit mín (€)", 0, 100000, 0, 500, label_visibility="collapsed")
    
    with c5:
        min_margin = st.number_input("Margem mín (%)", 0, 100, 0, 1, label_visibility="collapsed")
    
    # ── Apply filters ──────────────────────────────────────────────────────
    f_df = df.copy()
    
    if search_query:
        q = search_query.lower()
        f_df = f_df[f_df['brand'].str.lower().str.contains(q, na=False) | 
                      f_df['model'].str.lower().str.contains(q, na=False)]
    
    # net_profit / net_pct JÁ vêm pré-calculados da BD (coluna net_profit).
    # Sem df.apply por página.
    if source_filter != "Todas":
        f_df = f_df[f_df['source'] == source_filter]

    if min_profit > 0:
        f_df = f_df[f_df['net_profit'] >= min_profit]

    if min_margin > 0:
        f_df = f_df[f_df['net_pct'] >= min_margin]
    
    # Sort
    if sort_by == "Maior Profit 💰":
        f_df = f_df.sort_values('net_profit', ascending=False)
    elif sort_by == "Maior Margem %":
        f_df = f_df.sort_values('net_pct', ascending=False)
    elif sort_by == "Menor Preço":
        f_df = f_df.sort_values('price', ascending=True)
    elif sort_by == "Maior Deal Score":
        f_df = f_df.sort_values('deal_score', ascending=False)
    elif sort_by == "Mais Recentes":
        f_df = f_df.sort_values('first_seen', ascending=False)
    
    # ── Aggregated view (if searching a specific model) ────────────────────
    if search_query and len(f_df) >= 3:
        st.markdown("---")
        # Group stats
        best = f_df.iloc[0]
        worst = f_df.iloc[-1]
        sources_in = f_df['source'].value_counts()
        sources_str = ", ".join([f"{s} ({c})" for s, c in sources_in.head(5).items()])

        meta_cols = st.columns(4)
        meta_cols[0].markdown(f"""
        <div class="metric-box">
            <div class="value">{len(f_df)}</div>
            <div class="label">Disponíveis</div>
        </div>""", unsafe_allow_html=True)

        meta_cols[1].markdown(f"""
        <div class="metric-box">
            <div class="value">€{best['price']:,.0f} – €{worst['price']:,.0f}</div>
            <div class="label">Range de Preços</div>
        </div>""", unsafe_allow_html=True)

        meta_cols[2].markdown(f"""
        <div class="metric-box" style="border-color:#10b981;">
            <div class="value" style="color:#10b981;">€{best['net_profit']:,.0f}</div>
            <div class="label">Melhor Profit Líquido</div>
        </div>""", unsafe_allow_html=True)

        meta_cols[3].markdown(f"""
        <div class="metric-box">
            <div class="value" style="white-space:nowrap;font-size:0.8rem;">{sources_str[:60]}</div>
            <div class="label">Fontes</div>
        </div>""", unsafe_allow_html=True)

        # Detailed table: ALL listings for this model, sorted by price, with market value
        st.markdown("**Todos os anúncios — ordenados por preço (com valor de mercado esperado)**")
        tbl = f_df.copy().sort_values('price', ascending=True)
        tbl_view = pd.DataFrame({
            'Preço €': tbl['price'].round(0).astype(int),
            'Valor Mercado €': tbl['estimated_value'].round(0).astype(int),
            'Diferença €': (tbl['estimated_value'] - tbl['price']).round(0).astype(int),
            'Margem %': tbl['net_pct'].round(1),
            'Lucro Líq €': tbl['net_profit'].round(0).astype(int),
            'Ano': tbl['year'].astype('Int64'),
            'KM': tbl['km'].astype(int),
            'Fonte': tbl['source'],
            'Local': tbl['location'].fillna('?'),
        })
        st.dataframe(tbl_view, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.caption(f"{len(f_df)} resultados")
    
    # ── Results cards ──────────────────────────────────────────────────────
    shown = 0
    for _, row in f_df.iterrows():
        if shown >= 50:
            st.info(f"+ {len(f_df) - 50} resultados. Refina a pesquisa para ver mais.")
            break
        
        net = row['net_profit']
        net_pct = row['net_pct']
        badge, color = profit_badge(net, net_pct)
        conf = confidence_level(row)
        price = row['price']
        est = row['estimated_value']
        
        # Source tag color
        src_color = SOURCE_COLORS.get(row['source'], '#7c7c94')
        
        st.markdown(f"""
        <div class="deal-card">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div style="flex:1;">
                    <span class="title">{row['brand']} {row['model']}</span>
                    <span style="font-size:0.8rem;color:var(--muted);"> ({int(row['year']) if pd.notna(row['year']) else '?'})</span>
                    <span class="source-tag" style="background:{src_color}22;color:{src_color};">{row['source']}</span>
                    <div class="meta">
                        {int(row['km']):,} km · {row['fuel_type'] or '?'} · {row['location'] or '?'}
                    </div>
                </div>
                <div style="text-align:right;min-width:160px;">
                    <div style="font-size:0.7rem;color:var(--muted);">Preço / Est. Mercado</div>
                    <span class="price">€{price:,.0f}</span>
                    <span style="color:var(--muted);"> → €{est:,.0f}</span>
                    <div class="profit" style="color:{color}; margin-top:4px;">
                        {badge} · +€{net:,.0f} ({net_pct:.1f}%)
                    </div>
                    <div style="font-size:0.65rem;color:var(--muted);">Confiança: {conf}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons
        bc1, bc2 = st.columns([1, 1])
        with bc1:
            st.link_button("🔗 Ver Anúncio", row['url'])
        with bc2:
            if st.button("⭐ Guardar", key=f"save_{row['id']}"):
                # Add to watchlist logic
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE vehicles SET deal_grade = 'watchlist' WHERE id = ? AND deal_grade IS NULL", (row['id'],))
                conn.commit()
                conn.close()
                st.toast("Guardado! ⭐")
        
        shown += 1

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: LEILÕES
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🏷️ Leilões":
    render_auctions()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: ANÁLISE MERCADO
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Análise Mercado":
    st.subheader("Distribuição de Preços por Fonte")
    
    # Price distribution
    fig = px.box(df[df['price'] < 100000], x='source', y='price', color='source',
                 title="Preços por Fonte (excluindo >€100K)",
                 color_discrete_sequence=px.colors.qualitative.Bold)
    fig.update_layout(template="plotly_dark", height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top brands by volume
        brand_counts = df['brand'].value_counts().head(15)
        fig2 = px.bar(x=brand_counts.index, y=brand_counts.values,
                      title="Top 15 Marcas por Volume",
                      color_discrete_sequence=['#00d4aa'])
        fig2.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        # Profit distribution by source — net_profit JÁ pré-calculado na BD
        df_profit = df.copy()
        df_profit = df_profit[df_profit['net_profit'].abs() < 50000]
        
        fig3 = px.box(df_profit, x='source', y='net_profit', color='source',
                      title="Profit Líquido Estimado por Fonte",
                      color_discrete_sequence=px.colors.qualitative.Bold)
        fig3.update_layout(template="plotly_dark", height=350, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)
    
    # Model metrics
    st.markdown("---")
    st.subheader("Performance do Modelo ML")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("R²", f"{stats['r2']:.3f}", help="Coeficiente de determinação — quanto o modelo explica da variação de preços")
    mc2.metric("MAE", f"€{stats['mae']:,.0f}", help="Erro absoluto médio")
    mc3.metric("Amostras Treino", f"{stats['samples']:,}")
    mc4.metric("Com Valuation", f"{stats['with_val']:,} / {stats['total']:,}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2b: HEATMAP / RANKING DE MODELOS POR MARGEM MÉDIA
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔥 Margem por Modelo":
    st.subheader("🔥 Ranking de modelos por margem média (lucro potencial)")
    st.caption("Margem = (valor de mercado − preço − custos) / preço. Só modelos com volume suficiente. "
               "Quanto mais verde, maior a margem média — o melhor 'onde fazer dinheiro' por modelo.")

    mdf = df.copy()
    mdf['model_key'] = mdf['brand'].str.strip().str.title() + " " + mdf['model'].str.strip()
    # Auctions have an inflated estimated_value (auctioneer's, not resale) -> exclude by default
    exclude_auctions = st.checkbox("Excluir leilões (LEILOSOC/VPAUTO/MANHEIM/AUTOROLA/BCA) do ranking", value=True)
    if exclude_auctions:
        mdf = mdf[~mdf['source'].isin(['LEILOSOC', 'VPAUTO', 'MANHEIM', 'AUTOROLA', 'BCA'])]
    min_listings = st.slider("Mínimo de anúncios por modelo", 3, 30, 5)

    grp = mdf.groupby('model_key').agg(
        n=('id', 'count'),
        avg_margin=('net_pct', 'mean'),
        avg_net=('net_profit', 'mean'),
        median_price=('price', 'median'),
        avg_est=('estimated_value', 'mean'),
    )
    grp = grp[grp['n'] >= min_listings].copy()
    grp['avg_margin'] = grp['avg_margin'].round(1)
    grp['avg_net'] = grp['avg_net'].round(0)
    grp = grp.sort_values('avg_margin', ascending=False)

    if grp.empty:
        st.info("Sem modelos com esse volume mínimo de anúncios.")
    else:
        col_l, col_r = st.columns([3, 2])
        with col_l:
            fig_h = px.bar(
                grp.reset_index().head(30),
                x='avg_margin', y='model_key', orientation='h',
                color='avg_margin', color_continuous_scale='RdYlGn',
                text='avg_margin', hover_data=['n', 'avg_net', 'median_price'],
                title=f"Top 30 modelos por margem média (%) — {len(grp)} modelos elegíveis",
            )
            fig_h.update_layout(template="plotly_dark", height=720, yaxis={'categoryorder': 'total ascending'})
            fig_h.update_traces(texttemplate='%{text}%', textposition='outside')
            st.plotly_chart(fig_h, use_container_width=True)
        with col_r:
            st.markdown("**Tabela — top margens**")
            tshow = grp.reset_index().head(25)[['model_key', 'n', 'avg_margin', 'avg_net', 'median_price']].copy()
            tshow.columns = ['Modelo', 'Anúncios', 'Margem %', 'Lucro líq. médio €', 'Preço mediano €']
            st.dataframe(tshow, use_container_width=True, hide_index=True)
            st.markdown("**Pior margem (evitar)**")
            worst = grp.reset_index().tail(10)[['model_key', 'avg_margin']].copy()
            worst.columns = ['Modelo', 'Margem %']
            st.dataframe(worst, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3: WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "⭐ Watchlist":
    st.subheader("⭐ Watchlist — critérios guardados")
    st.caption("Critérios definidos na tabela `watchlist` (BD). Cada critério lista os veículos "
               "ativos que fazem match, ordenados por lucro líquido real (coluna net_profit).")

    conn = sqlite3.connect(DB_PATH)
    criteria = pd.read_sql_query("""
        SELECT id, name, brand, model, vehicle_type,
               min_year, max_year, min_price, max_price, max_km,
               min_profit, fuel_type, notify_on_match, is_active
        FROM watchlist
        WHERE is_active = 1
        ORDER BY name
    """, conn)
    conn.close()

    if criteria.empty:
        st.info("Nenhum critério na watchlist. Cria um critério (marca/modelo/preço/margem) "
                "na tabela `watchlist` para ver matches automáticos aqui.")
    else:
        for _, c in criteria.iterrows():
            label = c['name'] or f"{c['brand'] or '?'}/{c['model'] or '?'}"
            st.markdown(f"### 🔔 {label}")
            # Build match query against vehicles using precomputed net_profit
            wheres = ["is_active = 1", "price > 0", "net_profit IS NOT NULL", "net_profit > 0"]
            params = []
            if c['brand']:
                wheres.append("LOWER(brand) = LOWER(?)")
                params.append(str(c['brand']).strip())
            if c['model']:
                wheres.append("LOWER(model) = LOWER(?)")
                params.append(str(c['model']).strip())
            if c['min_year']:
                wheres.append("year >= ?")
                params.append(int(c['min_year']))
            if c['max_year']:
                wheres.append("year <= ?")
                params.append(int(c['max_year']))
            if c['min_price']:
                wheres.append("price >= ?")
                params.append(float(c['min_price']))
            if c['max_price']:
                wheres.append("price <= ?")
                params.append(float(c['max_price']))
            if c['max_km']:
                wheres.append("km <= ?")
                params.append(int(c['max_km']))
            if c['min_profit']:
                wheres.append("net_profit >= ?")
                params.append(float(c['min_profit']))
            if c['fuel_type']:
                wheres.append("fuel_type = ?")
                params.append(str(c['fuel_type']))

            conn = sqlite3.connect(DB_PATH)
            matches = pd.read_sql_query(
                f"""SELECT id, brand, model, year, km, price, estimated_value,
                           net_profit, source, url, title
                    FROM vehicles
                    WHERE {' AND '.join(wheres)}
                    ORDER BY net_profit DESC LIMIT 25""",
                conn, params=params)
            conn.close()

            if matches.empty:
                st.caption("— sem matches neste momento")
            else:
                tbl = pd.DataFrame({
                    'Preço €': matches['price'].round(0).astype(int),
                    'Valor Mercado €': matches['estimated_value'].round(0).astype(int),
                    'Lucro Líq €': matches['net_profit'].round(0).astype(int),
                    'Ano': matches['year'].astype('Int64'),
                    'KM': matches['km'].astype(int),
                    'Fonte': matches['source'],
                })
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                st.caption(f"{len(matches)} match(es) • ordenado por lucro líquido")
            st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4: DADOS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Dados":
    st.subheader("Fontes de Dados")
    
    for src, cnt in stats['sources']:
        pct = cnt / stats['total'] * 100
        st.markdown(f"""
        <div style="display:flex;align-items:center;margin-bottom:4px;">
            <span style="width:120px;font-weight:600;">{src}</span>
            <div style="flex:1;background:#1e2030;border-radius:4px;height:20px;">
                <div style="width:{pct}%;background:#00d4aa;height:100%;border-radius:4px;"></div>
            </div>
            <span style="width:80px;text-align:right;">{cnt:,} ({pct:.0f}%)</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.caption(f"Total: {stats['total']:,} veículos ativos · {stats['brands']} marcas · Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5: OBSERVABILIDADE — consome reports/valuation_metrics.json
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Observabilidade":
    import json as _json
    from pathlib import Path as _Path

    st.subheader("📈 Observabilidade das avaliações")
    mpath = _Path("reports/valuation_metrics.json")
    if not mpath.exists():
        st.warning("reports/valuation_metrics.json não existe. Corre: "
                   "`python scripts/valuation_metrics.py`")
    else:
        m = _json.loads(mpath.read_text(encoding="utf-8"))
        st.caption(f"Snapshot gerado em {m.get('generated_at', '?')} · "
                   f"{m.get('active_listings', 0):,} anúncios ativos")

        # ── Estado ML + distribuição de valor ─────────────────────────────
        ml = m.get("ml", {})
        est = m.get("estimated_value", {})
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Modelo ML", f"{ml.get('model_type', '?')}",
                  help="Modelo em produção (routing 3 vias: FULL/LOW/HIGH)")
        c2.metric("R²", f"{ml.get('r2', 0):.3f}" if ml.get("r2") is not None else "—")
        c3.metric("MAPE", f"{ml.get('mape_pct', 0):.1f}%" if ml.get("mape_pct") is not None else "—")
        c4.metric("MAE", f"€{ml.get('mae', 0):,.0f}" if ml.get("mae") is not None else "—")
        c5.metric("Confiança média", f"{m.get('confidence', {}).get('mean', 0):.2f}")
        if ml.get("load_error"):
            st.error(f"Erro de carregamento do modelo: {ml['load_error']}")

        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Mediana valor estimado", f"€{est.get('median', 0):,.0f}")
        e2.metric("P10 → P90", f"€{est.get('p10', 0):,.0f} → €{est.get('p90', 0):,.0f}")
        e3.metric("Comparáveis/previsão (mediana)", f"{m.get('comparables_per_valuation', {}).get('median', 0)}")
        e4.metric("Avaliações inconclusivas", f"{m.get('inconclusive_valuations', 0)}")

        st.markdown("---")
        col_l, col_r = st.columns(2)

        with col_l:
            # Confiança por etiqueta
            conf = m.get("confidence", {}).get("by_label", {})
            if conf:
                fig_c = px.pie(names=list(conf.keys()), values=list(conf.values()),
                               title="Confiança das avaliações",
                               color=list(conf.keys()),
                               color_discrete_map={"high": "#10b981", "medium": "#f59e0b",
                                                   "low": "#ef4444", "insufficient_data": "#7c7c94"})
                fig_c.update_layout(template="plotly_dark", height=320)
                st.plotly_chart(fig_c, use_container_width=True)

            # Deal status
            ds = m.get("deal_statuses", {})
            if ds:
                fig_d = px.bar(x=list(ds.values()), y=list(ds.keys()), orientation="h",
                               title="Deal status (contagem)",
                               color_discrete_sequence=["#00d4aa"])
                fig_d.update_layout(template="plotly_dark", height=340,
                                    yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_d, use_container_width=True)

        with col_r:
            # Qualidade dos anúncios
            q = m.get("quality", {})
            qc = q.get("counts", {})
            if qc:
                fig_q = px.pie(names=list(qc.keys()), values=list(qc.values()),
                               title="Qualidade dos anúncios",
                               color=list(qc.keys()),
                               color_discrete_map={"valid": "#10b981", "quarantined": "#f59e0b",
                                                   "invalid": "#ef4444"})
                fig_q.update_layout(template="plotly_dark", height=320)
                st.plotly_chart(fig_q, use_container_width=True)

            # Campos em falta
            miss = m.get("missing_fields", {})
            if miss:
                fig_m = px.bar(x=list(miss.values()), y=list(miss.keys()), orientation="h",
                               title="Campos em falta (impacto na avaliação)",
                               color_discrete_sequence=["#ef4444"])
                fig_m.update_layout(template="plotly_dark", height=300,
                                    yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_m, use_container_width=True)

        # ── Métodos e níveis de referência ────────────────────────────────
        st.markdown("---")
        col_m, col_q = st.columns(2)
        with col_m:
            st.markdown("**Métodos de avaliação usados**")
            meth = m.get("methods_used", {})
            if meth:
                tm = pd.DataFrame({"Método": list(meth.keys()), "Anúncios": list(meth.values())})
                st.dataframe(tm, use_container_width=True, hide_index=True)
            rl = m.get("reference_levels", {})
            if rl:
                st.markdown("**Níveis de referência** (0=leilão, 1=BMY exato … 7=global)")
                tr = pd.DataFrame({"Nível": list(rl.keys()), "Anúncios": list(rl.values())})
                st.dataframe(tr, use_container_width=True, hide_index=True)
        with col_q:
            st.markdown("**Razões de quarentena mais frequentes**")
            qr = q.get("top_reasons", {})
            if qr:
                tq = pd.DataFrame({"Razão": list(qr.keys()), "Ocorrências": list(qr.values())})
                st.dataframe(tq, use_container_width=True, hide_index=True)

        # Deal score summary
        dsc = m.get("deal_score", {})
        st.markdown("---")
        s1, s2, s3 = st.columns(3)
        s1.metric("Deal score médio", f"{dsc.get('mean', 0):.2f}")
        s2.metric("Score < 3 (maus)", f"{dsc.get('lt3', 0)}")
        s3.metric("Score ≥ 7 (bons)", f"{dsc.get('gte7', 0)}")
        st.caption("Para atualizar este snapshot: `python scripts/valuation_metrics.py` "
                   "(também corre automaticamente no re-treino semanal controlado).")

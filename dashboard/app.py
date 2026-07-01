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
               first_seen, seller_name, horsepower, engine_size
        FROM vehicles WHERE is_active=1 AND price > 0
        ORDER BY profit_potential DESC NULLS LAST
    """, conn)
    conn.close()
    # Fill NAs
    df['profit_potential'] = df['profit_potential'].fillna(0)
    df['profit_percentage'] = df['profit_percentage'].fillna(0)
    df['deal_score'] = df['deal_score'].fillna(0)
    df['estimated_value'] = df['estimated_value'].fillna(df['price'])
    df['km'] = df['km'].fillna(0).astype(int)
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
    """Calculate realistic net profit after Portuguese taxes + repairs."""
    price = row['price'] or 0
    est = row['estimated_value'] or price
    # Taxes: 15.5% (IMT+ISV+Selo)
    taxes = price * 0.155
    # Repairs based on KM
    km = row['km'] or 0
    if km < 50000: repairs = 0
    elif km < 100000: repairs = 500
    elif km < 150000: repairs = 1000
    else: repairs = 1500
    # Transport/registration
    extra = 500
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
    """Rate confidence based on data completeness and source."""
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

def profit_badge(net_profit, net_pct):
    if net_profit > 3000 and net_pct > 8: return '🟢 EXCELENTE', '#10b981'
    if net_profit > 1000 and net_pct > 5: return '🟡 BOM', '#f59e0b'
    if net_profit > 0: return '⚪ MARGINAL', '#94a3b8'
    return '🔴 PREJUÍZO', '#ef4444'

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    :root {
        --bg: #0a0a0f; --surface: #13141f; --border: #1e2030;
        --text: #e4e4ec; --muted: #7c7c94; --accent: #00d4aa; --danger: #ef4444;
    }
    .stApp { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
    .main-header { font-size: 1.8rem; font-weight: 700; color: var(--accent); margin:0; }
    .sub-header { color: var(--muted); font-size: 0.9rem; margin-bottom: 1rem; }
    
    .deal-card {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 10px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
        transition: border-color 0.2s;
    }
    .deal-card:hover { border-color: var(--accent); }
    .deal-card .title { font-weight: 600; font-size: 0.95rem; }
    .deal-card .meta { color: var(--muted); font-size: 0.75rem; }
    .deal-card .profit { font-weight: 700; font-size: 1rem; }
    .deal-card .price { font-size: 0.9rem; }
    .deal-card .source-tag {
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
        background: #1e2030; color: var(--accent);
    }
    
    .metric-box {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 0.8rem; text-align: center;
    }
    .metric-box .value { font-size: 1.4rem; font-weight: 700; }
    .metric-box .label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }
    
    .stSelectbox [data-baseweb="select"], .stTextInput input {
        background: var(--surface) !important; border-color: var(--border) !important;
        color: var(--text) !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Load data ────────────────────────────────────────────────────────────────
df = load_all_vehicles()
stats = load_stats()

# ── Header ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 20])
with col1: st.markdown("<h1 style='font-size:2.5rem;'>💰</h1>", unsafe_allow_html=True)
with col2:
    st.markdown("<h1 class='main-header'>VER PRECOS</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p class='sub-header'>{stats['total']:,} veículos • {stats['brands']} marcas • "
        f"7 fontes • Modelo R²={stats['r2']:.2f}</p>",
        unsafe_allow_html=True,
    )

# ── NAV ──────────────────────────────────────────────────────────────────────
page = st.radio(
    "", ["🔍 Procurar Deals", "📊 Análise Mercado", "⭐ Watchlist", "📋 Dados"],
    horizontal=True, label_visibility="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: PROCURAR DEALS
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Procurar Deals":
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    
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
    
    # ── Apply filters ──────────────────────────────────────────────────────
    f_df = df.copy()
    
    if search_query:
        q = search_query.lower()
        f_df = f_df[f_df['brand'].str.lower().str.contains(q, na=False) | 
                      f_df['model'].str.lower().str.contains(q, na=False)]
    
    if source_filter != "Todas":
        f_df = f_df[f_df['source'] == source_filter]
    
    # Calculate net profits
    profits = f_df.apply(calculate_net_profit, axis=1, result_type='expand')
    f_df = pd.concat([f_df.reset_index(drop=True), profits.reset_index(drop=True)], axis=1)
    
    if min_profit > 0:
        f_df = f_df[f_df['net_profit'] >= min_profit]
    
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
        source_colors = {
            'LEILOSOC': '#f59e0b', 'AUTOPT': '#00d4aa', 'STANDVIRTUAL': '#0ea5e9',
            'OLX': '#8b5cf6', 'CUSTOJUSTO': '#ec4899',
        }
        src_color = source_colors.get(row['source'], '#7c7c94')
        
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
        # Profit distribution by source
        df_profit = df.copy()
        profits = df_profit.apply(calculate_net_profit, axis=1, result_type='expand')
        df_profit = pd.concat([df_profit.reset_index(drop=True), profits.reset_index(drop=True)], axis=1)
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
# PAGE 3: WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "⭐ Watchlist":
    st.subheader("Veículos Guardados")
    
    conn = sqlite3.connect(DB_PATH)
    watchlist = pd.read_sql_query("""
        SELECT * FROM vehicles WHERE is_active=1 AND deal_grade = 'watchlist'
        ORDER BY first_seen DESC
    """, conn)
    conn.close()
    
    if watchlist.empty:
        st.info("Nenhum veículo guardado. Usa ⭐ nos resultados de pesquisa para guardar.")
    else:
        for _, row in watchlist.iterrows():
            st.markdown(f"""
            <div class="deal-card">
                <span class="title">{row['brand']} {row['model']} ({int(row['year']) if pd.notna(row['year']) else '?'})</span>
                <span style="color:var(--muted);"> — €{row['price']:,.0f} · {int(row['km']):,} km · {row['source']}</span>
                <a href="{row['url']}" target="_blank" style="float:right;">🔗</a>
            </div>
            """, unsafe_allow_html=True)

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

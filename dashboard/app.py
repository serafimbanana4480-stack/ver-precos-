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
               net_profit
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
    for col in ['buyer_profit', 'buyer_profit_margin', 'buyer_roi', 'repair_costs', 'taxes', 'total_additional_costs', 'net_profit']:
        if col not in df.columns:
            df[col] = float('nan')
    # net_profit é agora pré-calculado (scripts/backfill_profit.py).
    # Fallback: calcular só para as linhas que ainda não têm (preserva performance).
    missing_net = df['net_profit'].isna()
    if missing_net.any():
        _fb = df[missing_net].apply(calculate_net_profit, axis=1, result_type='expand')
        df.loc[missing_net, 'net_profit'] = _fb['net_profit'].values
        df.loc[missing_net, 'net_pct'] = _fb['net_pct'].values
    else:
        # net_pct derivado da margem líquida
        df['net_pct'] = (df['net_profit'] / df['price'] * 100).where(df['price'] > 0, 0)
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
    est = row['estimated_value'] or price
    # Prefer the system's own realistic profit calc (real cost model) when present
    if pd.notna(row.get('buyer_profit')):
        net = float(row['buyer_profit'])
        net_pct = float(row['buyer_profit_margin']) if pd.notna(row.get('buyer_profit_margin')) else (net / price * 100 if price > 0 else 0)
        gross = max(0, est - price)
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
    "", ["🔍 Procurar Deals", "💸 Melhores Deals", "🏷️ Leilões", "🔥 Margem por Modelo", "📊 Análise Mercado", "⭐ Watchlist", "📋 Dados"],
    horizontal=True, label_visibility="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1b: MELHORES DEALS / ONDE GANHAR DINHEIRO
# ═══════════════════════════════════════════════════════════════════════════════
if page == "💸 Melhores Deals":
    st.subheader("💸 Onde fazer dinheiro — ranking por lucro líquido real")
    st.caption("Lucro líquido = valor de mercado − preço − impostos − reparações − custos. "
               "Usa o cálculo real do sistema (buyer_profit) quando disponível; senão, estimativa 15.5% impostos.")

    # Compute net profit — JÁ pré-calculado na BD (coluna net_profit) pelo
    # scripts/backfill_profit.py. Evita df.apply por página (lento).
    deals = df.copy()
    deals['net_profit'] = deals['net_profit'].astype(float)
    deals['net_pct'] = (deals['net_profit'] / deals['price'] * 100).where(deals['price'] > 0, 0)
    deals = deals[deals['net_profit'] > 0].copy()

    # Filters
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        d_sources = st.multiselect(
            "Fonte(s)", sorted(deals['source'].unique().tolist()),
            default=[], label_visibility="collapsed",
            help="Filtra por uma ou várias fontes. Vazio = todas.",
        )
    with fc2:
        min_net = st.number_input("Lucro líquido mín (€)", 0, 50000, 500, 250, label_visibility="collapsed")
    with fc3:
        min_margin = st.number_input("Margem mín (%)", 0, 100, 0, 1, label_visibility="collapsed")
    with fc4:
        d_sort = st.selectbox("Ordenar por",
                              ["Maior Lucro Líquido", "Maior Margem %", "Melhor ROI", "Menor Preço"],
                              label_visibility="collapsed")

    # Auctions (LEILOSOC) carry an inflated estimated_value from the auctioneer,
    # NOT a real resale value -> exclude by default to avoid misleading "deals".
    exclude_auctions = st.checkbox("Excluir leilões (LEILOSOC/VPAUTO/MANHEIM/AUTOROLA/BCA) — valor de mercado do leiloeiro não é revenda real", value=True)

    if d_sources:
        deals = deals[deals['source'].isin(d_sources)]
    if exclude_auctions:
        deals = deals[~deals['source'].isin(['LEILOSOC', 'VPAUTO', 'MANHEIM', 'AUTOROLA', 'BCA'])]
    deals = deals[(deals['net_profit'] >= min_net) & (deals['net_pct'] >= min_margin)]

    # Data quality caveat
    real_n = int(deals['buyer_profit'].notna().sum())
    if real_n < len(deals):
        st.info(f"⚠️ {len(deals) - real_n} deals usam estimativa heurística (15.5% impostos + reparações); "
                f"{real_n} usam o cálculo real do sistema. Confirma sempre o valor de revenda real antes de comprar.")
    elif exclude_auctions and d_source == "Todas":
        st.success(f"✅ A mostrar {len(deals)} deals de fontes de revenda (sem leilões). "
                   f"{real_n} com cálculo de lucro real do sistema.")

    if d_sort == "Maior Lucro Líquido":
        deals = deals.sort_values('net_profit', ascending=False)
    elif d_sort == "Maior Margem %":
        deals = deals.sort_values('net_pct', ascending=False)
    elif d_sort == "Melhor ROI":
        deals = deals.sort_values('buyer_roi', ascending=False, na_position='last')
    else:
        deals = deals.sort_values('price', ascending=True)

    # Summary metrics
    if not deals.empty:
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("Deals rentáveis", f"{len(deals):,}")
        sm2.metric("Lucro líquido total", f"€{deals['net_profit'].sum():,.0f}")
        sm3.metric("Lucro médio", f"€{deals['net_profit'].mean():,.0f}")
        sm4.metric("Margem média", f"{deals['net_pct'].mean():.1f}%")

    st.markdown("---")
    st.caption(f"{len(deals)} deals rentáveis")
    shown = 0
    for _, row in deals.iterrows():
        if shown >= 60:
            st.info(f"+ {len(deals) - 60} deals. Refina os filtros.")
            break
        net = row['net_profit']; net_pct = row['net_pct']
        badge, color = profit_badge(net, net_pct)
        est = row['estimated_value']
        src_color = SOURCE_COLORS.get(row['source'], '#7c7c94')
        rec = row.get('profit_recommendation') if pd.notna(row.get('profit_recommendation')) else ''
        conf = confidence_level(row)
        st.markdown(f"""
        <div class="deal-card">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div style="flex:1;">
                    <span class="title">{row['brand']} {row['model']}</span>
                    <span style="font-size:0.8rem;color:var(--muted);"> ({int(row['year']) if pd.notna(row['year']) else '?'})</span>
                    <span class="source-tag" style="background:{src_color}22;color:{src_color};">{row['source']}</span>
                    <div class="meta">{int(row['km']):,} km · {row['fuel_type'] or '?'} · {row['location'] or '?'}</div>
                    {'<div class="meta" style="color:#10b981;">📌 ' + str(rec) + '</div>' if rec else ''}
                </div>
                <div style="text-align:right;min-width:170px;">
                    <div style="font-size:0.7rem;color:var(--muted);">Preço → Valor Mercado</div>
                    <span class="price">€{row['price']:,.0f}</span>
                    <span style="color:var(--muted);"> → €{est:,.0f}</span>
                    <div class="profit" style="color:{color}; margin-top:4px;">{badge} · +€{net:,.0f} ({net_pct:.1f}%)</div>
                    <div style="font-size:0.65rem;color:var(--muted);">Confiança: {conf}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        bc1, bc2 = st.columns([1, 1])
        with bc1:
            st.link_button("🔗 Ver Anúncio", row['url'])
        with bc2:
            if st.button("⭐ Guardar", key=f"deal_save_{row['id']}"):
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE vehicles SET deal_grade = 'watchlist' WHERE id = ? AND deal_grade IS NULL", (row['id'],))
                conn.commit(); conn.close()
                st.toast("Guardado! ⭐")
        shown += 1
    if deals.empty:
        st.info("Nenhum deal rentável com os filtros atuais.")

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

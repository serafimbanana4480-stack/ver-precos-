#!/usr/bin/env python3
"""
Recalculate profit potential and recommendations for all vehicles.
Uses existing deal_score/deal_grade from DB (calculated by pricing v6)
and computes clean profit = estimated_value - price.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3


def get_recommendation(deal_grade: str) -> str:
    """Generate recommendation based on deal grade."""
    mapping = {
        'exceptional': 'EXCELLENT DEAL - Strong buy recommendation',
        'excellent': 'GOOD DEAL - Consider purchasing',
        'good': 'FAIR DEAL - Worth considering',
        'fair': 'NEUTRAL - Negotiate if possible',
        'poor': 'OVERPRICED - Avoid or inspect thoroughly',
    }
    return mapping.get(deal_grade, 'NEUTRAL - Monitor for better opportunities')


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT id, price, estimated_value, deal_score, deal_grade
        FROM vehicles WHERE is_active = 1
    """)
    vehicles = c.fetchall()
    
    print(f"Recalculating profits for {len(vehicles)} vehicles...")
    
    updated = 0
    grade_counts = {}
    
    for v in vehicles:
        vid, price, est_val, deal_score, deal_grade = v
        
        if not price or price <= 0:
            continue
        
        # Clean profit = market estimate - asking price
        profit = (est_val or price) - price
        profit_pct = (profit / price * 100) if price else 0
        
        # Use existing deal_grade; if missing, derive from deal_score
        if not deal_grade and deal_score is not None:
            if deal_score >= 8.5:
                deal_grade = 'exceptional'
            elif deal_score >= 7.5:
                deal_grade = 'excellent'
            elif deal_score >= 6.0:
                deal_grade = 'good'
            elif deal_score >= 4.5:
                deal_grade = 'fair'
            else:
                deal_grade = 'poor'
        elif not deal_grade:
            deal_grade = 'fair'
        
        recommendation = get_recommendation(deal_grade)
        
        c.execute("""
            UPDATE vehicles
            SET profit_potential = ?,
                profit_percentage = ?,
                deal_grade = ?,
                price_discount_percentage = ?,
                buyer_profit = ?,
                buyer_profit_margin = ?,
                profit_recommendation = ?
            WHERE id = ?
        """, (
            round(profit, 2),
            round(profit_pct, 2),
            deal_grade,
            round(profit_pct, 2),
            round(profit, 2),
            round(profit_pct, 2),
            recommendation,
            vid
        ))
        
        grade_counts[deal_grade] = grade_counts.get(deal_grade, 0) + 1
        updated += 1
    
    conn.commit()
    
    print(f"\nUpdated {updated} vehicles")
    print("Grade distribution:")
    for grade, count in sorted(grade_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {grade}: {count}")
    
    # Summary stats
    c.execute("""
        SELECT AVG(deal_score), AVG(profit_potential), COUNT(*) FROM vehicles WHERE is_active = 1
    """)
    avg_score, avg_profit, total = c.fetchone()
    print(f"\nAvg deal score: {avg_score:.2f}")
    print(f"Avg profit potential: {avg_profit:.0f} EUR")
    
    # Show top opportunities
    print("\n=== TOP 5 OPPORTUNITIES ===")
    c.execute("""
        SELECT brand, model, price, estimated_value, deal_score, deal_grade, profit_potential, profit_recommendation
        FROM vehicles WHERE is_active = 1
        ORDER BY profit_potential DESC LIMIT 5
    """)
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]} | Price={row[2]:.0f} | Est={row[3]:.0f} | Score={row[4]:.1f} | {row[5]} | Profit={row[6]:.0f} EUR")
        print(f"    → {row[7]}")
    
    # Show worst deals
    print("\n=== WORST 5 DEALS ===")
    c.execute("""
        SELECT brand, model, price, estimated_value, deal_score, deal_grade, profit_potential, profit_recommendation
        FROM vehicles WHERE is_active = 1
        ORDER BY profit_potential ASC LIMIT 5
    """)
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]} | Price={row[2]:.0f} | Est={row[3]:.0f} | Score={row[4]:.1f} | {row[5]} | Profit={row[6]:.0f} EUR")
        print(f"    → {row[7]}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()

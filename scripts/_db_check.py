1: """Quick DB inspection script"""
2: import sqlite3
3: c = sqlite3.connect('autodeal.db')
4: tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
5: print("Tables:", tables)
6: for t in tables:
7:     count = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
8:     print(f"  {t}: {count} rows")
9: if 'listings' in tables:
10:     print("\n--- listings schema ---")
11:     cols = c.execute("PRAGMA table_info(listings)").fetchall()
12:     for col in cols:
13:         print(f"  {col}")
14:     print(f"\n--- sample listings (3) ---")
15:     rows = c.execute("SELECT * FROM listings LIMIT 3").fetchall()
16:     print(f"  Columns: {[d[0] for d in c.description]}")
17:     for r in rows:
18:         print(f"  {r[:8]}...")

"""Test database connection and tables"""
import sqlite3

# Connect to database
conn = sqlite3.connect('autodeal.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Tables in database:")
for table in tables:
    print(f"  - {table[0]}")

# Check if expected tables exist
expected_tables = ['vehicles', 'price_history', 'watchlist', 'ai_reviews', 'scraping_logs']
found_tables = [t[0] for t in tables]

print("\nExpected tables check:")
for table in expected_tables:
    status = "[OK]" if table in found_tables else "[MISSING]"
    print(f"  {status} {table}")

conn.close()

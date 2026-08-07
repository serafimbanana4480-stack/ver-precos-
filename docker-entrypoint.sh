#!/bin/bash
set -e

# AutoDeal IA Hunter — Docker Entrypoint
# Handles database initialization, migrations, and service startup

echo "=========================================="
echo "AutoDeal IA Hunter — Starting up"
echo "=========================================="

# Wait for database
if [ -n "$DATABASE_URL" ]; then
    echo "⏳ Waiting for database..."
    python -c "
import time
from sqlalchemy import create_engine, text
import os

url = os.getenv('DATABASE_URL', 'sqlite:///data/autodeal.db')
for i in range(30):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('✅ Database is ready')
        break
    except Exception as e:
        print(f'  Attempt {i+1}/30: {e}')
        time.sleep(2)
else:
    print('⚠️  Database not available, continuing anyway...')
"
fi

# Initialize database if SQLite
if echo "$DATABASE_URL" | grep -q "sqlite"; then
    echo "📦 Initializing SQLite database..."
    python -c "
from database.db import init_db
try:
    init_db()
    print('✅ Database initialized')
except Exception as e:
    print(f'⚠️  Database init warning: {e}')
"
fi

# Run database migrations
if [ -f "alembic.ini" ]; then
    echo "🔄 Running database migrations..."
    alembic upgrade head || echo "⚠️  Migration skipped"
fi

# Execute the main command
echo "🚀 Starting service: $*"
exec "$@"

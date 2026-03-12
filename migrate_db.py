"""Add is_active and last_login columns to users table."""
import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1')
    print('Added is_active column')
except Exception as e:
    print(f'is_active: {e}')

try:
    cursor.execute('ALTER TABLE users ADD COLUMN last_login DATETIME')
    print('Added last_login column')
except Exception as e:
    print(f'last_login: {e}')

# Set all existing users as active
cursor.execute('UPDATE users SET is_active = 1 WHERE is_active IS NULL')
conn.commit()
conn.close()
print('Migration complete!')

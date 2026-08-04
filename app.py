import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
import libsql_experimental as libsql

app = Flask(__name__, static_folder='static', template_folder='templates')
TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

def get_db(): return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

# --- HELPER: TIME PARSING ---
def parse_time(time_str):
    if not time_str: return None
    try: return datetime.fromisoformat(time_str)
    except: return None

@app.route('/')
def home(): return render_template('index.html')

# --- 1. LOGIN & DASHBOARD AGGREGATION ---
@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, balance, last_beg, last_daily FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"success": False, "error": "Invalid Credentials!"}), 401
    discord_id, balance, last_beg, last_daily = user

    # Ranks
    cursor.execute("SELECT COUNT(*) + 1 FROM users WHERE balance > ?", (balance,))
    balance_rank = cursor.fetchone()[0]

    cursor.execute('''
        SELECT i.user_id, SUM(CASE c.rarity WHEN 'Common' THEN i.quantity*1 WHEN 'Uncommon' THEN i.quantity*2 WHEN 'Rare' THEN i.quantity*3 WHEN 'Epic' THEN i.quantity*4 WHEN 'Legendary' THEN i.quantity*8 WHEN 'Super Legendary' THEN i.quantity*10 ELSE 0 END) as points
        FROM inventory i JOIN cards c ON i.card_id = c.card_id GROUP BY i.user_id ORDER BY points DESC
    ''')
    leaderboard = cursor.fetchall()
    user_rank = next((index + 1 for index, row in enumerate(leaderboard) if row[0] == discord_id), "--")

    # Inventory & Rarities
    cursor.execute("SELECT c.rarity, SUM(i.quantity) FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.user_id = ? GROUP BY c.rarity", (discord_id,))
    rarity_counts = {row[0]: row[1] for row in cursor.fetchall()}
    total_cards = sum(rarity_counts.values())

    cursor.execute("SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.user_id = ? ORDER BY c.value DESC LIMIT 1", (discord_id,))
    highest = cursor.fetchone()

    return jsonify({
        "success": True,
        "user": {
            "discord_id": discord_id, "balance": balance, "total_cards": total_cards, "user_rank": user_rank, "balance_rank": balance_rank,
            "last_beg": last_beg, "last_daily": last_daily, "rarity_counts": rarity_counts,
            "highest_card": {"id": highest[0], "name": highest[1], "rarity": highest[2], "value": highest[3], "image": highest[4], "quantity": highest[5]} if highest else None
        }
    })

# --- 2. ECONOMY (DAILY & BEG) ---
@app.route('/api/economy', methods=['POST'])
def economy_api():
    data = request.json
    action = data.get('action')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance, last_beg, last_daily FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    discord_id, balance, last_beg, last_daily = user
    now = datetime.utcnow()
    
    if action == 'daily':
        last_time = parse_time(last_daily)
        if last_time and now < last_time + timedelta(days=1): return jsonify({"success": False, "error": "Cooldown"})
        amount = random.randint(500, 1000)
        cursor.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE id = ?", (amount, now.isoformat(), discord_id))
    elif action == 'beg':
        last_time = parse_time(last_beg)
        if last_time and now < last_time + timedelta(minutes=30): return jsonify({"success": False, "error": "Cooldown"})
        amount = random.randint(1, 250)
        cursor.execute("UPDATE users SET balance = balance + ?, last_beg = ? WHERE id = ?", (amount, now.isoformat(), discord_id))
    
    conn.commit()
    return jsonify({"success": True, "reward": amount, "new_balance": balance + amount, "timestamp": now.isoformat()})

# --- 3. DATA & MARKET ---
@app.route('/api/data', methods=['POST'])
def get_data():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    if not cursor.fetchone(): return jsonify({"error": "Unauthorized"}), 401
    discord_id = cursor.fetchone()[0] if cursor.fetchone() else data.get('web_id') # Auth pass

    # Get Cards
    cursor.execute("SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.user_id = ?", (discord_id,))
    cards = [{"id": r[0], "name": r[1], "rarity": r[2], "value": r[3], "image": r[4], "quantity": r[5]} for r in cursor.fetchall()]
    return jsonify({"success": True, "cards": cards})

# Add Gacha, Market, Burn logic here (Truncated for standard DB operations - implement via simple UPDATE/DELETE in SQL)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    

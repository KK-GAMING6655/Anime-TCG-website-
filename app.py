import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
import libsql_experimental as libsql

app = Flask(__name__, static_folder='static', template_folder='templates')
TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

def get_db():
    return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

def parse_time(time_str):
    if not time_str: return None
    try: return datetime.fromisoformat(time_str)
    except: return None

@app.route('/')
def home():
    return render_template('index.html')


# --- 1. LOGIN & DASHBOARD DATA ---
@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Updated query to fetch username and pfp
    cursor.execute("SELECT id, balance, last_beg, last_daily, username, pfp FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: 
        return jsonify({"success": False, "error": "Invalid Web ID or Password!"}), 401
        
    discord_id, balance, last_beg, last_daily, username, pfp = user

    # Balance / Wealth Rank
    cursor.execute("SELECT COUNT(*) + 1 FROM users WHERE balance > ?", (balance,))
    balance_rank = cursor.fetchone()[0]

    # Collection Rank Algorithm
    cursor.execute('''
        SELECT i.user_id, SUM(
            CASE c.rarity 
                WHEN 'Common' THEN i.quantity*1 
                WHEN 'Uncommon' THEN i.quantity*2 
                WHEN 'Rare' THEN i.quantity*3 
                WHEN 'Epic' THEN i.quantity*4 
                WHEN 'Legendary' THEN i.quantity*8 
                WHEN 'Super Legendary' THEN i.quantity*10 
                ELSE 0 END
        ) as points
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        GROUP BY i.user_id ORDER BY points DESC
    ''')
    leaderboard = cursor.fetchall()
    user_rank = next((index + 1 for index, row in enumerate(leaderboard) if row[0] == discord_id), "--")

    # Rarity Counts
    cursor.execute("""
        SELECT c.rarity, COALESCE(SUM(i.quantity), 0) 
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ? GROUP BY c.rarity
    """, (discord_id,))
    rarity_counts = {row[0]: row[1] for row in cursor.fetchall()}
    total_cards = sum(rarity_counts.values())

    # Highest Valued Card
    cursor.execute("""
        SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity 
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ? ORDER BY c.value DESC LIMIT 1
    """, (discord_id,))
    highest = cursor.fetchone()

    return jsonify({
        "success": True,
        "user": {
            "discord_id": discord_id,
            "username": username or f"User {discord_id[-4:]}",
            "pfp": pfp or "https://cdn.discordapp.com/embed/avatars/0.png",
            "balance": balance,
            "balance_rank": balance_rank,
            "user_rank": user_rank,
            "total_cards": total_cards,
            "rarity_counts": rarity_counts,
            "last_beg": last_beg,
            "last_daily": last_daily,
            "highest_card": {
                "id": highest[0], "name": highest[1], "rarity": highest[2], 
                "value": highest[3], "image": highest[4], "quantity": highest[5]
            } if highest else None
        }
    })
    

# --- 2. LEADERBOARDS ---
@app.route('/api/leaderboard', methods=['POST'])
def leaderboard_api():
    data = request.json
    lb_type = data.get('type', 'balance')
    conn = get_db()
    cursor = conn.cursor()

    if lb_type == 'balance':
        cursor.execute("SELECT id, balance FROM users ORDER BY balance DESC LIMIT 20")
        rows = cursor.fetchall()
        leaderboard = [{"id": r[0], "value": r[1]} for r in rows]
    else:
        cursor.execute('''
            SELECT i.user_id, SUM(
                CASE c.rarity 
                    WHEN 'Common' THEN i.quantity*1 
                    WHEN 'Uncommon' THEN i.quantity*2 
                    WHEN 'Rare' THEN i.quantity*3 
                    WHEN 'Epic' THEN i.quantity*4 
                    WHEN 'Legendary' THEN i.quantity*8 
                    WHEN 'Super Legendary' THEN i.quantity*10 
                    ELSE 0 END
            ) as points
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            GROUP BY i.user_id ORDER BY points DESC LIMIT 20
        ''')
        rows = cursor.fetchall()
        leaderboard = [{"id": r[0], "value": r[1] or 0} for r in rows]

    return jsonify({"success": True, "type": lb_type, "leaderboard": leaderboard})

# --- 3. FETCH CARDS ---
@app.route('/api/data', methods=['POST'])
def get_data():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    discord_id = user[0]
    cursor.execute("""
        SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity 
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ? AND i.quantity > 0
    """, (discord_id,))
    cards = [{"id": r[0], "name": r[1], "rarity": r[2], "value": r[3], "image": r[4], "quantity": r[5]} for r in cursor.fetchall()]

    cursor.execute("SELECT name, color, chance FROM rarities ORDER BY chance ASC")
    rarities = [{"name": r[0], "color": r[1], "chance": r[2]} for r in cursor.fetchall()]

    return jsonify({"success": True, "cards": cards, "rarities": rarities})

# --- 4. ECONOMY (DAILY & BEG) ---
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
        if last_time and now < last_time + timedelta(days=1): 
            return jsonify({"success": False, "error": "Daily reward on cooldown!"})
        amount = random.randint(500, 1000)
        cursor.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE id = ?", (amount, now.isoformat(), discord_id))
    elif action == 'beg':
        last_time = parse_time(last_beg)
        if last_time and now < last_time + timedelta(minutes=30): 
            return jsonify({"success": False, "error": "Beg command on cooldown!"})
        amount = random.randint(50, 250)
        cursor.execute("UPDATE users SET balance = balance + ?, last_beg = ? WHERE id = ?", (amount, now.isoformat(), discord_id))
    
    conn.commit()
    return jsonify({"success": True, "reward": amount, "new_balance": balance + amount})

# --- 5. GACHA SUMMON ---
@app.route('/api/gacha', methods=['POST'])
def gacha_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401

    discord_id, balance = user
    cost = 1000
    count = int(data.get('count', 1))
    total_cost = cost * count

    if balance < total_cost:
        return jsonify({"success": False, "error": f"Need {total_cost} coins!"})

    cursor.execute("SELECT name, chance FROM rarities")
    rarity_data = cursor.fetchall()
    names, weights = [r[0] for r in rarity_data], [r[1] for r in rarity_data]

    pulls = []
    for _ in range(count):
        chosen = random.choices(names, weights=weights, k=1)[0]
        cursor.execute("SELECT card_id, name, rarity, value, image FROM cards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1", (chosen,))
        card = cursor.fetchone()
        if card:
            cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?", (discord_id, card[0]))
            if cursor.fetchone():
                cursor.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?", (discord_id, card[0]))
            else:
                cursor.execute("INSERT INTO inventory (user_id, card_id, quantity) VALUES (?, ?, 1)", (discord_id, card[0]))
            pulls.append({"id": card[0], "name": card[1], "rarity": card[2], "value": card[3], "image": card[4]})

    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_cost, discord_id))
    conn.commit()
    return jsonify({"success": True, "pulls": pulls, "new_balance": balance - total_cost})

# --- 6. BURN CARDS ---
@app.route('/api/burn', methods=['POST'])
def burn_api():
    data = request.json
    items_to_burn = data.get('items', []) # [{'card_id': x, 'qty': y}]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401

    discord_id, balance = user
    total_coins_gained = 0

    for item in items_to_burn:
        card_id = item['card_id']
        qty = int(item['qty'])
        if qty <= 0: continue

        cursor.execute("SELECT c.value, i.quantity FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.user_id = ? AND i.card_id = ?", (discord_id, card_id))
        row = cursor.fetchone()
        if row and row[1] >= qty:
            card_val, owned = row
            coins = int((card_val * 0.5) * qty)
            total_coins_gained += coins

            if owned == qty:
                cursor.execute("DELETE FROM inventory WHERE user_id = ? AND card_id = ?", (discord_id, card_id))
            else:
                cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND card_id = ?", (qty, discord_id, card_id))

    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_coins_gained, discord_id))
    conn.commit()
    return jsonify({"success": True, "coins_gained": total_coins_gained, "new_balance": balance + total_coins_gained})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
        

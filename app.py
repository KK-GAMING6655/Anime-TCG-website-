import os
import random
from flask import Flask, request, jsonify, render_template
import libsql_experimental as libsql

app = Flask(__name__, static_folder='static', template_folder='templates')

TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

def get_db():
    return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

@app.route('/')
def home():
    return render_template('index.html')

# --- 1. LOGIN & STATS ---
@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Auth
    cursor.execute("SELECT id, balance, last_beg, last_daily FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"success": False, "error": "Invalid Credentials!"}), 401
    
    discord_id, balance, last_beg, last_daily = user

    # 1. Total Cards
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE user_id = ?", (discord_id,))
    total_cards = cursor.fetchone()[0]

    # 2. User Rank (Collection Points Algorithm from Discord Bot)
    cursor.execute('''
        SELECT i.user_id, SUM(
            CASE c.rarity
                WHEN 'Common' THEN i.quantity * 1
                WHEN 'Uncommon' THEN i.quantity * 2
                WHEN 'Rare' THEN i.quantity * 3
                WHEN 'Epic' THEN i.quantity * 4
                WHEN 'Legendary' THEN i.quantity * 8
                WHEN 'Super Legendary' THEN i.quantity * 10
                ELSE 0 END
        ) as points
        FROM inventory i JOIN cards c ON i.card_id = c.card_id
        GROUP BY i.user_id ORDER BY points DESC
    ''')
    leaderboard = cursor.fetchall()
    user_rank = next((index + 1 for index, row in enumerate(leaderboard) if row[0] == discord_id), "--")

    # 3. Highest Card
    cursor.execute("""
        SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity
        FROM inventory i JOIN cards c ON i.card_id = c.card_id
        WHERE i.user_id = ? ORDER BY c.value DESC LIMIT 1
    """, (discord_id,))
    highest = cursor.fetchone()

    return jsonify({
        "success": True,
        "user": {
            "discord_id": discord_id, "balance": balance, "total_cards": total_cards, "user_rank": user_rank,
            "highest_card": {"id": highest[0], "name": highest[1], "rarity": highest[2], "value": highest[3], "image": highest[4], "quantity": highest[5]} if highest else None
        }
    })

# --- 2. GET USER COLLECTION & RARITIES ---
@app.route('/api/data', methods=['POST'])
def get_user_data():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    discord_id = user[0]

    # Fetch User Cards
    cursor.execute("""
        SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity 
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ?
    """, (discord_id,))
    cards = [{"id": r[0], "name": r[1], "rarity": r[2], "value": r[3], "image": r[4], "quantity": r[5]} for r in cursor.fetchall()]

    # Fetch Rarities
    cursor.execute("SELECT name, color, chance FROM rarities ORDER BY chance ASC")
    rarities = [{"name": r[0], "color": r[1], "chance": r[2]} for r in cursor.fetchall()]

    return jsonify({"success": True, "cards": cards, "rarities": rarities})

# --- 3. GACHA SUMMONING ---
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
        return jsonify({"success": False, "error": f"Not enough coins! You need {total_cost}."})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    

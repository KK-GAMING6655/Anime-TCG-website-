import os
import random
import datetime
from flask import Flask, request, jsonify, render_template
import libsql_experimental as libsql

app = Flask(__name__, static_folder='static', template_folder='templates')

# Connect to Turso Cloud DB safely on server side
TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

def get_db():
    return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)

# Helper function to authenticate web user
def authenticate_user(cursor, web_id, web_pass):
    cursor.execute("SELECT id, balance, last_beg, last_daily FROM users WHERE web_id = ? AND web_password = ?", (web_id, web_pass))
    user = cursor.fetchone()
    return user

@app.route('/')
def home():
    return render_template('index.html')

# --- 1. AUTH & USER STATUS ---
@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.json
    web_id = data.get('web_id')
    web_pass = data.get('web_pass')

    conn = get_db()
    cursor = conn.cursor()
    user = authenticate_user(cursor, web_id, web_pass)

    if not user:
        return jsonify({"success": False, "error": "Invalid Web ID or Password!"}), 401

    discord_id, balance, last_beg, last_daily = user

    # Rarity breakdown
    cursor.execute("""
        SELECT c.rarity, COALESCE(SUM(i.quantity), 0) 
        FROM inventory i 
        JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ? 
        GROUP BY c.rarity
    """, (discord_id,))
    rarity_counts = dict(cursor.fetchall())

    # Total cards collected
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE user_id = ?", (discord_id,))
    total_cards = cursor.fetchone()[0] or 0

    # Ranks
    cursor.execute("SELECT COUNT(*) + 1 FROM users WHERE balance > ?", (balance,))
    balance_rank = cursor.fetchone()[0]

    # Highest Valued Card Owned
    cursor.execute("""
        SELECT c.card_id, c.name, c.rarity, c.value, c.image, i.quantity
        FROM inventory i
        JOIN cards c ON i.card_id = c.card_id
        WHERE i.user_id = ?
        ORDER BY c.value DESC LIMIT 1
    """, (discord_id,))
    highest_card = cursor.fetchone()

    return jsonify({
        "success": True,
        "user": {
            "discord_id": discord_id,
            "balance": balance,
            "total_cards": total_cards,
            "rarity_counts": rarity_counts,
            "balance_rank": balance_rank,
            "last_beg": last_beg,
            "last_daily": last_daily,
            "highest_card": {
                "id": highest_card[0], "name": highest_card[1], "rarity": highest_card[2],
                "value": highest_card[3], "image": highest_card[4], "quantity": highest_card[5]
            } if highest_card else None
        }
    })

# --- 2. GACHA ENGINE ---
@app.route('/api/gacha', methods=['POST'])
def gacha_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    user = authenticate_user(cursor, data.get('web_id'), data.get('web_pass'))
    if not user: return jsonify({"error": "Unauthorized"}), 401

    discord_id, balance, _, _ = user
    cursor.execute("SELECT value FROM config WHERE key = 'gacha_cost'")
    row = cursor.fetchone()
    cost = int(row[0]) if row else 1000

    count = int(data.get('count', 1))
    total_cost = cost * count

    if balance < total_cost:
        return jsonify({"success": False, "error": f"Not enough coins! Need {total_cost} coins."}), 400

    # Fetch rarities
    cursor.execute("SELECT name, chance, color FROM rarities")
    rarities = cursor.fetchall()
    names = [r[0] for r in rarities]
    weights = [r[1] for r in rarities]

    pulls = []
    for _ in range(count):
        chosen_rarity = random.choices(names, weights=weights, k=1)[0]
        cursor.execute("SELECT card_id, name, rarity, value, image FROM cards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1", (chosen_rarity,))
        card = cursor.fetchone()
        if card:
            c_id, c_name, c_rarity, c_val, c_img = card
            # Update inventory
            cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?", (discord_id, c_id))
            inv = cursor.fetchone()
            if inv:
                cursor.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?", (discord_id, c_id))
            else:
                cursor.execute("INSERT INTO inventory (user_id, card_id, quantity) VALUES (?, ?, 1)", (discord_id, c_id))
            
            pulls.append({"id": c_id, "name": c_name, "rarity": c_rarity, "value": c_val, "image": c_img})

    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_cost, discord_id))
    conn.commit()

    return jsonify({"success": True, "pulls": pulls, "new_balance": balance - total_cost})

# --- 3. MARKET & GIFTING APIs ---
@app.route('/api/market/buy', methods=['POST'])
def buy_market():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    user = authenticate_user(cursor, data.get('web_id'), data.get('web_pass'))
    if not user: return jsonify({"error": "Unauthorized"}), 401

    buyer_id, buyer_bal, _, _ = user
    market_id = data.get('market_id')

    cursor.execute("SELECT seller_id, card_id, price, quantity FROM market WHERE selling_id = ?", (market_id,))
    item = cursor.fetchone()

    if not item: return jsonify({"success": False, "error": "Item listing no longer exists!"}), 404

    seller_id, card_id, price, qty = item
    if buyer_bal < price: return jsonify({"success": False, "error": "Insufficient coins!"}), 400

    # Transfer funds & item
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, buyer_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, seller_id))
    cursor.execute("DELETE FROM market WHERE selling_id = ?", (market_id,))
    
    cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?", (buyer_id, card_id))
    inv = cursor.fetchone()
    if inv:
        cursor.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND card_id = ?", (qty, buyer_id, card_id))
    else:
        cursor.execute("INSERT INTO inventory (user_id, card_id, quantity) VALUES (?, ?, ?)", (buyer_id, card_id, qty))

    conn.commit()
    return jsonify({"success": True, "message": "Successfully purchased item!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


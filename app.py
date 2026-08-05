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
    
    cursor.execute("SELECT id, balance, last_beg, last_daily, username, pfp FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: 
        return jsonify({"success": False, "error": "Invalid Web ID or Password!"}), 401
        
    discord_id, balance, last_beg, last_daily, username, pfp = user

    cursor.execute("SELECT COUNT(*) + 1 FROM users WHERE balance > ?", (balance,))
    balance_rank = cursor.fetchone()[0]

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

    cursor.execute("""
        SELECT c.rarity, COALESCE(SUM(i.quantity), 0) 
        FROM inventory i JOIN cards c ON i.card_id = c.card_id 
        WHERE i.user_id = ? GROUP BY c.rarity
    """, (discord_id,))
    rarity_counts = {row[0]: row[1] for row in cursor.fetchall()}
    total_cards = sum(rarity_counts.values())

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


# --- 2. LEADERBOARDS (WITH USERNAMES) ---
@app.route('/api/leaderboard', methods=['POST'])
def leaderboard_api():
    data = request.json
    lb_type = data.get('type', 'balance')
    conn = get_db()
    cursor = conn.cursor()

    if lb_type == 'balance':
        cursor.execute("SELECT id, username, balance FROM users ORDER BY balance DESC LIMIT 20")
        rows = cursor.fetchall()
        leaderboard = [{"id": r[0], "username": r[1] or f"User {str(r[0])[-4:]}", "value": r[2]} for r in rows]
    else:
        cursor.execute('''
            SELECT u.id, u.username, SUM(
                CASE c.rarity 
                    WHEN 'Common' THEN i.quantity*1 
                    WHEN 'Uncommon' THEN i.quantity*2 
                    WHEN 'Rare' THEN i.quantity*3 
                    WHEN 'Epic' THEN i.quantity*4 
                    WHEN 'Legendary' THEN i.quantity*8 
                    WHEN 'Super Legendary' THEN i.quantity*10 
                    ELSE 0 END
            ) as points
            FROM users u
            JOIN inventory i ON u.id = i.user_id 
            JOIN cards c ON i.card_id = c.card_id 
            GROUP BY u.id, u.username ORDER BY points DESC LIMIT 20
        ''')
        rows = cursor.fetchall()
        leaderboard = [{"id": r[0], "username": r[1] or f"User {str(r[0])[-4:]}", "value": r[2] or 0} for r in rows]

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

    return jsonify({"success": True, "cards": cards})


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


# --- 5. GACHA SUMMON (1 to 20) ---
@app.route('/api/gacha', methods=['POST'])
def gacha_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401

    discord_id, balance = user
    cost_per_pull = 1000
    try:
        count = int(data.get('count', 1))
    except (ValueError, TypeError):
        count = 1

    if count < 1 or count > 20:
        return jsonify({"success": False, "error": "Summon count must be between 1 and 20!"})

    total_cost = cost_per_pull * count
    if balance < total_cost:
        return jsonify({"success": False, "error": f"Need {total_cost:,} coins!"})

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
    items_to_burn = data.get('items', [])
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


# --- 7. USERS LIST FOR GIFTING ---
@app.route('/api/users_list', methods=['POST'])
def users_list_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    user = cursor.fetchone()
    if not user: return jsonify({"error": "Unauthorized"}), 401

    sender_id = user[0]
    cursor.execute("SELECT id, username FROM users WHERE id != ?", (sender_id,))
    users = [{"id": r[0], "username": r[1] or f"User {str(r[0])[-4:]}"} for r in cursor.fetchall()]
    return jsonify({"success": True, "users": users})


# --- 8. SEND GIFT ---
@app.route('/api/gift', methods=['POST'])
def gift_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance FROM users WHERE web_id = ? AND web_password = ?", (data.get('web_id'), data.get('web_pass')))
    sender = cursor.fetchone()
    if not sender: return jsonify({"error": "Unauthorized"}), 401

    sender_id, balance = sender
    target_id = data.get('target_id')
    gift_type = data.get('gift_type') # 'coins' or 'card'

    cursor.execute("SELECT id, username FROM users WHERE id = ?", (target_id,))
    target = cursor.fetchone()
    if not target: return jsonify({"success": False, "error": "Recipient user not found!"})
    target_name = target[1] or f"User {str(target_id)[-4:]}"

    if gift_type == 'coins':
        try:
            amount = int(data.get('amount', 0))
        except:
            amount = 0
        if amount <= 0: return jsonify({"success": False, "error": "Enter a valid coin amount!"})
        if balance < amount: return jsonify({"success": False, "error": "Insufficient coins!"})

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, sender_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, target_id))
        conn.commit()
        return jsonify({"success": True, "message": f"Successfully gifted {amount:,} coins to {target_name}!"})

    elif gift_type == 'card':
        card_id = data.get('card_id')
        try:
            qty = int(data.get('qty', 1))
        except:
            qty = 1
        if qty <= 0: return jsonify({"success": False, "error": "Invalid card quantity!"})

        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?", (sender_id, card_id))
        row = cursor.fetchone()
        if not row or row[0] < qty:
            return jsonify({"success": False, "error": "You don't own enough of this card!"})

        # Subtract card from sender
        if row[0] == qty:
            cursor.execute("DELETE FROM inventory WHERE user_id = ? AND card_id = ?", (sender_id, card_id))
        else:
            cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND card_id = ?", (qty, sender_id, card_id))

        # Add card to receiver
        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND card_id = ?", (target_id, card_id))
        target_row = cursor.fetchone()
        if target_row:
            cursor.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND card_id = ?", (qty, target_id, card_id))
        else:
            cursor.execute("INSERT INTO inventory (user_id, card_id, quantity) VALUES (?, ?, ?)", (target_id, card_id, qty))

        conn.commit()
        return jsonify({"success": True, "message": f"Successfully gifted {qty}x card(s) to {target_name}!"})

    return jsonify({"success": False, "error": "Invalid gift type!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    

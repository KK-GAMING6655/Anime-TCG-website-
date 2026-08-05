let currentSession = { web_id: null, web_pass: null };
let userCards = [];
let currentCardIndex = 0;
let currentGiftType = 'coins';

window.onload = () => {
    const savedId = localStorage.getItem('web_id');
    const savedPass = localStorage.getItem('web_pass');
    if (savedId && savedPass) {
        document.getElementById('web-id-input').value = savedId;
        document.getElementById('web-pass-input').value = savedPass;
        handleLogin();
    }
};

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
function toggleLoginModal(show) { document.getElementById('login-modal').classList[show ? 'add' : 'remove']('active'); }
function toggleLeaderboardModal(show) { document.getElementById('leaderboard-modal').classList[show ? 'add' : 'remove']('active'); }

function showPage(pageId, element) {
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    element.classList.add('active');
    document.getElementById('current-page-title').innerText = element.innerText.trim();

    if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');

    if (pageId === 'cards' || pageId === 'burn' || pageId === 'gift') {
        fetchUserCards();
    }
    if (pageId === 'gift') {
        fetchGiftUsersList();
    }
}

async function handleLogin() {
    const web_id = document.getElementById('web-id-input').value;
    const web_pass = document.getElementById('web-pass-input').value;

    const res = await fetch('/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ web_id, web_pass })
    });
    const data = await res.json();

    if (data.success) {
        localStorage.setItem('web_id', web_id);
        localStorage.setItem('web_pass', web_pass);
        currentSession = { web_id, web_pass };

        toggleLoginModal(false);
        document.getElementById('login-btn').classList.add('hidden');
        document.getElementById('logout-btn').classList.remove('hidden');
        document.getElementById('sidebar-profile').classList.remove('hidden');

        renderDashboard(data.user);
        fetchUserCards();
    } else alert(data.error);
}

function handleLogout() {
    localStorage.removeItem('web_id');
    localStorage.removeItem('web_pass');
    currentSession = { web_id: null, web_pass: null };

    document.getElementById('logout-btn').classList.add('hidden');
    document.getElementById('login-btn').classList.remove('hidden');
    document.getElementById('sidebar-profile').classList.add('hidden');

    document.getElementById('profile-name').innerText = "User";
    document.getElementById('welcome-name').innerText = "Guest";
    document.getElementById('profile-balance').innerText = "0";
    document.getElementById('dash-balance').innerText = "0";
    document.getElementById('dash-bal-rank').innerText = "#--";
    document.getElementById('dash-rank').innerText = "#--";
    document.getElementById('dash-total-cards').innerText = "0";

    document.getElementById('highest-card-container').innerHTML = '<p class="text-muted">Login to view your highest valued card.</p>';
    userCards = [];
    alert("Logged out successfully.");
}

function renderDashboard(user) {
    document.getElementById('profile-name').innerText = user.username;
    document.getElementById('welcome-name').innerText = user.username;
    if (document.getElementById('sidebar-pfp')) {
        document.getElementById('sidebar-pfp').src = user.pfp;
    }

    document.getElementById('profile-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-bal-rank').innerText = `#${user.balance_rank}`;
    document.getElementById('dash-rank').innerText = `#${user.user_rank}`;
    document.getElementById('dash-total-cards').innerText = user.total_cards;

    document.getElementById('cnt-common').innerText = user.rarity_counts['Common'] || 0;
    document.getElementById('cnt-uncommon').innerText = user.rarity_counts['Uncommon'] || 0;
    document.getElementById('cnt-rare').innerText = user.rarity_counts['Rare'] || 0;
    document.getElementById('cnt-epic').innerText = user.rarity_counts['Epic'] || 0;
    document.getElementById('cnt-legendary').innerText = user.rarity_counts['Legendary'] || 0;
    document.getElementById('cnt-slegendary').innerText = user.rarity_counts['Super Legendary'] || 0;

    const hc = document.getElementById('highest-card-container');
    if (user.highest_card) {
        hc.innerHTML = `
            <div style="display: flex; gap: 20px; align-items: center;">
                <img src="${user.highest_card.image}" alt="Card" style="width: 100px; height: 140px; object-fit: cover; border-radius: 8px; border: 2px solid var(--primary);">
                <div>
                    <h3 style="margin-bottom: 4px;">${user.highest_card.name}</h3>
                    <p class="text-primary" style="font-weight: 600; font-size: 0.9rem;">${user.highest_card.rarity.toUpperCase()}</p>
                    <p class="text-muted" style="margin-top: 8px;"><i class="fa-solid fa-coins"></i> Value: ${user.highest_card.value.toLocaleString()} Coins</p>
                    <p class="text-muted"><i class="fa-solid fa-layer-group"></i> Owned: x${user.highest_card.quantity}</p>
                </div>
            </div>`;
    } else {
        hc.innerHTML = `<p class="text-muted">No cards found in inventory.</p>`;
    }

    startTimers(user.last_daily, user.last_beg);
}

async function openLeaderboard(type) {
    toggleLeaderboardModal(true);
    document.getElementById('lb-modal-title').innerText = type === 'balance' ? '🏆 Wealth Leaderboard' : '🏆 Collection Leaderboard';
    document.getElementById('lb-header-val').innerText = type === 'balance' ? 'Balance' : 'Points';

    const res = await fetch('/api/leaderboard', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type })
    });
    const data = await res.json();

    const tbody = document.getElementById('lb-table-body');
    tbody.innerHTML = data.leaderboard.map((row, i) => `
        <tr>
            <td><strong>#${i + 1}</strong></td>
            <td>${row.username}</td>
            <td>${row.value.toLocaleString()}</td>
        </tr>
    `).join('');
}

async function fetchUserCards() {
    if (!currentSession.web_id) return;
    const res = await fetch('/api/data', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentSession)
    });
    const data = await res.json();
    if (data.success) {
        userCards = data.cards;
        renderCardSlider();
        renderBurnGrid();
        populateGiftCardDropdown();
    }
}

function renderCardSlider() {
    const display = document.getElementById('card-carousel-display');
    const counter = document.getElementById('card-counter');
    if (userCards.length === 0) {
        display.innerHTML = '<p class="text-muted">No cards owned.</p>';
        return;
    }
    const c = userCards[currentCardIndex];
    counter.innerText = `${currentCardIndex + 1} / ${userCards.length}`;
    display.innerHTML = `
        <img src="${c.image}" alt="Card">
        <h3>${c.name}</h3>
        <p class="text-primary">${c.rarity}</p>
        <p class="text-muted">Value: ${c.value} 🪙 | Owned: x${c.quantity}</p>
    `;
}

function changeCard(dir) {
    if (userCards.length === 0) return;
    currentCardIndex = (currentCardIndex + dir + userCards.length) % userCards.length;
    renderCardSlider();
}

function renderBurnGrid() {
    const grid = document.getElementById('burn-cards-grid');
    if (userCards.length === 0) {
        grid.innerHTML = '<p class="text-muted">No cards available to burn.</p>';
        return;
    }
    grid.innerHTML = userCards.map(c => `
        <div class="burn-card">
            <img src="${c.image}" alt="Card">
            <h4 style="font-size: 0.85rem; margin-bottom: 4px;">${c.name}</h4>
            <p class="text-muted" style="font-size: 0.75rem;">Val: ${Math.floor(c.value * 0.5)} 🪙</p>
            <input type="number" min="0" max="${c.quantity}" value="0" data-cardid="${c.id}" data-val="${Math.floor(c.value * 0.5)}" onchange="calcBurnTotal()">
            <span class="text-muted" style="font-size: 0.75rem;">/ ${c.quantity}</span>
        </div>
    `).join('');
}

function calcBurnTotal() {
    let total = 0;
    document.querySelectorAll('.burn-card input').forEach(inp => {
        const qty = parseInt(inp.value) || 0;
        const val = parseInt(inp.dataset.val);
        total += qty * val;
    });
    document.getElementById('burn-total-coins').innerText = total.toLocaleString();
}

async function submitBurn() {
    const items = [];
    document.querySelectorAll('.burn-card input').forEach(inp => {
        const qty = parseInt(inp.value) || 0;
        if (qty > 0) items.push({ card_id: inp.dataset.cardid, qty });
    });

    if (items.length === 0) return alert("Select at least 1 card to burn!");

    const res = await fetch('/api/burn', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, items })
    });
    const data = await res.json();
    if (data.success) {
        alert(`Successfully burned cards for ${data.coins_gained} coins!`);
        handleLogin();
    }
}

/* --- GACHA ANIMATION & FLEXIBLE COUNT --- */
function updateGachaCost() {
    const inp = document.getElementById('gacha-count-input');
    let val = parseInt(inp.value) || 1;
    if (val < 1) val = 1;
    if (val > 20) val = 20;
    inp.value = val;
    document.getElementById('gacha-total-cost').innerText = (val * 1000).toLocaleString();
}

async function pullGacha() {
    if (!currentSession.web_id) return alert("Please login first!");

    const count = parseInt(document.getElementById('gacha-count-input').value) || 1;
    const stage = document.getElementById('gacha-stage');
    const suspense = document.getElementById('gacha-suspense');
    const featured = document.getElementById('gacha-featured-card');
    const bulkResults = document.getElementById('gacha-bulk-results');

    // Reset Stage
    stage.classList.remove('hidden');
    suspense.classList.remove('hidden');
    featured.classList.add('hidden');
    bulkResults.classList.add('hidden');

    const res = await fetch('/api/gacha', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, count })
    });
    const data = await res.json();

    if (!data.success) {
        stage.classList.add('hidden');
        return alert(data.error);
    }

    // Sort pulls by value descending (highest value card is featured)
    const sortedPulls = [...data.pulls].sort((a, b) => b.value - a.value);
    const topPull = sortedPulls[0];

    // EA Sports / eFootball Suspense Delay Animation (2.2 seconds)
    setTimeout(() => {
        suspense.classList.add('hidden');
        featured.classList.remove('hidden');

        // Apply dynamic rarity glow color
        const cardBox = document.getElementById('summon-card-box');
        cardBox.className = `summon-card-box ${topPull.rarity.toLowerCase().replace(' ', '-')}`;

        document.getElementById('summon-rarity').innerText = topPull.rarity.toUpperCase();
        document.getElementById('summon-img').src = topPull.image;
        document.getElementById('summon-name').innerText = topPull.name;
        document.getElementById('summon-val').innerText = `Value: ${topPull.value.toLocaleString()} 🪙`;

        // Render bulk cards if more than 1 pulled
        if (data.pulls.length > 1) {
            bulkResults.classList.remove('hidden');
            const grid = document.getElementById('bulk-cards-grid');
            grid.innerHTML = data.pulls.map(c => `
                <div class="bulk-card-item ${c.rarity.toLowerCase().replace(' ', '-')}">
                    <img src="${c.image}" alt="Card">
                    <h5>${c.name}</h5>
                    <p class="rarity-tag">${c.rarity}</p>
                </div>
            `).join('');
        }

        handleLogin(); // Refresh balance
    }, 2200);
}

/* --- GIFTING SYSTEM --- */
async function fetchGiftUsersList() {
    if (!currentSession.web_id) return;
    const res = await fetch('/api/users_list', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentSession)
    });
    const data = await res.json();

    const select = document.getElementById('gift-user-select');
    if (data.success && data.users.length > 0) {
        select.innerHTML = '<option value="">-- Choose Target User --</option>' +
            data.users.map(u => `<option value="${u.id}">${u.username}</option>`).join('');
    } else {
        select.innerHTML = '<option value="">No other users found</option>';
    }
}

function setGiftType(type) {
    currentGiftType = type;
    document.getElementById('type-btn-coins').classList[type === 'coins' ? 'add' : 'remove']('active');
    document.getElementById('type-btn-card').classList[type === 'card' ? 'add' : 'remove']('active');

    document.getElementById('gift-coins-sec').classList[type === 'coins' ? 'remove' : 'add']('hidden');
    document.getElementById('gift-card-sec').classList[type === 'card' ? 'remove' : 'add']('hidden');
}

function populateGiftCardDropdown() {
    const select = document.getElementById('gift-card-select');
    if (userCards.length === 0) {
        select.innerHTML = '<option value="">No cards available</option>';
        return;
    }
    select.innerHTML = '<option value="">-- Select Card to Gift --</option>' + 
        userCards.map(c => `<option value="${c.id}">${c.name} (${c.rarity}) - x${c.quantity} Owned</option>`).join('');
}

async function submitGift() {
    if (!currentSession.web_id) return alert("Please login first!");

    const target_id = document.getElementById('gift-user-select').value;
    if (!target_id) return alert("Please select a target user!");

    let payload = { ...currentSession, target_id, gift_type: currentGiftType };

    if (currentGiftType === 'coins') {
        const amount = document.getElementById('gift-coin-amount').value;
        if (!amount || amount <= 0) return alert("Enter a valid coin amount!");
        payload.amount = amount;
    } else {
        const card_id = document.getElementById('gift-card-select').value;
        const qty = document.getElementById('gift-card-qty').value;
        if (!card_id) return alert("Please select a card to gift!");
        if (!qty || qty <= 0) return alert("Enter a valid card quantity!");
        payload.card_id = card_id;
        payload.qty = qty;
    }

    const res = await fetch('/api/gift', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.success) {
        alert(data.message);
        handleLogin(); // Refresh user balance & cards
    } else alert(data.error);
}

function startTimers(lastDaily, lastBeg) {
    setInterval(() => {
        const now = new Date();
        if (lastDaily) {
            const dailyTime = new Date(lastDaily);
            dailyTime.setDate(dailyTime.getDate() + 1);
            if (now < dailyTime) {
                const diff = new Date(dailyTime - now);
                document.getElementById('daily-time').innerText = `Wait ${diff.getUTCHours()}h ${diff.getUTCMinutes()}m`;
                document.getElementById('btn-daily').disabled = true;
            } else {
                document.getElementById('daily-time').innerText = "Ready!";
                document.getElementById('btn-daily').disabled = false;
            }
        }
        if (lastBeg) {
            const begTime = new Date(lastBeg);
            begTime.setMinutes(begTime.getMinutes() + 30);
            if (now < begTime) {
                const diff = new Date(begTime - now);
                document.getElementById('beg-time').innerText = `Wait ${diff.getUTCMinutes()}m ${diff.getUTCSeconds()}s`;
                document.getElementById('btn-beg').disabled = true;
            } else {
                document.getElementById('beg-time').innerText = "Ready!";
                document.getElementById('btn-beg').disabled = false;
            }
        }
    }, 1000);
}

async function doEconomy(action) {
    const res = await fetch('/api/economy', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, action })
    });
    const data = await res.json();
    if (data.success) {
        alert(`Claimed ${data.reward} coins!`);
        handleLogin();
    } else alert(data.error);
            }
                            

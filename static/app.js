let currentSession = { web_id: null, web_pass: null };
let userCards = [];
let currentCardIndex = 0;

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

    if (pageId === 'cards' || pageId === 'burn') {
        fetchUserCards();
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
        document.getElementById('login-btn').style.display = 'none';
        document.getElementById('sidebar-profile').classList.remove('hidden');

        renderDashboard(data.user);
        fetchUserCards();
    } else alert(data.error);
}

function renderDashboard(user) {
    document.getElementById('profile-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-bal-rank').innerText = `#${user.balance_rank}`;
    document.getElementById('dash-rank').innerText = `#${user.user_rank}`;
    document.getElementById('dash-total-cards').innerText = user.total_cards;

    // Rarity Counts
    document.getElementById('cnt-common').innerText = user.rarity_counts['Common'] || 0;
    document.getElementById('cnt-uncommon').innerText = user.rarity_counts['Uncommon'] || 0;
    document.getElementById('cnt-rare').innerText = user.rarity_counts['Rare'] || 0;
    document.getElementById('cnt-epic').innerText = user.rarity_counts['Epic'] || 0;
    document.getElementById('cnt-legendary').innerText = user.rarity_counts['Legendary'] || 0;
    document.getElementById('cnt-slegendary').innerText = user.rarity_counts['Super Legendary'] || 0;

    // Highest Valued Card Display
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
            <td>User ${row.id.slice(-4)}</td>
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

async function pullGacha(count) {
    const stage = document.getElementById('gacha-stage');
    stage.classList.remove('hidden');

    const res = await fetch('/api/gacha', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, count })
    });
    const data = await res.json();

    if (!data.success) return alert(data.error);

    const pull = data.pulls[0];
    document.getElementById('summon-rarity').innerText = pull.rarity.toUpperCase();
    document.getElementById('summon-img').src = pull.image;
    document.getElementById('summon-name').innerText = pull.name;

    handleLogin();
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
        

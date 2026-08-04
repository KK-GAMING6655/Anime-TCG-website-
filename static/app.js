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

function showPage(pageId, element) {
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    element.classList.add('active');
    document.getElementById('current-page-title').innerText = element.innerText.trim();
    if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');
}

function toggleLoginModal(show) {
    document.getElementById('login-modal').classList[show ? 'add' : 'remove']('active');
}

async function handleLogin() {
    const web_id = document.getElementById('web-id-input').value;
    const web_pass = document.getElementById('web-pass-input').value;
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ web_id, web_pass })
        });
        const data = await response.json();
        
        if (data.success) {
            localStorage.setItem('web_id', web_id);
            localStorage.setItem('web_pass', web_pass);
            currentSession = { web_id, web_pass };

            toggleLoginModal(false);
            document.getElementById('login-btn').style.display = 'none';
            document.getElementById('sidebar-profile').classList.remove('hidden');
            
            // Dashboard Data
            renderDashboard(data.user);
            
            // Load Collection & Rarities
            fetchCollectionData();
        } else {
            alert(data.error);
        }
    } catch (err) { alert("Server error connecting to database."); }
}

function renderDashboard(user) {
    document.getElementById('profile-name').innerText = `User`;
    document.getElementById('profile-balance').innerText = user.balance.toLocaleString();
    document.getElementById('profile-rank').innerText = `#${user.user_rank}`;
    
    document.getElementById('welcome-name').innerText = `User`;
    document.getElementById('dash-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-rank').innerText = `#${user.user_rank}`;
    document.getElementById('dash-total-cards').innerText = user.total_cards;

    const hcContainer = document.getElementById('highest-card-container');
    if (user.highest_card) {
        hcContainer.innerHTML = `
            <div style="display: flex; gap: 20px; align-items: center;">
                <img src="${user.highest_card.image}" alt="Card" style="width: 120px; border-radius: 8px;">
                <div>
                    <h3>${user.highest_card.name}</h3>
                    <p style="color: var(--primary);">${user.highest_card.rarity.toUpperCase()}</p>
                    <p class="text-muted"><i class="fa-solid fa-coins"></i> Value: ${user.highest_card.value}</p>
                    <p class="text-muted"><i class="fa-solid fa-layer-group"></i> Owned: x${user.highest_card.quantity}</p>
                </div>
            </div>`;
    }
}

async function fetchCollectionData() {
    const res = await fetch('/api/data', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentSession)
    });
    const data = await res.json();
    if (data.success) {
        userCards = data.cards;
        renderCardSlider();
        
        // Render Rarities
        const rarityBox = document.getElementById('rarity-container');
        rarityBox.innerHTML = data.rarities.map(r => `
            <div class="rarity-item" style="border-left-color: ${r.color}">
                <h4 style="color: ${r.color}">${r.name}</h4>
                <span class="rate">${r.chance}%</span>
            </div>
        `).join('');
    }
}

function renderCardSlider() {
    const display = document.getElementById('card-carousel-display');
    const counter = document.getElementById('card-counter');
    
    if (userCards.length === 0) {
        display.innerHTML = '<p class="text-muted">You have no cards yet.</p>';
        return;
    }
    
    const c = userCards[currentCardIndex];
    counter.innerText = `${currentCardIndex + 1} / ${userCards.length}`;
    display.innerHTML = `
        <img src="${c.image}" alt="Card">
        <h3>${c.name}</h3>
        <p style="color: var(--primary); font-weight: bold;">${c.rarity}</p>
        <p class="text-muted">Value: ${c.value} | Owned: ${c.quantity}</p>
    `;
}

function changeCard(dir) {
    if (userCards.length === 0) return;
    currentCardIndex += dir;
    if (currentCardIndex < 0) currentCardIndex = userCards.length - 1;
    if (currentCardIndex >= userCards.length) currentCardIndex = 0;
    renderCardSlider();
}

async function pullGacha(count) {
    const stage = document.getElementById('gacha-stage');
    stage.classList.remove('hidden');
    document.getElementById('summon-rarity').innerText = "SUMMONING...";
    document.getElementById('summon-img').src = "";
    document.getElementById('summon-name').innerText = "---";

    const res = await fetch('/api/gacha', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, count })
    });
    const data = await res.json();
    
    if (!data.success) return alert(data.error);

    // Update balances
    document.getElementById('profile-balance').innerText = data.new_balance.toLocaleString();
    document.getElementById('dash-balance').innerText = data.new_balance.toLocaleString();
    
    // Show pull (If bulk, shows the first card for animation, but updates inventory behind scenes)
    const pull = data.pulls[0];
    setTimeout(() => {
        document.getElementById('summon-rarity').innerText = pull.rarity.toUpperCase();
        document.getElementById('summon-img').src = pull.image;
        document.getElementById('summon-name').innerText = pull.name;
        if(count > 1) alert(`Bulk Pull Complete! Check your 'My Cards' tab for all ${count} cards.`);
        fetchCollectionData(); // Refresh background inventory
    }, 1000);
                  }


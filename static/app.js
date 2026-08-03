let currentSession = { web_id: null, web_pass: null };

// Check saved credentials on site open
window.onload = () => {
    const savedId = localStorage.getItem('web_id');
    const savedPass = localStorage.getItem('web_pass');
    if (savedId && savedPass) {
        document.getElementById('web-id-input').value = savedId;
        document.getElementById('web-pass-input').value = savedPass;
        handleLogin();
    }
};

async function handleLogin() {
    const web_id = document.getElementById('web-id-input').value;
    const web_pass = document.getElementById('web-pass-input').value;

    const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ web_id, web_pass })
    });

    const data = await response.json();
    if (data.success) {
        currentSession = { web_id, web_pass };
        localStorage.setItem('web_id', web_id);
        localStorage.setItem('web_pass', web_pass);

        document.getElementById('login-modal').classList.remove('active');
        document.getElementById('user-profile-header').classList.remove('hidden');
        
        // Render user stats
        renderUserStats(data.user);
    } else {
        alert(data.error || "Login Failed!");
    }
}

function renderUserStats(user) {
    document.getElementById('stat-balance').innerText = user.balance.toLocaleString();
    document.getElementById('header-balance').innerText = user.balance.toLocaleString();
    document.getElementById('stat-rank').innerText = `#${user.balance_rank}`;
    document.getElementById('stat-total-cards').innerText = user.total_cards;

    // Set rarity breakdown counts
    document.getElementById('cnt-common').innerText = user.rarity_counts['Common'] || 0;
    document.getElementById('cnt-uncommon').innerText = user.rarity_counts['Uncommon'] || 0;
    document.getElementById('cnt-rare').innerText = user.rarity_counts['Rare'] || 0;
    document.getElementById('cnt-epic').innerText = user.rarity_counts['Epic'] || 0;
    document.getElementById('cnt-legendary').innerText = user.rarity_counts['Legendary'] || 0;
    document.getElementById('cnt-slegendary').innerText = user.rarity_counts['Super Legendary'] || 0;
}

// Animated Gacha Pulling Sequence
async function pullGacha(count = 1) {
    const response = await fetch('/api/gacha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...currentSession, count })
    });

    const data = await response.json();
    if (!data.success) return alert(data.error);

    const pull = data.pulls[0];
    const cardBox = document.getElementById('card-reveal-box');
    
    // Step 1: Reveal Rarity Glow Animation
    document.getElementById('gacha-rarity-text').innerText = pull.rarity.toUpperCase();
    cardBox.style.boxShadow = `0 0 30px var(--${pull.rarity.toLowerCase().replace(' ', '')})`;

    // Step 2: Smooth flip delay to show the card image and details
    setTimeout(() => {
        document.getElementById('gacha-img').src = pull.image;
        document.getElementById('gacha-card-name').innerText = pull.name;
    }, 1000);
}

function showPage(pageId) {
    document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');
}


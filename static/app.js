let currentSession = { web_id: null, web_pass: null };
let userCards = [];

window.onload = () => {
    const savedId = localStorage.getItem('web_id');
    const savedPass = localStorage.getItem('web_pass');
    if (savedId && savedPass) {
        document.getElementById('web-id-input').value = savedId;
        document.getElementById('web-pass-input').value = savedPass;
        handleLogin();
    }
};

function showPage(pageId, element) {
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    element.classList.add('active');
    document.getElementById('current-page-title').innerText = element.innerText.trim();
}

function toggleLoginModal(show) { document.getElementById('login-modal').classList[show ? 'add' : 'remove']('active'); }
function toggleLeaderboard(show) { document.getElementById('leaderboard-modal').classList[show ? 'add' : 'remove']('active'); }

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
    } else alert(data.error);
}

function renderDashboard(user) {
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

    startTimers(user.last_daily, user.last_beg);
}

// Timer Logic for Cooldowns
function startTimers(lastDaily, lastBeg) {
    setInterval(() => {
        const now = new Date();
        
        // Daily (24 hours)
        if(lastDaily) {
            const dailyTime = new Date(lastDaily);
            dailyTime.setDate(dailyTime.getDate() + 1);
            if(now < dailyTime) {
                const diff = new Date(dailyTime - now);
                document.getElementById('daily-time').innerText = `Wait ${diff.getUTCHours()}h ${diff.getUTCMinutes()}m`;
                document.getElementById('btn-daily').disabled = true;
            } else {
                document.getElementById('daily-time').innerText = "Ready!";
                document.getElementById('btn-daily').disabled = false;
            }
        }

        // Beg (30 mins)
        if(lastBeg) {
            const begTime = new Date(lastBeg);
            begTime.setMinutes(begTime.getMinutes() + 30);
            if(now < begTime) {
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
    if(data.success) {
        alert(`You received ${data.reward} coins!`);
        document.getElementById('dash-balance').innerText = data.new_balance.toLocaleString();
        document.getElementById('profile-balance').innerText = data.new_balance.toLocaleString();
        handleLogin(); // Refresh timers
    } else {
        alert("You are on cooldown!");
    }
        }

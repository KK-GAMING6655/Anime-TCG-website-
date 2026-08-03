// Local Storage Session
let currentSession = { web_id: null, web_pass: null };

window.onload = () => {
    const savedId = localStorage.getItem('web_id');
    const savedPass = localStorage.getItem('web_pass');
    if (savedId && savedPass) {
        document.getElementById('web-id-input').value = savedId;
        document.getElementById('web-pass-input').value = savedPass;
        handleLogin();
    }
};

// Toggle Sidebar for Mobile
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// Page Navigation Logic
function showPage(pageId, element) {
    // Hide all pages
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    // Show target page
    document.getElementById(`page-${pageId}`).classList.add('active');
    
    // Update active state in sidebar
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    element.classList.add('active');

    // Update Topbar Title
    document.getElementById('current-page-title').innerText = element.innerText.trim();
    
    // Close sidebar on mobile after clicking
    if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('open');
    }
}

// Modal Logic
function toggleLoginModal(show) {
    const modal = document.getElementById('login-modal');
    if (show) modal.classList.add('active');
    else modal.classList.remove('active');
}

// Login System API Call
async function handleLogin() {
    const web_id = document.getElementById('web-id-input').value;
    const web_pass = document.getElementById('web-pass-input').value;
    const btn = document.querySelector('.modal-content .btn-primary');
    
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Logging in...';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ web_id, web_pass })
        });

        const data = await response.json();
        
        if (data.success) {
            // Save Session
            localStorage.setItem('web_id', web_id);
            localStorage.setItem('web_pass', web_pass);
            currentSession = { web_id, web_pass };

            // Update UI components
            toggleLoginModal(false);
            document.getElementById('login-btn').style.display = 'none'; // Hide login button
            document.getElementById('sidebar-profile').classList.remove('hidden'); // Show profile in sidebar
            
            // Populate Data
            renderUserStats(data.user);
        } else {
            alert(data.error || "Login Failed! Check your ID and Password.");
        }
    } catch (err) {
        console.error(err);
        alert("Server error. Make sure the bot database is running.");
    } finally {
        btn.innerHTML = 'Login';
    }
}

// Map Backend Data to Frontend
function renderUserStats(user) {
    // Sidebar Profile Update
    document.getElementById('profile-name').innerText = `User ${user.discord_id.slice(-4)}`; // Fallback name
    document.getElementById('profile-balance').innerText = user.balance.toLocaleString();
    document.getElementById('profile-rank').innerText = `#${user.balance_rank}`;
    
    // Dashboard Stats Update
    document.getElementById('welcome-name').innerText = `User ${user.discord_id.slice(-4)}`;
    document.getElementById('dash-balance').innerText = user.balance.toLocaleString();
    document.getElementById('dash-rank').innerText = `#${user.balance_rank}`;
    document.getElementById('dash-total-cards').innerText = user.total_cards;

    // Highest Valued Card Rendering
    const hcContainer = document.getElementById('highest-card-container');
    if (user.highest_card) {
        hcContainer.innerHTML = `
            <div style="display: flex; gap: 20px; align-items: center;">
                <img src="${user.highest_card.image}" alt="Card" style="width: 120px; border-radius: 8px; border: 2px solid var(--primary);">
                <div>
                    <h3 style="margin-bottom: 8px;">${user.highest_card.name}</h3>
                    <p style="color: var(--primary); font-weight: 600; margin-bottom: 4px;">${user.highest_card.rarity.toUpperCase()}</p>
                    <p class="text-muted"><i class="fa-solid fa-coins"></i> Value: ${user.highest_card.value}</p>
                    <p class="text-muted"><i class="fa-solid fa-layer-group"></i> Owned: x${user.highest_card.quantity}</p>
                </div>
            </div>
        `;
    } else {
        hcContainer.innerHTML = `<p class="text-muted">You haven't collected any cards yet.</p>`;
    }
                }
            

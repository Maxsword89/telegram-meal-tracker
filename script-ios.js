// --- ІМІТАЦІЯ ДАНИХ (резерв) ---
const mockApiData = {
    target: 2000,
    consumed: 1450,
    date: new Date().toLocaleDateString('uk-UA', { day: 'numeric', month: 'long', year: 'numeric' }),
    meals: [
        { time: '08:30', name: 'Сніданок (Вівсянка з ягодами)', calories: 420 },
        { time: '13:00', name: 'Обід (Курка гриль, овочі)', calories: 580 },
    ]
};

// --- КОНСТАНТИ URL АДРЕС ВАШОГО API ---
const BASE_URL = 'https://Maxsword2025.pythonanywhere.com/api'; 

const API_DASHBOARD_URL = `${BASE_URL}/get_daily_report`; 
const API_PROCESS_PHOTO_URL = `${BASE_URL}/process_photo`; 
const API_SAVE_MEAL_URL = `${BASE_URL}/save_meal`; 

// -------------------------------------------------------------------------


// --- 1. ФУНКЦІЯ: ВІДПРАВКА НА AI-СЕРВЕР (ТЕПЕР JSON, НЕ ФАЙЛ!) ---
async function callAIApi(file) {
    const tg = window.Telegram.WebApp;
    
    // Надсилаємо initData та ігноруємо файл, оскільки бекенд очікує JSON
    const response = await fetch(API_PROCESS_PHOTO_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            initData: tg.initData || '',
            // Тут можуть бути інші дані, але не сам файл
        }),
    });

    if (!response.ok) {
        throw new Error(`AI API failed with status: ${response.status}`);
    }

    return response.json(); 
}


// --- 2. ФУНКЦІЯ: РЕАЛЬНА ФІКСАЦІЯ СТРАВИ НА СЕРВЕРІ ---
async function confirmAndSaveMeal(mealData) {
    const tg = window.Telegram.WebApp;
    
    const response = await fetch(API_SAVE_MEAL_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            initData: tg.initData || '', 
            meal: {
                name: mealData.name,
                calories: mealData.calories,
            }
        })
    });
    
    return response.ok; 
}


// --- ФУНКЦІЯ: ПОКАЗ РЕЗУЛЬТАТУ У СПЛИВАЮЧОМУ ВІКНІ ---
function showResultPopup(mealData) {
    if (!window.Telegram || !window.Telegram.WebApp) return;
    const tg = window.Telegram.WebApp;

    const message = 
        `🍽️ *Розпізнана страва:* **${mealData.name}**\n\n` +
        `🔥 *Оцінка калорій:* **${mealData.calories} ккал**\n\n` +
        `*Деталі:* ${mealData.description}`;

    tg.showPopup({
        title: "Результат розпізнавання",
        message: message,
        buttons: [
            { id: 'confirm', type: 'default', text: `✅ Додати (${mealData.calories} ккал)` },
            { id: 'edit', type: 'destructive', text: '✏️ Редагувати' }
        ]
    }, async (buttonId) => {
        if (buttonId === 'confirm') {
            tg.showProgress(true); 
            
            try {
                const success = await confirmAndSaveMeal(mealData);
                tg.showProgress(false); 
                
                if (success) {
                    tg.showAlert('Страва успішно додана до вашого звіту!');
                    // Перезавантажуємо через невелику затримку
                    setTimeout(() => window.location.reload(), 500); 
                } else {
                    tg.showAlert('Помилка: Не вдалося зберегти дані на сервері. Перевірте логі бекенду (Error log).');
                }
            } catch (error) {
                tg.showProgress(false);
                tg.showAlert('Помилка мережі при збереженні.');
            }

        } else if (buttonId === 'edit') {
            tg.showAlert('Функціонал редагування буде доданий пізніше.');
        }
    });
}


// --- ФУНКЦІЯ ЗАВАНТАЖЕННЯ ТА РЕНДЕРИНГУ ---
async function fetchDataAndRender(initData) {
    let data = mockApiData; 

    if (initData) {
        try { 
            const response = await fetch(API_DASHBOARD_URL, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData: initData }) 
            });
            
            if (response.ok) {
                data = await response.json(); 
            } else {
                 console.warn(`Failed to fetch real data, status: ${response.status}. Using mock data.`);
            }
        } catch (e) { 
            console.error("API Error fetching dashboard data:", e); 
        }
    }
    
    renderMetrics(data); renderMeals(data.meals); renderComment(data);
}

// --- ФУНКЦІЯ ДЛЯ КНОПКИ "ДОДАТИ ФОТО" ---
function setupButtonListener() {
    const button = document.getElementById('add-meal-button');
    const fileInput = document.getElementById('file-input');

    button.addEventListener('click', () => {
        if (window.Telegram && window.Telegram.WebApp) {
            fileInput.click();
        } else {
            alert('Функція "Додати фото" доступна лише в Telegram Mini App.');
        }
    });

    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        
        if (file) {
            button.textContent = '⏳ Обробка фото...';
            button.disabled = true;

            try {
                // Викликаємо API, який тепер очікує JSON
                const mealData = await callAIApi(file); 
                
                showResultPopup(mealData);

            } catch (error) {
                console.error("Помилка обробки файлу:", error);
                if (window.Telegram && window.Telegram.WebApp) {
                     window.Telegram.WebApp.showAlert('Помилка: Не вдалося розпізнати страву. Перевірте API.');
                }
            } finally {
                button.textContent = '📸 Додати прийом їжі за фото';
                button.disabled = false;
                fileInput.value = ''; 
            }
        }
    });
}

// --- ІНІЦІАЛІЗАЦІЯ TELEGRAM MINI APP ---
function initTelegramWebApp() {
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        tg.ready();
        
        document.body.style.backgroundColor = 'var(--ios-bg)'; 
        const username = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.first_name : 'Користувач';
        document.getElementById('welcome-message').textContent = `Сьогодні`;
        document.getElementById('date-display').textContent = `Привіт, ${username}! Звіт за сьогодні.`;
        
        fetchDataAndRender(tg.initData);
        setupButtonListener();
        
    } else {
        fetchDataAndRender(null); 
        setupButtonListener(); 
    }
}

// Запуск програми
initTelegramWebApp();

// --- Функції рендерингу (незмінні) ---

function renderMetrics(data) {
    const consumed = data.consumed;
    const target = data.target;
    const remaining = target - consumed;
    const percent = Math.min(100, Math.round((consumed / target) * 100));

    document.getElementById('date-display').textContent = `Звіт за ${data.date}`;
    document.getElementById('calories-consumed').textContent = consumed;
    document.getElementById('calories-target').textContent = target;

    const progressCircle = document.querySelector('.circular-progress');
    progressCircle.style.background = `conic-gradient(var(--ios-success) ${percent}%, var(--ios-separator) ${percent}%)`;
    progressCircle.setAttribute('aria-valuenow', percent);
    document.getElementById('progress-percent').textContent = `${percent}%`;
    
    const remainingEl = document.querySelector('.progress-remaining');
    
    if (remaining < 0) {
        remainingEl.textContent = `Перевищення: ${Math.abs(remaining)} ккал`;
        remainingEl.style.color = '#FF3B30';
    } else {
        remainingEl.textContent = `${remaining} ккал`;
        remainingEl.style.color = 'var(--ios-accent)';
    }
}

function renderMeals(meals) {
    const list = document.getElementById('meals-list');
    list.innerHTML = ''; 

    if (meals.length === 0) {
        list.innerHTML = `<li class="ios-list-item">Сьогодні ще не було зафіксовано прийомів їжі.</li>`;
        return;
    }

    meals.forEach(meal => {
        const li = document.createElement('li');
        li.className = 'ios-list-item'; 
        li.innerHTML = `
            <div>
                <div class="meal-time">${meal.time}</div>
                <div class="meal-name">${meal.name}</div>
            </div>
            <div class="meal-calories">${meal.calories} ккал</div>
        `;
        list.appendChild(li);
    });
}

function renderComment(data) {
    const commentEl = document.getElementById('daily-comment');
    const consumed = data.consumed;
    const target = data.target;
    let comment = '';
    
    if (consumed === 0) {
        comment = "День тільки почався! Надішліть перше фото, щоб розпочати трекінг. 💪";
    } else if (consumed < target * 0.75) {
        comment = `Ви на гарному шляху! Спожито ${consumed} ккал. Не забувайте про необхідну активність.`;
    } else if (consumed >= target && consumed < target * 1.05) {
        comment = "🏆 **Вітаємо! Ви досягли або дуже близькі до вашої добової цілі.** Відмінна робота!";
    } else if (consumed >= target * 1.05) {
        comment = `⚠️ **Увага! Ви перевищили ціль на ${consumed - target} ккал.** Радимо скоригувати раціон на наступний день.`;
    }
    
    commentEl.innerHTML = comment;
}
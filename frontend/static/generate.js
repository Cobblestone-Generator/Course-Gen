// CourseGen Frontend JavaScript - Complete Version
document.addEventListener('DOMContentLoaded', function() {
    console.log('CourseGen initialized');
    initializeApp();
});

// Функция для проверки и обновления токена
async function validateToken() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return false;
    }
    
    try {
        // Простая проверка - если токен есть, считаем его валидным
        // В реальном приложении можно добавить проверку через API
        return true;
    } catch (error) {
        console.error('Token validation error:', error);
        return false;
    }
}

// Обновите функцию checkAuthStatus
async function checkAuthStatus() {
    const token = localStorage.getItem('access_token');
    const navButtons = document.querySelector('.flex.items-center.gap-2');
    
    if (!navButtons) return;

    if (token) {
        try {
            const isValid = await validateToken();
            if (!isValid) {
                logout();
                return;
            }
            
            const userEmail = localStorage.getItem('user_email');
            const userName = localStorage.getItem('user_name');
            
            navButtons.innerHTML = `
                <span class="text-sm text-graphite-gray hidden md:block">${userEmail || 'Пользователь'}</span>
                <button onclick="logout()" class="flex h-10 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-gray-100 px-4 text-sm font-bold leading-normal tracking-wide text-cobblestone-blue transition-transform hover:scale-105">
                    <span class="truncate">Выйти</span>
                </button>
            `;
        } catch (error) {
            console.error('Auth check failed:', error);
            logout();
        }
    }
}

async function initializeApp() {
    await checkAuthStatus();
    setupEventListeners();
}

function setupEventListeners() {
    console.log('Setting up event listeners...');
    
    // Course generation - основной обработчик
    const createCourseBtn = document.getElementById('create-course');
    if (createCourseBtn) {
        console.log('Found create course button');
        createCourseBtn.addEventListener('click', handleCourseCreation);
    } else {
        console.log('Create course button not found');
    }

    // Login form
    const loginForm = document.querySelector('form');
    if (loginForm && (window.location.pathname.includes('/login') || window.location.pathname === '/login')) {
        console.log('Setting up login form');
        loginForm.addEventListener('submit', handleLogin);
    }

    // Registration form
    if (loginForm && (window.location.pathname.includes('/register') || window.location.pathname === '/register')) {
        console.log('Setting up registration form');
        loginForm.addEventListener('submit', handleRegister);
    }

    // Support form
    const supportForm = document.querySelector('form');
    if (supportForm && (window.location.pathname.includes('/support') || window.location.pathname === '/support')) {
        console.log('Setting up support form');
        supportForm.addEventListener('submit', handleSupport);
    }

    // Load courses on my-courses page
    if (window.location.pathname.includes('/my-courses') || window.location.pathname === '/my-courses') {
        console.log('Loading user courses');
        loadUserCourses();
    }

    // Password visibility toggles
    setupPasswordToggles();
    
    // Enter key support for course creation
    setupEnterKeySupport();
}

function setupEnterKeySupport() {
    const videoInput = document.getElementById('video-url-input') || document.getElementById('video-url');
    if (videoInput) {
        videoInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleCourseCreation();
            }
        });
    }
}

function setupPasswordToggles() {
    document.querySelectorAll('button').forEach(button => {
        const icon = button.querySelector('.material-symbols-outlined');
        if (icon && icon.textContent === 'visibility') {
            button.addEventListener('click', function() {
                const input = this.parentElement.querySelector('input[type="password"]');
                if (input) {
                    if (input.type === 'password') {
                        input.type = 'text';
                        this.querySelector('.material-symbols-outlined').textContent = 'visibility_off';
                    } else {
                        input.type = 'password';
                        this.querySelector('.material-symbols-outlined').textContent = 'visibility';
                    }
                }
            });
        }
    });
}

async function checkAuthStatus() {
    const token = localStorage.getItem('access_token');
    const navButtons = document.querySelector('.flex.items-center.gap-2');
    
    if (!navButtons) return;

    if (token) {
        try {
            const userEmail = localStorage.getItem('user_email');
            const userName = localStorage.getItem('user_name');
            
            navButtons.innerHTML = `
                <span class="text-sm text-graphite-gray hidden md:block">${userEmail || 'Пользователь'}</span>
                <button onclick="logout()" class="flex h-10 min-w-[84px] cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-gray-100 px-4 text-sm font-bold leading-normal tracking-wide text-cobblestone-blue transition-transform hover:scale-105">
                    <span class="truncate">Выйти</span>
                </button>
            `;
        } catch (error) {
            console.error('Auth check failed:', error);
            logout();
        }
    }
}

// Функция для создания курса (основная)
window.handleCourseCreation = async function() {
    console.log('handleCourseCreation called');
    
    const videoUrlInput = document.getElementById('video-url-input') || document.getElementById('video-url');
    const videoUrl = videoUrlInput ? videoUrlInput.value.trim() : '';
    
    console.log('Video URL:', videoUrl);
    
    if (!videoUrl) {
        showResult('Пожалуйста, введите ссылку на YouTube видео', 'error');
        return;
    }
    
    if (!isValidYouTubeUrl(videoUrl)) {
        showResult('Пожалуйста, введите корректную ссылку на YouTube', 'error');
        return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) {
        showResult('Пожалуйста, войдите в систему для создания курсов', 'error');
        setTimeout(() => {
            window.location.href = '/login';
        }, 2000);
        return;
    }
    
    // Находим кнопку и показываем состояние загрузки
    const createButton = document.getElementById('create-course');
    if (createButton) {
        const originalText = createButton.innerHTML;
        createButton.innerHTML = '<span class="truncate">Создание...</span>';
        createButton.disabled = true;
        
        try {
            console.log('Sending request to /api/generate-course...');
            
            const formData = new URLSearchParams();
            formData.append('video_url', videoUrl);
            
            const response = await fetch('/api/generate-course', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });
            
            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('API response data:', data);
            
            if (response.ok) {
                if (data.success) {
                    showResult(`✅ Курс "${data.title}" успешно создан! Перенаправление...`, 'success');
                    
                    setTimeout(() => {
                        window.location.href = '/my-courses';
                    }, 2000);
                } else {
                    showResult('❌ Ошибка при создании курса: ' + (data.detail || 'Неизвестная ошибка'), 'error');
                }
            } else {
                showResult('❌ Ошибка сервера: ' + (data.detail || `HTTP ${response.status}`), 'error');
            }
            
        } catch (error) {
            console.error('Network error:', error);
            showResult('❌ Ошибка сети при создании курса: ' + error.message, 'error');
        } finally {
            createButton.innerHTML = originalText;
            createButton.disabled = false;
        }
    } else {
        showResult('❌ Кнопка создания курса не найдена', 'error');
    }
};

// Функция для кнопки на главной странице
window.handleMainPageCourseCreation = async function() {
    console.log('handleMainPageCourseCreation called');
    
    const videoUrlInput = document.querySelector('input[placeholder*="YouTube"]');
    const videoUrl = videoUrlInput ? videoUrlInput.value.trim() : '';
    
    if (!videoUrl) {
        showResult('Пожалуйста, введите ссылку на YouTube видео', 'error');
        return;
    }
    
    if (!isValidYouTubeUrl(videoUrl)) {
        showResult('Пожалуйста, введите корректную ссылку на YouTube', 'error');
        return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) {
        // Перенаправляем на страницу генератора, где будет проверка авторизации
        window.location.href = '/generator';
        return;
    }
    
    // Если пользователь авторизован, создаем курс
    await handleCourseCreation();
};

// Старая функция для обратной совместимости
async function generateCourse() {
    console.warn('generateCourse is deprecated, use handleCourseCreation instead');
    await handleCourseCreation();
}

async function handleLogin(e) {
    e.preventDefault();
    console.log('Login form submitted');
    
    const form = e.target;
    const emailInput = form.querySelector('input[type="email"]');
    const passwordInput = form.querySelector('input[type="password"]');
    
    if (!emailInput || !passwordInput) {
        showResult('❌ Форма входа не найдена', 'error');
        return;
    }
    
    const email = emailInput.value;
    const password = passwordInput.value;
    
    if (!email || !password) {
        showResult('❌ Заполните все поля', 'error');
        return;
    }
    
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'Вход...';
    submitBtn.disabled = true;
    
    try {
        console.log('Sending login request...');
        
        const formData = new URLSearchParams();
        formData.append('email', email);
        formData.append('password', password);
        
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });
        
        console.log('Login response status:', response.status);
        const data = await response.json();
        console.log('Login response data:', data);
        
        if (response.ok) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_email', data.email);
            localStorage.setItem('user_name', `${data.first_name} ${data.last_name}`);
            
            showResult('✅ Успешный вход! Перенаправление...', 'success');
            
            setTimeout(() => {
                window.location.href = '/my-courses';
            }, 1000);
        } else {
            showResult('❌ Ошибка входа: ' + (data.detail || 'Неизвестная ошибка'), 'error');
        }
        
    } catch (error) {
        console.error('Login error:', error);
        showResult('❌ Ошибка сети при входе', 'error');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

async function handleRegister(e) {
    e.preventDefault();
    console.log('Registration form submitted');
    
    const form = e.target;
    
    // Находим поля формы
    const emailInput = form.querySelector('input[type="email"]');
    const passwordInput = form.querySelector('input[type="password"]');
    const firstNameInput = form.querySelector('input[placeholder="Имя"]');
    const lastNameInput = form.querySelector('input[placeholder="Фамилия"]');
    const confirmPasswordInput = form.querySelector('input[placeholder="Повторите пароль"]');
    
    if (!emailInput || !passwordInput || !firstNameInput || !lastNameInput || !confirmPasswordInput) {
        showResult('❌ Не все поля формы найдены', 'error');
        return;
    }
    
    const email = emailInput.value;
    const password = passwordInput.value;
    const firstName = firstNameInput.value;
    const lastName = lastNameInput.value;
    const confirmPassword = confirmPasswordInput.value;
    
    // Валидация
    if (!email || !password || !firstName || !lastName || !confirmPassword) {
        showResult('❌ Заполните все поля', 'error');
        return;
    }
    
    if (password !== confirmPassword) {
        showResult('❌ Пароли не совпадают', 'error');
        return;
    }
    
    if (password.length < 8) {
        showResult('❌ Пароль должен содержать минимум 8 символов', 'error');
        return;
    }
    
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'Регистрация...';
    submitBtn.disabled = true;
    
    try {
        console.log('Sending registration request...');
        
        const formData = new URLSearchParams();
        formData.append('email', email);
        formData.append('password', password);
        formData.append('first_name', firstName);
        formData.append('last_name', lastName);
        
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });
        
        console.log('Registration response status:', response.status);
        const data = await response.json();
        console.log('Registration response data:', data);
        
        if (response.ok) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_email', data.email);
            localStorage.setItem('user_name', `${data.first_name} ${data.last_name}`);
            
            showResult('✅ Регистрация успешна! Перенаправление...', 'success');
            
            setTimeout(() => {
                window.location.href = '/my-courses';
            }, 1000);
        } else {
            showResult('❌ Ошибка регистрации: ' + (data.detail || 'Неизвестная ошибка'), 'error');
        }
        
    } catch (error) {
        console.error('Registration error:', error);
        showResult('❌ Ошибка сети при регистрации', 'error');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

async function loadUserCourses() {
    console.log('Loading user courses...');
    
    const token = localStorage.getItem('access_token');
    
    if (!token) {
        console.log('No token, redirecting to login');
        window.location.href = '/login';
        return;
    }
    
    try {
        const response = await fetch('/api/courses', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        console.log('Courses response status:', response.status);
        const data = await response.json();
        console.log('Courses data:', data);
        
        if (response.ok) {
            displayCourses(data.courses);
        } else {
            console.error('Failed to load courses:', data);
            showEmptyState();
            showResult('❌ Ошибка загрузки курсов: ' + (data.detail || 'Неизвестная ошибка'), 'error');
        }
        
    } catch (error) {
        console.error('Error loading courses:', error);
        showEmptyState();
        showResult('❌ Ошибка сети при загрузке курсов', 'error');
    }
}

function displayCourses(courses) {
    console.log('Displaying courses:', courses);
    
    const emptyState = document.querySelector('.mt-12.text-center');
    const layoutContainer = document.querySelector('.layout-content-container');
    
    if (!courses || courses.length === 0) {
        showEmptyState();
        showResult('📝 У вас пока нет созданных курсов. Создайте первый курс!', 'info');
        return;
    }
    
    // Hide empty state
    if (emptyState) {
        emptyState.style.display = 'none';
    }
    
    // Remove existing courses grid if any
    const existingGrid = document.getElementById('courses-grid');
    if (existingGrid) {
        existingGrid.remove();
    }
    
    // Create courses grid
    const coursesGrid = document.createElement('div');
    coursesGrid.id = 'courses-grid';
    coursesGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8';
    
    courses.forEach(course => {
        const courseCard = createCourseCard(course);
        coursesGrid.appendChild(courseCard);
    });
    
    // Add after the page heading
    const pageHeading = document.querySelector('.layout-content-container > .flex.items-center.justify-between');
    if (pageHeading && pageHeading.nextSibling) {
        pageHeading.parentNode.insertBefore(coursesGrid, pageHeading.nextSibling);
    } else if (layoutContainer) {
        layoutContainer.appendChild(coursesGrid);
    }
    
    showResult(`✅ Загружено ${courses.length} курсов`, 'success');
}

function createCourseCard(course) {
    const card = document.createElement('div');
    card.className = 'bg-white rounded-xl border border-graphite-gray/20 p-6 hover:shadow-lg transition-shadow';
    
    const createdDate = course.created_at ? new Date(course.created_at).toLocaleDateString('ru-RU') : 'Сегодня';
    
    // Создаем красивый ID видео для отображения
    let videoId = 'YouTube видео';
    if (course.video_url) {
        if (course.video_url.includes('youtube.com/watch?v=')) {
            videoId = course.video_url.split('youtube.com/watch?v=')[1]?.split('&')[0] || 'видео';
        } else if (course.video_url.includes('youtu.be/')) {
            videoId = course.video_url.split('youtu.be/')[1]?.split('?')[0] || 'видео';
        }
    }
    
    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <h3 class="text-lg font-bold text-cobblestone-blue">${course.title || 'Без названия'}</h3>
            <span class="material-symbols-outlined text-primary">school</span>
        </div>
        <p class="text-graphite-gray text-sm mb-4">${course.description || 'Автоматически сгенерированный курс'}</p>
        <div class="text-xs text-graphite-gray mb-4">
            <div class="flex items-center gap-1 mb-1">
                <span class="material-symbols-outlined text-sm">video_library</span>
                <span>ID видео: ${videoId}</span>
            </div>
            <div class="flex items-center gap-1">
                <span class="material-symbols-outlined text-sm">calendar_today</span>
                <span>Создан: ${createdDate}</span>
            </div>
        </div>
        <div class="flex gap-2">
            <button onclick="openCourse(${course.id})" class="flex-1 bg-primary text-cobblestone-blue py-2 px-4 rounded-lg text-sm font-bold hover:scale-105 transition-transform flex items-center justify-center gap-2">
                <span class="material-symbols-outlined text-sm">visibility</span>
                Открыть
            </button>
            <button onclick="downloadCoursePdf(${course.id})" class="flex items-center gap-1 bg-gray-100 text-cobblestone-blue py-2 px-3 rounded-lg text-sm font-bold hover:scale-105 transition-transform">
                <span class="material-symbols-outlined text-sm">download</span>
            </button>
        </div>
    `;
    
    return card;
}


function createCourseCard(course) {
    const card = document.createElement('div');
    card.className = 'bg-white rounded-xl border border-graphite-gray/20 p-6 hover:shadow-lg transition-shadow';
    
    const createdDate = course.created_at ? new Date(course.created_at).toLocaleDateString('ru-RU') : 'Сегодня';
    
    // Создаем красивый ID видео для отображения
    let videoId = 'YouTube видео';
    if (course.video_url) {
        if (course.video_url.includes('youtube.com/watch?v=')) {
            videoId = course.video_url.split('youtube.com/watch?v=')[1]?.split('&')[0] || 'видео';
        } else if (course.video_url.includes('youtu.be/')) {
            videoId = course.video_url.split('youtu.be/')[1]?.split('?')[0] || 'видео';
        }
    }
    
    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <h3 class="text-lg font-bold text-cobblestone-blue">${course.title || 'Без названия'}</h3>
            <span class="material-symbols-outlined text-primary">school</span>
        </div>
        <p class="text-graphite-gray text-sm mb-4">${course.description || 'Автоматически сгенерированный курс'}</p>
        <div class="text-xs text-graphite-gray mb-4">
            <div class="flex items-center gap-1 mb-1">
                <span class="material-symbols-outlined text-sm">video_library</span>
                <span>ID видео: ${videoId}</span>
            </div>
            <div class="flex items-center gap-1">
                <span class="material-symbols-outlined text-sm">calendar_today</span>
                <span>Создан: ${createdDate}</span>
            </div>
        </div>
        <div class="flex gap-2">
            <button onclick="openCourse(${course.id})" class="flex-1 bg-primary text-cobblestone-blue py-2 px-4 rounded-lg text-sm font-bold hover:scale-105 transition-transform flex items-center justify-center gap-2">
                <span class="material-symbols-outlined text-sm">visibility</span>
                Открыть
            </button>
            <button onclick="downloadCoursePdf(${course.id})" class="flex items-center gap-1 bg-gray-100 text-cobblestone-blue py-2 px-3 rounded-lg text-sm font-bold hover:scale-105 transition-transform">
                <span class="material-symbols-outlined text-sm">download</span>
            </button>
        </div>
    `;
    
    return card;
}

// Новая функция для открытия курса
window.openCourse = function(courseId) {
    console.log('Opening course:', courseId);
    showResult(`📖 Открываем курс...`, 'info');
    
    // Переходим на страницу курса
    setTimeout(() => {
        window.location.href = `/course-detail?id=${courseId}`;
    }, 500);
};

async function viewCourse(courseId) {
    console.log('Viewing course:', courseId);
    showResult(`👀 Просмотр курса #${courseId} - функция в разработке`, 'info');
}

async function downloadCoursePdf(courseId) {
    console.log('Downloading PDF for course:', courseId);
    
    const token = localStorage.getItem('access_token');
    
    if (!token) {
        showResult('❌ Для скачивания необходимо войти в систему', 'error');
        return;
    }
    
    try {
        showResult('⏳ Начинаем загрузку PDF...', 'info');
        
        const response = await fetch(`/api/courses/${courseId}/pdf`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `course_${courseId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showResult('✅ PDF успешно скачан!', 'success');
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
            showResult('❌ Ошибка при загрузке PDF: ' + (errorData.detail || `HTTP ${response.status}`), 'error');
        }
    } catch (error) {
        console.error('Download error:', error);
        showResult('❌ Ошибка сети при загрузке PDF', 'error');
    }
}

function handleSupport(e) {
    e.preventDefault();
    console.log('Support form submitted');
    showResult('✅ Сообщение отправлено! Мы ответим вам в течение 24 часов.', 'success');
    e.target.reset();
}

function isValidYouTubeUrl(url) {
    const patterns = [
        /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=)/,
        /^(https?:\/\/)?(www\.)?(youtube\.com\/embed\/)/,
        /^(https?:\/\/)?(www\.)?(youtu\.be\/)/
    ];
    return patterns.some(pattern => pattern.test(url));
}

function showResult(message, type) {
    console.log(`Showing result: ${type} - ${message}`);
    
    // Create or get result box
    let resultBox = document.getElementById('generator-result');
    if (!resultBox) {
        resultBox = document.createElement('div');
        resultBox.id = 'generator-result';
        document.body.appendChild(resultBox);
    }
    
    resultBox.textContent = message;
    resultBox.className = `fixed bottom-6 right-6 max-w-lg rounded-lg border p-4 shadow-lg text-sm z-50 ${
        type === 'success' 
            ? 'border-green-200 bg-green-50 text-green-800'
            : type === 'error'
            ? 'border-red-200 bg-red-50 text-red-800'
            : type === 'info'
            ? 'border-blue-200 bg-blue-50 text-blue-800'
            : 'border-gray-200 bg-gray-50 text-gray-800'
    }`;
    resultBox.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        resultBox.style.display = 'none';
    }, 5000);
}

// Global functions
window.logout = function() {
    console.log('Logging out...');
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_name');
    showResult('👋 Вы вышли из системы', 'info');
    setTimeout(() => {
        window.location.href = '/';
    }, 1000);
};

window.viewCourse = viewCourse;
window.downloadCoursePdf = downloadCoursePdf;
window.handleCourseCreation = handleCourseCreation;
window.handleMainPageCourseCreation = handleMainPageCourseCreation;

// Utility function to get form data
window.getFormData = function(form) {
    const data = new FormData(form);
    const result = {};
    for (let [key, value] of data.entries()) {
        result[key] = value;
    }
    return result;
};

// Auto-check auth status on page load
window.addEventListener('load', function() {
    console.log('Page loaded, checking auth status...');
    setTimeout(checkAuthStatus, 100);
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        isValidYouTubeUrl,
        showResult,
        handleCourseCreation,
        handleLogin,
        handleRegister
    };
}

// Глобальная функция для открытия курса
window.openCourse = function(courseId) {
    console.log('Opening course:', courseId);
    // Переходим на страницу курса
    window.location.href = `/course-detail?id=${courseId}`;
};

// Глобальная функция для скачивания PDF
window.downloadCoursePdf = async function(courseId) {
    console.log('Downloading PDF for course:', courseId);
    
    const token = localStorage.getItem('access_token');
    
    if (!token) {
        showResult('❌ Для скачивания необходимо войти в систему', 'error');
        return;
    }
    
    try {
        showResult('⏳ Начинаем загрузку PDF...', 'info');
        
        const response = await fetch(`/api/courses/${courseId}/pdf`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `course_${courseId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showResult('✅ PDF успешно скачан!', 'success');
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Неизвестная ошибка' }));
            showResult('❌ Ошибка при загрузке PDF: ' + (errorData.detail || `HTTP ${response.status}`), 'error');
        }
    } catch (error) {
        console.error('Download error:', error);
        showResult('❌ Ошибка сети при загрузке PDF', 'error');
    }
};
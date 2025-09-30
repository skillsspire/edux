// ====================== УМНЫЙ AI ASSISTANT SKILLSSPIRE ======================
class AIAssistant {
    constructor() {
        this.config = { enableAI: true };

        // 📚 База знаний
        this.knowledgeBase = [
            {
                "title": "Бизнес-анализ и принятие решений", 
                "category": "Бизнес-аналитика",
                "price": "15 000 ₸",
                "originalPrice": "18 000 ₸",
                "description": "Научитесь принимать эффективные бизнес-решения на основе данных. Анализ рынка, оценка рисков и построение финансовых моделей.",
                "rating": "4.8",
                "features": ["Анализ данных", "Финансовые модели", "Оценка рисков", "Принятие решений"],
                "duration": "6 недель",
                "level": "Начинающий"
            },
            {
                "title": "Стратегический менеджмент и бизнес-планирование", 
                "category": "Стратегический менеджмент",
                "price": "17 000 ₸",
                "originalPrice": "20 000 ₸",
                "description": "Освойте инструменты стратегического анализа и планирования для устойчивого роста вашей компании. От SWOT-анализа до разработки KPI.",
                "rating": "4.8",
                "features": ["SWOT-анализ", "KPI разработка", "Бизнес-планирование", "Стратегический анализ"],
                "duration": "8 недель",
                "level": "Средний"
            },
            {
                "title": "Финансовая грамотность для руководителей", 
                "category": "Управление финансами",
                "price": "12 000 ₸",
                "originalPrice": "15 000 ₸",
                "description": "Научитесь читать и анализировать финансовую отчетность, чтобы принимать обоснованные управленческие решения и говорить с финансистами на одном языке.",
                "rating": "4.8",
                "features": ["Финансовая отчетность", "Управленческие решения", "Бюджетирование", "Анализ инвестиций"],
                "duration": "4 недели",
                "level": "Начинающий"
            }
        ];

        // 📞 Инфо о компании
        this.companyInfo = {
            name: "SkillsSpire",
            description: "Академическое качество в современном формате. Классика, переосмысленная для будущего.",
            mission: "Соединяем классическое университетское образование с современными бизнес-задачами",
            email: "skillsspire@gmail.com",
            phone: "+7 (701) 292-55-68",
            instagram: "@skillsspire",
            linkedin: "SkillSpire Official",
            telegram: "@SkillsSpire",
            responseTime: "24 часа в рабочие дни (Пн-Пт с 9:00 до 18:00)",
            certificates: "более 100 выданных сертификатов"
        };

        // Контекст диалога
        this.context = {
            lastTopic: null,
            userName: null,
            userInterest: null,
            testStage: null,
            testAnswers: {}
        };

        // История
        this.chatHistory = [
            { role: "bot", text: "👋 Привет! Я ваш помощник SkillsSpire!\n\nЯ помогу:\n• Подобрать курс\n• Рассказать о программах обучения\n• Ответить на вопросы\n• Связать с поддержкой\n\nС чего начнем? 😊" }
        ];

        this.isFollowing = false;
        this.init();
    }

    // -------------------- БАЗОВЫЕ МЕТОДЫ --------------------
    init() {
        this.bindElements();
        this.bindEvents();
        console.log('🎯 Умный помощник SkillsSpire запущен!');
    }

    bindElements() {
        this.bubble = document.getElementById('ai-bubble');
        this.panel = document.getElementById('ai-panel');
        this.closeBtn = document.getElementById('ai-close');
        this.messages = document.getElementById('ai-messages');
        this.input = document.getElementById('ai-text');
        this.sendBtn = document.getElementById('ai-send');
        this.statusEl = document.getElementById('ai-status');
    }

    bindEvents() {
        this.bubble?.addEventListener('click', () => this.togglePanel());
        this.closeBtn?.addEventListener('click', () => this.togglePanel());
        this.sendBtn?.addEventListener('click', () => this.sendMessage());

        this.input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.input?.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        this.bubble?.addEventListener('dblclick', () => this.toggleFollowMode());

        document.addEventListener('click', (e) => {
            if (this.panel?.contains(e.target) || this.bubble?.contains(e.target)) return;
            if (this.panel?.style.display === 'flex') this.togglePanel();
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isFollowing && this.bubble) {
                this.bubble.style.left = (e.clientX - 28) + 'px';
                this.bubble.style.top = (e.clientY - 28) + 'px';
                this.bubble.style.right = 'auto';
                this.bubble.style.bottom = 'auto';
            }
        });
    }

    togglePanel() {
        const isOpen = this.panel.style.display === 'flex';
        this.panel.style.display = isOpen ? 'none' : 'flex';
        this.bubble.setAttribute('aria-expanded', !isOpen);

        if (!isOpen) {
            this.input.focus();
            if (this.chatHistory.length === 1) setTimeout(() => this.showQuickReplies(), 500);
        }
    }

    toggleFollowMode() {
        this.isFollowing = !this.isFollowing;
        this.bubble.style.animation = this.isFollowing ? 'none' : 'floating 3s ease-in-out infinite';
        this.bubble.title = this.isFollowing ? 'Режим следования за курсором' : 'ИИ помощник SkillsSpire';

        if (!this.isFollowing) {
            this.bubble.style.left = '';
            this.bubble.style.top = '';
            this.bubble.style.right = '20px';
            this.bubble.style.bottom = '20px';
        }
    }

    appendMessage(text, role = 'bot') {
        const msgDiv = document.createElement('div');
        msgDiv.className = `ai-msg ai-${role}`;
        msgDiv.textContent = text;
        this.messages.appendChild(msgDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
        this.chatHistory.push({ role, text });
    }

    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'ai-msg ai-bot ai-typing';
        typingDiv.id = 'typing-indicator';
        typingDiv.textContent = 'Думаю...';
        this.messages.appendChild(typingDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    hideTypingIndicator() {
        const typing = document.getElementById('typing-indicator');
        if (typing) typing.remove();
    }

    // -------------------- БЫСТРЫЕ ОТВЕТЫ --------------------
    showQuickReplies() {
        const quickReplies = [
            "🎯 Подобрать курс по целям",
            "📝 Пройти тест на курс",
            "💰 Стоимость и скидки", 
            "📜 Сертификаты и дипломы",
            "🚀 Как помогает в карьере",
            "👨‍🎓 Кто преподаёт",
            "📞 Контакты поддержки",
            "🏫 О компании SkillsSpire"
        ];
        
        const quickDiv = document.createElement('div');
        quickDiv.className = 'ai-quick-replies';

        quickReplies.forEach(reply => {
            const btn = document.createElement('button');
            btn.textContent = reply;
            btn.onclick = () => {
                this.input.value = reply.replace(/[🎯💰📞🏫📚🚀👨‍🎓📜📝]/g, '').trim();
                this.sendMessage();
            };
            quickDiv.appendChild(btn);
        });

        this.messages.appendChild(quickDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    // -------------------- МИНИ-ТЕСТ --------------------
    handleCourseTest(answer) {
        if (!this.context.testStage) {
            this.context.testStage = 1;
            return "📝 Отлично! Давайте подберем курс.\nВопрос 1: Ваш уровень — начинающий или опытный?";
        }

        if (this.context.testStage === 1) {
            this.context.testAnswers.level = answer.toLowerCase().includes("нач") ? "beginner" : "advanced";
            this.context.testStage = 2;
            return "Вопрос 2: Больше интересует управление людьми или работа с финансами?";
        }

        if (this.context.testStage === 2) {
            if (answer.toLowerCase().includes("финанс")) this.context.testAnswers.track = "finance";
            else if (answer.toLowerCase().includes("управ")) this.context.testAnswers.track = "management";
            else this.context.testAnswers.track = "analytics";

            this.context.testStage = 3;
            return "Вопрос 3: Сколько времени готовы уделять обучению? (4, 6 или 8 недель)";
        }

        if (this.context.testStage === 3) {
            this.context.testAnswers.duration = answer.match(/\d+/) ? parseInt(answer.match(/\d+/)[0]) : 6;

            // Финальный подбор
            this.context.testStage = null;
            let recommended;
            if (this.context.testAnswers.track === "finance") recommended = this.knowledgeBase[2];
            else if (this.context.testAnswers.track === "management") recommended = this.knowledgeBase[1];
            else recommended = this.knowledgeBase[0];

            return `✅ По вашим ответам подходит курс:\n\n${this.formatCourse(recommended)}\n\nХотите записаться прямо сейчас?`;
        }
    }

    // -------------------- НАМЕРЕНИЯ --------------------
    analyzeIntent(message) {
        const lowerMessage = message.toLowerCase();

        const intents = {
            greeting: /(привет|здравств|добр|hello|hi)/,
            farewell: /(пока|до свидан|увидимся|bye)/,
            thanks: /(спасиб|thank|мерси)/,
            personal: /(как.*дел|как.*ты)/,
            smalltalk: /(погода|день|час|шутк|анекдот|мотивируй)/,
            name: /(меня зовут|я\s+[а-яa-z]+)/,
            goal: /(карьер|работ|бизнес|финанс|рост|повышен)/,
            test: /(тест|подбор|quiz|опрос)/,
            courses: /(курс|обучен|урок)/,
            pricing: /(цена|стоим|оплат|сколько)/,
            contacts: /(контакт|поддерж|телефон|почт|email)/,
            about: /(о.*компан|skillsspire|мисси|кто.*вы)/,
            recommend: /(совет|рекоменд|что выбрать)/,
            specific: {
                business_analytics: /(бизнес.*анализ|аналитик)/,
                strategy: /(стратеги|менеджмент|swot|kpi)/,
                finance: /(финанс|отчетност|бухгалтер)/,
                certificate: /(сертифика|диплом)/,
                teacher: /(препод|лектор|кто ведет)/,
                career: /(карьер|работа|повышен)/
            }
        };

        const detectedIntents = [];
        for (const [intent, pattern] of Object.entries(intents)) {
            if (intent === 'specific') {
                for (const [subIntent, subPattern] of Object.entries(intents.specific)) {
                    if (subPattern.test(lowerMessage)) detectedIntents.push(subIntent);
                }
            } else if (pattern.test(lowerMessage)) {
                detectedIntents.push(intent);
            }
        }

        return detectedIntents.length > 0 ? detectedIntents : ['general'];
    }

    // -------------------- ГЕНЕРАЦИЯ ОТВЕТОВ --------------------
    generateAIResponse(userMessage) {
        if (this.context.testStage) return this.handleCourseTest(userMessage);

        const intents = this.analyzeIntent(userMessage);
        const lowerMessage = userMessage.toLowerCase();
        this.context.lastTopic = intents[0];

        // Имя
        if (intents.includes('name')) {
            const match = lowerMessage.match(/меня зовут\s+([а-яa-z]+)/i);
            if (match) {
                this.context.userName = match[1].charAt(0).toUpperCase() + match[1].slice(1);
                return `Очень приятно, ${this.context.userName}! 🙌`;
            }
        }

        if (intents.includes('greeting')) return "👋 Привет! Чем могу помочь — подбор курса, цены или тест?";
        if (intents.includes('farewell')) return "До встречи! 🚀 Успехов в обучении!";
        if (intents.includes('thanks')) return "Всегда рад помочь 🙌";
        if (intents.includes('personal')) return "У меня всё отлично! А у вас как дела?";
        if (intents.includes('smalltalk')) return "Сегодня отличный день, чтобы учиться 🎓🚀";
        if (intents.includes('test')) return this.handleCourseTest("");

        if (intents.includes('goal')) {
            if (lowerMessage.includes("финанс")) return this.formatCourse(this.knowledgeBase[2]);
            if (lowerMessage.includes("карьер")) return this.formatCourse(this.knowledgeBase[1]);
            return this.formatCourse(this.knowledgeBase[0]);
        }

        if (intents.includes('courses')) return this.knowledgeBase.map(c => this.formatCourse(c)).join("\n\n");
        if (intents.includes('pricing')) return this.knowledgeBase.map(c => `• ${c.title}: ${c.price}`).join("\n");
        if (intents.includes('contacts')) return `Email: ${this.companyInfo.email}\nТел: ${this.companyInfo.phone}`;
        if (intents.includes('about')) return `${this.companyInfo.name}: ${this.companyInfo.description}`;

        if (intents.includes('certificate')) return `🎓 Сертификат выдается после окончания курса (${this.companyInfo.certificates})`;
        if (intents.includes('teacher')) return "👨‍🏫 Преподаватели — практики и PhD из топ-университетов.";
        if (intents.includes('career')) return "🚀 Наши выпускники получают повышение и новые карьерные возможности.";

        if (intents.includes('business_analytics')) return this.formatCourse(this.knowledgeBase[0]);
        if (intents.includes('strategy')) return this.formatCourse(this.knowledgeBase[1]);
        if (intents.includes('finance')) return this.formatCourse(this.knowledgeBase[2]);

        return "Не совсем понял 🤔 Хотите пройти тест или показать список курсов?";
    }

    formatCourse(course) {
        return `📖 ${course.title}\n${course.description}\n💰 ${course.price} | ⏱️ ${course.duration} | ⭐ ${course.rating}`;
    }

    // -------------------- ОТПРАВКА --------------------
    sendMessage() {
        const text = this.input.value.trim();
        if (!text) return;
        this.input.value = '';
        this.appendMessage(text, 'user');
        this.showTypingIndicator();

        const delay = 600 + Math.random() * 1000;
        setTimeout(() => {
            this.hideTypingIndicator();
            const response = this.generateAIResponse(text);
            this.appendMessage(response, 'bot');
            if (this.chatHistory.length <= 8) setTimeout(() => this.showQuickReplies(), 400);
        }, delay);
    }
}

// -------------------- ИНИЦИАЛИЗАЦИЯ --------------------
document.addEventListener('DOMContentLoaded', () => {
    window.aiAssistant = new AIAssistant();
});

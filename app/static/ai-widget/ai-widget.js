// Умный AI Assistant для SkillsSpire с системой тестирования
class AIAssistant {
    constructor() {
        this.config = {
            enableAI: true
        };
        
        // База знаний курсов
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
                "level": "Начинающий",
                "instructor": "Профессор с PhD в бизнес-аналитике",
                "career": "Бизнес-аналитик, Менеджер проектов, Аналитик данных",
                "tags": ["аналитика", "данные", "финансы", "решения"]
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
                "level": "Средний",
                "instructor": "Доктор экономических наук",
                "career": "Руководитель, Стратегический менеджер, Владелец бизнеса",
                "tags": ["стратегия", "управление", "планирование", "лидерство"]
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
                "level": "Начинающий",
                "instructor": "Профессор финансов с 15-летним опытом",
                "career": "Финансовый менеджер, Руководитель, Предприниматель",
                "tags": ["финансы", "отчетность", "бюджет", "инвестиции"]
            }
        ];

        // Система тестирования
        this.testSystem = {
            isActive: false,
            currentQuestion: 0,
            userAnswers: {},
            questions: [
                {
                    question: "🎯 Ваш текущий уровень знаний?",
                    options: ["Начинающий (только основы)", "Средний (есть опыт)", "Опытный (глубокие знания)"],
                    key: "level"
                },
                {
                    question: "💼 Что вас интересует больше?",
                    options: ["Управление людьми и стратегия", "Анализ данных и финансы", "Бизнес-планирование и развитие"],
                    key: "interest"
                },
                {
                    question: "⏱️ Сколько времени готовы уделять обучению?",
                    options: ["4 недели (интенсив)", "6 недель (стандарт)", "8 недель (комфортный темп)"],
                    key: "duration"
                },
                {
                    question: "🚀 Ваша основная цель?",
                    options: ["Карьерный рост", "Развитие бизнеса", "Личное развитие"],
                    key: "goal"
                }
            ]
        };

        // Контекст диалога
        this.context = {
            lastTopic: null,
            userName: null,
            userInterest: null,
            userGoal: null,
            userExperience: null,
            conversationStage: 'greeting'
        };
        
        this.chatHistory = [
            { role: "bot", text: "👋 Привет! Я ваш умный помощник SkillsSpire!\n\nЯ помогу подобрать идеальный курс, пройти тест или ответить на любые вопросы! 💫" }
        ];
        
        this.isFollowing = false;
        this.init();
    }

    // ... остальные методы (init, bindElements, bindEvents, togglePanel и т.д.) остаются без изменений ...
    init() {
        this.bindElements();
        this.bindEvents();
        console.log('🎯 Умный помощник SkillsSpire загружен!');
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
            if (this.panel?.style.display === 'flex') {
                this.togglePanel();
            }
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
            if (this.chatHistory.length === 1) {
                setTimeout(() => this.showQuickReplies(), 500);
            }
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
        typingDiv.textContent = 'Думаю';
        this.messages.appendChild(typingDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }
    
    hideTypingIndicator() {
        const typing = document.getElementById('typing-indicator');
        if (typing) typing.remove();
    }
    
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
                this.input.value = reply.replace(/[🎯📝💰📜🚀👨‍🎓📞🏫]/g, '').trim();
                this.sendMessage();
            };
            quickDiv.appendChild(btn);
        });
        
        this.messages.appendChild(quickDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    // 🔹 СИСТЕМА ТЕСТИРОВАНИЯ
    startTest() {
        this.testSystem.isActive = true;
        this.testSystem.currentQuestion = 0;
        this.testSystem.userAnswers = {};
        this.showTestQuestion();
    }

    showTestQuestion() {
        const question = this.testSystem.questions[this.testSystem.currentQuestion];
        let questionText = `📝 Вопрос ${this.testSystem.currentQuestion + 1}/${this.testSystem.questions.length}:\n${question.question}\n\n`;
        
        question.options.forEach((option, index) => {
            questionText += `${index + 1}. ${option}\n`;
        });
        
        questionText += "\nПросто напишите номер ответа (1, 2, 3) или текст";
        this.appendMessage(questionText, 'bot');
    }

    processTestAnswer(userAnswer) {
        const currentQuestion = this.testSystem.questions[this.testSystem.currentQuestion];
        let answerIndex = -1;

        // Пытаемся найти номер ответа
        const numberMatch = userAnswer.match(/[123]/);
        if (numberMatch) {
            answerIndex = parseInt(numberMatch[0]) - 1;
        } else {
            // Ищем текстовое совпадение
            answerIndex = currentQuestion.options.findIndex(option => 
                option.toLowerCase().includes(userAnswer.toLowerCase()) ||
                userAnswer.toLowerCase().includes(option.split(' ')[0].toLowerCase())
            );
        }

        if (answerIndex >= 0 && answerIndex < currentQuestion.options.length) {
            this.testSystem.userAnswers[currentQuestion.key] = currentQuestion.options[answerIndex];
            this.testSystem.currentQuestion++;

            if (this.testSystem.currentQuestion < this.testSystem.questions.length) {
                this.showTestQuestion();
            } else {
                this.finishTest();
            }
        } else {
            this.appendMessage("🤔 Пожалуйста, выберите один из предложенных вариантов (1, 2 или 3)", 'bot');
        }
    }

    finishTest() {
        this.testSystem.isActive = false;
        const recommendation = this.generateRecommendation();
        this.appendMessage(recommendation, 'bot');
        
        // Показываем кнопки после теста
        setTimeout(() => {
            this.showQuickReplies();
        }, 1000);
    }

    generateRecommendation() {
        const answers = this.testSystem.userAnswers;
        
        // Логика подбора курса на основе ответов
        let recommendedCourse = this.knowledgeBase[2]; // По умолчанию финансы
        
        if (answers.interest?.includes("Управление людьми")) {
            recommendedCourse = this.knowledgeBase[1]; // Стратегический менеджмент
        } else if (answers.interest?.includes("Анализ данных")) {
            recommendedCourse = this.knowledgeBase[0]; // Бизнес-анализ
        }
        
        // Корректировка по времени
        if (answers.duration?.includes("6 недель") && recommendedCourse.duration === "6 недель") {
            recommendedCourse = this.knowledgeBase[0]; // Бизнес-анализ
        } else if (answers.duration?.includes("8 недель")) {
            recommendedCourse = this.knowledgeBase[1]; // Стратегический менеджмент
        }

        return `✅ Отлично! По вашим ответам идеально подходит:\n\n🎯 ${recommendedCourse.title}\n\n${recommendedCourse.description}\n\n⭐ Рейтинг: ${recommendedCourse.rating}/5\n💰 Цена: ${recommendedCourse.price} (скидка!)\n⏱️ Длительность: ${recommendedCourse.duration}\n🎓 Уровень: ${recommendedCourse.level}\n\nХотите узнать больше об этом курсе или посмотреть другие варианты? 😊`;
    }

    // 🔹 ОБНОВЛЕННЫЙ АНАЛИЗ ИНТЕНТОВ
    analyzeIntent(message) {
        const lowerMessage = message.toLowerCase();
        
        const intents = {
            test: /(тест|подобр|рекоменд|посовет|что.*выбр|какой.*курс)/,
            greeting: /(привет|здравств|добр|хай|hello|hi|салам)/,
            courses: /(курс|обучен|программ)/,
            pricing: /(цена|стоим|оплат|деньг|сколько|стоит)/,
            contacts: /(контакт|поддерж|помощ|связ|телефон|почт|email)/,
            about: /(о.*компан|о.*вас|skillsspire)/,
            certificate: /(сертифика|документ|диплом)/,
            instructor: /(преподав|учитель|лектор|кто.*учит)/,
            career: /(карьер|работ|трудоустрой)/,
            yes: /(да|yes|конечно|хочу|ага)/,
            no: /(нет|no|не хочу|не надо)/
        };
        
        for (const [intent, pattern] of Object.entries(intents)) {
            if (pattern.test(lowerMessage)) {
                return intent;
            }
        }
        
        return 'general';
    }

    // 🔹 ОБНОВЛЕННАЯ ГЕНЕРАЦИЯ ОТВЕТОВ
    generateAIResponse(userMessage) {
        // Если активен тест - обрабатываем ответ на вопрос
        if (this.testSystem.isActive) {
            this.processTestAnswer(userMessage);
            return null;
        }

        const intent = this.analyzeIntent(userMessage);
        const lowerMessage = userMessage.toLowerCase();

        switch (intent) {
            case 'test':
                this.startTest();
                return null;

            case 'greeting':
                return "👋 Привет! Чем могу помочь — подбор курса, цены или тест?";
                
            case 'courses':
                return "📚 Наши курсы:\n\n• Бизнес-анализ и принятие решений - 15 000 ₸\n• Стратегический менеджмент - 17 000 ₸\n• Финансовая грамотность - 12 000 ₸\n\nХотите пройти тест для подбора?";
                
            case 'pricing':
                return "💰 Стоимость курсов:\n\n• Бизнес-анализ и принятие решений: 15 000 ₸\n• Стратегический менеджмент и бизнес-планирование: 17 000 ₸\n• Финансовая грамотность для руководителей: 12 000 ₸\n\n💎 Все курсы со скидками!";
                
            case 'contacts':
                return "📞 Контакты поддержки:\n\n📧 Email: skillsspire@gmail.com\n📱 Телефон: +7 (701) 292-55-68\n📸 Instagram: @skillsspire\n✈️ Telegram: @SkillsSpire";
                
            case 'about':
                return "🏫 О компании SkillsSpire:\n\nSkillsSpire: Академическое качество в современном формате. Классика, переосмысленная для будущего.";
                
            case 'certificate':
                return "📜 Сертификаты и дипломы:\n\n• Официальный документ о прохождении\n• Подтверждает компетенции\n• Признается работодателями\n• Более 100 выпускников";
                
            case 'instructor':
                return "👨‍🎓 Кто преподаёт:\n\n👨‍🏫 Преподаватели — практики и PhD из топ-университетов.";
                
            case 'career':
                return "🚀 Как помогает в карьере:\n\n• 85% выпускников находят работу за 3 месяца\n• Помощь с резюме и собеседованиями\n• Стажировки в компаниях-партнерах\n• Карьерные консультации";
                
            case 'yes':
                return "Отлично! Хотите пройти тест для подбора курса или показать все варианты?";
                
            case 'no':
                return "Понял! Может быть, вас интересует что-то другое? Спросите о курсах, ценах или поддержке!";
                
            default:
                if (/(меня зовут|я (.+))/i.test(userMessage)) {
                    const name = userMessage.match(/меня зовут|я (.+)/i)[1];
                    this.context.userName = name;
                    return `Приятно познакомиться, ${name}! 😊 Чем могу помочь?`;
                }
                return "Не совсем понял 🤔 Хотите пройти тест или показать список курсов?";
        }
    }

    sendMessage() {
        const text = this.input.value.trim();
        if (!text) return;
        
        this.input.value = '';
        this.appendMessage(text, 'user');
        this.showTypingIndicator();
        
        const delay = this.testSystem.isActive ? 400 : 800 + Math.random() * 800;
        
        setTimeout(() => {
            this.hideTypingIndicator();
            const response = this.generateAIResponse(text);
            if (response) {
                this.appendMessage(response, 'bot');
            }
            
            if (!this.testSystem.isActive && this.chatHistory.length <= 8) {
                setTimeout(() => this.showQuickReplies(), 500);
            }
        }, delay);
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    window.aiAssistant = new AIAssistant();
});
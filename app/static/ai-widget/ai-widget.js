// AI Assistant для SkillsSpire с актуальными данными
class AIAssistant {
    constructor() {
        this.config = {
            enableAI: true
        };
        
        // Актуальная база знаний по твоим курсам
        this.knowledgeBase = [
            {
                "title": "Бизнес-анализ и принятие решений", 
                "category": "Бизнес-аналитика",
                "price": "15 000 ₸",
                "originalPrice": "18 000 ₸",
                "description": "Научитесь принимать эффективные бизнес-решения на основе данных. Анализ рынка, оценка рисков и построение финансовых моделей.",
                "rating": "4.8"
            },
            {
                "title": "Стратегический менеджмент и бизнес-планирование", 
                "category": "Стратегический менеджмент",
                "price": "17 000 ₸",
                "originalPrice": "20 000 ₸",
                "description": "Освойте инструменты стратегического анализа и планирования для устойчивого роста вашей компании. От SWOT-анализа до разработки KPI.",
                "rating": "4.8"
            },
            {
                "title": "Финансовая грамотность для руководителей", 
                "category": "Управление финансами",
                "price": "12 000 ₸",
                "originalPrice": "15 000 ₸",
                "description": "Научитесь читать и анализировать финансовую отчетность, чтобы принимать обоснованные управленческие решения.",
                "rating": "4.8"
            }
        ];

        this.companyInfo = {
            name: "SkillsSpire",
            description: "Академическое качество в современном формате. Классика, переосмысленная для будущего.",
            email: "skillsspire@gmail.com",
            phone: "+7 (701) 292-55-68",
            instagram: "@skillsspire",
            linkedin: "SkillSpire Official",
            telegram: "@SkillsSpire",
            responseTime: "24 часа в рабочие дни (Пн-Пт с 9:00 до 18:00)"
        };
        
        this.chatHistory = [
            { role: "bot", text: "Привет! Я ваш помощник SkillsSpire 🎓\n\nЧем могу помочь?\n• Подобрать курс\n• Рассказать о программах\n• Ответить на вопросы\n• Дать контакты" }
        ];
        
        this.isFollowing = false;
        this.init();
    }
    
    init() {
        this.bindElements();
        this.bindEvents();
        console.log('🤖 ИИ помощник SkillsSpire загружен!');
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
        
        // Двойной клик для следования за курсором
        this.bubble?.addEventListener('dblclick', () => this.toggleFollowMode());
        
        // Закрытие по клику вне панели
        document.addEventListener('click', (e) => {
            if (this.panel?.contains(e.target) || this.bubble?.contains(e.target)) return;
            if (this.panel?.style.display === 'flex') {
                this.togglePanel();
            }
        });
        
        // Следование за курсором
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
            // Возвращаем в исходное положение
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
            "Какие курсы есть по бизнес-аналитике?",
            "Сколько стоит обучение?",
            "Как связаться с поддержкой?",
            "Расскажи о SkillsSpire"
        ];
        
        const quickDiv = document.createElement('div');
        quickDiv.className = 'ai-quick-replies';
        
        quickReplies.forEach(reply => {
            const btn = document.createElement('button');
            btn.textContent = reply;
            btn.onclick = () => {
                this.input.value = reply;
                this.sendMessage();
            };
            quickDiv.appendChild(btn);
        });
        
        this.messages.appendChild(quickDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }
    
    searchCourses(query) {
        const lowercaseQuery = query.toLowerCase();
        return this.knowledgeBase.filter(course => 
            course.title.toLowerCase().includes(lowercaseQuery) ||
            course.category.toLowerCase().includes(lowercaseQuery) ||
            course.description.toLowerCase().includes(lowercaseQuery)
        );
    }
    
    generateAIResponse(userMessage) {
        const lowerMessage = userMessage.toLowerCase();
        
        // Приветствие
        if (/(привет|здравств|добр|hi|hello|хай)/.test(lowerMessage)) {
            return `Привет! 👋 Я помощник SkillsSpire!\n\nМы предлагаем курсы бизнес-образования с академическим качеством:\n\n• Бизнес-анализ и аналитика\n• Стратегический менеджмент  \n• Финансовая грамотность\n\nЧем могу помочь?`;
        }
        
        // Курсы
        if (/(курс|обучен|программ|занят|урок)/.test(lowerMessage)) {
            const foundCourses = this.searchCourses(userMessage);
            
            if (foundCourses.length > 0) {
                let response = "🎯 Нашел подходящие курсы:\n\n";
                foundCourses.forEach(course => {
                    response += `📚 ${course.title}\n`;
                    response += `⭐ Рейтинг: ${course.rating}/5\n`;
                    response += `💰 Цена: ${course.price} (было ${course.originalPrice})\n`;
                    response += `📖 ${course.description}\n\n`;
                });
                response += "Подробнее на странице курса!";
                return response;
            }
            
            return `📚 Наши курсы:\n\n1. Бизнес-анализ и принятие решений - 15 000 ₸\n   • Анализ данных и финансовые модели\n\n2. Стратегический менеджмент - 17 000 ₸\n   • SWOT-анализ и KPI\n\n3. Финансовая грамотность - 12 000 ₸\n   • Управленческие решения\n\nКакой курс вас интересует?`;
        }
        
        // Цены
        if (/(цена|стоим|оплат|деньг|сколько|стоит)/.test(lowerMessage)) {
            return `💰 Стоимость курсов:\n\n• Бизнес-анализ: 15 000 ₸ (скидка!)\n• Стратегический менеджмент: 17 000 ₸\n• Финансовая грамотность: 12 000 ₸\n\n🎁 Все курсы со скидками! Подробности на страницах курсов.`;
        }
        
        // Контакты
        if (/(контакт|поддерж|помощ|связ|телефон|почт|email|instagram|telegram)/.test(lowerMessage)) {
            return `📞 Контакты SkillsSpire:\n\n📧 Email: ${this.companyInfo.email}\n📱 Телефон: ${this.companyInfo.phone}\n📸 Instagram: ${this.companyInfo.instagram}\n💼 LinkedIn: ${this.companyInfo.linkedin}\n✈️ Telegram: ${this.companyInfo.telegram}\n\n⏰ Время ответа: ${this.companyInfo.responseTime}`;
        }
        
        // О компании
        if (/(о.*компан|о.*вас|skillsspire|мисси|ценност)/.test(lowerMessage)) {
            return `🏫 О SkillsSpire:\n\n"${this.companyInfo.description}"\n\n• Академическое качество от профессоров с PhD\n• Практическое применение знаний\n• Более 100 выданных сертификатов\n• Бесплатное обучение для оценки качества\n• Партнёрства с университетами\n\nМы соединяем классическое образование с современными технологиями!`;
        }
        
        // Бесплатное обучение
        if (/(бесплат|free|подарок|акци)/.test(lowerMessage)) {
            return `🎁 Бесплатное обучение!\n\nДа, мы предлагаем бесплатные курсы как инвестицию в качество. Так вы можете оценить глубину и практичность нашего материала перед оплатой.\n\nОбратитесь к нам для получения доступа!`;
        }
        
        // Сертификаты
        if (/(сертифика|документ|подтвержден|диплом)/.test(lowerMessage)) {
            return `📜 Сертификация:\n\nПосле окончания курсов вы получаете сертификат, подтверждающий ваши компетенции. Уже более 100 студентов получили наши сертификаты!`;
        }
        
        // Бизнес-аналитика
        if (/(бизнес.*анализ|анализ.*данн|финансов.*модел|риск)/.test(lowerMessage)) {
            const course = this.knowledgeBase[0];
            return `📊 ${course.title}\n\n${course.description}\n\n⭐ Рейтинг: ${course.rating}/5\n💰 Цена: ${course.price} (скидка от ${course.originalPrice})\n\nИдеально для:\n• Менеджеров проектов\n• Аналитиков\n• Руководителей\n\nНаучитесь принимать решения на основе данных!`;
        }
        
        // Стратегический менеджмент
        if (/(стратеги|менеджмент|swot|kpi|планирован)/.test(lowerMessage)) {
            const course = this.knowledgeBase[1];
            return `🎯 ${course.title}\n\n${course.description}\n\n⭐ Рейтинг: ${course.rating}/5\n💰 Цена: ${course.price} (скидка от ${course.originalPrice})\n\nДля руководителей и собственников бизнеса!`;
        }
        
        // Финансы
        if (/(финанс|деньг|отчетност|бухгалтер)/.test(lowerMessage)) {
            const course = this.knowledgeBase[2];
            return `💼 ${course.title}\n\n${course.description}\n\n⭐ Рейтинг: ${course.rating}/5\n💰 Цена: ${course.price} (скидка от ${course.originalPrice})\n\nНаучитесь говорить с финансистами на одном языке!`;
        }
        
        // Умный ответ по умолчанию
        const smartResponses = [
            "Интересный вопрос! 🤔 Рекомендую посмотреть подробности на нашем сайте или связаться с поддержкой для точного ответа.",
            "Хороший вопрос! Чтобы дать максимально точный ответ, загляните в раздел 'Все курсы' или напишите нам напрямую.",
            "Понял ваш запрос! 📚 Для детальной информации рекомендую:\n• Посмотреть программы курсов\n• Почитать о нашей миссии\n• Написать в поддержку\n\nТак вы получите самую актуальную информацию!"
        ];
        
        return smartResponses[Math.floor(Math.random() * smartResponses.length)];
    }
    
    sendMessage() {
        const text = this.input.value.trim();
        if (!text) return;
        
        this.input.value = '';
        this.appendMessage(text, 'user');
        this.showTypingIndicator();
        
        setTimeout(() => {
            this.hideTypingIndicator();
            const response = this.generateAIResponse(text);
            this.appendMessage(response, 'bot');
            
            // Показываем быстрые ответы после некоторых сообщений
            if (this.chatHistory.length <= 6) {
                setTimeout(() => this.showQuickReplies(), 300);
            }
        }, 800 + Math.random() * 800);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.aiAssistant = new AIAssistant();
});
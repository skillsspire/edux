// AI Assistant Widget
class AIAssistant {
    constructor() {
        this.config = {
            kbUrl: "/static/ai-widget/kb.json",
            enableAI: true
        };
        
        this.knowledgeBase = [
            {
                "title": "Популярные направления", 
                "text": "Data Science, AI/ML, Веб-разработка, DevOps, Аналитика данных, Продукт-менеджмент, Маркетинг, Дизайн"
            },
            {
                "title": "Как начать обучение", 
                "text": "Выберите курс → Зарегистрируйтесь → Оплатите → Начните обучение в личном кабинете"
            },
            {
                "title": "Оплата и возврат", 
                "text": "Оплата картой, крипто или рассрочка. Возврат в течение 14 дней после покупки."
            },
            {
                "title": "Поддержка", 
                "text": "support@skillsspire.ru | Чат на сайте | Telegram: @skillsspire_support"
            }
        ];
        
        this.chatHistory = [
            { role: "bot", text: "Привет! Я ваш помощник по курсам SkillsSpire. Чем могу помочь? 🎓" }
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
        this.bubble.title = this.isFollowing ? 'Режим следования за курсором' : 'ИИ помощник';
        
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
            "Какие курсы есть по Data Science?",
            "Как оплатить обучение?",
            "Нужна помощь с выбором курса"
        ];
        
        const quickDiv = document.createElement('div');
        quickDiv.className = 'ai-quick-replies';
        quickDiv.style.marginTop = '10px';
        quickDiv.style.display = 'flex';
        quickDiv.style.flexDirection = 'column';
        quickDiv.style.gap = '8px';
        
        quickReplies.forEach(reply => {
            const btn = document.createElement('button');
            btn.textContent = reply;
            btn.style.padding = '8px 12px';
            btn.style.border = '1px solid #ddd';
            btn.style.borderRadius = '8px';
            btn.style.background = 'white';
            btn.style.cursor = 'pointer';
            btn.style.textAlign = 'left';
            btn.style.fontSize = '13px';
            btn.onclick = () => {
                this.input.value = reply;
                this.sendMessage();
            };
            btn.onmouseover = () => btn.style.background = '#f5f5f5';
            btn.onmouseout = () => btn.style.background = 'white';
            quickDiv.appendChild(btn);
        });
        
        this.messages.appendChild(quickDiv);
        this.messages.scrollTop = this.messages.scrollHeight;
    }
    
    searchKnowledge(query) {
        const lowercaseQuery = query.toLowerCase();
        const results = this.knowledgeBase.filter(item => 
            item.title.toLowerCase().includes(lowercaseQuery) || 
            item.text.toLowerCase().includes(lowercaseQuery)
        );
        
        return results.slice(0, 2);
    }
    
    generateAIResponse(userMessage) {
        const knowledge = this.searchKnowledge(userMessage);
        
        // Простые правила для демонстрации
        if (userMessage.toLowerCase().includes('привет') || userMessage.includes('здравств')) {
            return "Привет! Рад вас видеть! Расскажите, какой курс вас интересует? 🎯";
        }
        
        if (userMessage.toLowerCase().includes('курс') || userMessage.includes('обучен')) {
            if (knowledge.length > 0) {
                return `По вашему запросу нашел:\n${knowledge.map(k => `• ${k.title}: ${k.text}`).join('\n')}\n\nНужна более подробная информация?`;
            }
            return "У нас есть курсы по Data Science, AI, веб-разработке, маркетингу и дизайну. Какое направление вас интересует? 📚";
        }
        
        if (userMessage.toLowerCase().includes('оплат') || userMessage.includes('цена') || userMessage.includes('стоим')) {
            return "Оплатить можно картой, криптовалютой или в рассрочку. Стоимость курсов от 15 000 ₽. Есть возможность возврата в течение 14 дней. 💳";
        }
        
        if (userMessage.toLowerCase().includes('поддерж') || userMessage.includes('помощ') || userMessage.includes('контакт')) {
            return "Служба поддержки: support@skillsspire.ru | Чат на сайте | Telegram: @skillsspire_support 📞";
        }
        
        if (knowledge.length > 0) {
            return `Нашел информацию:\n${knowledge.map(k => `• ${k.title}: ${k.text}`).join('\n')}`;
        }
        
        return "Понял ваш вопрос! Для точного ответа свяжитесь с поддержкой: support@skillsspire.ru или задайте вопрос более конкретно о курсах. 🤔";
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
            
            if (this.chatHistory.length <= 4) {
                this.showQuickReplies();
            }
        }, 1000 + Math.random() * 1000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new AIAssistant();
});
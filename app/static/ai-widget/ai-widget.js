// ====== ES module (no Django tags / no <script> wrapper) ======
import { pipeline } from "https://cdn.jsdelivr.net/npm/@xenova/transformers@3.1.0";
import MiniSearch from "https://cdn.jsdelivr.net/npm/minisearch@7.1.0/dist/umd/index.min.js";

// ---- Config ----
const CONFIG = (globalThis.AI_WIDGET_CONFIG || {});
const KB_URL = CONFIG.kbUrl || "/static/ai-widget/kb.json";
const MODEL_ID = "Xenova/phi-3.1-mini-4k-instruct"; // можно заменить на webml-community/MiniThinky-v2

// ---- System prompt & few-shot ----
const SYSTEM_PROMPT = `Ты — вежливый ассистент сайта SkillsSpire. Отвечай кратко и по делу на русском.
Если вопрос непонятен — уточни. Если нет данных — скажи "не знаю".`;

const FEWSHOT = [
  { q: "Привет", a: "Привет! Чем могу помочь?" },
  { q: "Какие есть популярные направления?", a: "Data/AI, Аналитика, Продукт, DevOps, Маркетинг, Дизайн." }
];

// ---- State ----
let generator = null;
let loading = false;
let KB = [];
let mini = null;
const history = [];

// ---- DOM ----
const $ = (sel) => document.querySelector(sel);
const bubble   = $("#ai-bubble");
const panel    = $("#ai-panel");
const closeBtn = $("#ai-close");
const messages = $("#ai-messages");
const input    = $("#ai-text");
const send     = $("#ai-send");
const statusEl = $("#ai-status");

// ---- Load KB ----
try {
  fetch(KB_URL)
    .then((r) => r.ok ? r.json() : Promise.reject(new Error("KB fetch failed")))
    .then((data) => {
      KB = Array.isArray(data) ? data : [];
      mini = new MiniSearch({ fields: ["title", "text"], storeFields: ["title", "text"] });
      mini.addAll(KB);
    })
    .catch(() => { /* тихо игнорируем; виджет всё равно работает */ });
} catch { /* ignore */ }

// ---- Helpers ----
function kbSnippet(q, limit = 2) {
  if (!mini || !q) return "";
  const hits = mini.search(q, { boost: { title: 2 }, prefix: true }).slice(0, limit);
  return hits.length ? hits.map(h => `- ${h.title}: ${h.text}`).join("\n") : "";
}

function hist(n = 6) {
  return history.slice(-n).map(t => `${t.role === "user" ? "Пользователь" : "Ассистент"}: ${t.text}`).join("\n");
}

function buildPrompt(userText) {
  const demo = FEWSHOT.map(e => `Пользователь: ${e.q}\nАссистент: ${e.a}`).join("\n\n");
  const k = kbSnippet(userText);
  const h = hist(6);
  return `${SYSTEM_PROMPT}\n\n${demo}\n\nНедавний диалог:\n${h}\n\n${k ? ("Контекст сайта:\n" + k + "\n\n") : ""}Пользователь: ${userText}\nАссистент:`;
}

function append(text, who = "bot") {
  const d = document.createElement("div");
  d.className = `ai-msg ${who === "user" ? "ai-user" : "ai-bot"}`;
  d.textContent = text;
  messages.appendChild(d);
  messages.scrollTop = messages.scrollHeight;
}

function togglePanel() {
  if (!panel) return;
  const open = panel.style.display === "block";
  panel.style.display = open ? "none" : "block";
  if (!open) input?.focus();
}

// ---- Model load ----
async function ensureModel() {
  if (generator || loading) return;
  loading = true;
  try {
    const hasWebGPU = !!navigator.gpu;
    if (statusEl) statusEl.textContent = hasWebGPU ? "Загрузка модели (WebGPU)..." : "Загрузка (CPU, может быть медленнее)...";
    generator = await pipeline("text-generation", MODEL_ID, {
      device: hasWebGPU ? "webgpu" : "wasm",
      dtype: "q8",
      progress_callback: (p) => { if (statusEl) statusEl.textContent = `Загрузка: ${Math.round(p * 100)}%`; },
    });
    if (statusEl) statusEl.textContent = "Готово.";
  } catch (e) {
    console.error(e);
    if (statusEl) statusEl.textContent = "Ошибка загрузки модели.";
  } finally {
    loading = false;
  }
}

// ---- Chat ----
async function ask() {
  const text = (input?.value || "").trim();
  if (!text) return;
  input.value = "";
  append(text, "user");
  history.push({ role: "user", text });

  await ensureModel();
  if (!generator) { append("Не удалось инициализировать модель.", "bot"); return; }

  if (send) send.disabled = true;
  if (statusEl) statusEl.textContent = "Думаю…";

  try {
    const out = await generator(buildPrompt(text), {
      max_new_tokens: 180,
      temperature: 0.4,
      top_p: 0.9,
      repetition_penalty: 1.08,
    });
    const reply = Array.isArray(out) ? (out[0]?.generated_text ?? "") : String(out);
    const clean = (reply.split("Ассистент:").pop() || reply).trim();
    const finalText = clean || "Готово.";
    append(finalText, "bot");
    history.push({ role: "bot", text: finalText });
  } catch (e) {
    console.error(e);
    append("Ошибка генерации.", "bot");
  } finally {
    if (send) send.disabled = false;
    if (statusEl) statusEl.textContent = "";
  }
}

// ---- Events ----
bubble?.addEventListener("click", togglePanel);
closeBtn?.addEventListener("click", togglePanel);
send?.addEventListener("click", ask);
input?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
});
вс
"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("chat-form"), input = byId("message"), log = byId("messages");
const welcome = byId("welcome"), send = byId("send"), reset = byId("new-conversation");
const toggle = byId("technical-toggle"), errorBox = byId("connection-error");
let conversationId = null, busy = false, technical = false;

function scrollDown() { document.querySelector(".chat-area").scrollTop = document.querySelector(".chat-area").scrollHeight; }
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function setBusy(value) {
  busy = value;
  send.disabled = reset.disabled = value;
  input.disabled = value;
  document.querySelectorAll(".suggestion").forEach((button) => { button.disabled = value; });
  form.setAttribute("aria-busy", String(value));
}
function addMessage(role, text) {
  const article = element("article", `message ${role}`);
  if (role === "assistant") article.append(element("div", "avatar", "♪"));
  const body = element("div", "message-body");
  if (role === "assistant") {
    const label = element("div", "message-label", "Empório da Música");
    label.append(element("small", "", "assistente virtual"));
    body.append(label);
  }
  body.append(element("p", "message-text", text));
  article.append(body); log.append(article); scrollDown();
  return { article, body };
}
function addSources(body, sources) {
  if (!sources.length) return;
  const details = element("details", "sources");
  details.append(element("summary", "", `Fontes consultadas (${sources.length})`));
  const list = element("div", "source-list");
  sources.forEach((source) => {
    const item = element("div", "source-item");
    if (source.kind === "policy" && Number.isInteger(source.page_start)) {
      const anchor = element("a", "", source.label);
      anchor.href = `/manual#page=${source.page_start}`;
      anchor.target = "_blank"; anchor.rel = "noopener"; item.append(anchor);
    } else item.textContent = source.label;
    list.append(item);
  });
  details.append(list); body.append(details);
}
function addDiagnostics(body, data) {
  if (!data) return;
  const panel = element("section", "technical-panel");
  panel.hidden = !technical;
  panel.append(element("h3", "", "EXECUÇÃO DESTA MENSAGEM"));
  const elapsed = (data.elapsed_ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  panel.append(element("p", "technical-meta", `${data.provider} / ${data.model} · ${data.model_calls} chamada(s) ao modelo · ${elapsed}s`));
  if (data.input_tokens !== null && data.input_tokens !== undefined) {
    panel.append(element("p", "technical-meta", `Tokens reportados: ${data.input_tokens} entrada / ${data.output_tokens} saída`));
  }
  if (!data.tools.length) panel.append(element("p", "technical-meta", "Nenhuma ferramenta executada nesta mensagem."));
  data.tools.forEach((tool) => {
    const row = element("div", "tool-event");
    row.append(element("span", "", tool.tool), element("span", "", `${tool.status} · ${tool.duration_ms}ms`));
    panel.append(row);
  });
  body.append(panel);
}
async function ask(text) {
  if (busy || !text.trim()) return;
  errorBox.hidden = true; welcome.hidden = true;
  addMessage("user", text.trim());
  input.value = ""; input.style.height = "auto"; updateCount(); setBusy(true);
  const pending = addMessage("assistant", "");
  const dots = element("div", "typing");
  dots.setAttribute("role", "status"); dots.setAttribute("aria-label", "Consultando informações");
  for (let i = 0; i < 3; i++) dots.append(element("span"));
  pending.body.querySelector(".message-text").replaceWith(dots);
  pending.body.append(element("p", "typing-status", "Consultando as informações para você…"));
  scrollDown();
  try {
    const response = await fetch("/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text.trim(), conversation_id: conversationId }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 404) conversationId = null;
      throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível enviar a mensagem. Tente novamente.");
    }
    conversationId = data.conversation_id;
    pending.article.remove();
    const result = addMessage("assistant", data.answer);
    if (data.status === "unavailable") result.article.classList.add("unavailable");
    addSources(result.body, data.sources || []);
    addDiagnostics(result.body, data.diagnostics);
  } catch (error) {
    pending.article.remove();
    errorBox.textContent = error.message === "Failed to fetch" ? "A conexão com o atendimento foi interrompida. Confira se o servidor está aberto e tente novamente." : error.message;
    errorBox.hidden = false;
    input.value = text; updateCount();
  } finally {
    setBusy(false); input.focus(); scrollDown();
  }
}
function updateCount() { byId("character-count").textContent = `${input.value.length.toLocaleString("pt-BR")} / 2.000`; }
form.addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 130)}px`; updateCount(); });
input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); ask(input.value); } });
document.querySelectorAll(".suggestion").forEach((button) => { button.addEventListener("click", () => ask(button.dataset.question)); });
toggle.addEventListener("click", () => {
  technical = !technical; toggle.setAttribute("aria-pressed", String(technical));
  document.querySelectorAll(".technical-panel").forEach((panel) => { panel.hidden = !technical; });
});
reset.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true); errorBox.hidden = true;
  try {
    if (conversationId) {
      const response = await fetch(`/conversations/${conversationId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Não foi possível limpar a conversa. Tente novamente.");
    }
    conversationId = null; log.replaceChildren(); welcome.hidden = false; input.value = ""; updateCount();
  } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; }
  finally { setBusy(false); input.focus(); }
});
fetch("/health").then((response) => response.json()).then((data) => {
  toggle.hidden = !data.diagnostics_enabled;
}).catch(() => { errorBox.textContent = "O servidor de atendimento ainda não está disponível. Recarregue a página quando ele estiver pronto."; errorBox.hidden = false; });

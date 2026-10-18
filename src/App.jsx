import React, { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  BookOpen,
  MessageSquare,
  FileText,
  Plus,
  Search,
  LogOut,
  Send,
  Download,
  Trash2,
  Pencil,
  X,
  LoaderCircle,
  Check,
  Languages,
  Layers,
  ShieldCheck,
  Sparkles,
  Menu,
  Palette,
  FolderOpen,
  PanelLeft,
  History,
  ChevronRight,
  Info,
} from "lucide-react";
import Landing from "./marketing/Landing.jsx";
import {
  ChatMessage,
  ChatWelcome,
  ChatComposer,
  Typing,
  LibraryInspector,
  JumpToLatest,
} from "./workspace/ChatUI.jsx";
import "./workspace/workspace.css";
import { Avatar, AvatarPicker } from "./workspace/AvatarUI.jsx";
import "./workspace/avatars.css";
import ImportProgress from "./workspace/ImportProgress.jsx";
import { uploadPdf, validateImportFiles, importQueue } from "./workspace/importUpload.mjs";
import { THEMES, getTheme, themeStyle } from "../shared/themes.mjs";

import { api } from "./workspace/apiClient.mjs";
const langs = {
  vi: "Tiếng Việt",
  en: "English",
  fr: "Français",
  de: "Deutsch",
  es: "Español",
  pt: "Português",
  it: "Italiano",
  nl: "Nederlands",
  ru: "Русский",
  uk: "Українська",
  ja: "日本語",
  ko: "한국어",
  "zh-CN": "中文（简体）",
  "zh-TW": "中文（繁體）",
  th: "ไทย",
  id: "Bahasa Indonesia",
  tr: "Türkçe",
  ar: "العربية",
  hi: "हिन्दी",
};
function Brand() {
  return (
    <span className="brand">
      <span className="brand-icon">
        <Layers size={20} />
      </span>
      BIG<span className="brand-light">RAG</span>
      <span className="brand-dot">.</span>
    </span>
  );
}
function Language({ value, onChange, auto = false }) {
  return (
    <select
      aria-label="Ngôn ngữ"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {auto && <option value="auto">Tự nhận diện</option>}
      {Object.entries(langs).map(([key, name]) => (
        <option key={key} value={key}>
          {name}
        </option>
      ))}
    </select>
  );
}
function Auth({ mode, close, setMode, onUser }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const form = new FormData(e.currentTarget),
        result = await api("/auth/" + mode, {
          method: "POST",
          body: Object.fromEntries(form),
        });
      onUser(result.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <section
        className="auth-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
      >
        <button className="close" aria-label="Đóng" onClick={close}>
          <X size={20} />
        </button>
        <Brand />
        <div className="eyebrow">KHÔNG GIAN CỦA BẠN</div>
        <h2 id="auth-title">
          {mode === "register"
            ? "Bắt đầu hành trình mới."
            : "Chào mừng trở lại."}
        </h2>
        <p>
          {mode === "register"
            ? "Tạo tài khoản để lưu tài liệu và những cuộc trò chuyện của riêng bạn."
            : "Tiếp tục học tập từ nơi bạn đã dừng lại."}
        </p>
        <form onSubmit={submit}>
          {mode === "register" && (
            <label>
              Tên của bạn
              <input
                name="name"
                autoComplete="name"
                required
                maxLength={80}
                placeholder="Nguyễn Minh"
              />
            </label>
          )}
          <label>
            Email
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="ban@example.com"
              maxLength={254}
            />
          </label>
          <label>
            Mật khẩu
            <input
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              placeholder={
                mode === "register"
                  ? "Ít nhất 8 ký tự"
                  : "Nhập mật khẩu của bạn"
              }
            />
          </label>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <button className="primary large full" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ArrowRight size={18} />
            )}{" "}
            {mode === "register" ? "Tạo tài khoản" : "Đăng nhập"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "register" ? "Đã có tài khoản?" : "Chưa có tài khoản?"}{" "}
          <button
            className="text-button"
            onClick={() => {
              setError("");
              setMode(mode === "register" ? "login" : "register");
            }}
          >
            {mode === "register" ? "Đăng nhập" : "Đăng ký ngay"}
          </button>
        </p>
      </section>
    </div>
  );
}

function Workspace({ user, logout, onUserChange }) {
  const [topics, setTopics] = useState([]),
    [topic, setTopic] = useState(""),
    [view, setView] = useState("chat"),
    [chats, setChats] = useState([]),
    [search, setSearch] = useState(""),
    [conversation, setConversation] = useState(null),
    [docs, setDocs] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [question, setQuestion] = useState(""),
    [language, setLanguage] = useState("vi"),
    [modal, setModal] = useState(null),
    [avatarModal, setAvatarModal] = useState(null),
    [newName, setNewName] = useState(""),
    [botDraft, setBotDraft] = useState("BIGRAG"),
    [themeDraft, setThemeDraft] = useState("mint"),
    [mobile, setMobile] = useState(false),
    [smallScreen, setSmallScreen] = useState(
      () => window.matchMedia("(max-width: 860px)").matches,
    ),
    [collapsed, setCollapsed] = useState(false),
    [inspector, setInspector] = useState(false),
    [sending, setSending] = useState(false),
    [awayFromBottom, setAwayFromBottom] = useState(false),
    [docsLoading, setDocsLoading] = useState(false),
    [importJob, setImportJob] = useState(null);
  const [files, setFiles] = useState([]),
    [forceOcr, setForceOcr] = useState(false),
    [translatePdf, setTranslatePdf] = useState(false),
    [sourceLang, setSourceLang] = useState("auto"),
    [preview, setPreview] = useState(null),
    [page, setPage] = useState(0),
    [editText, setEditText] = useState(""),
    [translationInput, setTranslationInput] = useState(""),
    [translationOutput, setTranslationOutput] = useState(""),
    [provider, setProvider] = useState("groq"),
    [quality, setQuality] = useState("careful"),
    [domain, setDomain] = useState(""),
    [glossary, setGlossary] = useState("");
  const composerRef = useRef(null),
    chatScroll = useRef(null),
    nearBottom = useRef(true),
    lastConversation = useRef(null),
    end = useRef(null),
    topicRef = useRef(topic),
    requestRef = useRef(0),
    importController = useRef(null),
    importCounter = useRef(0);
  const isImporting = !!importJob && !importJob.finished;
  topicRef.current = topic;
  useEffect(() => () => importController.current?.abort(), []);
  async function loadTopics() {
    const result = await api("/topics");
    setTopics(result.topics);
    setTopic((old) => result.topics.some((item) => item.id === old) ? old : result.topics[0]?.id || "");
  }
  async function loadChats() {
    const result = await api(
      "/conversations?" +
        new URLSearchParams({
          ...(topic ? { topic } : {}),
          ...(search ? { search } : {}),
        }),
    );
    if (topicRef.current === topic) setChats(result.conversations);
  }
  async function loadDocs() {
    if (!topic) { setDocsLoading(false); return; }
    const selected = topic;
    setDocsLoading(true);
    try {
      const result = await api(
        "/documents?topic=" + encodeURIComponent(selected),
      );
      if (topicRef.current === selected) setDocs(result.documents);
    } finally {
      if (topicRef.current === selected) setDocsLoading(false);
    }
  }
  useEffect(() => {
    loadTopics().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 860px)");
    const update = () => {
      setSmallScreen(query.matches);
      if (!query.matches) setMobile(false);
    };
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    setConversation(null);
    setDocs([]);
    loadChats().catch((e) => setError(e.message));
    loadDocs().catch((e) => setError(e.message));
  }, [topic]);
  useEffect(() => {
    const timer = setTimeout(
      () => loadChats().catch((e) => setError(e.message)),
      200,
    );
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (lastConversation.current !== conversation?.id || nearBottom.current) {
      end.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }
    lastConversation.current = conversation?.id;
  }, [conversation?.messages, conversation?.id, sending]);
  useEffect(() => {
    const onEscape = (event) => {
      if (event.key !== "Escape") return;
      setMobile(false);
      setInspector(false);
      if (!busy) {
        if (avatarModal) setAvatarModal(null);
        else setModal(null);
      }
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [busy, avatarModal]);
  function selectView(next) {
    setView(next);
    setInspector(false);
    setMobile(false);
  }
  function openTopic() {
    setNewName("");
    setModal({ type: "topic" });
  }
  function suggest(text) {
    setQuestion(text);
    composerRef.current?.focus();
  }
  function watchScroll(event) {
    const node = event.currentTarget;
    nearBottom.current =
      node.scrollHeight - node.scrollTop - node.clientHeight < 160;
    setAwayFromBottom(!nearBottom.current);
  }
  function jumpToLatest() {
    nearBottom.current = true;
    end.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "end",
    });
    setAwayFromBottom(false);
  }
  function downloadChat() {
    if (!conversation?.messages?.length) return;
    const blob = new Blob(
      [
        conversation.messages
          .map(
            (m) => `${m.role === "user" ? user.name : botName}: ${m.content}`,
          )
          .join("\n\n"),
      ],
      { type: "text/plain;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob),
      link = document.createElement("a");
    link.href = url;
    link.download = "bigrag-chat.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function work(action) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function openChat(chat) {
    const version = ++requestRef.current;
    await work(async () => {
      const result = await api("/conversations/" + chat.id);
      if (version === requestRef.current) {
        setConversation(result);
        setView("chat");
        setMobile(false);
      }
    });
  }
  function newChat() {
    requestRef.current++;
    setConversation(null);
    setView("chat");
    setMobile(false);
    setQuestion("");
  }
  async function send(e) {
    e.preventDefault();
    if (!question.trim() || !topic || busy || !canChat) return;
    const text = question.trim();
    nearBottom.current = true;
    setSending(true);
    try {
      await work(async () => {
        let chat = conversation;
        if (!chat) {
          chat = await api("/conversations", {
            method: "POST",
            body: { topic },
          });
          setConversation({ ...chat, messages: [] });
        }
        setQuestion("");
        setConversation((old) => ({
          ...old,
          messages: [
            ...(old?.messages || []),
            { role: "user", content: text, pending: true },
          ],
        }));
        try {
          await api("/conversations/" + chat.id + "/messages", {
            method: "POST",
            body: { question: text, answer_language: language },
          });
        } catch (e) {
          setQuestion(text);
          throw e;
        } finally {
          setConversation(await api("/conversations/" + chat.id));
          await loadChats();
        }
      });
    } finally {
      setSending(false);
      requestAnimationFrame(() => composerRef.current?.focus());
    }
  }
  async function saveName(e) {
    e.preventDefault();
    await work(async () => {
      if (modal?.type === "topic") {
        const made = await api("/topics", {
          method: "POST",
          body: { name: newName },
        });
        await loadTopics();
        setTopic(made.id);
      } else {
        await api("/conversations/" + modal.chat.id, {
          method: "PATCH",
          body: { title: newName },
        });
        if (conversation?.id === modal.chat.id)
          setConversation((old) => ({ ...old, title: newName }));
        await loadChats();
      }
      setModal(null);
      setNewName("");
    });
  }
  async function saveAppearance(e) {
    e.preventDefault();
    await work(async () => {
      await api("/topics/" + encodeURIComponent(topic) + "/preferences", {
        method: "PATCH",
        body: { bot_name: botDraft, theme: themeDraft },
      });
      await loadTopics();
      setModal(null);
    });
  }
  function openAppearance() {
    setBotDraft(botName);
    setThemeDraft(chatTheme.id);
    setModal({ type: "appearance" });
  }
  function openBotAvatar() {
    setAvatarModal({
      bot: true,
      topic,
      name: botName,
      avatar: active?.avatar,
      library: active?.name,
    });
  }
  async function saveAvatar(selection, file) {
    setBusy(true);
    try {
      if (selection.preset === "custom" && !file) {
        setAvatarModal(null);
        return;
      }
      const endpoint = avatarModal.bot
        ? `/topics/${encodeURIComponent(avatarModal.topic)}/avatar`
        : "/avatars/profile";
      let body = { preset: selection.preset };
      if (file) {
        body = new FormData();
        body.append("image", file);
      }
      const result = await api(endpoint + (file ? "/image" : ""), {
        method: file ? "POST" : "PUT",
        body,
      });
      if (avatarModal.bot) await loadTopics();
      else onUserChange(result.user);
      setAvatarModal(null);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    await work(async () => {
      if (modal.type === "delete-topic") {
        const deleted = modal.topic.id;
        await api("/topics/" + encodeURIComponent(deleted), { method: "DELETE" });
        setTopics((items) => items.filter((item) => item.id !== deleted));
        if (topic === deleted) {
          setTopic(topics.find((item) => item.id !== deleted)?.id || "");
          newChat();
          setDocs([]);
          setChats([]);
          setFiles([]);
          setDocsLoading(false);
        }
        setPreview((current) => current?.topic === deleted ? null : current);
        setImportJob((current) => current?.topic === deleted ? null : current);
        setNotice("Đã xóa thư viện “" + modal.topic.name + "”.");
      } else if (modal.type === "delete-doc") {
        await api("/documents/" + modal.doc.id, { method: "DELETE" });
        await loadDocs();
        await loadTopics();
      } else {
        await api("/conversations/" + modal.chat.id, { method: "DELETE" });
        if (conversation?.id === modal.chat.id) newChat();
        await loadChats();
      }
      setModal(null);
    });
  }
  async function runPdfJob(mode, selectedFiles, operation) {
    if (importController.current) return;
    const controller = new AbortController();
    importController.current = controller;
    const id = ++importCounter.current;
    setError("");
    setNotice("");
    setImportJob({
      id, mode, topic, topicName: topics.find((item) => item.id === topic)?.name || "Thư viện",
      startedAt: Date.now(), finished: false,
      items: selectedFiles.map((file) => ({ name: file.name, sourceFile: file, status: "queued", upload: 0 })),
    });
    try {
      const results = await importQueue(selectedFiles,
        (file, progress) => operation(file, progress, controller.signal),
        (index, patch) => setImportJob((old) => old?.id === id ? {
          ...old, items: old.items.map((item, i) => i === index ? { ...item, ...patch } : item),
        } : old), controller.signal);
      setImportJob((old) => old?.id === id ? { ...old, finished: true, endedAt: Date.now() } : old);
      return results;
    } catch (error) {
      if (error.name !== "AbortError") setError(error.message);
    } finally {
      if (importController.current === controller) importController.current = null;
    }
  }
  function openImportProgress() {
    const result = importJob.items[0]?.result?.preview;
    if (result && preview?.id !== result.id) {
      setPreview({ ...result, topic: importJob.topic });
      setPage(0);
      setEditText(result.pages[0]?.translation || result.pages[0]?.original || "");
    }
    if (importJob.finished && importJob.mode === "import") {
      setFiles(importJob.items.filter((item) => item.status === "error").map((item) => item.sourceFile));
    }
    setTopic(importJob.topic);
    selectView("docs");
  }
  async function importFiles() {
    if (importController.current) return;
    try {
      validateImportFiles(files, translatePdf);
    } catch (error) {
      setError(error.message);
      return;
    }
    const selectedTopic = topic;
    const selectedFiles = [...files];
    const preparingPreview = translatePdf;
    const results = await runPdfJob(preparingPreview ? "preview" : "import", selectedFiles, async (file, progress, signal) => {
      const form = new FormData();
      form.set("topic", selectedTopic);
      form.set("force_ocr", String(forceOcr));
      if (preparingPreview) {
        form.set("source_language", sourceLang);
        form.set("target_language", language);
        form.set("provider", provider);
        form.set("quality", quality);
        form.set("domain", provider === "groq" ? domain : "");
        form.set("glossary", provider === "groq" ? glossary : "");
        form.append("file", file);
        const result = await uploadPdf("/previews", form, progress, signal);
        return { file: file.name, status: "ready", preview: result };
      } else {
        form.append("files", file);
        const result = await uploadPdf("/ingest", form, progress, signal);
        if (!result.results?.[0]) throw new Error("Chưa nhận được kết quả nhập PDF. Kiểm tra thư viện trước khi thử lại.");
        return result.results[0];
      }
    });
    if (!results) return;
    if (preparingPreview && results[0]?.preview) {
      const result = results[0].preview;
      setPreview({ ...result, topic: selectedTopic });
      setPage(0);
      setEditText(result.pages[0]?.translation || result.pages[0]?.original || "");
    } else if (!preparingPreview) {
      setFiles(topicRef.current === selectedTopic ? selectedFiles.filter((file, index) => results[index].status === "error") : []);
      try {
        if (topicRef.current === selectedTopic) await loadDocs();
        await loadTopics();
      } catch (error) {
        setError("PDF đã được xử lý, nhưng chưa tải lại được thư viện: " + error.message);
      }
    }
  }
  async function savePage(savedPreview = preview, text = editText, pageIndex = page) {
    const result = await api("/previews/" + savedPreview.id, {
      method: "PATCH",
      body: { page: savedPreview.pages[pageIndex].page, text },
    });
    setPreview((old) => old?.id === savedPreview.id ? { ...result, topic: savedPreview.topic } : old);
    return result;
  }
  async function confirmPreview(mode) {
    const savedPreview = preview;
    const results = await runPdfJob("confirm", [{ name: savedPreview.file }], async (_, progress) => {
      progress(100);
      await savePage(savedPreview);
      return await api("/previews/" + savedPreview.id + "/import", {
        method: "POST",
        body: { index_mode: mode },
      });
    });
    if (results?.length && results[0].status !== "error") {
      setPreview((old) => old?.id === savedPreview.id ? null : old);
      setFiles([]);
      try {
        if (topicRef.current === savedPreview.topic) await loadDocs();
        await loadTopics();
      } catch (error) {
        setError("PDF đã được xử lý, nhưng chưa tải lại được thư viện: " + error.message);
      }
    }
  }
  const translationSettings = (
    <details className="translation-settings">
      <summary>Tùy chỉnh bản dịch</summary>
      <div className="translation-settings-grid">
        <label>
          Bộ dịch
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="groq">Groq</option>
            <option value="google">Google Cloud Translation</option>
          </select>
        </label>
        <label>
          Chất lượng
          <select
            disabled={provider !== "groq"}
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
          >
            <option value="careful">Có lượt rà soát</option>
            <option value="fast">Nhanh · một lượt</option>
          </select>
        </label>
        <label>
          Chuyên ngành
          <input
            disabled={provider !== "groq"}
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="Ví dụ: Machine Learning"
          />
        </label>
        <label>
          Thuật ngữ
          <textarea
            disabled={provider !== "groq"}
            value={glossary}
            onChange={(e) => setGlossary(e.target.value)}
            placeholder="Từ gốc = từ đích"
            rows={2}
          />
        </label>
      </div>
    </details>
  );
  const active = topics.find((t) => t.id === topic),
    botName = active?.bot_name || "BIGRAG",
    chatTheme = getTheme(active?.theme),
    pdfTotal = topics.reduce((n, t) => n + Number(t.pdf_count), 0),
    canChat = !!topic && docs.some((d) => d.status === "ready");
  useEffect(() => {
    document.title = `${botName} · BIGRAG`;
  }, [botName]);
  const historyGroups = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  for (const chat of chats) {
    const updated = new Date(chat.updated_at);
    const title =
      updated >= today
        ? "Hôm nay"
        : updated >= yesterday
          ? "Hôm qua"
          : "Trước đó";
    let group = historyGroups.find((g) => g.title === title);
    if (!group) {
      group = { title, chats: [] };
      historyGroups.push(group);
    }
    group.chats.push(chat);
  }
  return (
    <div
      className={
        "workspace " +
        (collapsed ? "ws-sidebar-collapsed " : "") +
        (inspector ? "ws-has-inspector" : "")
      }
      style={themeStyle(chatTheme)}
    >
      {mobile && (
        <button
          className="ws-sidebar-backdrop"
          aria-label="Đóng menu thư viện"
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        id="workspace-sidebar"
        className={"sidebar " + (mobile ? "is-open" : "")}
        aria-label="Thư viện và lịch sử"
      >
        <div className="side-brand">
          {collapsed ? (
            <span className="ws-mini-brand">
              <Layers size={23} />
            </span>
          ) : (
            <Brand />
          )}
          <button
            className="icon mobile-close"
            onClick={() => setMobile(false)}
            aria-label="Đóng menu"
          >
            <X size={20} />
          </button>
        </div>
        <button
          className="primary new-chat"
          disabled={!topic || busy}
          onClick={newChat}
          aria-label="Cuộc trò chuyện mới"
          title="Cuộc trò chuyện mới"
        >
          <Plus size={19} />
          <span className="ws-sidebar-label">Cuộc trò chuyện mới</span>
        </button>
        <div className="side-section">
          <span>
            THƯ VIỆN <small>{topics.length}</small>
          </span>
          <button
            aria-label="Thêm chủ đề"
            title="Thêm thư viện"
            disabled={busy}
            className="icon"
            onClick={openTopic}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="topic-list">
          {topics.map((t) => (
            <div className="ws-topic-row" key={t.id}>
            <button
              disabled={busy}
              className={"topic-item " + (topic === t.id ? "selected" : "")}
              aria-pressed={topic === t.id}
              aria-label={t.name}
              title={t.name}
              onClick={() => {
                setTopic(t.id);
                newChat();
              }}
            >
              <span
                className="ws-topic-cover"
                style={{ "--folder-accent": getTheme(t.theme).accent }}
              >
                <FolderOpen size={19} />
              </span>
              <span className="ws-topic-text">
                <b>{t.name}</b>
                <small>{t.pdf_count} tài liệu</small>
              </span>
              {topic === t.id && <ChevronRight size={13} />}
            </button>
            <button
              className="icon ws-topic-delete"
              aria-label={"Xóa thư viện " + t.name}
              title={isImporting && importJob.topic === t.id ? "Chờ import xong để xóa thư viện" : "Xóa thư viện " + t.name}
              disabled={busy || (isImporting && importJob.topic === t.id)}
              onClick={() => { setError(""); setModal({ type: "delete-topic", topic: t }); }}
            >
              <Trash2 size={15} />
            </button>
            </div>
          ))}
          {!topics.length && (
            <p className="side-empty">Thêm thư viện để bắt đầu.</p>
          )}
        </div>
        {collapsed && (
          <button
            className="ws-rail-history"
            aria-label="Mở lịch sử trò chuyện"
            title="Mở lịch sử"
            onClick={() => setCollapsed(false)}
          >
            <History size={20} />
          </button>
        )}
        <div className="side-section ws-history-label">
          <span>LỊCH SỬ TRÒ CHUYỆN</span>
          <History size={15} />
        </div>
        <div className="search">
          <Search size={15} />
          <input
            aria-label="Tìm lịch sử"
            placeholder="Tìm cuộc trò chuyện…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              className="icon"
              aria-label="Xóa tìm kiếm"
              onClick={() => setSearch("")}
            >
              <X size={13} />
            </button>
          )}
        </div>
        <div className="chat-list">
          {historyGroups.map((group) => (
            <div key={group.title} className="ws-history-group">
              <h3>{group.title}</h3>
              {group.chats.map((chat) => (
                <div
                  key={chat.id}
                  className={
                    "chat-row " +
                    (conversation?.id === chat.id ? "selected" : "")
                  }
                >
                  <button
                    className="chat-title"
                    disabled={busy}
                    onClick={() => openChat(chat)}
                    title={chat.title}
                  >
                    <MessageSquare size={15} />
                    <span>{chat.title}</span>
                  </button>
                  <div className="ws-chat-row-actions">
                    <button
                      className="icon"
                      aria-label={"Đổi tên " + chat.title}
                      disabled={busy}
                      onClick={() => {
                        setModal({ type: "rename", chat });
                        setNewName(chat.title);
                      }}
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className="icon"
                      aria-label={"Xóa " + chat.title}
                      disabled={busy}
                      onClick={() => setModal({ type: "delete-chat", chat })}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
          {!chats.length && (
            <div className="ws-history-empty">
              <MessageSquare size={22} />
              <b>{search ? "Chưa tìm thấy chat" : "Một câu hỏi để bắt đầu"}</b>
              <p>
                {search
                  ? "Thử từ khóa khác nhé."
                  : "Cuộc trò chuyện sẽ được lưu ở đây."}
              </p>
            </div>
          )}
        </div>
        <div className="ws-side-stats">
          <ShieldCheck size={12} />
          <span>{pdfTotal} PDF · Thư viện riêng</span>
        </div>
        <div className="profile">
          <button
            className="avatar profile-avatar-button"
            aria-label="Đổi avatar của bạn"
            title="Đổi avatar của bạn"
            disabled={busy}
            onClick={() =>
              setAvatarModal({
                bot: false,
                name: user.name,
                avatar: user.avatar,
              })
            }
          >
            <Avatar avatar={user.avatar} name={user.name} />
            <span className="profile-avatar-edit">
              <Pencil size={8} />
            </span>
          </button>
          <div>
            <b>{user.name}</b>
            <small>{user.email}</small>
          </div>
          <button
            className="icon"
            aria-label="Đăng xuất"
            title="Đăng xuất"
            disabled={busy || isImporting}
            onClick={logout}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <main className="workspace-main" data-chat-view={view}>
        <header className="workspace-header">
          <button
            className="icon ws-sidebar-toggle"
            aria-label={
              collapsed
                ? "Mở rộng thư viện và lịch sử"
                : "Thu gọn hoặc mở menu thư viện"
            }
            aria-controls="workspace-sidebar"
            aria-expanded={smallScreen ? mobile : !collapsed}
            onClick={() => {
              if (window.matchMedia("(max-width: 860px)").matches) {
                setCollapsed(false);
                setMobile((v) => !v);
              } else setCollapsed((v) => !v);
            }}
            title="Thư viện và lịch sử"
          >
            <PanelLeft size={21} />
          </button>
          <div className="ws-header-identity">
            <button
              className="ws-agent-avatar"
              aria-label="Đổi avatar bot của thư viện"
              title="Đổi avatar bot"
              disabled={!topic || busy}
              onClick={openBotAvatar}
            >
              <Avatar avatar={active?.avatar} name={botName} bot />
              <i />
            </button>
            <div>
              <h1>{botName}</h1>
              <p>
                <FolderOpen size={12} />
                {active?.name || "Không gian học tập"}
                <span>· {active?.pdf_count || 0} PDF</span>
              </p>
            </div>
          </div>
          <div className="ws-header-actions">
            <button
              className="appearance-button"
              aria-label="Cá nhân hóa thư viện"
              title="Biệt danh & theme"
              disabled={!topic || busy}
              onClick={openAppearance}
            >
              <Palette size={17} />
              <span>Cá nhân hóa</span>
            </button>
            <button
              className={"icon ws-info-button " + (inspector ? "active" : "")}
              aria-label="Thông tin thư viện"
              title="Thông tin thư viện"
              aria-pressed={inspector}
              disabled={!topic}
              onClick={() => setInspector((v) => !v)}
            >
              <Info size={20} />
            </button>
          </div>
        </header>
        <div className="workspace-toolbar">
          <div className="tabs" aria-label="Công cụ thư viện">
            {[
              ["chat", MessageSquare, "Trò chuyện"],
              ["docs", FileText, "Tài liệu"],
              ["translate", Languages, "Dịch văn bản"],
            ].map(([key, Icon, name]) => (
              <button
                key={key}
                disabled={busy}
                className={view === key ? "active" : ""}
                aria-pressed={view === key}
                onClick={() => selectView(key)}
              >
                <Icon size={16} />
                {name}
                {key === "docs" && <span>{active?.pdf_count || 0}</span>}
              </button>
            ))}
          </div>
          <div className="toolbar-actions">
            <span className="ws-language-label">Trả lời bằng</span>
            <Language value={language} onChange={setLanguage} />
          </div>
        </div>
        {error && (
          <div className="banner error" role="alert">
            {error}
            <button className="icon" onClick={() => setError("")}>
              <X size={15} />
            </button>
          </div>
        )}
        {notice && (
          <div className="banner success" role="status">
            {notice}
            <button className="icon" onClick={() => setNotice("")}>
              <X size={15} />
            </button>
          </div>
        )}
        {importJob && (view !== "docs" || topic !== importJob.topic) && (
          <ImportProgress
            job={importJob}
            compact
            onOpen={openImportProgress}
            onDismiss={() => setImportJob(null)}
          />
        )}
        {view === "chat" && (
          <>
            <div className="ws-chat-area">
              <div
                className="chat-content"
                ref={chatScroll}
                onScroll={watchScroll}
              >
                {!conversation?.messages?.length ? (
                  <>
                    {docsLoading ? (
                      <div className="ws-chat-loading" role="status">
                        <LoaderCircle className="spin" size={24} />
                        Đang mở thư viện…
                      </div>
                    ) : (
                      <ChatWelcome
                        user={user}
                        botName={botName}
                        active={active}
                        documents={docs}
                        busy={busy}
                        onSuggest={suggest}
                        onDocuments={() => selectView("docs")}
                        onTopic={openTopic}
                      />
                    )}
                  </>
                ) : (
                  <div className="messages">
                    <div className="conversation-heading">
                      <div>
                        <span className="ws-thread-label">CUỘC TRÒ CHUYỆN</span>
                        <h2>{conversation.title}</h2>
                      </div>
                      <div className="ws-thread-actions">
                        <button
                          className="icon"
                          disabled={busy}
                          aria-label="Đổi tên hội thoại đang xem"
                          title="Đổi tên"
                          onClick={() => {
                            setNewName(conversation.title);
                            setModal({ type: "rename", chat: conversation });
                          }}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon"
                          aria-label="Tải lịch sử"
                          title="Tải hội thoại"
                          onClick={downloadChat}
                        >
                          <Download size={17} />
                        </button>
                      </div>
                    </div>
                    {conversation.messages.map((message, i) => (
                      <ChatMessage
                        key={message.id || i}
                        message={message}
                        user={user}
                        botName={botName}
                        botAvatar={active?.avatar}
                        documents={docs}
                      />
                    ))}
                    {sending && (
                      <Typing botName={botName} botAvatar={active?.avatar} />
                    )}
                    <div ref={end} />
                  </div>
                )}
              </div>
              {awayFromBottom && conversation?.messages?.length > 0 && (
                <JumpToLatest onClick={jumpToLatest} />
              )}
            </div>
            <ChatComposer
              inputRef={composerRef}
              question={question}
              setQuestion={setQuestion}
              botName={botName}
              topic={topic}
              canChat={canChat}
              language={language}
              languageName={langs[language]}
              busy={busy}
              sending={sending}
              onSubmit={send}
              onDocuments={() => selectView("docs")}
            />
          </>
        )}
        {view === "docs" && (
          <div className="panel-content">
            <div className="page-title">
              <div>
                <span className="eyebrow">THƯ VIỆN RIÊNG</span>
                <h2>Tài liệu của bạn</h2>
                <p>Tất cả PDF được lưu theo tài khoản và chủ đề.</p>
              </div>
              <span className="count-badge">{docs.length} tài liệu</span>
            </div>
            {!topic ? (
              <button
                className="primary"
                onClick={() => setModal({ type: "topic" })}
              >
                <Plus size={18} /> Tạo chủ đề đầu tiên
              </button>
            ) : (
              <>
                <section className="upload-card">
                  <label className="drop-zone">
                    <span className="upload-icon">
                      <FileText size={24} />
                    </span>
                    <b>
                      {files.length
                        ? `${files.length} PDF đã chọn`
                        : "Thêm tài liệu vào thư viện"}
                    </b>
                    <span>Chọn PDF · Tối đa 50 MB / file, 75 MB / lượt</span>
                    <input
                      aria-label="Chọn PDF"
                      type="file"
                      accept="application/pdf,.pdf"
                      multiple={!translatePdf}
                      disabled={busy || isImporting}
                      onChange={(e) =>
                        setFiles(Array.from(e.target.files || []))
                      }
                    />
                    <span className="secondary">
                      Chọn PDF <Plus size={15} />
                    </span>
                  </label>
                  {files.length > 0 && (
                    <div className="selected-files">
                      {files.map((f, i) => (
                        <span key={i}>{f.name}</span>
                      ))}
                    </div>
                  )}
                  <div className="upload-options">
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={forceOcr}
                        disabled={isImporting}
                        onChange={(e) => setForceOcr(e.target.checked)}
                      />{" "}
                      Buộc OCR
                    </label>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={translatePdf}
                        disabled={isImporting}
                        onChange={(e) => {
                          setTranslatePdf(e.target.checked);
                          setFiles([]);
                        }}
                      />{" "}
                      Dịch & xem trước khi nhập
                    </label>
                    {translatePdf && (
                      <Language
                        auto
                        value={sourceLang}
                        onChange={setSourceLang}
                      />
                    )}
                    <button
                      className="primary"
                      disabled={!files.length || busy || isImporting}
                      onClick={importFiles}
                    >
                      {isImporting ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <Plus size={16} />
                      )}{" "}
                      {isImporting ? "Đang xử lý…" : translatePdf ? "Tạo bản xem trước" : "Nhập tài liệu"}
                    </button>
                  </div>
                  {translatePdf && translationSettings}
                  {importJob && topic === importJob.topic && (
                    <ImportProgress
                      job={importJob}
                      onOpen={openImportProgress}
                      onDismiss={() => setImportJob(null)}
                    />
                  )}
                </section>
                {preview && preview.topic === topic && (
                  <section className="preview-card">
                    <div className="preview-toolbar">
                      <h3>{preview.file}</h3>
                      <button
                        className="icon"
                        disabled={busy || isImporting}
                        aria-label="Hủy xem trước"
                        onClick={() =>
                          work(async () => {
                            await api("/previews/" + preview.id, {
                              method: "DELETE",
                            });
                            setImportJob((old) => old?.mode === "preview" && old.items[0]?.result?.preview?.id === preview.id ? null : old);
                            setPreview(null);
                          })
                        }
                      >
                        <X size={16} />
                      </button>
                      <select
                        aria-label="Trang xem trước"
                        value={page}
                        disabled={busy || isImporting}
                        onChange={(e) => {
                          const n = Number(e.target.value);
                          setPage(n);
                          setEditText(
                            preview.pages[n].translation ||
                              preview.pages[n].original ||
                              "",
                          );
                        }}
                      >
                        {preview.pages.map((p, i) => (
                          <option key={i} value={i}>
                            Trang {p.page}
                          </option>
                        ))}
                      </select>
                      <button
                        className="secondary"
                        disabled={busy || isImporting}
                        onClick={() =>
                          work(async () => {
                            await savePage();
                            setNotice("Đã lưu chỉnh sửa trang.");
                          })
                        }
                      >
                        Lưu trang
                      </button>
                    </div>
                    <div className="preview-columns">
                      <div>
                        <b>Bản gốc</b>
                        <pre>{preview.pages[page]?.original}</pre>
                      </div>
                      <label>
                        Bản dịch · Có thể chỉnh sửa
                        <textarea
                          value={editText}
                          disabled={busy || isImporting}
                          onChange={(e) => setEditText(e.target.value)}
                          rows={15}
                        />
                      </label>
                    </div>
                    <div className="preview-toolbar">
                      <span className="muted">
                        Lưu từng trang trước khi chuyển trang.
                      </span>
                      <button
                        className="secondary"
                        disabled={busy || isImporting}
                        onClick={() => confirmPreview("original")}
                      >
                        Nhập bản gốc
                      </button>
                      <button
                        className="primary"
                        disabled={busy || isImporting}
                        onClick={() => confirmPreview("translated")}
                      >
                        Nhập bản dịch <Check size={16} />
                      </button>
                    </div>
                  </section>
                )}
                <div className="documents">
                  {docs.map((d) => (
                    <article key={d.id}>
                      <span className="pdf-icon">
                        <FileText size={21} />
                      </span>
                      <div>
                        <b>{d.filename}</b>
                        <p>
                          {d.status === "ready"
                            ? `${d.page_count} trang · ${d.index_mode === "translated" ? "Bản dịch" : "Bản gốc"}`
                            : "Chưa lập chỉ mục · Tải lại để thử lại"}
                        </p>
                      </div>
                      <a
                        className="icon"
                        href={"/api/documents/" + d.id + "/file"}
                        aria-label={"Tải " + d.filename}
                      >
                        <Download size={17} />
                      </a>
                      <button
                        className="icon danger"
                        disabled={busy || (isImporting && topic === importJob.topic)}
                        aria-label={"Xóa " + d.filename}
                        onClick={() => setModal({ type: "delete-doc", doc: d })}
                      >
                        <Trash2 size={17} />
                      </button>
                    </article>
                  ))}
                  {!docs.length && (
                    <div className="empty-docs">
                      <BookOpen size={28} />
                      <p>Thư viện đang chờ tài liệu đầu tiên của bạn.</p>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
        {view === "translate" && (
          <div className="panel-content">
            <div className="page-title">
              <div>
                <span className="eyebrow">KẾT NỐI TRI THỨC</span>
                <h2>Dịch văn bản</h2>
                <p>Dịch nhanh đoạn nội dung sang ngôn ngữ đang chọn.</p>
              </div>
              <Languages size={30} />
            </div>
            <div className="translation-controls">
              <span>Ngôn ngữ gốc</span>
              <Language value={sourceLang} onChange={setSourceLang} auto />
              <ArrowRight size={17} />
              <Language value={language} onChange={setLanguage} />
            </div>
            {translationSettings}
            <div className="translation-columns">
              <label>
                Nội dung gốc
                <textarea
                  rows={15}
                  placeholder="Dán nội dung cần dịch…"
                  value={translationInput}
                  onChange={(e) => setTranslationInput(e.target.value)}
                />
              </label>
              <div>
                <b>Bản dịch</b>
                <pre>
                  {translationOutput || "Bản dịch sẽ xuất hiện tại đây."}
                </pre>
              </div>
            </div>
            <button
              className="primary"
              disabled={!translationInput.trim() || busy}
              onClick={() =>
                work(async () => {
                  const result = await api("/translate", {
                    method: "POST",
                    body: {
                      text: translationInput,
                      source_language: sourceLang,
                      target_language: language,
                      provider,
                      quality,
                      domain: provider === "groq" ? domain : "",
                      glossary: provider === "groq" ? glossary : "",
                    },
                  });
                  setTranslationOutput(result.translation);
                })
              }
            >
              {busy ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <Languages size={17} />
              )}{" "}
              Dịch văn bản
            </button>
          </div>
        )}
      </main>
      {inspector && topic && (
        <LibraryInspector
          active={active}
          documents={docs}
          botName={botName}
          theme={chatTheme}
          close={() => setInspector(false)}
          onDocuments={() => selectView("docs")}
          onAppearance={openAppearance}
        />
      )}
      {avatarModal && (
        <div className="modal-backdrop">
          <section
            className="dialog avatar-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="avatar-dialog-title"
          >
            <div className="bgr-avatar-dialog-heading">
              <h2 id="avatar-dialog-title">
                {avatarModal.bot
                  ? "Gương mặt của trợ lý"
                  : "Một avatar đúng chất bạn"}
              </h2>
              <button
                className="icon"
                aria-label="Đóng chỉnh avatar"
                disabled={busy}
                onClick={() => setAvatarModal(null)}
              >
                <X size={20} />
              </button>
            </div>
            <p className="bgr-avatar-scope">
              {avatarModal.bot
                ? `Dành riêng cho bot của thư viện ${avatarModal.library}.`
                : "Avatar này theo bạn trong mọi thư viện và cuộc trò chuyện."}
            </p>
            <AvatarPicker
              key={avatarModal.bot ? avatarModal.topic : "profile"}
              current={avatarModal.avatar}
              name={avatarModal.name}
              bot={avatarModal.bot}
              busy={busy}
              onSave={saveAvatar}
            />
          </section>
        </div>
      )}
      {modal && !avatarModal && (
        <div className="modal-backdrop">
          <section
            className={
              "dialog " +
              (modal.type === "appearance" ? "appearance-dialog" : "")
            }
            role="dialog"
            aria-modal="true"
            aria-labelledby="workspace-modal-title"
          >
            <button
              className="close"
              disabled={busy}
              onClick={() => setModal(null)}
              aria-label="Đóng"
            >
              <X size={20} />
            </button>
            <h2 id="workspace-modal-title">
              {modal.type === "appearance"
                ? "Góc nhỏ, phong cách riêng."
                : modal.type === "topic"
                  ? "Thêm chủ đề"
                  : modal.type === "rename"
                    ? "Đổi tên cuộc trò chuyện"
                    : modal.type === "delete-topic"
                      ? "Xóa thư viện này?"
                      : "Xóa khỏi không gian của bạn?"}
            </h2>
            {modal.type === "appearance" ? (
              <form onSubmit={saveAppearance}>
                <div className="bgr-bot-avatar-option">
                  <Avatar
                    avatar={active?.avatar}
                    name={botName}
                    bot
                    size={44}
                  />
                  <div>
                    <b>Avatar của trợ lý</b>
                    <small>Mẫu sẵn hoặc ảnh bạn chọn</small>
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={openBotAvatar}
                  >
                    Đổi avatar bot
                  </button>
                </div>
                <p className="appearance-scope">
                  Dành riêng cho <b>{active?.name}</b> trong tài khoản{" "}
                  {user.name}.
                </p>
                <label>
                  Biệt danh trợ lý
                  <input
                    autoFocus
                    required
                    maxLength={80}
                    value={botDraft}
                    onChange={(e) => setBotDraft(e.target.value)}
                    placeholder="Ví dụ: Mây, Nova, Giáo sư Gấu…"
                  />
                </label>
                <span className="theme-label">
                  Chọn không khí cho cuộc trò chuyện
                </span>
                <div className="theme-grid">
                  {THEMES.map((theme) => (
                    <button
                      key={theme.id}
                      type="button"
                      className={
                        "theme-card " +
                        (themeDraft === theme.id ? "chosen" : "")
                      }
                      aria-label={"Theme " + theme.name}
                      aria-pressed={themeDraft === theme.id}
                      onClick={() => setThemeDraft(theme.id)}
                    >
                      <span
                        className="theme-swatch"
                        style={{
                          background: theme.background,
                          borderColor: theme.border,
                        }}
                      >
                        <i style={{ background: theme.surface }} />
                        <i style={{ background: theme.user }} />
                        {themeDraft === theme.id && (
                          <Check size={13} style={{ color: theme.accent }} />
                        )}
                      </span>
                      <b>{theme.name}</b>
                      <small>{theme.description}</small>
                    </button>
                  ))}
                </div>
                <div
                  className="appearance-preview"
                  style={themeStyle(getTheme(themeDraft))}
                >
                  <span className="preview-label">XEM TRƯỚC</span>
                  <div className="preview-user">
                    <small>{user.name}</small>
                    <span>Hôm nay mình học gì nhỉ? ✨</span>
                  </div>
                  <div className="preview-bot">
                    <small>{botDraft.trim() || "BIGRAG"}</small>
                    <span>Mình sẵn sàng rồi. Cùng khám phá nhé!</span>
                  </div>
                </div>
                <div className="appearance-actions">
                  <button
                    type="button"
                    className="text-button"
                    disabled={busy}
                    onClick={() => {
                      setBotDraft("BIGRAG");
                      setThemeDraft("mint");
                    }}
                  >
                    Khôi phục mặc định
                  </button>
                  <button className="primary" disabled={busy}>
                    {busy ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : (
                      <Check size={16} />
                    )}{" "}
                    Lưu cá nhân hóa
                  </button>
                </div>
              </form>
            ) : ["topic", "rename"].includes(modal.type) ? (
              <form onSubmit={saveName}>
                <label>
                  {modal.type === "topic"
                    ? "Tên chủ đề"
                    : "Tên cuộc trò chuyện"}
                  <input
                    autoFocus
                    required
                    maxLength={modal.type === "topic" ? 100 : 120}
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Ví dụ: Machine Learning"
                  />
                </label>
                <button className="primary full" disabled={busy}>
                  Lưu <Check size={16} />
                </button>
              </form>
            ) : (
              <>
                <p>{modal.topic?.name || modal.doc?.filename || modal.chat?.title}</p>
                <p className="muted">
                  Thao tác này xóa{" "}
                  {modal.type === "delete-topic"
                    ? "toàn bộ PDF, chỉ mục tìm kiếm và lịch sử trò chuyện trong thư viện này. Không thể hoàn tác"
                    : modal.doc
                    ? "PDF và chỉ mục tìm kiếm"
                    : "cuộc trò chuyện cùng các tin nhắn đã lưu"}
                  .
                </p>
                <div className="dialog-actions">
                  <button className="secondary" disabled={busy} onClick={() => setModal(null)}>
                    Giữ lại
                  </button>
                  <button
                    className="danger-button"
                    disabled={busy}
                    onClick={remove}
                  >
                    {busy ? <LoaderCircle size={16} className="spin" /> : null}
                    {modal.type === "delete-topic" ? "Xóa thư viện" : "Xóa"}
                  </button>
                </div>
              </>
            )}
            {error && <div className="error">{error}</div>}
          </section>
        </div>
      )}
    </div>
  );
}
export default function App() {
  const [user, setUser] = useState(null),
    [ready, setReady] = useState(false),
    [auth, setAuth] = useState(null);
  useEffect(() => {
    api("/auth/me")
      .then((r) => setUser(r.user))
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);
  if (!ready)
    return (
      <div className="loading">
        <Brand />
        <LoaderCircle size={25} className="spin" />
      </div>
    );
  return user ? (
    <Workspace
      user={user}
      onUserChange={setUser}
      logout={async () => {
        await api("/auth/logout", { method: "POST" });
        setUser(null);
      }}
    />
  ) : (
    <>
      <Landing open={setAuth} Brand={Brand} />
      {auth && (
        <Auth
          key={auth}
          mode={auth}
          setMode={setAuth}
          close={() => setAuth(null)}
          onUser={(u) => {
            setUser(u);
            setAuth(null);
          }}
        />
      )}
    </>
  );
}

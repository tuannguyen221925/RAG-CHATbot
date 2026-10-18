import React, { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Avatar } from "./AvatarUI.jsx";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  FileText,
  FolderOpen,
  GitCompareArrows,
  Info,
  Lightbulb,
  LoaderCircle,
  Palette,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

export function initials(name) {
  return String(name || "B")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
const markdownComponents = {
  a: ({ node, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer" />
  ),
  table: ({ node, ...props }) => (
    <div className="ws-table-scroll">
      <table {...props} />
    </div>
  ),
};
export function AnswerBody({ content }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[[rehypeKatex, { trust: false, strict: "ignore", maxExpand: 1000, maxSize: 10 }]]}
      skipHtml
      disallowedElements={["img"]}
      components={markdownComponents}
    >
      {content}
    </Markdown>
  );
}
export function ChatMessage({ message, user, botName, botAvatar, documents }) {
  const [copied, setCopied] = useState(""),
    timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const assistant = message.role !== "user";
  const sourceFileCount = new Set((message.sources || []).map((source) => source.file)).size;
  const time = message.created_at ? new Date(message.created_at) : null;
  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied("Đã sao chép");
    } catch {
      setCopied("Chưa sao chép được");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(""), 2400);
  }
  return (
    <article className={"message " + message.role}>
      <span className="message-avatar" aria-hidden="true">
        <Avatar
          avatar={assistant ? botAvatar : user.avatar}
          name={assistant ? botName : user.name}
          bot={assistant}
        />
      </span>
      <div className="message-body">
        <b className="message-label">
          {assistant ? botName : user.name}
          {assistant && <span className="ws-ai-label">AI</span>}
        </b>
        <div className="message-text">
          {assistant ? (
            <AnswerBody content={message.content} />
          ) : (
            message.content
          )}
        </div>
        {message.sources?.length > 0 && (
          <details className="ws-sources">
            <summary>
              <BookOpen size={15} />
              <span>Nguồn tham khảo</span>
              <b>{message.sources.length} đoạn · {sourceFileCount} tài liệu</b>
              <ChevronDown size={15} />
            </summary>
            <div className="ws-source-list">
              {message.retrieval?.file_coverage_complete === false && (
                <p className="ws-source-coverage" role="status">
                  Tổng quan đang dựa trên {sourceFileCount}/{message.retrieval.available_files} tài liệu.
                  {" "}Hỏi riêng từng file để xem thêm.
                </p>
              )}
              {message.sources.map((source, i) => {
                const doc = documents.find((d) => d.filename === source.file);
                return (
                  <details className="ws-source" key={i}>
                    <summary>
                      <span className="ws-source-number">
                        {source.id || i + 1}
                      </span>
                      <span className="ws-source-file">
                        {source.file}
                        <small>Trang {source.page}</small>
                      </span>
                      <ChevronDown size={14} />
                    </summary>
                    <div className="ws-source-excerpt">
                      <p>{source.excerpt}</p>
                      {doc && (
                        <a href={"/api/documents/" + doc.id + "/file"} download>
                          <FileText size={13} />
                          Tải PDF gốc <ArrowUpRight size={13} />
                        </a>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          </details>
        )}
        <div className="ws-message-footer">
          {time && !Number.isNaN(time.getTime()) && (
            <time dateTime={time.toISOString()}>
              {time.toLocaleTimeString("vi-VN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </time>
          )}
          {message.pending && (
            <span className="ws-pending">
              <LoaderCircle size={11} className="spin" />
              Đang gửi
            </span>
          )}
          {assistant && (
            <button
              type="button"
              className="ws-copy"
              aria-label={"Sao chép câu trả lời của " + botName}
              onClick={copy}
            >
              {copied === "Đã sao chép" ? (
                <Check size={13} />
              ) : (
                <Copy size={13} />
              )}
              <span aria-live="polite">{copied || "Sao chép"}</span>
            </button>
          )}
          {assistant && message.usage?.total_tokens > 0 && (
            <details className="ws-message-info">
              <summary
                aria-label="Thông tin câu trả lời"
                title="Thông tin câu trả lời"
              >
                <Info size={13} />
              </summary>
              <span>{message.usage.total_tokens} tokens</span>
            </details>
          )}
        </div>
      </div>
    </article>
  );
}
export function ChatWelcome({
  user,
  botName,
  active,
  documents,
  busy,
  onSuggest,
  onDocuments,
  onTopic,
}) {
  const ready = documents.filter((d) => d.status === "ready");
  const ideas = [
    [
      FileText,
      "Tóm tắt nhanh",
      "Nắm các ý chính",
      "Tóm tắt nội dung chính của tài liệu",
    ],
    [
      Lightbulb,
      "Giải thích dễ hiểu",
      "Học từng khái niệm",
      "Giải thích các khái niệm quan trọng trong tài liệu theo cách dễ hiểu",
    ],
    [
      GitCompareArrows,
      "So sánh & kết nối",
      "Nhìn rõ điểm khác nhau",
      "So sánh các phương pháp trong tài liệu",
    ],
  ];
  return (
    <div className="chat-empty">
      <div className="ws-welcome-intro">
        <div className="ws-welcome-art" aria-hidden="true">
          <span className="ws-welcome-orbit" />
          <span className="welcome-icon">
            <Avatar avatar={active?.avatar} name={botName} bot />
            <i>
              <Sparkles size={14} />
            </i>
          </span>
          <span className="ws-welcome-star">✦</span>
        </div>
        <div className="ws-welcome-copy">
          <span className="eyebrow">MỘT GÓC NHỎ ĐỂ HIỂU THÊM</span>
          <h2>
            Chào {user.name}
            <span>Hôm nay, mình khám phá gì?</span>
          </h2>
          <p>
            {active ? (
              <>
                Mình là <b>{botName}</b>, cùng bạn học từ <b>{active.name}</b>.
              </>
            ) : (
              "Tạo thư viện đầu tiên để bắt đầu học cùng trợ lý của bạn."
            )}
          </p>
        </div>
      </div>
      {active && ready.length > 0 ? (
        <>
          <div className="ws-context-card">
            <span className="ws-context-icon">
              <FolderOpen size={23} />
            </span>
            <div>
              <b>{active.name}</b>
              <small>{ready.length} PDF sẵn sàng để trò chuyện</small>
            </div>
            <button
              type="button"
              onClick={onDocuments}
              title="Xem tài liệu"
              aria-label="Xem tài liệu của thư viện"
            >
              <ArrowUpRight size={19} />
            </button>
          </div>
          <div className="suggestions">
            {ideas.map(([Icon, title, description, prompt]) => (
              <button
                type="button"
                disabled={busy}
                key={title}
                onClick={() => onSuggest(prompt)}
              >
                <span className="ws-idea-icon">
                  <Icon size={21} />
                </span>
                <b>{title}</b>
                <small>{description}</small>
                <ArrowUpRight size={15} />
              </button>
            ))}
          </div>
        </>
      ) : (
        <div className="ws-first-file">
          <span>
            <FileText size={24} />
            <Plus size={13} />
          </span>
          <b>
            {active
              ? "Thêm PDF đầu tiên nhé"
              : "Mỗi chủ đề, một thư viện riêng"}
          </b>
          <p>
            {active
              ? "Tài liệu của bạn là điểm bắt đầu cho câu trả lời."
              : "Đặt tên môn học hoặc điều bạn đang tò mò."}
          </p>
          <button
            className="primary"
            disabled={busy}
            onClick={active ? onDocuments : onTopic}
          >
            <Plus size={16} />
            {active ? "Thêm tài liệu" : "Tạo thư viện"}
          </button>
        </div>
      )}
    </div>
  );
}
export function Typing({ botName, botAvatar }) {
  return (
    <div className="ws-typing" role="status">
      <span className="message-avatar">
        <Avatar avatar={botAvatar} name={botName} bot />
      </span>
      <div>
        <b>{botName} đang đọc tài liệu</b>
        <span className="ws-typing-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
    </div>
  );
}
export function ChatComposer({
  inputRef,
  question,
  setQuestion,
  botName,
  topic,
  canChat,
  language,
  languageName,
  busy,
  sending,
  onSubmit,
  onDocuments,
}) {
  useEffect(() => {
    const input = inputRef.current;
    if (input) {
      input.style.height = "0px";
      input.style.height =
        Math.min(Math.max(input.scrollHeight, 38), 155) + "px";
    }
  }, [question]);
  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={onSubmit}>
        <textarea
          ref={inputRef}
          aria-label="Câu hỏi"
          placeholder={
            !topic
              ? "Tạo thư viện để bắt đầu…"
              : canChat
                ? `Nhắn cho ${botName}…`
                : "Thêm PDF để bắt đầu trò chuyện…"
          }
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!canChat || busy}
          maxLength={4000}
          rows={1}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              e.keyCode !== 229
            ) {
              e.preventDefault();
              if (question.trim() && !busy && canChat) onSubmit(e);
            }
          }}
        />
        <div className="composer-bottom">
          <div className="ws-composer-tools">
            <button
              type="button"
              disabled={!topic || busy}
              onClick={onDocuments}
              aria-label="Thêm PDF vào thư viện"
              title="Thêm PDF"
            >
              <Plus size={18} />
            </button>
            <span>
              <BookOpen size={13} />
              {canChat ? "Dựa trên tài liệu của bạn" : "PDF là nguồn kiến thức"}
            </span>
          </div>
          <div className="ws-send-tools">
            <small title={language}>Trả lời bằng {languageName}</small>
            <button
              className="primary send"
              aria-label="Gửi câu hỏi"
              disabled={!canChat || !question.trim() || busy}
            >
              {sending ? (
                <LoaderCircle size={18} className="spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </div>
        </div>
      </form>
      <div className="composer-note">
        <span>
          <ShieldCheck size={12} />
          Đối chiếu nguồn khi cần.
        </span>
        <span>
          Enter gửi <i>·</i> Shift + Enter xuống dòng
        </span>
      </div>
    </div>
  );
}
export function LibraryInspector({
  active,
  documents,
  botName,
  theme,
  close,
  onDocuments,
  onAppearance,
}) {
  const ready = documents.filter((d) => d.status === "ready"),
    pages = ready.reduce((sum, d) => sum + Number(d.page_count), 0);
  return (
    <>
      <button
        className="ws-inspector-backdrop"
        aria-label="Đóng thông tin thư viện"
        onClick={close}
      />
      <aside className="ws-inspector" aria-label="Thông tin thư viện">
        <div className="ws-inspector-heading">
          <span>THƯ VIỆN ĐANG HỌC</span>
          <button className="icon" onClick={close} aria-label="Đóng thông tin">
            <X size={19} />
          </button>
        </div>
        <div className="ws-library-cover">
          <FolderOpen size={38} />
          <Sparkles size={17} />
        </div>
        <h2>{active?.name}</h2>
        <p className="ws-library-private">
          <ShieldCheck size={12} /> Không gian của riêng bạn
        </p>
        <div className="ws-library-stats">
          <div>
            <b>{ready.length.toLocaleString("vi-VN")}</b>
            <span>Tài liệu</span>
          </div>
          <div>
            <b>{pages.toLocaleString("vi-VN")}</b>
            <span>Trang nội dung</span>
          </div>
        </div>
        <div className="ws-inspector-section">
          <h3>
            Nguồn kiến thức <span>{documents.length}</span>
          </h3>
          {documents.slice(0, 5).map((doc) => (
            <a
              key={doc.id}
              href={"/api/documents/" + doc.id + "/file"}
              download
              className="ws-inspector-file"
              title={"Tải " + doc.filename}
            >
              <span>
                <FileText size={18} />
              </span>
              <div>
                <b>{doc.filename}</b>
                <small>
                  {doc.status === "ready"
                    ? `${doc.page_count} trang · ${doc.index_mode === "translated" ? "Bản dịch" : "Bản gốc"}`
                    : "Đang chuẩn bị"}
                </small>
              </div>
              <ArrowUpRight size={14} />
            </a>
          ))}
          {!documents.length && (
            <p className="ws-inspector-empty">
              Thêm PDF để có nguồn cho cuộc trò chuyện.
            </p>
          )}
          <button className="ws-inspector-link" onClick={onDocuments}>
            Quản lý tài liệu <ArrowRight size={15} />
          </button>
        </div>
        <div className="ws-companion-card">
          <span className="ws-companion-avatar">
            <Avatar avatar={active?.avatar} name={botName} bot />
          </span>
          <div>
            <small>TRỢ LÝ THƯ VIỆN</small>
            <b>{botName}</b>
          </div>
          <button
            className="icon"
            onClick={onAppearance}
            aria-label="Chỉnh biệt danh và theme"
          >
            <Palette size={17} />
          </button>
          <button className="ws-theme-shortcut" onClick={onAppearance}>
            <i style={{ background: theme.user }} />
            {theme.name}
            <ArrowUpRight size={13} />
          </button>
        </div>
      </aside>
    </>
  );
}
export function JumpToLatest({ onClick }) {
  return (
    <button className="ws-jump-latest" onClick={onClick}>
      <ArrowDown size={15} /> Tin nhắn mới nhất
    </button>
  );
}

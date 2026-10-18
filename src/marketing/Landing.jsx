import React, { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  FileText,
  FolderOpen,
  History,
  Heart,
  Languages,
  Layers,
  LockKeyhole,
  Menu,
  MessageSquare,
  Palette,
  Pause,
  Play,
  Search,
  ShieldCheck,
  Send,
  Sparkles,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { THEMES, getTheme, themeStyle } from "../../shared/themes.mjs";
import "./marketing.css";

const pages = [
  { id: "home", path: "/", name: "Tổng quan" },
  { id: "features", path: "/features", name: "Tính năng" },
  { id: "how", path: "/how-it-works", name: "Cách hoạt động" },
  { id: "personalization", path: "/personalization", name: "Cá nhân hóa" },
  { id: "privacy", path: "/privacy", name: "Không gian riêng" },
];
function currentPage() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const legacy = {
    "#how": "how",
    "#features": "features",
    "#privacy": "privacy",
  };
  return (
    pages.find(
      (p) => p.id === (path === "/" ? legacy[window.location.hash] : null),
    ) ||
    pages.find((p) => p.path === path) ||
    pages[0]
  );
}
const features = [
  {
    id: "library",
    icon: FolderOpen,
    name: "Thư viện PDF",
    title: "Gọn tài liệu. Dễ tìm hơn.",
    body: "Gom PDF theo môn học. Đọc cả trang scan với OCR.",
    tags: ["Nhiều PDF một lượt", "Nhận diện chữ scan"],
    color: "green",
  },
  {
    id: "ask",
    icon: MessageSquare,
    name: "Hỏi đáp có nguồn",
    title: "Hỏi một câu. Hiểu thêm một chút.",
    body: "Trò chuyện với tài liệu, mở nguồn để đọc lại khi cần.",
    tags: ["Nguồn & số trang", "Hỏi tiếp theo ngữ cảnh"],
    color: "blue",
  },
  {
    id: "translate",
    icon: Languages,
    name: "Dịch & duyệt",
    title: "Đọc theo ngôn ngữ của bạn.",
    body: "Xem hai bản cạnh nhau. Chỉnh bản dịch trước khi nhập.",
    tags: ["19 ngôn ngữ", "Bản gốc ↔ Bản dịch"],
    color: "purple",
  },
  {
    id: "history",
    icon: History,
    name: "Lịch sử chat",
    title: "Ý tưởng hôm qua, vẫn ở đây.",
    body: "Mở lại cuộc trò chuyện và tiếp tục điều đang khám phá.",
    tags: ["Tìm & đổi tên chat", "Tải hội thoại"],
    color: "peach",
  },
  {
    id: "style",
    icon: Palette,
    name: "Cá nhân hóa",
    title: "Một trợ lý. Mang màu sắc của bạn.",
    body: "Chọn theme, đặt biệt danh riêng cho bot ở mỗi thư viện.",
    tags: ["7 theme chat", "Biệt danh tùy chọn"],
    color: "pink",
  },
];
function Background() {
  return (
    <div className="mk-background" aria-hidden="true">
      <div className="mk-glow mk-glow-a" />
      <div className="mk-glow mk-glow-b" />
      <div className="mk-glow mk-glow-c" />
      <svg
        className="mk-waves"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <path d="M-150 540 C220 160 570 120 940 400 S1420 680 1620 220" />
        <path d="M-150 620 C200 230 550 180 940 465 S1440 740 1620 300" />
        <path d="M-150 700 C200 310 550 260 940 530 S1440 810 1620 380" />
      </svg>
      <div className="mk-specks">
        {Array.from({ length: 12 }, (_, i) => (
          <i
            key={i}
            style={{
              left: `${7 + ((i * 29) % 87)}%`,
              top: `${12 + ((i * 17) % 78)}%`,
              animationDelay: `${-i * 1.7}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
function Lead({ eyebrow, title, body }) {
  return (
    <header className="mk-lead">
      <span className="eyebrow">
        <span />
        {eyebrow}
      </span>
      <h1>{title}</h1>
      <p>{body}</p>
    </header>
  );
}
function CTA({ open, title = "Một câu hỏi. Một khám phá mới." }) {
  return (
    <section className="mk-cta">
      <div>
        <span className="eyebrow">GÓC HỌC TẬP CỦA BẠN</span>
        <h2>{title}</h2>
      </div>
      <button className="light-button large" onClick={() => open("register")}>
        Tạo không gian riêng <ArrowUpRight size={19} />
      </button>
    </section>
  );
}
function Demo({ motion }) {
  const [scene, setScene] = useState(0);
  useEffect(() => {
    if (!motion) return;
    const timer = setInterval(() => setScene((n) => (n + 1) % 3), 5200);
    return () => clearInterval(timer);
  }, [motion]);
  const labels = ["Thư viện", "Hỏi đáp", "Bản dịch"];
  return (
    <div className="mk-demo-scene">
      <div className="mk-demo-orbit" />
      <div className="mk-person-orbit mk-person-one">
        <img
          src="/images/learner-one.png"
          alt="Người học đặt câu hỏi"
          width="70"
          height="70"
        />
        <span>
          <MessageSquare size={11} /> Bạn hỏi…
        </span>
      </div>
      <div className="mk-person-orbit mk-person-two">
        <img
          src="/images/learner-two.png"
          alt="Người học khám phá kiến thức"
          width="70"
          height="82"
        />
        <span>
          <BookOpen size={11} /> Bạn khám phá.
        </span>
      </div>
      <div className="mk-robot-portrait">
        <img
          src="/images/robot-assistant.png"
          alt="Robot trợ lý BIGRAG minh họa"
          width="160"
          height="245"
        />
        <span>Xin chào, mình là Mây ✨</span>
      </div>
      <div className="mk-demo-window">
        <div className="mk-window-top">
          <span className="mk-window-dots">
            <i />
            <i />
            <i />
          </span>
          <span>Không gian học tập</span>
          <span className="mk-online">● Sẵn sàng</span>
        </div>
        <div className="mk-demo-tabs">
          {labels.map((l, i) => (
            <button
              key={l}
              onClick={() => setScene(i)}
              aria-pressed={scene === i}
            >
              {l}
            </button>
          ))}
        </div>
        <div key={scene} className="mk-demo-body">
          {scene === 0 ? (
            <>
              <div className="mk-demo-heading">
                <BookOpen size={17} />
                <b>Machine Learning</b>
                <span>Thư viện minh họa</span>
              </div>
              {[
                "Chương 1 · Tổng quan",
                "Chương 2 · Học có giám sát",
                "Chương 3 · Học không giám sát",
              ].map((f, i) => (
                <div className="mk-mini-file" key={f}>
                  <span>
                    <FileText size={18} />
                  </span>
                  <div>
                    <b>{f}</b>
                    <small>PDF · Sẵn sàng để khám phá</small>
                  </div>
                  <Check size={14} />
                </div>
              ))}
              <div className="mk-processing">
                <Sparkles size={14} /> Tri thức đã sẵn sàng{" "}
                <span>
                  <i />
                </span>
              </div>
            </>
          ) : scene === 1 ? (
            <>
              <div className="mk-demo-heading">
                <Sparkles size={17} />
                <b>Mây · Trợ lý học tập</b>
              </div>
              <div className="mk-demo-chat-user">Học có giám sát là gì?</div>
              <div className="mk-demo-chat-bot">
                <b>Cùng tìm hiểu nhé.</b>
                <p>
                  Học từ các ví dụ đã có nhãn, để dự đoán kết quả cho dữ liệu
                  mới.
                </p>
                <span className="source-chip">
                  <FileText size={12} /> Nguồn PDF · Số trang
                </span>
              </div>
              <div className="mk-demo-composer">
                Nhắn thêm cho Mây…
                <ArrowRight size={16} />
              </div>
            </>
          ) : (
            <>
              <div className="mk-demo-heading">
                <Languages size={17} />
                <b>Đọc & hiểu qua ngôn ngữ</b>
              </div>
              <div className="mk-mini-translation">
                <div>
                  <small>ENGLISH</small>
                  <p>Learning from labeled examples.</p>
                </div>
                <span>
                  <ArrowRight size={17} />
                </span>
                <div>
                  <small>TIẾNG VIỆT</small>
                  <p>Học từ các ví dụ đã gắn nhãn.</p>
                </div>
              </div>
              <div className="mk-edit-note">
                <PencilIcon /> Đọc, chỉnh sửa, rồi xác nhận.
              </div>
              <div className="mk-demo-composer">
                Bản gốc và bản dịch, cạnh nhau.
                <Check size={16} />
              </div>
            </>
          )}
        </div>
        <div className="mk-demo-caption">VÍ DỤ MINH HỌA · {scene + 1}/3</div>
      </div>
      <div className="mk-floating-label">
        <ShieldCheck size={17} />
        <div>
          <b>Không gian riêng của bạn</b>
          <small>Tài liệu và lịch sử theo tài khoản</small>
        </div>
      </div>
      <div className="mk-scene-spark mk-spark-one">✦</div>
      <div className="mk-scene-spark mk-spark-two">✧</div>
    </div>
  );
}
function PencilIcon() {
  return <span aria-hidden="true">✎</span>;
}
function Home({ open, Link, motion }) {
  return (
    <>
      <section className="mk-hero">
        <div className="mk-hero-copy">
          <span className="eyebrow">
            <span /> BẠN, TÀI LIỆU & MỘT TRỢ LÝ AI
          </span>
          <h1>
            Tài liệu của bạn.
            <br />
            Tri thức <em>trong tầm tay.</em>
          </h1>
          <p>Thêm PDF, hỏi điều bạn tò mò. BIGRAG cùng bạn tìm câu trả lời.</p>
          <div className="mk-hero-actions">
            <button className="primary large" onClick={() => open("register")}>
              Bắt đầu ngay <ArrowUpRight size={18} />
            </button>
            <Link page="features" className="secondary large">
              Xem tính năng <ArrowRight size={17} />
            </Link>
          </div>
          <div className="mk-hero-checks">
            <span>
              <Check size={14} /> Có nguồn đối chiếu
            </span>
            <span>
              <Check size={14} /> Giữ mạch hội thoại
            </span>
            <span>
              <Check size={14} /> Mang phong cách riêng
            </span>
          </div>
        </div>
        <Demo motion={motion} />
      </section>
      <div className="mk-facts">
        <div>
          <b>05</b>
          <span>Tính năng</span>
        </div>
        <div>
          <b>19</b>
          <span>Ngôn ngữ</span>
        </div>
        <div>
          <b>07</b>
          <span>Theme chat</span>
        </div>
      </div>
      <section className="mk-section">
        <div className="mk-section-title">
          <div>
            <span className="eyebrow">KHÁM PHÁ BIGRAG</span>
            <h2>Chọn điều bạn muốn biết.</h2>
          </div>
        </div>
        <div className="mk-explore-grid">
          {[
            [
              FileText,
              "features",
              "Bạn học được gì?",
              "5 công cụ, cùng một thư viện.",
            ],
            [Layers, "how", "Bắt đầu thế nào?", "5 bước nhỏ, dễ làm quen."],
            [
              Palette,
              "personalization",
              "Phong cách của bạn",
              "Thử màu, đặt tên cho bot.",
            ],
            [
              ShieldCheck,
              "privacy",
              "Một góc riêng",
              "Tài liệu và chat theo tài khoản.",
            ],
          ].map(([Icon, page, title, body]) => (
            <Link key={page} page={page} className="mk-explore-card">
              <Icon size={23} />
              <h3>{title}</h3>
              <p>{body}</p>
              <span>
                Tìm hiểu thêm <ArrowUpRight size={16} />
              </span>
            </Link>
          ))}
        </div>
      </section>
      <CTA open={open} />
    </>
  );
}
function Illustration({ kind }) {
  return (
    <div
      className={"mk-illustration mk-illustration-" + kind}
      role="img"
      aria-label={
        {
          account: "Minh họa tạo tài khoản với tên riêng",
          library: "Minh họa PDF được gom vào một thư viện",
          ask: "Minh họa trò chuyện và nguồn trích dẫn từ PDF",
          translate: "Minh họa bản gốc tiếng Anh và bản dịch tiếng Việt",
          history: "Minh họa các cuộc trò chuyện được lưu để mở lại",
          style: "Minh họa màu sắc và biệt danh riêng cho trợ lý",
        }[kind]
      }
    >
      <div className="mk-art-halo" />
      <span className="mk-art-spark mk-art-spark-a" aria-hidden="true">
        ✦
      </span>
      <span className="mk-art-spark mk-art-spark-b" aria-hidden="true">
        ✧
      </span>
      {kind === "account" ? (
        <>
          <div className="mk-art-account mk-art-card">
            <span className="mk-art-avatar">
              <UserRound size={34} />
            </span>
            <b>Chào Minh Anh!</b>
            <span className="mk-art-line" />
            <span className="mk-art-line short" />
            <span className="mk-art-account-ready">
              <Check size={14} /> Góc học tập đã sẵn sàng
            </span>
          </div>
          <span className="mk-art-sticker mk-sticker-top">
            <Heart size={23} />
          </span>
        </>
      ) : kind === "library" ? (
        <>
          <div className="mk-art-papers">
            {["Bài giảng", "Ghi chú", "Tham khảo"].map((title, i) => (
              <div
                className="mk-art-paper mk-art-card"
                key={title}
                style={{ "--paper": i }}
              >
                <FileText size={27} />
                <b>{title}</b>
                <span className="mk-art-line" />
                <span className="mk-art-line short" />
                <small>PDF</small>
              </div>
            ))}
          </div>
          <div className="mk-art-folder">
            <FolderOpen size={36} />
            <b>Machine Learning</b>
            <span>3 tài liệu · 1 nơi</span>
          </div>
          <span className="mk-art-sticker mk-sticker-top">
            <Upload size={23} />
          </span>
          <span className="mk-art-pill">
            <Search size={14} /> OCR <Check size={14} />
          </span>
        </>
      ) : kind === "ask" ? (
        <>
          <div className="mk-art-conversation">
            <div className="mk-art-message mk-art-user">
              Học có giám sát là gì? <MessageSquare size={15} />
            </div>
            <div className="mk-art-message mk-art-bot">
              <Bot size={21} />
              <div>
                <b>Học từ ví dụ đã có nhãn.</b>
                <span className="mk-art-line" />
                <span className="mk-art-line short" />
              </div>
            </div>
            <div className="mk-art-source mk-art-card">
              <FileText size={23} />
              <div>
                <b>Chương 2.pdf</b>
                <small>Nguồn · Trang minh họa</small>
              </div>
              <ArrowUpRight size={17} />
            </div>
          </div>
          <span className="mk-art-sticker mk-sticker-bottom">
            <Send size={24} />
          </span>
        </>
      ) : kind === "translate" ? (
        <>
          <div className="mk-art-language mk-art-card mk-language-original">
            <small>ENGLISH</small>
            <b>Aa</b>
            <span>Learning</span>
            <span className="mk-art-line" />
            <span className="mk-art-line short" />
          </div>
          <div className="mk-art-language mk-art-card mk-language-translated">
            <small>TIẾNG VIỆT</small>
            <b>Âă</b>
            <span>Học tập</span>
            <span className="mk-art-line" />
            <span className="mk-art-line short" />
          </div>
          <span className="mk-art-sticker mk-sticker-middle">
            <Languages size={25} />
          </span>
          <span className="mk-art-pill">
            <Check size={14} /> Đọc · Chỉnh · Duyệt
          </span>
        </>
      ) : kind === "history" ? (
        <>
          <div className="mk-art-timeline">
            {["Ôn tập K-means", "Ghi chú chương 2", "Câu hỏi hôm nay"].map(
              (title, i) => (
                <div className="mk-art-history mk-art-card" key={title}>
                  <MessageSquare size={21} />
                  <div>
                    <small>{["HÔM QUA", "SÁNG NAY", "TIẾP TỤC"][i]}</small>
                    <b>{title}</b>
                  </div>
                  {i === 2 ? <ArrowRight size={17} /> : <Check size={15} />}
                </div>
              ),
            )}
          </div>
          <span className="mk-art-sticker mk-sticker-top">
            <History size={26} />
          </span>
        </>
      ) : (
        <>
          <div className="mk-art-style mk-art-card">
            <div>
              <span className="mk-art-avatar">
                <Bot size={26} />
              </span>
              <b>
                Mây <small>Trợ lý của bạn</small>
              </b>
              <Heart size={20} />
            </div>
            <p>Hôm nay cùng học gì nè? ✨</p>
            <div className="mk-art-swatches">
              {THEMES.map((t) => (
                <i key={t.id} style={{ background: t.user }} />
              ))}
            </div>
          </div>
          <span className="mk-art-sticker mk-sticker-top">
            <Palette size={28} />
          </span>
          <span className="mk-art-pill">
            <Sparkles size={14} /> Theo cách của bạn
          </span>
        </>
      )}
      <small className="mk-art-caption">MINH HỌA TÍNH NĂNG</small>
    </div>
  );
}
function Features({ open, Link }) {
  const [active, setActive] = useState(0);
  const feature = features[active];
  return (
    <>
      <Lead
        eyebrow="05 NHÓM TÍNH NĂNG"
        title={
          <>
            Ít thao tác.
            <br />
            <em>Nhiều điều để khám phá.</em>
          </>
        }
        body="Chạm vào một thẻ. Xem BIGRAG giúp bạn học thế nào."
      />
      <section className="mk-showcase" aria-label="Khám phá 5 tính năng">
        <div className="mk-feature-selector">
          {features.map((f, i) => (
            <button
              key={f.id}
              className={"mk-feature-choice mk-color-" + f.color}
              aria-pressed={active === i}
              onClick={() => setActive(i)}
            >
              <span className="mk-choice-icon">
                <f.icon size={23} />
              </span>
              <span>
                {f.name}
                <small>0{i + 1} / 05</small>
              </span>
              <ArrowUpRight size={16} />
            </button>
          ))}
        </div>
        <article
          className={"mk-showcase-stage mk-color-" + feature.color}
          aria-label={feature.name}
        >
          <Illustration key={feature.id} kind={feature.id} />
          <div className="mk-showcase-copy">
            <h2>{feature.title}</h2>
            <p>{feature.body}</p>
            <div className="mk-benefit-pills">
              {feature.tags.map((tag) => (
                <span key={tag}>
                  <Check size={13} />
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </article>
      </section>
      <div className="mk-next-link">
        <Link page="how">
          Xem cách bắt đầu <ArrowRight size={17} />
        </Link>
      </div>
      <CTA open={open} />
    </>
  );
}
function How({ open, Link }) {
  const [active, setActive] = useState(0);
  const steps = [
    {
      kind: "account",
      icon: UserRound,
      name: "Tạo tài khoản",
      title: "Một góc học tập mang tên bạn.",
      body: "Điền tên, email và mật khẩu để bắt đầu.",
    },
    {
      kind: "library",
      icon: FolderOpen,
      name: "Thêm PDF",
      title: "Gom tài liệu vào một chủ đề.",
      body: "Tạo thư viện, chọn PDF. BIGRAG đọc nội dung giúp bạn.",
    },
    {
      kind: "translate",
      icon: Languages,
      name: "Dịch nếu cần",
      title: "Đọc bằng ngôn ngữ quen thuộc.",
      body: "Xem, chỉnh và duyệt bản dịch. Bạn cũng có thể dùng ngay bản gốc.",
    },
    {
      kind: "ask",
      icon: MessageSquare,
      name: "Hỏi & xem nguồn",
      title: "Bắt đầu bằng điều bạn tò mò.",
      body: "Đặt câu hỏi, đọc câu trả lời rồi mở nguồn để đối chiếu.",
    },
    {
      kind: "history",
      icon: History,
      name: "Tiếp tục khám phá",
      title: "Lần sau, học tiếp từ đây.",
      body: "Mở chat cũ hoặc đổi theme, đặt biệt danh cho trợ lý.",
    },
  ];
  const step = steps[active];
  return (
    <>
      <Lead
        eyebrow="05 BƯỚC NHỎ"
        title={
          <>
            Có PDF rồi?
            <br />
            <em>Cùng bắt đầu thôi.</em>
          </>
        }
        body="Chọn từng bước để xem. Dịch tài liệu là bước tùy chọn."
      />
      <section className="mk-walkthrough" aria-label="Các bước sử dụng">
        <div className="mk-step-selector">
          {steps.map((s, i) => (
            <button
              key={s.kind}
              aria-pressed={i === active}
              onClick={() => setActive(i)}
            >
              <span>{i === active ? <s.icon size={21} /> : i + 1}</span>
              {s.name}
            </button>
          ))}
        </div>
        <article className="mk-walkthrough-stage">
          <Illustration key={step.kind} kind={step.kind} />
          <div className="mk-walkthrough-copy">
            <span className="eyebrow">BƯỚC 0{active + 1}</span>
            <h2>{step.title}</h2>
            <p>{step.body}</p>
            <button
              className="secondary"
              onClick={() => setActive((active + 1) % steps.length)}
            >
              {active === 4 ? "Xem lại từ đầu" : "Bước tiếp theo"}
              <ArrowRight size={16} />
            </button>
          </div>
        </article>
      </section>
      <section className="mk-faq">
        <h2>Cần biết thêm?</h2>
        {[
          [
            "PDF scan có dùng được không?",
            "Có, BIGRAG dùng OCR để nhận diện chữ. Scan rõ sẽ cho nội dung tốt hơn.",
          ],
          [
            "Cần dịch PDF tiếng Anh trước không?",
            "Không. Bạn có thể giữ bản gốc và hỏi bằng tiếng Việt.",
          ],
          [
            "Tạo chat mới có mất lịch sử không?",
            "Không. Chat cũ vẫn ở sidebar để mở lại.",
          ],
          [
            "Đổi tên bot và theme ở đâu?",
            "Chọn thư viện, bấm Cá nhân hóa trong khung chat rồi lưu.",
          ],
        ].map(([q, a]) => (
          <details key={q}>
            <summary>
              {q}
              <ChevronDown size={17} />
            </summary>
            <p>{a}</p>
          </details>
        ))}
      </section>
      <div className="mk-next-link">
        <Link page="personalization">
          Thử phong cách của bạn <ArrowRight size={17} />
        </Link>
      </div>
      <CTA open={open} />
    </>
  );
}
function Personalization({ open }) {
  const [themeId, setThemeId] = useState("blush"),
    [name, setName] = useState("Mây");
  const theme = getTheme(themeId);
  return (
    <>
      <Lead
        eyebrow="KHÔNG GIAN NHỎ. CÁ TÍNH LỚN."
        title={
          <>
            Màu bạn thích.
            <br />
            <em>Tên bạn đặt.</em>
          </>
        }
        body="Chọn một màu, đặt một tên. Xem trước ngay bên dưới."
      />
      <section className="mk-personalizer">
        <div className="mk-personalizer-controls">
          <span className="eyebrow">THỬ NGAY TẠI ĐÂY</span>
          <h2>Hôm nay, bạn thích màu gì?</h2>
          <p>Đây là bản xem trước. Đăng nhập để lưu vào thư viện.</p>
          <label>
            Biệt danh bot · xem trước
            <input
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mây, Nova, Giáo sư Gấu…"
            />
          </label>
          <div className="mk-theme-picker">
            {THEMES.map((t) => (
              <button
                key={t.id}
                className={themeId === t.id ? "chosen" : ""}
                aria-label={"Thử theme " + t.name}
                aria-pressed={themeId === t.id}
                onClick={() => setThemeId(t.id)}
              >
                <i style={{ background: t.user }} />
                {t.name}
                {themeId === t.id && <Check size={13} />}
              </button>
            ))}
          </div>
        </div>
        <div className="mk-preview-chat" style={themeStyle(theme)}>
          <div className="mk-preview-header">
            <span>
              <Sparkles size={19} />
            </span>
            <div>
              <b>{name.trim() || "Trợ lý của bạn"}</b>
              <small>Thư viện · Machine Learning</small>
            </div>
            <span className="mk-preview-badge">Xem trước</span>
          </div>
          <div className="mk-preview-messages">
            <div className="mk-public-user">
              <small>Minh Anh</small>
              <p>K-means là gì vậy?</p>
            </div>
            <div className="mk-public-bot">
              <small>{name.trim() || "Trợ lý của bạn"}</small>
              <p>
                Gom các điểm gần nhau thành nhóm, rồi tìm tâm cho mỗi nhóm nhé.
              </p>
              <span>
                <FileText size={12} /> Nguồn tài liệu · Trang liên quan
              </span>
            </div>
            <div className="mk-public-user">
              <small>Minh Anh</small>
              <p>Cùng học từng bước nha ✨</p>
            </div>
          </div>
          <div className="mk-preview-input">
            Nhắn cho {name.trim() || "trợ lý của bạn"}…<ArrowRight size={17} />
          </div>
        </div>
      </section>
      <section className="mk-section mk-personal-benefits">
        <div className="mk-section-title">
          <div>
            <h2>Riêng cho mỗi thư viện.</h2>
          </div>
        </div>
        <div className="mk-personal-perks mk-benefit-pills">
          <span>
            <UserRound size={14} />
            Tên bạn trên tin nhắn
          </span>
          <span>
            <Bot size={14} />
            Bot riêng mỗi thư viện
          </span>
          <span>
            <Check size={14} />
            Lưu phong cách đã chọn
          </span>
        </div>
      </section>
      <CTA open={open} title="Học cùng một trợ lý mang phong cách của bạn." />
    </>
  );
}
function Privacy({ open }) {
  return (
    <>
      <Lead
        eyebrow="MỘT THƯ VIỆN THẬT SỰ THUỘC VỀ BẠN"
        title={
          <>
            Tài liệu riêng.
            <br />
            <em>Chat cũng riêng.</em>
          </>
        }
        body="Tài liệu, lịch sử và phong cách thuộc về tài khoản của bạn."
      />
      <section className="mk-privacy-layout">
        <div className="mk-vault">
          <div className="mk-vault-orbit" />
          <span className="mk-vault-icon">
            <ShieldCheck size={50} />
          </span>
          <div className="mk-vault-label">
            <LockKeyhole size={15} /> Thư viện của bạn
          </div>
          <div className="mk-vault-doc">
            <FileText size={19} /> Tài liệu <Check size={14} />
          </div>
          <div className="mk-vault-chat">
            <MessageSquare size={19} /> Lịch sử chat <Check size={14} />
          </div>
          <small>Được quản lý theo tài khoản</small>
        </div>
        <div className="mk-privacy-points">
          {[
            [
              BookOpen,
              "Thư viện riêng",
              "Mỗi người có tài liệu và chủ đề độc lập.",
            ],
            [
              History,
              "Chat luôn nối mạch",
              "Mở lại, đổi tên, tải xuống hoặc xóa chat của bạn.",
            ],
            [
              LockKeyhole,
              "Tài khoản được bảo vệ",
              "Mật khẩu được băm, phiên đăng nhập có thời hạn.",
            ],
          ].map(([Icon, title, body]) => (
            <article key={title}>
              <span>
                <Icon size={21} />
              </span>
              <div>
                <h2>{title}</h2>
                <p>{body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="mk-data-notes mk-disclosure">
        <details>
          <summary>
            <span>
              <ShieldCheck size={18} /> Tài liệu được sử dụng thế nào?
            </span>
            <ChevronDown size={17} />
          </summary>
          <div>
            <p>
              <b>Bản gốc được giữ lại.</b> Bạn chọn bản gốc hoặc bản dịch đã
              duyệt để hỏi đáp.
            </p>
            <p>
              <b>Khi hỏi đáp:</b> các đoạn tài liệu được chọn gửi tới Groq. Khi
              dịch, văn bản gửi tới Groq hoặc Google Cloud Translation tùy bộ
              dịch bạn chọn.
            </p>
            <p>
              <b>Có nguồn để đối chiếu.</b> Mở trích dẫn khi muốn kiểm tra nội
              dung câu trả lời.
            </p>
          </div>
        </details>
      </section>
      <CTA
        open={open}
        title="Dành một góc riêng cho những điều bạn muốn hiểu."
      />
    </>
  );
}

export default function Landing({ open, Brand }) {
  const [page, setPage] = useState(currentPage),
    [menuOpen, setMenuOpen] = useState(false),
    [motion, setMotion] = useState(
      () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
  useEffect(() => {
    if (
      window.location.hash &&
      pages.some((p) => p.id === page.id) &&
      window.location.pathname === "/"
    )
      window.history.replaceState(null, "", page.path);
    const pop = () => {
      setPage(currentPage());
      setMenuOpen(false);
    };
    const escape = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("popstate", pop);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("popstate", pop);
      window.removeEventListener("keydown", escape);
    };
  }, []);
  useEffect(() => {
    document.title = `${page.name} · BIGRAG`;
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [page.id]);
  function navigate(e, target) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
      return;
    e.preventDefault();
    if (window.location.pathname !== target.path)
      window.history.pushState(null, "", target.path);
    setPage(target);
    setMenuOpen(false);
  }
  const Link = useCallback(function Link({
    page: identity,
    children,
    ...props
  }) {
    const target = pages.find((p) => p.id === identity);
    return (
      <a {...props} href={target.path} onClick={(e) => navigate(e, target)}>
        {children}
      </a>
    );
  }, []);
  return (
    <div
      className={
        "mk-site " + (motion ? "mk-motion-enabled" : "mk-motion-paused")
      }
    >
      <Background />
      <a className="mk-skip" href="#marketing-content">
        Đến nội dung chính
      </a>
      <header className="mk-fixed-header">
        <nav className="mk-nav" aria-label="Điều hướng giới thiệu">
          <Link
            page="home"
            className="mk-brand-link"
            aria-label="BIGRAG · Tổng quan"
          >
            <Brand />
          </Link>
          <div
            id="marketing-menu"
            className={"mk-nav-pages " + (menuOpen ? "is-open" : "")}
          >
            {pages.map((p) => (
              <Link
                key={p.id}
                page={p.id}
                aria-current={page.id === p.id ? "page" : undefined}
              >
                {p.name}
              </Link>
            ))}
            <button
              className="mk-menu-login"
              onClick={() => {
                setMenuOpen(false);
                open("login");
              }}
            >
              Đăng nhập <ArrowRight size={16} />
            </button>
          </div>
          <div className="mk-nav-auth">
            <button
              className="text-button"
              onClick={() => {
                setMenuOpen(false);
                open("login");
              }}
            >
              Đăng nhập
            </button>
            <button
              className="primary"
              onClick={() => {
                setMenuOpen(false);
                open("register");
              }}
            >
              Bắt đầu ngay <ArrowUpRight size={15} />
            </button>
          </div>
          <button
            className="mk-menu-toggle"
            aria-label={
              menuOpen ? "Đóng menu giới thiệu" : "Mở menu giới thiệu"
            }
            aria-expanded={menuOpen}
            aria-controls="marketing-menu"
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </nav>
      </header>
      <main id="marketing-content" className="mk-content" key={page.id}>
        {page.id === "home" ? (
          <Home open={open} Link={Link} motion={motion} />
        ) : page.id === "features" ? (
          <Features open={open} Link={Link} />
        ) : page.id === "how" ? (
          <How open={open} Link={Link} />
        ) : page.id === "personalization" ? (
          <Personalization open={open} />
        ) : (
          <Privacy open={open} />
        )}
      </main>
      <footer className="mk-footer">
        <Link page="home">
          <Brand />
        </Link>
        <div>
          {pages.slice(1).map((p) => (
            <Link key={p.id} page={p.id}>
              {p.name}
            </Link>
          ))}
        </div>
        <small>
          © {new Date().getFullYear()} BIGRAG · Một góc nhỏ cho những ý tưởng
          lớn.
        </small>
      </footer>
      <button
        className="mk-motion-toggle"
        aria-pressed={!motion}
        onClick={() => setMotion((v) => !v)}
      >
        {motion ? <Pause size={13} /> : <Play size={13} />}{" "}
        {motion ? "Tắt chuyển động" : "Bật chuyển động"}
      </button>
    </div>
  );
}

import React, { useEffect, useState } from "react";
import { Check, FileText, LoaderCircle, AlertCircle, ChevronRight, X } from "lucide-react";
import "./importProgress.css";

const complete = (item) => ["indexed", "skipped", "error", "ready"].includes(item.status);
const labels = {
  queued: "Đang chờ",
  uploading: "Đang tải lên",
  processing: "Đang xử lý PDF",
  indexed: "Đã nhập",
  skipped: "Đã có trong thư viện",
  ready: "Bản xem trước đã sẵn sàng",
  error: "Chưa nhập được",
};

export default function ImportProgress({ job, compact = false, onOpen, onDismiss }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (job.finished) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [job.id, job.finished]);
  const done = job.items.filter(complete).length;
  const failed = job.items.filter((item) => item.status === "error").length;
  const current = job.items.find((item) => ["uploading", "processing"].includes(item.status));
  const percent = Math.round((done / job.items.length) * 100);
  const seconds = Math.max(0, Math.floor(((job.endedAt || now) - job.startedAt) / 1000));
  const elapsed = seconds < 60 ? `${seconds} giây` : `${Math.floor(seconds / 60)} phút ${seconds % 60} giây`;
  const title = job.finished
    ? failed ? "Đã xử lý xong · Có PDF cần thử lại" : job.mode === "preview" ? "Bản xem trước đã sẵn sàng" : "Đã nhập xong tài liệu"
    : job.mode === "preview" ? "Đang chuẩn bị bản xem trước" : "Đang nhập tài liệu";
  const activity = current?.status === "uploading"
    ? `Đang tải lên · ${current.upload || 0}%`
    : job.mode === "preview" ? "Đang đọc PDF và chuẩn bị bản dịch…" : "Đang đọc PDF, OCR nếu cần và lập chỉ mục…";

  if (compact) {
    return (
      <div className="ws-import-compact" role="status" aria-live="polite">
        {job.finished ? <Check size={17} /> : <LoaderCircle className="spin" size={17} />}
        <div><b>{title}</b><span>{job.topicName} · {done}/{job.items.length} PDF đã xử lý</span></div>
        <button className="text-button" onClick={onOpen}>Xem tiến trình <ChevronRight size={14} /></button>
        {job.finished && <button className="icon" aria-label="Ẩn tiến trình nhập" onClick={onDismiss}><X size={15} /></button>}
      </div>
    );
  }
  return (
    <section className={"ws-import-progress " + (failed && job.finished ? "has-errors" : "")} aria-label="Tiến trình nhập tài liệu">
      <div className="ws-import-heading">
        <span className="ws-import-symbol">{job.finished ? failed ? <AlertCircle size={21} /> : <Check size={21} /> : <LoaderCircle className="spin" size={21} />}</span>
        <div role="status" aria-live="polite"><b>{title}</b><span>{done}/{job.items.length} PDF đã xử lý · {job.topicName}</span></div>
        <strong>{percent}%</strong>
        {job.finished && <button className="icon" aria-label="Ẩn tiến trình nhập" onClick={onDismiss}><X size={15} /></button>}
      </div>
      <progress className="ws-import-total" max={job.items.length} value={done} aria-label="Số PDF đã xử lý" />
      {!job.finished && (
        <div className="ws-import-activity">
          <div><span>{activity}</span><time aria-hidden="true">Đã chạy {elapsed}</time></div>
          <div className={"ws-import-live-track " + (current?.status === "uploading" ? "is-uploading" : "") } aria-hidden="true">
            <i style={current?.status === "uploading" ? { width: `${current.upload || 0}%` } : undefined} />
          </div>
          <p>Bạn có thể chuyển tab hoặc mở thư viện khác. Giữ trang này mở để tiếp tục nhập.</p>
        </div>
      )}
      <ol className="ws-import-files">
        {job.items.map((item, index) => (
          <li key={index} data-status={item.status}>
            {item.status === "error" ? <AlertCircle size={16} /> : complete(item) ? <Check size={16} /> : ["uploading", "processing"].includes(item.status) ? <LoaderCircle size={16} className="spin" /> : <FileText size={16} />}
            <div><b>{item.name}</b>{item.message && <small>{item.message}</small>}</div>
            <span>{item.status === "processing" && job.mode === "preview" ? "Đang chuẩn bị bản xem trước" : labels[item.status] || "Đang xử lý"}{item.status === "uploading" ? ` ${item.upload || 0}%` : ""}</span>
          </li>
        ))}
      </ol>
      {job.finished && <p className="ws-import-summary">{failed ? `${failed} PDF chưa nhập được. Các PDF đã nhập vẫn được giữ trong thư viện; bạn có thể thử lại những file lỗi.` : job.mode === "preview" ? "Bạn có thể đọc và chỉnh sửa từng trang trước khi nhập." : "Tài liệu đã sẵn sàng trong thư viện."}</p>}
    </section>
  );
}

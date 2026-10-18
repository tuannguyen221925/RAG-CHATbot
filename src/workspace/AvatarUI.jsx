import React, { useEffect, useRef, useState } from "react";
import {
  Bot,
  Camera,
  Check,
  ImagePlus,
  LoaderCircle,
  RotateCcw,
} from "lucide-react";
import { AVATARS, getAvatarPreset } from "../../shared/avatars.mjs";

export function Avatar({
  avatar,
  name = "",
  bot = false,
  size,
  className = "",
}) {
  const preset = getAvatarPreset(avatar?.preset);
  const source = avatar?.url;
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [source]);
  const letters = String(name || "B")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
  return (
    <span
      className={`bgr-avatar ${className}`}
      aria-hidden="true"
      style={{
        ...(size ? { width: size, height: size, fontSize: size * 0.49 } : {}),
        ...(preset.background
          ? { background: preset.background, color: preset.color }
          : {}),
      }}
    >
      {source?.startsWith("/api/avatars/") && !failed ? (
        <img src={source} alt="" onError={() => setFailed(true)} />
      ) : (
        preset.emoji ||
        (bot ? <Bot /> : <span className="bgr-avatar-letters">{letters}</span>)
      )}
    </span>
  );
}

export function AvatarPicker({ current, name, bot = false, busy, onSave }) {
  const [selected, setSelected] = useState(current || { preset: "default" });
  const [image, setImage] = useState(null),
    [zoom, setZoom] = useState(1),
    [panX, setPanX] = useState(0),
    [panY, setPanY] = useState(0);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const fileInput = useRef(null),
    imageRef = useRef(null),
    version = useRef(0);
  useEffect(
    () => () => {
      version.current++;
    },
    [],
  );
  useEffect(
    () => () => {
      if (image?.url) URL.revokeObjectURL(image.url);
    },
    [image],
  );
  async function pickFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const request = ++version.current;
    setError("");
    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size > 5 * 1024 * 1024
    ) {
      setError("Chọn JPG, PNG hoặc WebP, tối đa 5 MB.");
      return;
    }
    setLoading(true);
    const url = URL.createObjectURL(file);
    try {
      const loaded = new Image();
      loaded.src = url;
      await loaded.decode();
      if (loaded.naturalWidth * loaded.naturalHeight > 20_000_000)
        throw new Error("Ảnh quá lớn. Chọn ảnh tối đa 20 triệu pixel.");
      if (request !== version.current) {
        URL.revokeObjectURL(url);
        return;
      }
      imageRef.current = loaded;
      setImage({
        url,
        width: loaded.naturalWidth,
        height: loaded.naturalHeight,
      });
      setZoom(1);
      setPanX(0);
      setPanY(0);
      setSelected({ preset: "custom" });
    } catch (e) {
      URL.revokeObjectURL(url);
      if (request === version.current)
        setError(
          e.message.startsWith("Ảnh quá")
            ? e.message
            : "Không đọc được ảnh. Thử một ảnh khác nhé.",
        );
    } finally {
      if (request === version.current) setLoading(false);
    }
  }
  function choose(preset) {
    version.current++;
    setLoading(false);
    setError("");
    setImage(null);
    imageRef.current = null;
    setSelected({ preset });
  }
  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      let file = null;
      if (image) {
        const side = Math.min(image.width, image.height) / zoom;
        const canvas = document.createElement("canvas");
        canvas.width = 384;
        canvas.height = 384;
        const context = canvas.getContext("2d");
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, 384, 384);
        context.drawImage(
          imageRef.current,
          ((image.width - side) / 2) * (1 + panX / 100),
          ((image.height - side) / 2) * (1 + panY / 100),
          side,
          side,
          0,
          0,
          384,
          384,
        );
        const blob = await new Promise((resolve) =>
          canvas.toBlob(resolve, "image/jpeg", 0.9),
        );
        if (!blob) throw new Error("Không xử lý được ảnh. Thử lại nhé.");
        file = new File([blob], "avatar.jpg", { type: "image/jpeg" });
      }
      await onSave(selected, file);
    } catch (e) {
      setError(e.message);
    }
  }
  const scale = image ? (180 / Math.min(image.width, image.height)) * zoom : 1;
  return (
    <form className="bgr-avatar-editor" onSubmit={save}>
      <div className="bgr-avatar-hero">
        {image ? (
          <div
            className="bgr-crop-preview"
            aria-label="Xem trước vùng cắt avatar"
          >
            <img
              src={image.url}
              alt="Ảnh đang chỉnh"
              style={{
                width: image.width * scale,
                height: image.height * scale,
                left: (-(image.width * scale - 180) / 2) * (1 + panX / 100),
                top: (-(image.height * scale - 180) / 2) * (1 + panY / 100),
              }}
            />
          </div>
        ) : (
          <Avatar avatar={selected} name={name} bot={bot} size={86} />
        )}
        <div>
          <b>{name}</b>
          <small>
            {bot
              ? "Một gương mặt riêng cho trợ lý của bạn"
              : "Gương mặt của bạn trong mọi cuộc trò chuyện"}
          </small>
          <button
            type="button"
            autoFocus
            className="secondary bgr-avatar-upload"
            disabled={busy || loading}
            onClick={() => fileInput.current?.click()}
          >
            {loading ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <ImagePlus size={16} />
            )}{" "}
            Chọn ảnh từ máy
          </button>
          <span className="bgr-avatar-file-hint">
            JPG, PNG, WebP · Tối đa 5 MB
          </span>
        </div>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={pickFile}
        disabled={busy}
      />
      {image && (
        <div className="bgr-crop-controls">
          <label>
            Phóng to{" "}
            <input
              type="range"
              aria-label="Phóng to avatar"
              min="1"
              max="3"
              step="0.05"
              value={zoom}
              disabled={busy}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
          </label>
          <label>
            Trái / phải{" "}
            <input
              type="range"
              aria-label="Vị trí ngang avatar"
              min="-100"
              max="100"
              value={panX}
              disabled={busy}
              onChange={(e) => setPanX(Number(e.target.value))}
            />
          </label>
          <label>
            Lên / xuống{" "}
            <input
              type="range"
              aria-label="Vị trí dọc avatar"
              min="-100"
              max="100"
              value={panY}
              disabled={busy}
              onChange={(e) => setPanY(Number(e.target.value))}
            />
          </label>
        </div>
      )}
      <div className="bgr-avatar-heading">
        <Camera size={15} />
        <span>Hoặc chọn một mẫu bạn thích</span>
      </div>
      <div className="bgr-avatar-grid">
        {AVATARS.map((preset) => (
          <button
            type="button"
            key={preset.id}
            aria-label={`Avatar ${preset.name}`}
            aria-pressed={!image && selected.preset === preset.id}
            className={!image && selected.preset === preset.id ? "chosen" : ""}
            disabled={busy || loading}
            onClick={() => choose(preset.id)}
          >
            <Avatar
              avatar={{ preset: preset.id }}
              name={name}
              bot={bot}
              size={45}
            />
            <span>{preset.name}</span>
            {!image && selected.preset === preset.id && (
              <Check className="bgr-avatar-check" size={12} />
            )}
          </button>
        ))}
      </div>
      {current?.preset === "custom" && !image && (
        <button
          type="button"
          className="bgr-current-photo"
          aria-pressed={selected.preset === "custom"}
          disabled={busy || loading}
          onClick={() => {
            setSelected(current);
            setError("");
          }}
        >
          <Avatar avatar={current} name={name} bot={bot} size={30} /> Giữ ảnh
          hiện tại {selected.preset === "custom" && <Check size={14} />}
        </button>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="bgr-avatar-actions">
        <button
          type="button"
          className="text-button"
          disabled={busy || loading}
          onClick={() => choose("default")}
        >
          <RotateCcw size={13} /> Dùng mặc định
        </button>
        <button type="submit" className="primary" disabled={busy || loading}>
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Check size={16} />
          )}{" "}
          Lưu avatar
        </button>
      </div>
    </form>
  );
}

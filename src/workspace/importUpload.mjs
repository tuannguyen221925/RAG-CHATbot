// Browser upload progress is separate from PDF processing on the server.
import { logApiError } from "./apiClient.mjs";
export function uploadPdf(url, form, onProgress = () => {}, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const clean = () => signal?.removeEventListener("abort", abort);
    if (signal?.aborted) {
      reject(new DOMException("Đã dừng gửi tài liệu.", "AbortError"));
      return;
    }
    xhr.open("POST", "/api" + url);
    xhr.responseType = "json";
    xhr.withCredentials = true;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    xhr.upload.onload = () => onProgress(100);
    xhr.onload = () => {
      clean();
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response) {
        resolve(xhr.response);
      } else {
        logApiError(url, xhr.status, xhr.getResponseHeader?.("X-Request-ID"));
        reject(new Error(xhr.response?.error || "Không thể xử lý PDF. Kiểm tra thư viện trước khi thử lại."));
      }
    };
    xhr.onerror = () => {
      clean();
      logApiError(url, 0);
      reject(new Error("Mất kết nối khi nhập PDF. Kiểm tra thư viện trước khi thử lại."));
    };
    xhr.onabort = () => {
      clean();
      reject(new DOMException("Đã dừng gửi tài liệu.", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
    onProgress(0);
    xhr.send(form);
  });
}

export function validateImportFiles(files, preview = false) {
  if (!files.length) throw new Error("Chọn ít nhất một PDF.");
  if (preview && files.length !== 1) {
    throw new Error("Chọn một PDF để xem và sửa bản dịch từng trang.");
  }
  if (files.length > 10) throw new Error("Chọn tối đa 10 PDF mỗi lượt.");
  if (files.some((file) => file.size > 50 * 1024 * 1024)) {
    throw new Error("Mỗi PDF tối đa 50 MB.");
  }
  if (files.reduce((total, file) => total + file.size, 0) > 75 * 1024 * 1024) {
    throw new Error("Tổng PDF vượt 75 MB.");
  }
}

export async function importQueue(files, importOne, onItem, signal) {
  const results = [];
  for (let index = 0; index < files.length; index++) {
    if (signal?.aborted) throw new DOMException("Đã dừng gửi tài liệu.", "AbortError");
    onItem(index, { status: "uploading", upload: 0 });
    let active = true;
    try {
      const result = await importOne(files[index], (upload) => {
        if (active) onItem(index, { upload, status: upload === 100 ? "processing" : "uploading" });
      });
      active = false;
      results.push(result);
      const coverage = result.status === "indexed" && result.pages != null
        ? `${result.pages}/${result.total_pages ?? result.pages} trang · OCR ${result.ocr_pages || 0} trang${result.empty_pages?.length ? ` · Không đọc được chữ ở trang ${result.empty_pages.join(", ")}` : ""}`
        : "";
      onItem(index, { status: result.status, message: result.error || coverage, result });
    } catch (error) {
      active = false;
      if (error.name === "AbortError") throw error;
      const result = { file: files[index].name, status: "error", error: error.message };
      results.push(result);
      onItem(index, { status: "error", message: error.message, result });
    }
  }
  return results;
}

export function logApiError(url, status, requestId) {
  console.error("[BIG_RAG] API request failed", {
    methodPath: "/api" + url.split("?")[0],
    status,
    requestId: requestId || null,
  });
}

export async function api(url, options = {}) {
  const init = { credentials: "same-origin", ...options };
  if (init.body && !(init.body instanceof FormData)) {
    init.headers = { "Content-Type": "application/json", ...init.headers };
    init.body = JSON.stringify(init.body);
  }
  let response;
  try {
    response = await fetch("/api" + url, init);
  } catch (cause) {
    logApiError(url, 0);
    throw new Error("Không kết nối được API. Kiểm tra backend đang chạy.", { cause });
  }
  const requestId = response.headers.get("X-Request-ID");
  let data;
  try {
    data = await response.json();
  } catch (cause) {
    logApiError(url, response.status, requestId);
    throw new Error("API trả dữ liệu không hợp lệ. Kiểm tra log backend.", { cause });
  }
  if (!response.ok) {
    logApiError(url, response.status, requestId);
    const error = new Error(data.error || "Không thể xử lý yêu cầu.");
    error.requestId = requestId;
    throw error;
  }
  return data;
}

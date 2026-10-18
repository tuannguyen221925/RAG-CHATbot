import assert from "node:assert/strict";
import { api } from "../src/workspace/apiClient.mjs";

const originalFetch = globalThis.fetch;
const originalError = console.error;
const logs = [];
console.error = (...args) => logs.push(args);
try {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: "Synthetic backend failure" }), {
    status: 500, headers: { "Content-Type": "application/json", "X-Request-ID": "test-request" },
  });
  await assert.rejects(api("/auth/login?token=private-query", {
    method: "POST", body: { password: "never-log-this-password" },
  }), (error) => error.requestId === "test-request" && /Synthetic backend failure/.test(error.message));
  assert.equal(logs[0][1].status, 500);
  assert.equal(logs[0][1].requestId, "test-request");
  assert.doesNotMatch(JSON.stringify(logs), /private-query|never-log-this-password/);
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(api("/topics"), /Không kết nối được API/);
  assert.equal(logs[1][1].status, 0);
  globalThis.fetch = async () => new Response("Upstream unavailable", { status: 502 });
  await assert.rejects(api("/topics"), /dữ liệu không hợp lệ/);
  assert.equal(logs[2][1].status, 502);
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true }));
  assert.deepEqual(await api("/topics"), { ok: true });
  assert.equal(logs.length, 3);
} finally {
  globalThis.fetch = originalFetch;
  console.error = originalError;
}
console.log("PASS: API failures log status/request ID, omit credentials/query and preserve successful responses");

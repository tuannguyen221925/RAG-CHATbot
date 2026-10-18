// Exercise queue ordering, transport errors and the user-visible progress states.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { importQueue, uploadPdf, validateImportFiles } from "../src/workspace/importUpload.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "storage", "import-progress-check.mjs");
const files = [{ name: "chapter.pdf", size: 1200 }, { name: "broken.pdf", size: 1300 }, { name: "existing.pdf", size: 1200 }];
let release;
let lateProgress;
const requested = [];
const items = files.map((file) => ({ name: file.name, status: "queued" }));
const resultsPromise = importQueue(files, async (file, onProgress) => {
  requested.push(file.name);
  onProgress(50);
  onProgress(100);
  if (file.name === "chapter.pdf") {
    lateProgress = onProgress;
    await new Promise((resolve) => { release = resolve; });
    return { file: file.name, status: "indexed" };
  }
  if (file.name === "broken.pdf") throw new Error("Unreadable PDF");
  return { file: file.name, status: "skipped" };
}, (index, patch) => Object.assign(items[index], patch));
assert.deepEqual(requested, ["chapter.pdf"]);
assert.equal(items[0].status, "processing");
assert.equal(items[1].status, "queued");
release();
const results = await resultsPromise;
assert.deepEqual(results.map((result) => result.status), ["indexed", "error", "skipped"]);
assert.equal(items[1].message, "Unreadable PDF");
lateProgress(90);
assert.equal(items[0].status, "indexed");
console.log("PASS: sequential PDFs, live processing state, per-file errors and late upload events");

let coverageMessage;
await importQueue([files[0]], async () => ({ status: "indexed", pages: 4, total_pages: 5, ocr_pages: 3, empty_pages: [2] }),
  (index, item) => { if (item.message) coverageMessage = item.message; });
assert.match(coverageMessage, /4\/5 trang · OCR 3 trang/);
assert.match(coverageMessage, /Không đọc được chữ ở trang 2/);
console.log("PASS: page coverage and unreadable pages are visible after import");

const abortController = new AbortController();
let abortedRequests = 0;
await assert.rejects(importQueue(files, async (file) => {
  abortedRequests++;
  abortController.abort();
  return { file: file.name, status: "indexed" };
}, () => {}, abortController.signal), { name: "AbortError" });
assert.equal(abortedRequests, 1);
console.log("PASS: leaving the workspace stops sending queued PDFs");

assert.throws(() => validateImportFiles([]), /PDF/);
assert.throws(() => validateImportFiles(files, true), /một PDF/);
assert.throws(() => validateImportFiles(Array(11).fill(files[0])), /10 PDF/);
assert.throws(() => validateImportFiles([{ size: 51 * 1024 * 1024 }]), /50 MB/);
assert.throws(() => validateImportFiles([{ size: 40 * 1024 * 1024 }, { size: 40 * 1024 * 1024 }]), /75 MB/);
validateImportFiles(files);
console.log("PASS: batch and per-file limits stay enforced with sequential uploads");

class FakeXHR {
  constructor() { this.upload = {}; FakeXHR.last = this; }
  open(method, url) { this.method = method; this.url = url; }
  send(form) { this.form = form; }
  abort() { this.onabort(); }
}
globalThis.XMLHttpRequest = FakeXHR;
const progress = [];
const form = new FormData();
const request = uploadPdf("/ingest", form, (value) => progress.push(value));
const xhr = FakeXHR.last;
assert.equal(xhr.url, "/api/ingest");
assert.equal(xhr.method, "POST");
assert.equal(xhr.withCredentials, true);
xhr.upload.onprogress({ lengthComputable: true, loaded: 5, total: 10 });
xhr.upload.onload();
assert.deepEqual(progress, [0, 50, 100]);
xhr.status = 200;
xhr.response = { results: [{ status: "indexed" }] };
xhr.onload();
assert.equal((await request).results[0].status, "indexed");
const failure = uploadPdf("/ingest", form);
FakeXHR.last.status = 401;
FakeXHR.last.response = { error: "Session expired" };
FakeXHR.last.onload();
await assert.rejects(failure, /Session expired/);
const network = uploadPdf("/ingest", form);
FakeXHR.last.onerror();
await assert.rejects(network, /Mất kết nối/);
const controller = new AbortController();
const cancelled = uploadPdf("/ingest", form, () => {}, controller.signal);
controller.abort();
await assert.rejects(cancelled, { name: "AbortError" });
console.log("PASS: actual byte progress, credential cookies, server/network errors and abort");

try {
  await build({ entryPoints: [path.join(root, "src/workspace/ImportProgress.jsx")], outfile: output, bundle: true, platform: "node", format: "esm", packages: "external", loader: { ".css": "empty" }, logLevel: "silent" });
  const { default: ImportProgress } = await import(pathToFileURL(output));
  const job = { id: 1, mode: "import", topicName: "Deep Learning", startedAt: Date.now() - 65000, finished: false, items: files.map((file, index) => ({ name: file.name, status: index === 0 ? "indexed" : index === 1 ? "processing" : "queued" })) };
  const render = (value, compact = false) => renderToStaticMarkup(React.createElement(ImportProgress, { job: value, compact }));
  const html = render(job);
  assert.match(html, /1\/3 PDF đã xử lý/);
  assert.match(html, /33%/);
  assert.match(html, /<progress[^>]*max="3"[^>]*value="1"/);
  assert.match(html, /1 phút 5 giây/);
  assert.match(html, /Đang xử lý PDF/);
  assert.match(html, /Giữ trang này mở/);
  assert.match(render(job, true), /Xem tiến trình/);
  const failed = render({ ...job, finished: true, endedAt: Date.now(), items });
  assert.match(failed, /100%/);
  assert.match(failed, /Có PDF cần thử lại/);
  assert.match(failed, /Unreadable PDF/);
  const preview = render({ ...job, mode: "preview", finished: true, items: [{ name: "one.pdf", status: "ready" }] });
  assert.match(preview, /Bản xem trước đã sẵn sàng/);
  assert.doesNotMatch(preview, /Đã nhập xong tài liệu/);
  console.log("PASS: honest file counts, activity timer, compact navigation, errors and preview status");
} finally {
  await fs.unlink(output).catch(() => {});
}

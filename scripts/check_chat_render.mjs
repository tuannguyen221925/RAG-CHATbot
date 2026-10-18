// Checks answer formatting and untrusted content without a browser or a live LLM.
import assert from "node:assert/strict";
import { build } from "esbuild";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "storage", "chat-ui-check.mjs");
await fs.mkdir(path.dirname(output), { recursive: true });
try {
  await build({
    entryPoints: [path.join(root, "src/workspace/ChatUI.jsx")],
    outfile: output,
    bundle: true,
    platform: "node",
    format: "esm",
    packages: "external",
    logLevel: "silent",
  });
  const { AnswerBody, ChatMessage, ChatWelcome } = await import(
    pathToFileURL(output)
  );
  const answer = (content) =>
    renderToStaticMarkup(React.createElement(AnswerBody, { content }));
  assert.match(
    answer("### Học tập\n\n**Dữ liệu có nhãn**\n\n- Ví dụ đầu tiên"),
    /<h3>Học tập<\/h3>[\s\S]*<strong>Dữ liệu có nhãn<\/strong>[\s\S]*<ul>/,
  );
  console.log("PASS: headings, emphasis and lists");
  const table = answer(
    "| Cách học | Nhãn |\n| --- | --- |\n| Có giám sát | Có |",
  );
  assert.match(table, /ws-table-scroll/);
  assert.match(table, /<table>/);
  assert.match(table, /<td>Có giám sát<\/td>/);
  console.log("PASS: readable table in a scroll container");
  assert.match(
    answer("`y = f(x)`\n\n```python\nprint('hello')\n```"),
    /<code>y = f\(x\)<\/code>[\s\S]*<pre><code class="language-python">/,
  );
  console.log("PASS: inline and fenced code");
  const formulas = answer(String.raw`- Công thức: $Accuracy = \frac{TP + TN}{TP + FP + FN + TN}$ [3].

1. **Độ chính xác (Precision):**
   - Công thức: $Precision = \frac{TP}{TP + FP}$ [3].
   - Công thức: $Recall = \frac{TP}{TP + FN}$ [3].`);
  assert.equal((formulas.match(/class="katex"/g) || []).length, 3);
  assert.equal((formulas.match(/<mfrac>/g) || []).length, 3);
  assert.match(formulas, /\[3\]/);
  assert.doesNotMatch(formulas, /katex-error/);
  assert.match(answer(String.raw`$$
F_1 = \frac{2 \cdot Precision \cdot Recall}{Precision + Recall}
$$`), /class="katex-display"/);
  console.log("PASS: inline fractions, block formulas and source citations");
  const literalFormula = answer("`" + String.raw`$Precision = \frac{TP}{TP + FP}$` + "`");
  assert.doesNotMatch(literalFormula, /class="katex"/);
  assert.match(literalFormula, /<code>/);
  console.log("PASS: math inside code remains literal");
  const malformedMath = answer(String.raw`$\frac{TP}{$`);
  assert.match(malformedMath, /katex-error/);
  const untrustedMath = answer(String.raw`$\href{javascript:alert(1)}{click}$`);
  assert.doesNotMatch(untrustedMath, /href="javascript:|<script/);
  console.log("PASS: malformed and untrusted math does not crash or create unsafe links");
  const untrusted = answer(
    "<script>alert(1)</script>\n\n[unsafe](javascript:alert(1))\n\n![remote](https://example.com/track.png)",
  );
  assert.doesNotMatch(untrusted, /<script|javascript:|<img/);
  console.log("PASS: raw HTML, unsafe links and remote images blocked");
  const user = { name: "Minh Anh" };
  const userMessage = renderToStaticMarkup(
    React.createElement(ChatMessage, {
      user,
      botName: "Nova",
      documents: [],
      message: { role: "user", content: "<img src=x onerror=alert(1)>" },
    }),
  );
  assert.match(userMessage, /Minh Anh/);
  assert.match(userMessage, /&lt;img/);
  assert.doesNotMatch(userMessage, /<img/);
  console.log("PASS: account name and literal user content");
  const botMessage = renderToStaticMarkup(
    React.createElement(ChatMessage, {
      user,
      botName: "Nova",
      documents: [{ id: "doc1", filename: "chapter.pdf" }],
      message: {
        role: "assistant",
        content: "Câu trả lời [1]",
        sources: [
          { id: 1, file: "chapter.pdf", page: 2, excerpt: "Nội dung nguồn" },
        ],
      },
    }),
  );
  assert.match(botMessage, /Nova/);
  assert.match(botMessage, /Nguồn tham khảo/);
  assert.match(botMessage, /Trang <!-- -->2|Trang 2/);
  assert.match(botMessage, /\/api\/documents\/doc1\/file/);
  console.log("PASS: bot nickname, source page and original PDF link");
  const coverage = renderToStaticMarkup(React.createElement(ChatMessage, {
    user, botName: "Nova", documents: [],
    message: { role: "assistant", content: "Overview [1]",
      sources: [{ file: "a.pdf", page: 1 }, { file: "a.pdf", page: 2 }, { file: "b.pdf", page: 1 }],
      retrieval: { file_coverage_complete: false, available_files: 7 } },
  }));
  assert.match(coverage.replace(/<!--.*?-->/g, ""), /3 đoạn · 2 tài liệu/);
  assert.match(coverage, /role="status"/);
  assert.match(coverage.replace(/<!--.*?-->/g, ""), /2\/7 tài liệu/);
  console.log("PASS: distinct file count and incomplete overview are visible");
  const welcome = renderToStaticMarkup(
    React.createElement(ChatWelcome, {
      user,
      botName: "Nova",
      active: null,
      documents: [],
      busy: false,
    }),
  );
  assert.match(welcome, /Tạo thư viện/);
  assert.doesNotMatch(welcome, /Tóm tắt nhanh/);
  console.log("PASS: useful first-use state with no library");
  const customAvatars = renderToStaticMarkup(
    React.createElement(ChatMessage, {
      message: { role: "user", content: "Hello" },
      user: {
        name: "Alice",
        avatar: {
          preset: "custom",
          url: "/api/avatars/profile/image?v=fixture",
        },
      },
      botName: "Nova",
      documents: [],
    }),
  );
  assert.match(
    customAvatars,
    /src="\/api\/avatars\/profile\/image\?v=fixture"/,
  );
  const botAvatar = renderToStaticMarkup(
    React.createElement(ChatMessage, {
      message: { role: "assistant", content: "Hello" },
      user,
      botName: "Nova",
      botAvatar: { preset: "fox" },
      documents: [],
    }),
  );
  assert.match(botAvatar, /🦊/);
  console.log("PASS: custom profile avatar and per-library bot avatar");
  const unsafeAvatar = renderToStaticMarkup(
    React.createElement(ChatMessage, {
      message: { role: "user", content: "Hello" },
      user: {
        name: "Alice",
        avatar: { preset: "custom", url: "https://example.com/track.png" },
      },
      botName: "Nova",
      documents: [],
    }),
  );
  assert.doesNotMatch(unsafeAvatar, /<img/);
  console.log("PASS: external avatar image URLs blocked");
  console.log("13 chat rendering checks passed.");
} finally {
  await fs.unlink(output).catch(() => {});
}

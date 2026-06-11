#!/usr/bin/env node
/**
 * papergirl · 可选增强：给本地 browser-relay 加一个 /api/cookies 路由。
 *
 * 为什么需要：last30days 的 X 源要 auth_token（httpOnly cookie），页面 JS / relay 的
 * eval 都读不到。browser-relay 的扩展已持有 chrome.debugger CDP 会话，能跑
 * Network.getAllCookies 拿到 httpOnly cookie，但 relay 没暴露对应 HTTP 路由。
 * 本补丁只给 relay 加这一个路由（扩展无需改动），且强制按域名过滤，不开"导出全部 cookie"的口子。
 *
 * 特性：幂等（已打过就跳过）、自带备份、可 --revert 还原。改的是你本机全局 npm 包，
 * npm 更新 browser-relay 后需重跑本脚本。开源用户若不用 X 源，完全不必跑它。
 *
 * 用法：
 *   node ops/patch-browser-relay.mjs           # 打补丁
 *   node ops/patch-browser-relay.mjs --revert  # 还原
 * 打完/还原后重启 relay：browser-relay restart
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const MARKER = "PAPERGIRL_COOKIES_ROUTE";
const revert = process.argv.includes("--revert");

function relayServerPath() {
  // `browser-relay path` 打印扩展目录：<pkg>/extension —— 包根是它的父目录
  const extDir = execSync("browser-relay path", { encoding: "utf8" }).trim();
  const file = path.join(path.dirname(extDir), "server", "relay-server.js");
  if (!fs.existsSync(file)) {
    throw new Error(`relay-server.js not found at ${file}`);
  }
  return file;
}

const HANDLER = `
// ${MARKER} — injected by papergirl ops/patch-browser-relay.mjs
async function handleCookies(req, res) {
  await ensureExtension();
  const body = await readBody(req);
  const domain = typeof body.domain === "string" ? body.domain.replace(/^\\./, "") : "";
  if (!domain) return errorResponse(res, 400, "domain is required (e.g. .x.com) — refusing to dump all cookies");
  const sessionId = resolveTab(body.tabId);
  let result;
  try {
    result = await sendToExtension("Network.getAllCookies", {}, sessionId);
  } catch (e) {
    result = await sendToExtension("Storage.getCookies", {}, sessionId);
  }
  const all = (result && result.cookies) || [];
  const cookies = all.filter((c) => String(c.domain || "").replace(/^\\./, "").endsWith(domain));
  jsonResponse(res, 200, { ok: true, cookies });
}

`;

const HANDLER_ANCHOR = "async function handleSnapshot(req, res) {";
const ROUTE_ANCHOR = '      "POST /api/eval": handleEval,\n';
const ROUTE_LINE = '      "POST /api/cookies": handleCookies,\n';

function main() {
  const file = relayServerPath();
  const backup = file + ".papergirl-bak";
  let src = fs.readFileSync(file, "utf8");

  if (revert) {
    if (!fs.existsSync(backup)) {
      console.error("no backup found; nothing to revert");
      process.exit(1);
    }
    fs.copyFileSync(backup, file);
    fs.rmSync(backup);
    console.log(`reverted ${file} from backup`);
    console.log("now run: browser-relay restart");
    return;
  }

  if (src.includes(MARKER)) {
    console.log("already patched (marker present); nothing to do");
    return;
  }
  if (!src.includes(HANDLER_ANCHOR) || !src.includes(ROUTE_ANCHOR)) {
    console.error("anchors not found — browser-relay version may differ. Aborting without changes.");
    process.exit(1);
  }

  if (!fs.existsSync(backup)) fs.copyFileSync(file, backup);

  src = src.replace(HANDLER_ANCHOR, HANDLER + HANDLER_ANCHOR);
  src = src.replace(ROUTE_ANCHOR, ROUTE_ANCHOR + ROUTE_LINE);
  fs.writeFileSync(file, src);

  console.log(`patched ${file}`);
  console.log(`backup at ${backup}`);
  console.log("now run: browser-relay restart");
}

main();

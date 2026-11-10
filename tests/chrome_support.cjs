"use strict";
// Chrome creates DevToolsActivePort before HTTP discovery is necessarily serving.
// Only this pre-test readiness step retries. Actual inference assertions never do.
async function waitForDebugger(
  url,
  {
    fetchFn = globalThis.fetch,
    sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
    alive = () => true,
    attempts = 1200,
    timeoutMs = 30000,
  } = {},
) {
  let last;
  const deadline = Date.now() + timeoutMs;
  for (let i = 0; i < attempts && alive() && Date.now() < deadline; i++) {
    try {
      const r = await fetchFn(url, { signal: AbortSignal.timeout(1000) });
      if (!r.ok) throw Error("debugger HTTP " + r.status);
      const tabs = await r.json();
      const page = tabs.find(
        (t) => t.type === "page" && typeof t.webSocketDebuggerUrl === "string",
      );
      if (page) return page;
      last = Error("debugger has no page target");
    } catch (e) {
      last = e;
    }
    if (i + 1 < attempts) await sleep(25);
  }
  throw new Error(
    "Chrome debugger endpoint did not become ready: " +
      (last?.message || "browser exited"),
    { cause: last },
  );
}
module.exports = { waitForDebugger };

// setup-chrome may launch Chrome through a short-lived wrapper. Waiting only for
// that wrapper's exit leaves its children writing the profile during removal.
// Each test owns a detached POSIX process group; terminate that group, not any
// other Chrome session. Bounded waits here are teardown only, not test retries.
async function stopChrome(browser) {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const signalGroup = (signal) => {
    try {
      process.kill(-browser.pid, signal);
    } catch (e) {
      if (e.code !== "ESRCH") throw e;
    }
  };
  const groupAlive = () => {
    try {
      process.kill(-browser.pid, 0);
      return true;
    } catch (e) {
      if (e.code === "ESRCH") return false;
      throw e;
    }
  };
  if (!browser.pid) return;
  signalGroup("SIGTERM");
  for (let i = 0; i < 100 && groupAlive(); i++) await sleep(20);
  if (groupAlive()) {
    signalGroup("SIGKILL");
    // A just-killed process may briefly retain an open write before teardown.
    for (let i = 0; i < 50 && groupAlive(); i++) await sleep(20);
  }
  if (browser.exitCode === null && browser.signalCode === null)
    await Promise.race([
      new Promise((r) => browser.once("exit", r)),
      sleep(1000),
    ]);
}
module.exports.stopChrome = stopChrome;

// Download destinations may exist while Chrome is still flushing their bytes.
// Wait only for transport completion; parse and evidence assertions run once.
async function waitForDownload(
  file,
  expectedBytes,
  { timeoutMs = 10000, pollMs = 20 } = {},
) {
  const fs = require("node:fs");
  if (!Number.isInteger(expectedBytes) || expectedBytes < 1)
    throw new TypeError("expected download byte count must be positive");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const size = fs.statSync(file).size;
      if (size > expectedBytes)
        throw Error("download exceeds expected byte count");
      if (size === expectedBytes && !fs.existsSync(file + ".crdownload"))
        return;
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }
  throw Error("download did not complete within " + timeoutMs + "ms: " + file);
}
module.exports.waitForDownload = waitForDownload;

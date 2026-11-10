"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict"),
  fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path"),
  { spawn, execFileSync } = require("node:child_process"),
  { waitForDebugger } = require("./chrome_support.cjs");
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
async function stop(browser) {
  try {
    process.kill(-browser.pid, "SIGTERM");
  } catch {}
  if (browser.exitCode === null)
    await Promise.race([
      new Promise((r) => browser.once("exit", r)),
      delay(3000),
    ]);
  try {
    process.kill(-browser.pid, "SIGKILL");
  } catch {}
}
test(
  "actual Chrome full reports, all rows and stages, trusted certificate downloads",
  { timeout: 180000 },
  async () => {
    const server = require("node:http").createServer((req, res) => {
      try {
        const file = path.join(
          __dirname,
          "../docs",
          req.url === "/" ? "index.html" : req.url,
        );
        res.setHeader(
          "Content-Type",
          {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
          }[path.extname(file)] || "text/plain",
        );
        res.end(fs.readFileSync(file));
      } catch {
        res.statusCode = 404;
        res.end("not found");
      }
    });
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), "absorblab-")),
      browser = spawn(
        process.env.CHROME_BIN || "google-chrome",
        [
          "--headless",
          "--no-sandbox",
          "--disable-gpu",
          "--disable-extensions",
          "--disable-dev-shm-usage",
          "--remote-debugging-port=0",
          `--user-data-dir=${profile}`,
          "about:blank",
        ],
        { detached: true, stdio: ["ignore", "ignore", "pipe"] },
      );
    let ws,
      startupError,
      diagnostics = "";
    browser.on("error", (e) => (startupError = e));
    browser.stderr.on(
      "data",
      (d) => (diagnostics = (diagnostics + d).slice(-4000)),
    );
    try {
      for (
        let i = 0;
        i < 1200 &&
        !startupError &&
        browser.exitCode === null &&
        !fs.existsSync(path.join(profile, "DevToolsActivePort"));
        i++
      )
        await delay(25);
      assert.ok(
        fs.existsSync(path.join(profile, "DevToolsActivePort")),
        startupError?.message || diagnostics,
      );
      const port = fs
          .readFileSync(path.join(profile, "DevToolsActivePort"), "utf8")
          .split("\n")[0],
        tab = await waitForDebugger(`http://127.0.0.1:${port}/json/list`, {
          alive: () => browser.exitCode === null && !startupError,
        });
      ws = new WebSocket(tab.webSocketDebuggerUrl);
      await new Promise((r, j) => {
        ws.onopen = r;
        ws.onerror = j;
      });
      let seq = 0;
      const pending = new Map(),
        errors = [],
        downloads = new Map();
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.method === "Browser.downloadWillBegin")
          downloads.set(m.params.guid, { ...m.params, state: "started" });
        if (
          m.method === "Browser.downloadProgress" &&
          downloads.has(m.params.guid)
        )
          Object.assign(downloads.get(m.params.guid), m.params);
        if (m.method === "Runtime.exceptionThrown") errors.push(m.params);
        if (pending.has(m.id)) {
          const { r, j } = pending.get(m.id);
          pending.delete(m.id);
          m.error ? j(Error(JSON.stringify(m.error))) : r(m.result);
        }
      };
      const call = (method, params = {}) =>
          new Promise((r, j) => {
            const id = ++seq;
            pending.set(id, { r, j });
            ws.send(JSON.stringify({ id, method, params }));
          }),
        js = async (expression) => {
          const r = await call("Runtime.evaluate", {
            expression,
            returnByValue: true,
            awaitPromise: true,
          });
          if (r.exceptionDetails)
            throw Error(JSON.stringify(r.exceptionDetails));
          return r.result.value;
        };
      await call("Runtime.enable");
      await call("Page.enable");
      await call("Page.navigate", {
        url:
          process.env.ABSORBLAB_URL ||
          `http://127.0.0.1:${server.address().port}/`,
      });
      for (
        let i = 0;
        i < 500 && !(await js("Boolean(window.absorbReport)"));
        i++
      )
        await delay(20);
      assert.ok(await js("window.absorbReport"));
      const controls = JSON.parse(
          fs.readFileSync(
            path.join(__dirname, "../docs/controls.json"),
            "utf8",
          ),
        ),
        reports = JSON.parse(
          execFileSync(
            process.env.PYTHON || "python",
            [
              "-c",
              'import json;from absorblab import analyze;print(json.dumps([analyze(c["input"])for c in json.load(open("docs/controls.json"))]))',
            ],
            { maxBuffer: 128 * 1024 * 1024 },
          ),
        );
      const set = (id, value, event = "change") =>
          js(
            `document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event(${JSON.stringify(event)}))`,
          ),
        text = (id) =>
          js(`document.getElementById(${JSON.stringify(id)}).textContent`),
        cards = (id) =>
          js(
            `Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' .card'),e=>Array.from(e.children,c=>c.textContent))`,
          ),
        list = (xs) => (xs.length ? xs.join(", ") : "none"),
        cond = (x) => (x === null ? "undefined (zero success probability)" : x);
      async function shot(name) {
        if (!process.env.ABSORBLAB_SCREEN_DIR) return;
        await js(
          'document.activeElement.blur();window.scrollTo(0,0);document.querySelectorAll("textarea").forEach(e=>e.scrollTop=0);new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))',
        );
        const m = await call("Page.getLayoutMetrics"),
          image = await call("Page.captureScreenshot", {
            format: "png",
            captureBeyondViewport: true,
            clip: {
              x: 0,
              y: 0,
              width: await js("innerWidth"),
              height: m.cssContentSize.height,
              scale: 1,
            },
          });
        fs.mkdirSync(process.env.ABSORBLAB_SCREEN_DIR, { recursive: true });
        fs.writeFileSync(
          path.join(process.env.ABSORBLAB_SCREEN_DIR, name + ".png"),
          Buffer.from(image.data, "base64"),
        );
      }
      const counts = {
        reports: 0,
        stateSelections: 0,
        conditionedEdges: 0,
        forecastRows: 0,
        supportRounds: 0,
        eliminationStages: 0,
        downloads: 0,
      };
      for (const width of [1280, 390, 320]) {
        await call("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: false,
        });
        for (let ci = 0; ci < controls.length; ci++) {
          await set("control", ci);
          const r = reports[ci];
          assert.deepEqual(await js("window.absorbReport"), r);
          assert.deepEqual(JSON.parse(await text("json")), r);
          assert.equal(await text("why"), controls[ci].why);
          counts.reports++;
          const l = r.linear_system;
          assert.deepEqual(await cards("system"), [
            ["Unknowns", list(l.unknowns)],
            ["I-Q", JSON.stringify(l.matrix)],
            ["Exact inverse", JSON.stringify(l.inverse)],
            [
              "Boundary right-hand sides",
              `Success: ${l.success_rhs.join(", ") || "empty"}. Failure: ${l.failure_rhs.join(", ") || "empty"}.`,
            ],
          ]);
          assert.equal(
            await js('document.getElementById("elimination").disabled'),
            l.elimination.length === 0,
          );
          if (!l.elimination.length)
            assert.equal(
              await text("stage"),
              "No transient unknowns. The empty system needs no row operation.",
            );
          assert.deepEqual(
            await js(
              'Array.from(document.querySelectorAll("#limits li"),e=>e.textContent)',
            ),
            r.limits,
          );
          assert.deepEqual(
            await cards("components"),
            r.components.map((c) => [
              list(c.states),
              `Closed: ${c.closed}. Terminal kind: ${c.terminal_kind}. Nonterminal trap: ${c.nonterminal_trap}.`,
            ]),
          );
          for (let i = 0; i < r.states.length; i++) {
            await set("state", i);
            const s = r.states[i];
            assert.deepEqual(
              await js(
                'Array.from(document.querySelectorAll(".metric strong"),e=>e.textContent)',
              ),
              [
                s.success_probability,
                s.failure_probability,
                s.never_terminal_probability,
              ],
            );
            assert.deepEqual(
              await cards("conditioned"),
              r.conditioned[i].edges.map((e) => [
                `${s.name} → ${e.to}`,
                `Original: ${e.original_prob}. First-hit stopped: ${e.stopped_prob}. Future success h(${e.to}): ${e.success_weight}. Joint success mass: ${e.joint_success_mass}. Given eventual success: ${cond(e.conditioned_prob)}.`,
              ]),
            );
            assert.equal(
              (await cards("state-view"))[0][1],
              s.conditional_success
                ? `Mean: ${s.conditional_success.mean}. Second moment: ${s.conditional_success.second_moment}. Variance: ${s.conditional_success.variance}.`
                : "Undefined: success has probability zero.",
            );
            const t = (x) => (x.kind === "finite" ? x.value : "infinite");
            assert.deepEqual((await cards("state-view")).slice(1), [
              [
                "Unconditional first-hit times",
                `Stopped success: ${t(s.unconditional_success_time)}. Any terminal: ${t(s.unconditional_terminal_time)}. Mean given a terminal hit: ${s.conditional_terminal_mean ?? "undefined"}.`,
              ],
              [
                "Weighted success moments",
                `E[T; success] = ${s.success_time_numerator}. E[T²; success] = ${s.success_second_moment_numerator}. These are weighted numerators, not conditional means.`,
              ],
            ]);
            const p = r.support.paths[i];
            assert.deepEqual(await cards("path"), [
              [
                `Terminal path from ${s.name}`,
                p.path === null
                  ? "No positive-support terminal path."
                  : p.path.length
                    ? `${p.path.map((e) => e.from + " → " + e.to + " (" + e.prob + ")").join("; ")}. Product probability: ${p.probability}.`
                    : "Already terminal at time zero; probability 1.",
              ],
            ]);
            counts.stateSelections++;
            counts.conditionedEdges += r.states.length;
            for (const f of r.forecasts[i].rows) {
              await set("step", f.step);
              assert.deepEqual(await cards("forecast"), [
                [
                  `After ${f.step} transitions`,
                  `First success this step: ${f.new_success}. First failure this step: ${f.new_failure}. Success so far: ${f.success_by_step}. Failure so far: ${f.failure_by_step}. Still active: ${f.still_active}.`,
                ],
                [
                  "Successful trajectories not yet finished",
                  `Future success mass: ${f.future_success_mass}. Given eventual success, finished by now: ${cond(f.conditional_success_by_step)}. Remaining: ${cond(f.conditional_remaining)}.`,
                ],
              ]);
              assert.deepEqual(
                await cards("active"),
                r.states.map((s, j) => [
                  s.name + " / active mass",
                  f.active_mass[j],
                ]),
              );
              assert.equal(
                await js("document.documentElement.scrollWidth>innerWidth"),
                false,
              );
              counts.forecastRows++;
            }
          }
          for (const x of r.support.rounds) {
            await set("support", x.index);
            assert.deepEqual(await cards("support-view"), [
              [
                `Round ${x.index}`,
                `Before: ${list(x.before)}. After: ${list(x.after)}. Added: ${list(x.added)}.`,
              ],
              [
                "Boundary outside the restricted system",
                `Can hit a terminal: ${list(r.support.can_hit_terminal)}. Zero terminal-hit states: ${list(r.support.zero_terminal_states)}.`,
              ],
            ]);
            counts.supportRounds++;
          }
          for (const e of r.linear_system.elimination) {
            await set("elimination", e.column);
            assert.deepEqual(JSON.parse(await text("stage")), e);
            counts.eliminationStages++;
          }
          for (const id of ["state", "step", "support", "elimination"])
            await set(id, 0);
          await shot(`control-${ci}-${width}`);
          if ([1, 3, 4, 7, 8].includes(ci)) {
            await set("state", ci === 3 ? 1 : ci === 4 ? 2 : 0);
            await set("step", r.input.horizon);
            await shot(`detail-${ci}-${width}`);
            await set("state", 0);
            await set("step", 0);
          }
          if (width === 1280) {
            const dir = path.join(profile, "exports");
            fs.mkdirSync(dir, { recursive: true });
            await call("Browser.setDownloadBehavior", {
              behavior: "allowAndName",
              downloadPath: dir,
              eventsEnabled: true,
            });
            const previous = new Set(downloads.keys());
            await js(
              'document.getElementById("download").scrollIntoView({block:"center"})',
            );
            const b = await js(
              '(()=>{const r=document.getElementById("download").getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()',
            );
            await call("Input.dispatchMouseEvent", {
              type: "mousePressed",
              ...b,
              button: "left",
              clickCount: 1,
            });
            await call("Input.dispatchMouseEvent", {
              type: "mouseReleased",
              ...b,
              button: "left",
              clickCount: 1,
            });
            let item;
            for (let k = 0; k < 800; k++) {
              item = Array.from(downloads.values()).find(
                (d) => !previous.has(d.guid),
              );
              if (item?.state === "completed" || item?.state === "canceled")
                break;
              await delay(25);
            }
            assert.ok(item);
            assert.equal(item.suggestedFilename, "absorblab-certificate.json");
            assert.equal(item.state, "completed");
            const file = path.join(dir, item.guid);
            assert.deepEqual(JSON.parse(fs.readFileSync(file)), r);
            execFileSync(process.env.PYTHON || "python", [
              "-m",
              "absorblab",
              file,
              "--verify",
            ]);
            fs.unlinkSync(file);
            counts.downloads++;
          }
        }
      }
      await call("Emulation.setDeviceMetricsOverride", {
        width: 320,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false,
      });
      for (const raw of [
        "{}",
        '{"states":[],"states":[]}',
        "NaN",
        " ".repeat(65537),
      ]) {
        await set("input", raw, "input");
        assert.equal(await js("window.absorbReport"), null);
        assert.equal(
          await js('document.getElementById("results").hidden'),
          true,
        );
        assert.equal(
          await js('document.getElementById("download").disabled'),
          true,
        );
        assert.equal(await text("json"), "");
        await js('document.getElementById("run").click()');
        assert.match(await text("status"), /^Invalid input:/);
      }
      await shot("invalid-320");
      await set("control", 0);
      assert.deepEqual(await js("window.absorbReport"), reports[0]);
      await js('document.querySelector("details").open=true');
      assert.deepEqual(JSON.parse(await text("json")), reports[0]);
      await shot("expanded-320");
      await js(
        'document.querySelector("details").open=false;document.getElementById("run").focus()',
      );
      assert.equal(await js("document.activeElement.id"), "run");
      assert.deepEqual(errors, []);
      console.log(JSON.stringify(counts));
    } finally {
      ws?.close();
      await stop(browser);
      server.closeAllConnections();
      await new Promise((r) => server.close(r));
      await fs.promises.rm(profile, {
        recursive: true,
        force: true,
        maxRetries: 20,
        retryDelay: 100,
      });
    }
  },
);

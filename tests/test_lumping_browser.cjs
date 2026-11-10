"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os"),
  { spawn, execFileSync } = require("node:child_process"),
  {
    waitForDebugger,
    stopChrome,
    waitForDownload,
  } = require("./chrome_support.cjs"),
  delay = (ms) => new Promise((r) => setTimeout(r, ms));
test(
  "actual Chrome exact lumping: all partitions, pairs, rounds, forecasts and trusted downloads",
  { timeout: 180000 },
  async () => {
    const server = require("node:http").createServer((req, res) => {
      try {
        const f = path.join(
          __dirname,
          "../docs",
          req.url === "/" ? "lumping.html" : req.url.split("?")[0],
        );
        res.setHeader(
          "Content-Type",
          {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
          }[path.extname(f)] || "text/plain",
        );
        res.end(fs.readFileSync(f));
      } catch {
        res.statusCode = 404;
        res.end("not found");
      }
    });
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const profile = fs.mkdtempSync(
        path.join(os.tmpdir(), "absorblab-lumping-"),
      ),
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
      error,
      diagnostics = "";
    browser.on("error", (e) => (error = e));
    browser.stderr.on(
      "data",
      (d) => (diagnostics = (diagnostics + d).slice(-4000)),
    );
    try {
      for (
        let i = 0;
        i < 1200 &&
        !error &&
        browser.exitCode === null &&
        !fs.existsSync(path.join(profile, "DevToolsActivePort"));
        i++
      )
        await delay(25);
      assert.ok(
        fs.existsSync(path.join(profile, "DevToolsActivePort")),
        error?.message || diagnostics,
      );
      const port = fs
          .readFileSync(path.join(profile, "DevToolsActivePort"), "utf8")
          .split("\n")[0],
        tab = await waitForDebugger(`http://127.0.0.1:${port}/json/list`, {
          alive: () => browser.exitCode === null && !error,
        });
      ws = new WebSocket(tab.webSocketDebuggerUrl);
      await new Promise((r, j) => {
        ws.onopen = r;
        ws.onerror = j;
      });
      let seq = 0;
      const pending = new Map(),
        errors = [];
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
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
          process.env.ABSORBLAB_LUMPING_URL ||
          `http://127.0.0.1:${server.address().port}/`,
      });
      for (
        let i = 0;
        i < 400 && !(await js("Boolean(window.currentLumpingReport)"));
        i++
      )
        await delay(25);
      assert.ok(await js("Boolean(window.currentLumpingReport)"));
      const controls = JSON.parse(
          fs.readFileSync(
            path.join(__dirname, "../docs/lumping-controls.json"),
            "utf8",
          ),
        ),
        expected = JSON.parse(
          execFileSync(
            process.env.PYTHON || "python",
            [
              "-c",
              "import json;from absorblab.lumping import analyze_lumping;from absorblab.lumping_verify import verify_lumping;rs=[analyze_lumping(c['input'])for c in json.load(open('docs/lumping-controls.json'))];assert all(verify_lumping(r)for r in rs);print(json.dumps(rs))",
            ],
            { maxBuffer: 64e6 },
          ),
        );
      const set = (id, value, event = "change") =>
          js(
            `document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event(${JSON.stringify(event)}))`,
          ),
        rows = (id) =>
          js(
            `Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' tbody tr'),r=>Array.from(r.cells,c=>c.textContent))`,
          ),
        cards = (id) =>
          js(
            `Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' .card'),c=>[c.querySelector('h3').textContent,c.querySelector('p').textContent])`,
          ),
        yes = (x) => (x ? "yes" : "no"),
        fmt = (x) => (typeof x === "object" ? JSON.stringify(x) : String(x)),
        strings = (rs) => rs.map((r) => r.map(fmt)),
        part = (bs) =>
          bs
            .map((b) => "{" + b.map((i) => "s" + i).join(",") + "}")
            .join(" | "),
        record = (id) =>
          js(
            `JSON.parse(document.getElementById(${JSON.stringify(id)}).textContent)`,
          );
      async function shot(name) {
        if (!process.env.LUMPING_SCREEN_DIR) return;
        await js(
          'document.activeElement.blur();window.scrollTo(0,0);document.querySelectorAll("textarea").forEach(e=>e.scrollTop=0);new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))',
        );
        const m = await call("Page.getLayoutMetrics"),
          im = await call("Page.captureScreenshot", {
            format: "png",
            captureBeyondViewport: true,
            clip: {
              x: 0,
              y: 0,
              width: m.cssContentSize.width,
              height: m.cssContentSize.height,
              scale: 1,
            },
          });
        fs.mkdirSync(process.env.LUMPING_SCREEN_DIR, { recursive: true });
        fs.writeFileSync(
          path.join(process.env.LUMPING_SCREEN_DIR, name + ".png"),
          Buffer.from(im.data, "base64"),
        );
      }
      let reports = 0,
        rounds = 0,
        pairs = 0,
        partitions = 0,
        forecasts = 0,
        downloads = 0,
        graphEdges = 0;
      for (const width of [1280, 390, 320]) {
        await call("Emulation.setDeviceMetricsOverride", {
          width,
          height: 900,
          deviceScaleFactor: 1,
          mobile: false,
        });
        for (let ci = 0; ci < controls.length; ci++) {
          await set("control", ci);
          const r = expected[ci];
          assert.deepEqual(await js("window.currentLumpingReport"), r);
          assert.deepEqual(await record("report-json"), r);
          assert.equal(
            await js('document.getElementById("why").textContent'),
            controls[ci].why,
          );
          assert.deepEqual(
            await rows("block-table"),
            strings(
              r.final_blocks.map((b, i) => [
                "q" + i,
                part([b]),
                b.map((j) => r.input.chain.states[j].name).join(", "),
                r.colors[b[0]][0],
                r.colors[b[0]][1],
              ]),
            ),
          );
          assert.deepEqual(
            await rows("identity-table"),
            strings(
              r.intertwining.map((x) => [
                "s" + x.state,
                "q" + x.source_block,
                "q" + x.destination_block,
                x.original_mass,
                x.quotient_prob,
                yes(x.equal),
              ]),
            ),
          );
          for (const t of r.rounds) {
            await set("round", t.round);
            assert.deepEqual(await record("round-json"), t);
            const groups = r.colors.map((_, i) =>
              t.blocks.findIndex((b) => b.includes(i)),
            );
            assert.deepEqual(
              await rows("mass-table"),
              strings(
                t.masses.map((row, i) => [
                  "s" + i,
                  groups[i],
                  r.colors[i].join(" / "),
                  ...row,
                ]),
              ),
            );
            assert.deepEqual(
              await rows("pair-table"),
              strings(
                t.pairs.map((p) => [
                  "s" + p.left,
                  "s" + p.right,
                  yes(p.same_observation),
                  p.unequal_blocks
                    .map(
                      (x) =>
                        "B" +
                        x.block +
                        ": " +
                        x.left_mass +
                        " ≠ " +
                        x.right_mass,
                    )
                    .join("; ") || "none",
                ]),
              ),
            );
            assert.deepEqual(await cards("round-summary"), [
              ["Current partition", part(t.blocks)],
              ["Next partition", part(t.next_blocks)],
              [
                "Fixed point",
                t.fixed
                  ? "Every same-block pair agrees in every destination block."
                  : "At least one same-block pair differs. All resulting splits occur together.",
              ],
            ]);
            for (const [id, matrix, blocks] of [
              ["original-graph", r.original_matrix, groups],
              [
                "quotient-graph",
                r.quotient_matrix,
                r.final_blocks.map((_, i) => i),
              ],
            ]) {
              const ed = matrix.flatMap((row, i) =>
                row.flatMap((v, j) =>
                  v === "0" ? [] : [{ source: i, target: j, prob: v }],
                ),
              );
              assert.deepEqual(
                await js(
                  `Array.from(document.querySelectorAll('#${id} path.edge'),p=>({source:Number(p.dataset.source),target:Number(p.dataset.target),prob:p.dataset.prob}))`,
                ),
                ed,
              );
              assert.deepEqual(
                await js(
                  `Array.from(document.querySelectorAll('#${id} g[data-state]'),p=>[Number(p.dataset.state),Number(p.dataset.block)])`,
                ),
                blocks.map((b, i) => [i, b]),
              );
              assert.ok(
                await js(
                  `Array.from(document.querySelectorAll('#${id} path.edge')).every(p=>p.getTotalLength()>0)`,
                ),
              );
              graphEdges += ed.length;
            }
            if (ci === 0) await shot(`cascade-${t.round}-${width}`);
            rounds++;
          }
          for (let i = 0; i < r.pair_witnesses.length; i++) {
            await set("pair", i);
            const x = r.pair_witnesses[i];
            if (x.kind === "split") {
              await js('document.getElementById("open-split").click()');
              assert.equal(
                await js('Number(document.getElementById("round").value)'),
                x.round,
              );
              assert.match(
                (await cards("pair-summary"))[1][1],
                new RegExp(
                  x.left_mass.replace("/", "\\/") +
                    "; s" +
                    x.right +
                    " sends " +
                    x.right_mass.replace("/", "\\/"),
                ),
              );
            } else
              assert.equal(
                await js('document.getElementById("open-split").disabled'),
                true,
              );
            pairs++;
          }
          for (let i = 0; i < r.partition_atlas.length; i++) {
            await set("partition", i);
            const p = r.partition_atlas[i];
            assert.deepEqual(await record("partition-json"), p);
            assert.deepEqual(
              await rows("partition-masses"),
              strings(p.masses.map((row, i) => ["s" + i, ...row])),
            );
            assert.deepEqual(await cards("partition-summary"), [
              ["This candidate", part(p.blocks)],
              [
                "Two separate requirements",
                "Observations respected: " +
                  yes(p.respects_observations) +
                  "\nEvery block mass agrees: " +
                  yes(p.stable) +
                  "\nAllowed: " +
                  yes(p.allowed) +
                  "\nRefines final partition: " +
                  yes(p.refines_final),
              ],
              [
                "First observation conflict",
                p.first_observation_conflict
                  ? fmt(p.first_observation_conflict)
                  : "none",
              ],
              [
                "First transition-mass conflict",
                p.first_mass_conflict ? fmt(p.first_mass_conflict) : "none",
              ],
            ]);
            partitions++;
          }
          assert.deepEqual(
            await rows("atlas"),
            strings(
              r.partition_atlas.map((p, i) => [
                i,
                part(p.blocks),
                yes(p.respects_observations),
                yes(p.stable),
                yes(p.allowed),
                yes(p.refines_final),
              ]),
            ),
          );
          for (const f of r.forecasts) {
            await set("state", f.start);
            const h = r.first_hit[f.start],
              fields = [
                "success_probability",
                "failure_probability",
                "never_terminal_probability",
                "success_time_numerator",
                "success_second_moment_numerator",
                "conditional_success",
                "unconditional_success_time",
                "conditional_terminal_mean",
                "unconditional_terminal_time",
              ];
            assert.deepEqual(
              await rows("hit-table"),
              strings(fields.map((k) => [k, h.original[k], h.quotient[k]])),
            );
            for (const row of f.rows) {
              await set("step", row.step);
              assert.deepEqual(
                await rows("forecast-table"),
                strings(
                  r.final_blocks.map((b, j) => [
                    "q" + j,
                    part([b]),
                    row.original_blocks[j],
                    row.quotient_blocks[j],
                  ]),
                ),
              );
              forecasts++;
            }
          }
          await set("round", 0);
          await set("state", 0);
          await set("step", 0);
          await set("pair", 0);
          await set(
            "partition",
            r.partition_atlas.findIndex(
              (p) =>
                JSON.stringify(p.blocks) === JSON.stringify(r.initial_blocks),
            ),
          );
          assert.ok(
            await js("document.documentElement.scrollWidth<=innerWidth"),
            "overflow " + ci + " " + width,
          );
          await shot(`control-${ci}-${width}`);
          if (width === 1280) {
            await call("Page.setDownloadBehavior", {
              behavior: "allow",
              downloadPath: profile,
            });
            await js(
              'document.getElementById("download").scrollIntoView({block:"center"})',
            );
            const rect = await js(
              '(()=>{const r=document.getElementById("download").getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()',
            );
            await call("Input.dispatchMouseEvent", {
              type: "mousePressed",
              ...rect,
              button: "left",
              clickCount: 1,
            });
            await call("Input.dispatchMouseEvent", {
              type: "mouseReleased",
              ...rect,
              button: "left",
              clickCount: 1,
            });
            const dest = path.join(profile, "absorblab-lumping.json");
            await waitForDownload(
              dest,
              Buffer.byteLength(JSON.stringify(r, null, 2) + "\n"),
            );
            assert.deepEqual(JSON.parse(fs.readFileSync(dest)), r);
            execFileSync(process.env.PYTHON || "python", [
              "-m",
              "absorblab.lumping_cli",
              dest,
              "--verify",
            ]);
            fs.unlinkSync(dest);
            downloads++;
          }
          reports++;
        }
      }
      for (const bad of [
        "{}",
        '{"chain":{},"chain":{},"observations":[]}',
        '{"chain":{"horizon":1.0},"observations":[]}',
      ]) {
        await set("input", bad, "input");
        assert.equal(await js("window.currentLumpingReport"), null);
        assert.equal(
          await js('document.getElementById("results").hidden'),
          true,
        );
        assert.equal(
          await js('document.getElementById("download").disabled'),
          true,
        );
        assert.equal(
          await js('document.getElementById("original-graph").children.length'),
          0,
        );
        await js('document.getElementById("run").click()');
        assert.match(
          await js('document.getElementById("status").textContent'),
          /^Invalid input:/,
        );
      }
      await shot("invalid");
      await set("control", 0);
      assert.deepEqual(await js("window.currentLumpingReport"), expected[0]);
      assert.deepEqual(errors, []);
      console.log(
        JSON.stringify({
          reports,
          refinement_states: rounds,
          pair_selections: pairs,
          partition_selections: partitions,
          forecast_selections: forecasts,
          graph_edges: graphEdges,
          trusted_downloads: downloads,
          widths: [1280, 390, 320],
        }),
      );
    } finally {
      ws?.close();
      await stopChrome(browser);
      server.closeAllConnections();
      await new Promise((r) => server.close(r));
      fs.rmSync(profile, {
        recursive: true,
        force: true,
        maxRetries: 5,
        retryDelay: 100,
      });
    }
  },
);

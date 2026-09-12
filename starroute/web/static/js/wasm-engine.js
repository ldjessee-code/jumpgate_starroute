/** Main-thread helper for the Pyodide worker. */
function createWasmEngine() {
  const script = document.querySelector('script[src*="wasm-engine.js"]');
  const workerUrl = script
    ? script.src.replace(/wasm-engine\.js.*$/, "wasm-worker.js")
    : "js/wasm-worker.js";
  const worker = new Worker(workerUrl);
  let bootPromise = null;
  const waiters = [];

  worker.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type === "status" && typeof engine.onstatus === "function") {
      engine.onstatus(msg.message);
    }
    if (waiters.length && (msg.type === "ready" || msg.type === "result" || msg.type === "error")) {
      const { resolve, reject } = waiters.shift();
      if (msg.type === "error") reject(new Error(msg.message));
      else resolve(msg);
    }
  };

  worker.onerror = (err) => {
    if (waiters.length) waiters.shift().reject(err);
  };

  function send(payload) {
    return new Promise((resolve, reject) => {
      waiters.push({ resolve, reject });
      worker.postMessage(payload);
    });
  }

  const engine = {
    onstatus: null,
    boot() {
      if (!bootPromise) {
        bootPromise = send({ type: "boot" }).catch((err) => {
          bootPromise = null;
          throw err;
        });
      }
      return bootPromise;
    },
    async rebuild(request) {
      await engine.boot();
      const msg = await send({ type: "rebuild", ...(request || {}) });
      return msg.data;
    },
  };
  return engine;
}

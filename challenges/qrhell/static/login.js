const MODULES = 21;
const QUIET = 4;
const SCALE = 12;

let cells = [];
let pageTeardown = null;

function buildGrid(gridEl) {
  gridEl.innerHTML = "";
  cells = [];
  for (let y = 0; y < MODULES; y += 1) {
    for (let x = 0; x < MODULES; x += 1) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cell";
      cell.dataset.x = String(x);
      cell.dataset.y = String(y);
      cell.setAttribute("aria-label", `module ${x},${y}`);
      cell.addEventListener("click", () => {
        cell.classList.toggle("on");
      });
      gridEl.appendChild(cell);
      cells.push(cell);
    }
  }
}

function moduleAt(x, y) {
  return cells[y * MODULES + x];
}

function isOn(x, y) {
  const cell = moduleAt(x, y);
  return cell && cell.classList.contains("on");
}

function setOn(x, y, on) {
  const cell = moduleAt(x, y);
  if (!cell) return;
  cell.classList.toggle("on", on);
}

function clearGrid() {
  cells.forEach((c) => c.classList.remove("on"));
}

/** Light QR finder-style corners help players orient 21x21 modules. */
function fillFinders() {
  const finder = [
    [0, 0],
    [MODULES - 7, 0],
    [0, MODULES - 7],
  ];
  finder.forEach(([ox, oy]) => {
    for (let y = 0; y < 7; y += 1) {
      for (let x = 0; x < 7; x += 1) {
        const border = x === 0 || x === 6 || y === 0 || y === 6;
        const inner = x >= 2 && x <= 4 && y >= 2 && y <= 4;
        setOn(ox + x, oy + y, border || inner);
      }
    }
  });
}

function renderPngBase64() {
  const size = (MODULES + 2 * QUIET) * SCALE;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, size, size);

  ctx.fillStyle = "#000000";
  for (let y = 0; y < MODULES; y += 1) {
    for (let x = 0; x < MODULES; x += 1) {
      if (!isOn(x, y)) continue;
      const px = (x + QUIET) * SCALE;
      const py = (y + QUIET) * SCALE;
      ctx.fillRect(px, py, SCALE, SCALE);
    }
  }

  const dataUrl = canvas.toDataURL("image/png");
  const comma = dataUrl.indexOf(",");
  return comma === -1 ? null : dataUrl.slice(comma + 1);
}

function showLoginPageHtml(html) {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const nextWrap = parsed.querySelector(".wrap");
  const currentWrap = document.querySelector(".wrap");

  if (nextWrap && currentWrap) {
    currentWrap.replaceWith(document.importNode(nextWrap, true));
    if (parsed.title) {
      document.title = parsed.title;
    }
  } else {
    document.open();
    document.write(html);
    document.close();
  }

  initLoginPage();
}

function initLoginPage() {
  if (pageTeardown) {
    pageTeardown();
    pageTeardown = null;
  }

  const gridEl = document.getElementById("draw-grid");
  const form = document.getElementById("login-form");
  const clearBtn = document.getElementById("clear-grid");
  const fillBtn = document.getElementById("fill-quiet");

  if (!gridEl || !form) {
    return;
  }

  buildGrid(gridEl);

  const onClear = () => clearGrid();
  const onFill = () => fillFinders();
  const onSubmit = async (event) => {
    event.preventDefault();

    const username = (document.getElementById("username")?.value || "").trim();
    const passwordPngB64 = renderPngBase64();
    if (!passwordPngB64) {
      alert("Could not render password image.");
      return;
    }

    const res = await fetch(form.action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password_png_b64: passwordPngB64,
      }),
      credentials: "same-origin",
    });

    if (res.redirected) {
      window.location.href = res.url;
      return;
    }

    showLoginPageHtml(await res.text());
  };

  clearBtn?.addEventListener("click", onClear);
  fillBtn?.addEventListener("click", onFill);
  form.addEventListener("submit", onSubmit);

  pageTeardown = () => {
    clearBtn?.removeEventListener("click", onClear);
    fillBtn?.removeEventListener("click", onFill);
    form.removeEventListener("submit", onSubmit);
  };
}

window.initLoginPage = initLoginPage;

function bootLoginPage() {
  if (document.getElementById("login-form")) {
    initLoginPage();
  }
}

window.addEventListener("pageshow", () => {
  if (document.getElementById("login-form")) {
    bootLoginPage();
  }
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootLoginPage);
} else {
  bootLoginPage();
}

"use strict";

// Static catalog. `available` gates the not-yet-built games.
// `icon` is the chess glyph shown as the challenge's "image".
const GAMES = [
  { id: "game1", title: "Baby's first checkmate", diff: "Trivial",   icon: "♟", available: true,
    blurb: "" },
  { id: "game2", title: "Welcome to the jungle", diff: "Easy",   icon: "♞", available: true,
    blurb: "" },
  { id: "game3", title: "Behind enemy lines",    diff: "Medium", icon: "♜", available: true,
    blurb: "" },
  { id: "game4", title: "Chessmaster",  diff: "Hard",   icon: "♛", available: true,
    blurb: "" },
];

const GLYPH = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};
const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

const state = {
  game: null,      // catalog entry
  session: null,
  fen: null,
  board: {},       // square -> piece char (true board, from server)
  hidden: false,
  turn: "w",
  lastMove: null,  // uci of server's most recent move (may be Black's)
  myMove: null,    // uci of the player's own last move (used for hidden games)
  selected: null,
  locked: false,
};

// ---- DOM helpers ---------------------------------------------------------- //
const $ = (id) => document.getElementById(id);

function show(view) {
  $("menu-view").hidden = view !== "menu";
  $("game-view").hidden = view !== "game";
}

// ---- Menu ----------------------------------------------------------------- //
function renderMenu() {
  const menu = $("menu");
  menu.innerHTML = "";
  for (const g of GAMES) {
    const card = document.createElement("div");
    card.className = "card" + (g.available ? "" : " disabled");
    card.innerHTML =
      `<div class="icon">${g.icon}</div>` +
      `<h3>${g.title}</h3>` +
      `<div class="diff">${g.diff}</div>` +
      (g.available ? "" : `<p class="soon">Coming soon</p>`);
    if (g.available) card.onclick = () => startGame(g);
    menu.appendChild(card);
  }
  show("menu");
}

// ---- FEN parsing ---------------------------------------------------------- //
function parseFen(fen) {
  const board = {};
  const rows = fen.split(" ")[0].split("/");
  for (let r = 0; r < 8; r++) {
    const rank = 8 - r;
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) { file += parseInt(ch, 10); }
      else { board[FILES[file] + rank] = ch; file += 1; }
    }
  }
  return board;
}

// ---- Board rendering ------------------------------------------------------ //
function renderBoard() {
  const el = $("board");
  el.innerHTML = "";
  // In hidden games, highlighting the server's last move would reveal Black's
  // moves (defeating the point). Highlight the player's own move instead.
  const hl = state.hidden ? state.myMove : state.lastMove;
  const from = hl ? hl.slice(0, 2) : null;
  const to = hl ? hl.slice(2, 4) : null;

  for (let rank = 8; rank >= 1; rank--) {
    for (let f = 0; f < 8; f++) {
      const sq = FILES[f] + rank;
      const dark = (f + rank) % 2 === 0;
      const cell = document.createElement("div");
      cell.className = "square " + (dark ? "dark" : "light");
      if (sq === state.selected) cell.classList.add("sel");
      else if (sq === from || sq === to) cell.classList.add("last");

      const piece = state.board[sq];
      if (piece) {
        const isWhite = piece === piece.toUpperCase();
        // Game 2: hide Black's pieces client-side only (server still sends them).
        if (!(state.hidden && !isWhite)) {
          const span = document.createElement("span");
          span.className = "pc " + (isWhite ? "white" : "black");
          span.textContent = GLYPH[piece];
          cell.appendChild(span);
        }
      }
      cell.onclick = () => onSquareClick(sq);
      el.appendChild(cell);
    }
  }
}

// ---- Interaction ---------------------------------------------------------- //
function onSquareClick(sq) {
  if (state.locked) return;
  const piece = state.board[sq];
  const isWhitePiece = piece && piece === piece.toUpperCase();

  if (state.selected === null) {
    if (isWhitePiece && state.turn === "w") {
      state.selected = sq;
      renderBoard();
    }
    return;
  }
  if (sq === state.selected) { state.selected = null; renderBoard(); return; }
  // Re-select another own piece.
  if (isWhitePiece) { state.selected = sq; renderBoard(); return; }

  const uci = buildUci(state.selected, sq);
  state.selected = null;
  state.myMove = uci;   // remember our own move for hidden-game highlighting
  sendMove(uci);
}

function buildUci(from, to) {
  let uci = from + to;
  // Auto-queen: player is always White, so a pawn reaching rank 8 promotes to Q.
  const piece = state.board[from];
  if (piece === "P" && to[1] === "8") uci += "q";
  return uci;
}

// ---- API ------------------------------------------------------------------ //
async function startGame(g) {
  state.game = g;
  $("game-title").textContent = `${g.title} — ${g.diff}`;
  setMessage("Loading…", "");
  setStatus("");
  show("game");
  try {
    const res = await fetch(`/api/${g.id}/new`, { method: "POST" });
    const data = await res.json();
    applyResponse(data, /*fresh=*/true);
  } catch (e) {
    setMessage("Could not reach the server.", "bad");
  }
}

async function sendMove(uci) {
  try {
    const res = await fetch(`/api/${state.game.id}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, move: uci }),
    });
    const data = await res.json();
    if (data.detail) { setStatus(data.detail, "bad"); return; }
    applyResponse(data, false);
  } catch (e) {
    setStatus("Network error.", "bad");
  }
}

function applyResponse(data, fresh) {
  if (fresh) state.myMove = null;
  state.session = data.session ?? state.session;
  state.fen = data.fen;
  state.board = parseFen(data.fen);
  state.hidden = !!data.hidden;
  state.turn = data.turn;
  state.lastMove = data.last_move;
  state.locked = data.status !== "in_progress";
  renderBoard();

  if (data.message) {
    const kind = data.status === "victory" ? "ok" : data.status === "failed" ? "bad" : "";
    setMessage(data.message, kind);
  } else if (fresh) {
    setMessage("", "");
  }

  if (data.error) {
    setStatus(data.error, "bad");
  } else {
    setStatus(statusLine(data));
  }
}

function statusLine(data) {
  if (data.status === "victory") return "🏆 Victory, start another to keep going.";
  if (data.status === "failed") return "💀 Game over, press Restart to try again.";
  // Game 3: maze progress + clock.
  if (typeof data.solved === "number" && typeof data.total === "number") {
    return `Maze ${data.solved + 1}/${data.total}  ·  Solved: ${data.solved}  ·  ⏱ ${data.time_left}s left`;
  }
  // Game 4: win streak + whole-run clock.
  if (typeof data.streak === "number" && typeof data.target === "number") {
    return `Win streak: ${data.streak}/${data.target}  ·  Moves left this game: ${data.moves_left}  ·  ⏱ ${data.time_left}s left`;
  }
  const bits = [];
  bits.push(state.turn === "w" ? "Your move (White)." : "Black to move…");
  if (typeof data.moves_left === "number") bits.push(`Moves left: ${data.moves_left}`);
  return bits.join("  ·  ");
}

// ---- Message / status bar ------------------------------------------------- //
function setMessage(text, kind) {
  const m = $("message");
  m.textContent = text || "";
  m.className = "message" + (kind ? " " + kind : "");
}
function setStatus(text, kind) {
  const s = $("status-bar");
  s.textContent = text || "";
  s.className = "status-bar" + (kind ? " " + kind : "");
}

// ---- Wire up -------------------------------------------------------------- //
$("home-link").onclick = (e) => { e.preventDefault(); renderMenu(); };
$("back-btn").onclick = () => renderMenu();
$("restart-btn").onclick = () => { if (state.game) startGame(state.game); };

renderMenu();

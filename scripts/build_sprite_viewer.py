#!/usr/bin/env python3
"""Chrono Trigger DS - Standalone Interactive Sprite Sheet & OAM Visualizer Builder.

Generates `tools/sprite_viewer.html` with embedded base64 graphics and JSON metadata.
Zero external dependencies, completely standalone, works by opening directly in any browser.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSLATED_PNG = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"
EXTRACTED_PNG = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.png"
TRANSLATED_JSON = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_JSON = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
OUTPUT_HTML = PROJECT_ROOT / "tools" / "sprite_viewer.html"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chrono Trigger DS — Title Sprite Sheet & OAM Visualizer</title>
<style>
  :root {
    --bg-dark: #0d1117;
    --bg-panel: #161b22;
    --bg-card: #21262d;
    --bg-card-hover: #30363d;
    --border: #30363d;
    --border-accent: #58a6ff;
    --text: #c9d1d9;
    --text-bright: #ffffff;
    --text-muted: #8b949e;
    --accent-cyan: #00e5ff;
    --accent-red: #ff1744;
    --accent-yellow: #ffd600;
    --accent-green: #3fb950;
    --accent-blue: #58a6ff;
    --font-mono: 'Consolas', 'Fira Code', 'Roboto Mono', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    background-color: var(--bg-dark);
    color: var(--text);
    font-family: var(--font-sans);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* HEADER */
  header {
    background-color: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    padding: 10px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .header-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-bright);
    letter-spacing: 0.5px;
  }

  .header-tag {
    background: #238636;
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .btn-group {
    display: inline-flex;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }

  .btn {
    background: var(--bg-card);
    border: none;
    color: var(--text);
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    border-right: 1px solid var(--border);
  }

  .btn:last-child {
    border-right: none;
  }

  .btn:hover {
    background: var(--bg-card-hover);
    color: var(--text-bright);
  }

  .btn.active {
    background: #1f6feb;
    color: #fff;
  }

  .coord-readout {
    font-family: var(--font-mono);
    font-size: 12px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 6px;
    color: var(--accent-cyan);
  }

  /* MAIN LAYOUT */
  .main-container {
    display: flex;
    flex: 1;
    overflow: hidden;
    position: relative;
  }

  /* LEFT SIDEBAR */
  .sidebar-left {
    width: 320px;
    background-color: var(--bg-panel);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex-shrink: 0;
  }

  .panel-section {
    padding: 14px;
    border-bottom: 1px solid var(--border);
  }

  .section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-muted);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  /* TOGGLE SWITCHES */
  .toggle-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .toggle-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    cursor: pointer;
    user-select: none;
    padding: 4px 0;
  }

  .toggle-item input {
    cursor: pointer;
    accent-color: #1f6feb;
  }

  /* CELL LIST */
  .cell-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .cell-card {
    background: var(--bg-card);
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 10px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .cell-card:hover {
    background: var(--bg-card-hover);
  }

  .cell-card.selected {
    border-color: var(--border-accent);
    background: #192330;
  }

  .cell-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .cell-badge {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .cell-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-bright);
    flex: 1;
  }

  .cell-id-tag {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
  }

  .cell-details {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    gap: 10px;
  }

  /* CRITICAL WARNING CARD */
  .warning-box {
    background: #271015;
    border: 1px solid var(--accent-red);
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 11px;
    line-height: 1.5;
  }

  .warning-title {
    color: var(--accent-red);
    font-weight: 700;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .warning-box ul {
    padding-left: 16px;
    color: #f0c5ca;
  }

  .warning-box li {
    margin-bottom: 4px;
  }

  /* CENTER CANVAS AREA */
  .canvas-viewport {
    flex: 1;
    position: relative;
    background: #090c10;
    overflow: hidden;
    cursor: grab;
  }

  .canvas-viewport.dragging {
    cursor: grabbing;
  }

  #sheetCanvas {
    position: absolute;
    top: 0;
    left: 0;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
  }

  /* CANVAS FLOATING TOOLBAR */
  .canvas-toolbar {
    position: absolute;
    bottom: 16px;
    left: 16px;
    background: rgba(22, 27, 34, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 10;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  }

  /* TOOLTIP */
  .floating-tooltip {
    position: absolute;
    background: rgba(13, 17, 23, 0.95);
    border: 1px solid var(--accent-cyan);
    border-radius: 6px;
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.4;
    color: #fff;
    pointer-events: none;
    z-index: 100;
    display: none;
    box-shadow: 0 4px 14px rgba(0,0,0,0.6);
  }

  /* RIGHT SIDEBAR (INSPECTOR & NDS PREVIEW) */
  .sidebar-right {
    width: 360px;
    background-color: var(--bg-panel);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex-shrink: 0;
  }

  /* NDS PREVIEW FRAME */
  .nds-frame-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .nds-screen-shell {
    background: #2a2e39;
    border: 3px solid #1c202a;
    border-radius: 8px;
    padding: 10px;
    box-shadow: inset 0 2px 6px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.5);
  }

  .nds-screen {
    width: 256px;
    height: 192px;
    background: #000;
    position: relative;
    border: 1px solid #111;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    overflow: hidden;
  }

  #ndsCanvas {
    width: 100%;
    height: 100%;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
  }

  .nds-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;
    margin-top: 6px;
  }

  /* PROPERTY TABLE */
  .prop-table {
    width: 100%;
    font-size: 11px;
    border-collapse: collapse;
    font-family: var(--font-mono);
  }

  .prop-table tr {
    border-bottom: 1px solid #262c36;
  }

  .prop-table td {
    padding: 6px 4px;
  }

  .prop-name {
    color: var(--text-muted);
    width: 42%;
  }

  .prop-val {
    color: var(--text-bright);
    font-weight: 600;
  }

  .badge-highlight {
    background: rgba(88, 166, 255, 0.15);
    color: var(--accent-blue);
    padding: 2px 6px;
    border-radius: 4px;
  }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="header-title">Chrono Trigger DS — Title Sprite Sheet & OAM Visualizer</div>
    <div class="header-tag">obj_logo_new</div>
  </div>

  <div class="header-controls">
    <div class="btn-group">
      <button class="btn active" id="btnSourceTrans">Translated (RU)</button>
      <button class="btn" id="btnSourceOrig">Original (EN/FR)</button>
    </div>

    <div class="btn-group">
      <button class="btn" id="btnZoom1x">1x</button>
      <button class="btn" id="btnZoom2x">2x</button>
      <button class="btn active" id="btnZoom4x">4x</button>
      <button class="btn" id="btnZoom8x">8x</button>
      <button class="btn" id="btnZoomFit">Fit</button>
    </div>

    <div class="coord-readout" id="coordReadout">X: --, Y: --</div>
  </div>
</header>

<div class="main-container">
  <!-- LEFT SIDEBAR -->
  <aside class="sidebar-left">
    <div class="panel-section">
      <div class="section-title">Overlay Layers</div>
      <div class="toggle-grid">
        <label class="toggle-item">
          <span>Cell Bounding Boxes</span>
          <input type="checkbox" id="chkCells" checked>
        </label>
        <label class="toggle-item">
          <span>OAM Boxes (Dashed)</span>
          <input type="checkbox" id="chkOams" checked>
        </label>
        <label class="toggle-item">
          <span>Seam (x=48) & 4px Gap</span>
          <input type="checkbox" id="chkSeamGap" checked>
        </label>
        <label class="toggle-item">
          <span>8x8 Tile Grid</span>
          <input type="checkbox" id="chkGrid" checked>
        </label>
        <label class="toggle-item">
          <span>Labels & Tile Tags</span>
          <input type="checkbox" id="chkLabels" checked>
        </label>
      </div>
    </div>

    <div class="panel-section" style="flex: 1;">
      <div class="section-title">
        <span>Cells (NCER Components)</span>
        <span id="cellCountTag" style="font-weight: 400;">10 Cells</span>
      </div>
      <div class="cell-list" id="cellListContainer">
        <!-- Injected via JavaScript -->
      </div>
    </div>

    <div class="panel-section">
      <div class="warning-box">
        <div class="warning-title">&#9888; CRITICAL: THE SEAM & GAP RULE</div>
        <ul>
          <li><strong>Shared ROM Tiles:</strong> Cell 0 & 3 share tiles 0..36. Cell 1 & 4 share tiles 40..88.</li>
          <li><strong>Seam at x=48:</strong> Left word width &le; 48px (x=0..47). Seam at x=48 MUST be empty.</li>
          <li><strong>4px Hardware Gap:</strong> Cell 3 & 4 shift the Right OAM +4px (gap at x=48..52). Any word crossing x=48 gets torn apart!</li>
          <li><strong>No OAM in Gap:</strong> Pixels drawn in x=48..52 vanish in ROM.</li>
        </ul>
      </div>
    </div>
  </aside>

  <!-- CENTER CANVAS VIEWPORT -->
  <main class="canvas-viewport" id="viewport">
    <canvas id="sheetCanvas"></canvas>

    <div class="canvas-toolbar">
      <button class="btn" id="btnZoomIn" title="Zoom In (+)">+</button>
      <button class="btn" id="btnZoomOut" title="Zoom Out (-)">-</button>
      <button class="btn" id="btnResetPan" title="Center Sheet">Reset View</button>
      <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">Pan: Drag mouse | Zoom: Scroll</span>
    </div>

    <div class="floating-tooltip" id="tooltip"></div>
  </main>

  <!-- RIGHT SIDEBAR: NDS SCREEN PREVIEW & INSPECTOR -->
  <aside class="sidebar-right">
    <div class="panel-section">
      <div class="section-title">Live NDS Screen Preview</div>
      <div class="nds-frame-container">
        <div class="nds-screen-shell">
          <div class="nds-screen" id="ndsScreenShell">
            <canvas id="ndsCanvas" width="256" height="192"></canvas>
          </div>
        </div>

        <div class="nds-controls">
          <button class="btn" id="btnCompareShift" style="flex: 1;">Compare Selection Shift</button>
          <button class="btn" id="btnBlinkToggle" title="Auto-alternate between Normal and Selected">Blink: Off</button>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); width: 100%; text-align: center;">
          Reconstructs current cell on native 256x192 NDS screen
        </div>
      </div>
    </div>

    <div class="panel-section">
      <div class="section-title">Hovered OAM Inspector</div>
      <table class="prop-table" id="oamPropTable">
        <tr><td class="prop-name">Cell ID:</td><td class="prop-val" id="inspOamCell">--</td></tr>
        <tr><td class="prop-name">OAM Index:</td><td class="prop-val" id="inspOamIdx">--</td></tr>
        <tr><td class="prop-name">Rel Position:</td><td class="prop-val" id="inspOamRelPos">--</td></tr>
        <tr><td class="prop-name">Dimensions:</td><td class="prop-val" id="inspOamSize">--</td></tr>
        <tr><td class="prop-name">Sheet Canvas:</td><td class="prop-val" id="inspOamCanvasPos">--</td></tr>
        <tr><td class="prop-name">NCGR Start Tile:</td><td class="prop-val" id="inspOamTile">--</td></tr>
        <tr><td class="prop-name">Tile Count:</td><td class="prop-val" id="inspOamTileCount">--</td></tr>
        <tr><td class="prop-name">Palette Index:</td><td class="prop-val" id="inspOamPal">--</td></tr>
      </table>
    </div>

    <div class="panel-section">
      <div class="section-title">Selected Cell Metadata</div>
      <table class="prop-table" id="cellPropTable">
        <tr><td class="prop-name">Cell ID:</td><td class="prop-val" id="inspCellId">--</td></tr>
        <tr><td class="prop-name">Name / Role:</td><td class="prop-val" id="inspCellName">--</td></tr>
        <tr><td class="prop-name">Sheet Pos:</td><td class="prop-val" id="inspCellPos">--</td></tr>
        <tr><td class="prop-name">Size:</td><td class="prop-val" id="inspCellSize">--</td></tr>
        <tr><td class="prop-name">OAM Count:</td><td class="prop-val" id="inspCellOams">--</td></tr>
        <tr><td class="prop-name">Tile Range:</td><td class="prop-val" id="inspCellTiles">--</td></tr>
        <tr><td class="prop-name">Min Bounds:</td><td class="prop-val" id="inspCellMin">--</td></tr>
      </table>
    </div>
  </aside>
</div>

<script>
  // Embedded Data
  const TRANSLATED_B64 = "__TRANSLATED_B64__";
  const ORIGINAL_B64 = "__ORIGINAL_B64__";
  const METADATA = __METADATA_JSON__;

  const CELL_COLORS = {
    0: "#00e5ff",
    1: "#00e676",
    2: "#2979ff",
    3: "#ff9100",
    4: "#e040fb",
    5: "#1de9b6",
    6: "#ff5252",
    7: "#c6ff00",
    8: "#ff4081",
    "-1": "#90a4ae"
  };

  const CELL_NAMES = {
    0: "Game Mode (Normal)",
    1: "Battle Mode (Normal)",
    2: "Movies (Normal)",
    3: "Game Mode (Selected / Gap)",
    4: "Battle Mode (Selected / Gap)",
    5: "Movies (Selected)",
    6: "Mode Jeu (French)",
    7: "Mode de combat (French)",
    8: "Cinématiques (French)",
    "-1": "Uncovered Tiles"
  };

  // State
  let currentImageSrc = TRANSLATED_B64 || ORIGINAL_B64;
  let spriteImg = new Image();
  let imgLoaded = false;

  let selectedCellId = 0;
  let hoveredOam = null;
  let hoveredCell = null;

  let scale = 4.0;
  let panX = 40;
  let panY = 40;
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;

  let blinkInterval = null;

  // DOM Elements
  const viewport = document.getElementById("viewport");
  const sheetCanvas = document.getElementById("sheetCanvas");
  const sheetCtx = sheetCanvas.getContext("2d");
  const ndsCanvas = document.getElementById("ndsCanvas");
  const ndsCtx = ndsCanvas.getContext("2d");
  const tooltip = document.getElementById("tooltip");
  const coordReadout = document.getElementById("coordReadout");

  // Layers
  const chkCells = document.getElementById("chkCells");
  const chkOams = document.getElementById("chkOams");
  const chkSeamGap = document.getElementById("chkSeamGap");
  const chkGrid = document.getElementById("chkGrid");
  const chkLabels = document.getElementById("chkLabels");

  // Initialize
  function init() {
    spriteImg.onload = () => {
      imgLoaded = true;
      renderCellList();
      selectCell(0);
      centerCanvas();
      redraw();
    };
    spriteImg.src = currentImageSrc;

    setupEvents();
  }

  function centerCanvas() {
    const vw = viewport.clientWidth;
    const vh = viewport.clientHeight;
    panX = Math.round((vw - 256 * scale) / 2);
    panY = Math.round((vh - 250 * scale) / 2);
  }

  function setupEvents() {
    // Resize
    window.addEventListener("resize", () => {
      resizeSheetCanvas();
      redraw();
    });
    resizeSheetCanvas();

    // Source toggle
    document.getElementById("btnSourceTrans").onclick = function() {
      if (!TRANSLATED_B64) return;
      document.getElementById("btnSourceTrans").classList.add("active");
      document.getElementById("btnSourceOrig").classList.remove("active");
      currentImageSrc = TRANSLATED_B64;
      spriteImg.src = currentImageSrc;
    };
    document.getElementById("btnSourceOrig").onclick = function() {
      if (!ORIGINAL_B64) return;
      document.getElementById("btnSourceOrig").classList.add("active");
      document.getElementById("btnSourceTrans").classList.remove("active");
      currentImageSrc = ORIGINAL_B64;
      spriteImg.src = currentImageSrc;
    };

    // Zoom Buttons
    document.getElementById("btnZoom1x").onclick = () => setZoom(1.0);
    document.getElementById("btnZoom2x").onclick = () => setZoom(2.0);
    document.getElementById("btnZoom4x").onclick = () => setZoom(4.0);
    document.getElementById("btnZoom8x").onclick = () => setZoom(8.0);
    document.getElementById("btnZoomFit").onclick = () => {
      const vw = viewport.clientWidth - 60;
      const vh = viewport.clientHeight - 60;
      const fitScale = Math.min(vw / 256, vh / 250);
      setZoom(Math.max(1.0, Math.floor(fitScale)));
      centerCanvas();
    };
    document.getElementById("btnResetPan").onclick = () => {
      setZoom(4.0);
      centerCanvas();
      redraw();
    };
    document.getElementById("btnZoomIn").onclick = () => zoomAtCenter(1.25);
    document.getElementById("btnZoomOut").onclick = () => zoomAtCenter(0.8);

    // Pan & Mouse interaction
    viewport.addEventListener("mousedown", (e) => {
      if (e.button === 0) {
        isDragging = true;
        dragStartX = e.clientX - panX;
        dragStartY = e.clientY - panY;
        viewport.classList.add("dragging");
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (isDragging) {
        panX = e.clientX - dragStartX;
        panY = e.clientY - dragStartY;
        redraw();
      } else {
        handleCanvasHover(e);
      }
    });

    window.addEventListener("mouseup", () => {
      isDragging = false;
      viewport.classList.remove("dragging");
    });

    viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const factor = e.deltaY < 0 ? 1.2 : 0.833;
      const newScale = Math.min(24, Math.max(0.75, scale * factor));

      panX = mouseX - (mouseX - panX) * (newScale / scale);
      panY = mouseY - (mouseY - panY) * (newScale / scale);
      scale = newScale;

      updateZoomButtons();
      redraw();
    }, { passive: false });

    // Layer toggles
    [chkCells, chkOams, chkSeamGap, chkGrid, chkLabels].forEach(chk => {
      chk.onchange = () => redraw();
    });

    // Shift comparison
    document.getElementById("btnCompareShift").onclick = toggleShiftPair;
    document.getElementById("btnBlinkToggle").onclick = toggleBlink;
  }

  function resizeSheetCanvas() {
    sheetCanvas.width = viewport.clientWidth;
    sheetCanvas.height = viewport.clientHeight;
  }

  function setZoom(z) {
    const rect = viewport.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    panX = cx - (cx - panX) * (z / scale);
    panY = cy - (cy - panY) * (z / scale);
    scale = z;
    updateZoomButtons();
    redraw();
  }

  function zoomAtCenter(factor) {
    const rect = viewport.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const newScale = Math.min(24, Math.max(0.75, scale * factor));
    panX = cx - (cx - panX) * (newScale / scale);
    panY = cy - (cy - panY) * (newScale / scale);
    scale = newScale;
    updateZoomButtons();
    redraw();
  }

  function updateZoomButtons() {
    ["1x", "2x", "4x", "8x"].forEach(z => {
      const b = document.getElementById("btnZoom" + z);
      if (Math.abs(parseFloat(z) - scale) < 0.1) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }

  function renderCellList() {
    const container = document.getElementById("cellListContainer");
    container.innerHTML = "";

    METADATA.components.forEach(comp => {
      const cid = comp.cell_idx;
      const color = CELL_COLORS[cid] || "#888";
      const name = CELL_NAMES[cid] || ("Cell " + cid);

      const card = document.createElement("div");
      card.className = "cell-card" + (cid === selectedCellId ? " selected" : "");
      card.id = "cellCard_" + cid;
      card.onclick = () => selectCell(cid);

      const tiles = comp.oams.map(o => o.tile);
      const minTile = tiles.length ? Math.min(...tiles) : 0;
      const maxTile = tiles.length ? Math.max(...tiles) : 0;

      card.innerHTML = `
        <div class="cell-card-header">
          <span class="cell-badge" style="background:${color}"></span>
          <span class="cell-title">${name}</span>
          <span class="cell-id-tag">[${cid}]</span>
        </div>
        <div class="cell-details">
          <span>Pos: (${comp.canvas_x}, ${comp.canvas_y})</span>
          <span>${comp.width}x${comp.height}</span>
          <span>${comp.oams.length} OAMs</span>
          <span>T: ${minTile}..${maxTile}</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function selectCell(cid) {
    selectedCellId = cid;
    document.querySelectorAll(".cell-card").forEach(c => c.classList.remove("selected"));
    const card = document.getElementById("cellCard_" + cid);
    if (card) card.classList.add("selected");

    updateCellInspector(cid);
    renderNdsPreview(cid);
    redraw();
  }

  function updateCellInspector(cid) {
    const comp = METADATA.components.find(c => c.cell_idx === cid);
    if (!comp) return;

    document.getElementById("inspCellId").textContent = cid;
    document.getElementById("inspCellName").textContent = CELL_NAMES[cid] || "Cell " + cid;
    document.getElementById("inspCellPos").textContent = `(${comp.canvas_x}, ${comp.canvas_y})`;
    document.getElementById("inspCellSize").textContent = `${comp.width} x ${comp.height} px`;
    document.getElementById("inspCellOams").textContent = `${comp.oams.length} OAMs`;

    const tiles = comp.oams.map(o => o.tile);
    const minT = tiles.length ? Math.min(...tiles) : 0;
    const maxT = tiles.length ? Math.max(...tiles) : 0;
    document.getElementById("inspCellTiles").textContent = `${minT} .. ${maxT} (NCGR)`;
    document.getElementById("inspCellMin").textContent = `min_x: ${comp.min_x}, min_y: ${comp.min_y}`;
  }

  function updateOamInspector(oam, comp, idx) {
    if (!oam) {
      document.getElementById("inspOamCell").textContent = "--";
      document.getElementById("inspOamIdx").textContent = "--";
      document.getElementById("inspOamRelPos").textContent = "--";
      document.getElementById("inspOamSize").textContent = "--";
      document.getElementById("inspOamCanvasPos").textContent = "--";
      document.getElementById("inspOamTile").textContent = "--";
      document.getElementById("inspOamTileCount").textContent = "--";
      document.getElementById("inspOamPal").textContent = "--";
      return;
    }

    const sx = comp.canvas_x + (oam.x - comp.min_x);
    const sy = comp.canvas_y + (oam.y - comp.min_y);
    const tileCount = (oam.w * oam.h) / 64;

    document.getElementById("inspOamCell").textContent = `Cell ${comp.cell_idx} (${CELL_NAMES[comp.cell_idx] || ''})`;
    document.getElementById("inspOamIdx").textContent = `#${idx}`;
    document.getElementById("inspOamRelPos").textContent = `(${oam.x}, ${oam.y})`;
    document.getElementById("inspOamSize").textContent = `${oam.w} x ${oam.h} px`;
    document.getElementById("inspOamCanvasPos").textContent = `(${sx}, ${sy})`;
    document.getElementById("inspOamTile").textContent = `Tile #${oam.tile}`;
    document.getElementById("inspOamTileCount").textContent = `${tileCount} tiles`;
    document.getElementById("inspOamPal").textContent = `Palette ${oam.pal}`;
  }

  // Canvas Hover Detection
  function handleCanvasHover(e) {
    const rect = viewport.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const sheetX = Math.floor((mx - panX) / scale);
    const sheetY = Math.floor((my - panY) / scale);

    if (sheetX >= 0 && sheetX < 256 && sheetY >= 0 && sheetY < 250) {
      coordReadout.textContent = `Sheet: (${sheetX}, ${sheetY})`;

      // Find hovering OAM
      let foundOam = null;
      let foundComp = null;
      let foundIdx = -1;

      for (const comp of METADATA.components) {
        for (let i = 0; i < comp.oams.length; i++) {
          const oam = comp.oams[i];
          const ox = comp.canvas_x + (oam.x - comp.min_x);
          const oy = comp.canvas_y + (oam.y - comp.min_y);
          if (sheetX >= ox && sheetX < ox + oam.w && sheetY >= oy && sheetY < oy + oam.h) {
            foundOam = oam;
            foundComp = comp;
            foundIdx = i;
            break;
          }
        }
        if (foundOam) break;
      }

      if (foundOam) {
        hoveredOam = { oam: foundOam, comp: foundComp, idx: foundIdx };
        updateOamInspector(foundOam, foundComp, foundIdx);

        // Tooltip
        tooltip.style.display = "block";
        tooltip.style.left = (mx + 16) + "px";
        tooltip.style.top = (my + 16) + "px";
        tooltip.innerHTML = `
          <div style="font-weight:700; color:var(--accent-cyan);">Cell ${foundComp.cell_idx} &bull; OAM #${foundIdx}</div>
          <div>Size: ${foundOam.w}x${foundOam.h} px</div>
          <div>NCER Pos: (${foundOam.x}, ${foundOam.y})</div>
          <div>Tile: #${foundOam.tile} (count: ${(foundOam.w * foundOam.h)/64})</div>
        `;
      } else {
        hoveredOam = null;
        tooltip.style.display = "none";
        updateOamInspector(null);
      }
    } else {
      coordReadout.textContent = "X: --, Y: --";
      hoveredOam = null;
      tooltip.style.display = "none";
      updateOamInspector(null);
    }

    redraw();
  }

  // Redraw Main Canvas
  function redraw() {
    sheetCtx.clearRect(0, 0, sheetCanvas.width, sheetCanvas.height);
    if (!imgLoaded) return;

    sheetCtx.imageSmoothingEnabled = false;

    // 1. Draw Sprite Sheet
    sheetCtx.drawImage(
      spriteImg,
      0, 0, 256, 250,
      panX, panY, 256 * scale, 250 * scale
    );

    // 2. Faint 8x8 Grid
    if (chkGrid.checked) {
      sheetCtx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      sheetCtx.lineWidth = 1;
      const step = 8 * scale;
      for (let x = 0; x <= 256; x += 8) {
        const cx = panX + x * scale;
        sheetCtx.beginPath();
        sheetCtx.moveTo(cx, panY);
        sheetCtx.lineTo(cx, panY + 250 * scale);
        sheetCtx.stroke();
      }
      for (let y = 0; y <= 250; y += 8) {
        const cy = panY + y * scale;
        sheetCtx.beginPath();
        sheetCtx.moveTo(panX, cy);
        sheetCtx.lineTo(panX + 256 * scale, cy);
        sheetCtx.stroke();
      }
    }

    // 3. Cell Bounding Boxes & Labels
    if (chkCells.checked) {
      METADATA.components.forEach(comp => {
        const cid = comp.cell_idx;
        const color = CELL_COLORS[cid] || "#fff";
        const isSel = (cid === selectedCellId);

        const cx = panX + comp.canvas_x * scale;
        const cy = panY + comp.canvas_y * scale;
        const cw = comp.width * scale;
        const ch = comp.height * scale;

        sheetCtx.strokeStyle = color;
        sheetCtx.lineWidth = isSel ? 3 : 1.5;
        sheetCtx.strokeRect(cx, cy, cw, ch);

        if (isSel) {
          sheetCtx.fillStyle = color.replace(")", ", 0.08)").replace("rgb", "rgba");
          sheetCtx.fillRect(cx, cy, cw, ch);
        }

        // Badge label
        if (chkLabels.checked) {
          sheetCtx.font = "bold 10px " + getComputedStyle(document.body).fontFamily;
          const label = `[${cid}] ${CELL_NAMES[cid] || ''}`;
          const tw = sheetCtx.measureText(label).width;

          sheetCtx.fillStyle = "rgba(13, 17, 23, 0.85)";
          sheetCtx.fillRect(cx, cy - 14, tw + 8, 14);
          sheetCtx.strokeStyle = color;
          sheetCtx.lineWidth = 1;
          sheetCtx.strokeRect(cx, cy - 14, tw + 8, 14);

          sheetCtx.fillStyle = color;
          sheetCtx.fillText(label, cx + 4, cy - 3);
        }
      });
    }

    // 4. OAM Bounding Boxes (Dashed)
    if (chkOams.checked) {
      sheetCtx.setLineDash([3 * (scale > 2 ? 2 : 1), 3 * (scale > 2 ? 2 : 1)]);
      METADATA.components.forEach(comp => {
        const cid = comp.cell_idx;
        const color = CELL_COLORS[cid] || "#fff";

        comp.oams.forEach((oam, i) => {
          const ox = panX + (comp.canvas_x + (oam.x - comp.min_x)) * scale;
          const oy = panY + (comp.canvas_y + (oam.y - comp.min_y)) * scale;
          const ow = oam.w * scale;
          const oh = oam.h * scale;

          sheetCtx.strokeStyle = color;
          sheetCtx.lineWidth = 1;
          sheetCtx.strokeRect(ox, oy, ow, oh);

          if (chkLabels.checked && scale >= 3 && ow >= 32) {
            sheetCtx.font = "9px monospace";
            sheetCtx.fillStyle = color;
            sheetCtx.fillText(`T:${oam.tile}`, ox + 3, oy + 10);
          }
        });
      });
      sheetCtx.setLineDash([]);
    }

    // 5. Seam (x=48) & 4px Hardware Gap
    if (chkSeamGap.checked) {
      // Cell 0 and 1: SEAM at x=48
      [0, 1].forEach(cid => {
        const comp = METADATA.components.find(c => c.cell_idx === cid);
        if (comp) {
          const sx = panX + (comp.canvas_x + 48) * scale;
          const sy = panY + comp.canvas_y * scale;
          const sh = 24 * scale;

          // Glowing bright red line
          sheetCtx.strokeStyle = "rgba(255, 23, 68, 0.4)";
          sheetCtx.lineWidth = 4;
          sheetCtx.beginPath();
          sheetCtx.moveTo(sx, sy);
          sheetCtx.lineTo(sx, sy + sh);
          sheetCtx.stroke();

          sheetCtx.strokeStyle = "#ff1744";
          sheetCtx.lineWidth = 2;
          sheetCtx.beginPath();
          sheetCtx.moveTo(sx, sy);
          sheetCtx.lineTo(sx, sy + sh);
          sheetCtx.stroke();

          // Seam text
          sheetCtx.fillStyle = "#ff1744";
          sheetCtx.font = "bold 9px monospace";
          sheetCtx.fillText("SEAM (48px)", sx - 30, sy + sh + 11);
        }
      });

      // Cell 3 and 4: 4px Hardware Gap at local x=48..52
      [3, 4].forEach(cid => {
        const comp = METADATA.components.find(c => c.cell_idx === cid);
        if (comp) {
          const gx1 = panX + (comp.canvas_x + 48) * scale;
          const gy = panY + comp.canvas_y * scale;
          const gw = 4 * scale;
          const gh = 24 * scale;

          // Yellow hatched area
          sheetCtx.fillStyle = "rgba(255, 214, 0, 0.25)";
          sheetCtx.fillRect(gx1, gy, gw, gh);
          sheetCtx.strokeStyle = "#ffd600";
          sheetCtx.lineWidth = 1.5;
          sheetCtx.strokeRect(gx1, gy, gw, gh);

          // Diagonal hatch lines
          sheetCtx.save();
          sheetCtx.beginPath();
          sheetCtx.rect(gx1, gy, gw, gh);
          sheetCtx.clip();
          sheetCtx.strokeStyle = "rgba(255, 214, 0, 0.8)";
          sheetCtx.lineWidth = 2;
          for (let d = -gh; d < gw + gh; d += 6) {
            sheetCtx.beginPath();
            sheetCtx.moveTo(gx1 + d, gy);
            sheetCtx.lineTo(gx1 + d + gh, gy + gh);
            sheetCtx.stroke();
          }
          sheetCtx.restore();

          // Warning label
          sheetCtx.fillStyle = "#ffd600";
          sheetCtx.font = "bold 9px monospace";
          sheetCtx.fillText("4px GAP", gx1 - 16, gy + gh + 11);
        }
      });
    }

    // 6. Highlight Hovered OAM
    if (hoveredOam) {
      const oam = hoveredOam.oam;
      const comp = hoveredOam.comp;
      const hx = panX + (comp.canvas_x + (oam.x - comp.min_x)) * scale;
      const hy = panY + (comp.canvas_y + (oam.y - comp.min_y)) * scale;
      const hw = oam.w * scale;
      const hh = oam.h * scale;

      sheetCtx.strokeStyle = "#ffffff";
      sheetCtx.lineWidth = 2;
      sheetCtx.strokeRect(hx, hy, hw, hh);
      sheetCtx.fillStyle = "rgba(255, 255, 255, 0.15)";
      sheetCtx.fillRect(hx, hy, hw, hh);
    }
  }

  // Live NDS Screen Preview
  function renderNdsPreview(cid) {
    ndsCtx.clearRect(0, 0, 256, 192);
    if (!imgLoaded) return;

    ndsCtx.imageSmoothingEnabled = false;

    // Screen Background
    ndsCtx.fillStyle = "#0c1017";
    ndsCtx.fillRect(0, 0, 256, 192);

    // Subtle Screen Grid
    ndsCtx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ndsCtx.lineWidth = 1;
    for (let x = 0; x < 256; x += 16) {
      ndsCtx.beginPath();
      ndsCtx.moveTo(x, 0);
      ndsCtx.lineTo(x, 192);
      ndsCtx.stroke();
    }
    for (let y = 0; y < 192; y += 16) {
      ndsCtx.beginPath();
      ndsCtx.moveTo(0, y);
      ndsCtx.lineTo(256, y);
      ndsCtx.stroke();
    }

    const comp = METADATA.components.find(c => c.cell_idx === cid);
    if (!comp) return;

    // Compute cell bounding box across all OAMs
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    comp.oams.forEach(o => {
      if (o.x < minX) minX = o.x;
      if (o.x + o.w > maxX) maxX = o.x + o.w;
      if (o.y < minY) minY = o.y;
      if (o.y + o.h > maxY) maxY = o.y + o.h;
    });

    const cellW = maxX - minX;
    const cellH = maxY - minY;

    // Center on NDS screen (256x192)
    const anchorX = Math.round((256 - cellW) / 2) - minX;
    const anchorY = Math.round((192 - cellH) / 2) - minY;

    // Draw each OAM
    comp.oams.forEach(oam => {
      const srcX = comp.canvas_x + (oam.x - comp.min_x);
      const srcY = comp.canvas_y + (oam.y - comp.min_y);
      const dstX = anchorX + oam.x;
      const dstY = anchorY + oam.y;

      ndsCtx.drawImage(
        spriteImg,
        srcX, srcY, oam.w, oam.h,
        dstX, dstY, oam.w, oam.h
      );
    });

    // Screen Center crosshair indicator
    ndsCtx.strokeStyle = "rgba(88, 166, 255, 0.25)";
    ndsCtx.beginPath();
    ndsCtx.moveTo(128, 88); ndsCtx.lineTo(128, 104);
    ndsCtx.moveTo(120, 96); ndsCtx.lineTo(136, 96);
    ndsCtx.stroke();
  }

  // Comparison & Shift logic
  function toggleShiftPair() {
    if (selectedCellId === 0) selectCell(3);
    else if (selectedCellId === 3) selectCell(0);
    else if (selectedCellId === 1) selectCell(4);
    else if (selectedCellId === 4) selectCell(1);
    else if (selectedCellId === 2) selectCell(5);
    else if (selectedCellId === 5) selectCell(2);
    else selectCell(3);
  }

  function toggleBlink() {
    const btn = document.getElementById("btnBlinkToggle");
    if (blinkInterval) {
      clearInterval(blinkInterval);
      blinkInterval = null;
      btn.textContent = "Blink: Off";
      btn.classList.remove("active");
    } else {
      blinkInterval = setInterval(() => {
        toggleShiftPair();
      }, 800);
      btn.textContent = "Blink: On";
      btn.classList.add("active");
    }
  }

  // Kickoff
  init();
</script>

</body>
</html>
"""


def build_viewer_html() -> None:
    # Read images and encode to base64
    trans_bytes = TRANSLATED_PNG.read_bytes() if TRANSLATED_PNG.is_file() else b""
    trans_b64 = f"data:image/png;base64,{base64.b64encode(trans_bytes).decode('ascii')}" if trans_bytes else ""

    orig_bytes = EXTRACTED_PNG.read_bytes() if EXTRACTED_PNG.is_file() else b""
    orig_b64 = f"data:image/png;base64,{base64.b64encode(orig_bytes).decode('ascii')}" if orig_bytes else ""

    json_path = TRANSLATED_JSON if TRANSLATED_JSON.is_file() else EXTRACTED_JSON
    metadata_obj = json.loads(json_path.read_text(encoding="utf-8"))
    metadata_json = json.dumps(metadata_obj)

    html_content = (
        HTML_TEMPLATE
        .replace("__TRANSLATED_B64__", trans_b64)
        .replace("__ORIGINAL_B64__", orig_b64)
        .replace("__METADATA_JSON__", metadata_json)
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Interactive visualizer saved to: {OUTPUT_HTML}")
    print(f"Size: {len(html_content):,} bytes")


if __name__ == "__main__":
    build_viewer_html()

/**
 * GFU · Ilha dos Dois Irmãos, 1778 — módulo para Foundry VTT v14.
 *
 * - Instala no mundo: cena com a carta (num nível v14), diário dos locais, Notas de Mapa e uma macro.
 * - Importa os segredos do Mestre de um arquivo .json que não fica no repositório público.
 * - Abre a carta interativa numa janela (ApplicationV2), com visão do Mestre para quem é GM.
 */
const MOD = "gfu-twin-brothers-1778";
const PATH = `modules/${MOD}`;
const LEVEL_ID = "ilhaNivel1778000";
const TITLE = "Ilha dos Dois Irmãos, 1778";
const RED = "#9a2b1e";
const INK = "#2f2216";

let DATA = null;
let SVG_TEXT = null;
const log = (...a) => console.log(`${MOD} |`, ...a);

async function loadData() {
  if (!DATA) DATA = await (await fetch(`${PATH}/dados/locais.json`)).json();
  return DATA;
}
async function loadSvg() {
  if (!SVG_TEXT) SVG_TEXT = await (await fetch(`${PATH}/assets/carta-atlas.svg`)).text();
  return SVG_TEXT;
}
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const state = () => foundry.utils.deepClone(game.settings.get(MOD, "install") ?? {});
const OWN = () => CONST.DOCUMENT_OWNERSHIP_LEVELS;
const HTML_FORMAT = () => CONST.JOURNAL_ENTRY_PAGE_FORMATS?.HTML ?? 1;
const anchorBottom = () => CONST.TEXT_ANCHOR_POINTS?.BOTTOM ?? 1;
function playerJournal() { return game.journal.find(j => j.getFlag(MOD, "kind") === "jogadores"); }
function gmJournal() { return game.journal.find(j => j.getFlag(MOD, "kind") === "mestre"); }
function pageFor(journal, ref) { return journal?.pages.find(p => p.getFlag(MOD, "ref") === ref); }

/* ------------------------------------------------------------------ instalação */

async function deleteIfExists(collection, id) {
  const doc = id ? collection.get(id) : null;
  if (doc) await doc.delete();
}

async function ensureBackground(scene, src) {
  const levels = scene.levels;
  const first = levels?.contents?.[0] ?? (levels ? [...levels.values?.() ?? []][0] : null);
  if (first) {
    if (first.background?.src !== src) await scene.updateEmbeddedDocuments("Level", [{ _id: first.id, "background.src": src }]);
  } else if ("background" in scene) {
    await scene.update({ "background.src": src });
  }
}

async function install({ secrets = null } = {}) {
  const d = await loadData();
  const st = state();
  // Reinstalar: apaga o que esta carta criou antes
  await deleteIfExists(game.scenes, st.scene);
  await deleteIfExists(game.journal, st.journal);
  await deleteIfExists(game.journal, st.journalGM);
  await deleteIfExists(game.macros, st.macro);
  await deleteIfExists(game.folders, st.folder);

  const folder = await Folder.create({ name: "GFU · 1778", type: "JournalEntry", color: "#6e5537" });
  const pages = [
    { name: "Como ler a carta", type: "text", sort: 0, text: { content: d.intro, format: HTML_FORMAT() }, flags: { [MOD]: { ref: "intro" } } },
    ...d.locais.map((l, i) => ({
      name: `${l.letra} · ${l.nome}`, type: "text", sort: (i + 1) * 1000,
      text: { content: l.html, format: HTML_FORMAT() }, flags: { [MOD]: { ref: l.id } }
    }))
  ];
  const journal = await JournalEntry.create({
    name: TITLE, folder: folder.id, ownership: { default: OWN().OBSERVER }, pages, flags: { [MOD]: { kind: "jogadores" } }
  });

  const src = `${PATH}/assets/carta-1778.webp`;
  const sceneData = {
    name: TITLE, navName: "Ilha, 1778", navigation: true,
    width: d.cena.W, height: d.cena.H, padding: 0.1, backgroundColor: "#3a2d22",
    thumb: `${PATH}/assets/carta-1778-thumb.webp`, journal: journal.id, tokenVision: false,
    grid: { type: CONST.GRID_TYPES.GRIDLESS, size: 100, distance: d.cena.km_por_100px, units: "km" },
    environment: { globalLight: { enabled: true } },
    levels: [{ _id: LEVEL_ID, name: "Carta", background: { src, color: "#efe2bf" } }],
    initialLevel: LEVEL_ID,
    flags: { [MOD]: { kind: "cena" } }
  };
  let scene;
  try {
    scene = await Scene.create(sceneData);
  } catch (err) {
    console.warn(`${MOD} | a cena com nível falhou, tentando sem nível`, err);
    delete sceneData.levels; delete sceneData.initialLevel;
    scene = await Scene.create(sceneData);
  }
  await ensureBackground(scene, src);

  const notes = d.locais.map(l => {
    const page = pageFor(journal, l.id);
    return {
      entryId: journal.id, pageId: page?.id ?? null, x: l.px[0], y: l.px[1],
      texture: { src: `${PATH}/assets/icons/ref-${l.letra}.svg` }, iconSize: 56,
      text: `${l.letra} · ${l.nome}`, fontSize: 30, textAnchor: anchorBottom(), textColor: INK, global: true,
      flags: { [MOD]: { ref: l.id } }
    };
  });
  await scene.createEmbeddedDocuments("Note", notes);

  const macro = await Macro.create({
    name: "Carta de 1778", type: "script", img: `${PATH}/assets/icons/carta.svg`,
    command: `game.modules.get("${MOD}")?.api?.openAtlas();`, ownership: { default: OWN().OBSERVER }
  });

  Object.assign(st, { version: game.modules.get(MOD)?.version, scene: scene.id, journal: journal.id, macro: macro.id, folder: folder.id, journalGM: null, dismissed: false });
  await game.settings.set(MOD, "install", st);
  if (secrets) await importSecrets(secrets);
  ui.notifications.info(`${TITLE}: carta instalada. A cena está na lista de cenas e a macro "Carta de 1778" abre a carta interativa.`);
  return scene;
}

async function importSecrets(json) {
  if (json?.module !== MOD || json?.tipo !== "segredos" || !Array.isArray(json.locais)) {
    throw new Error("Este arquivo não é o arquivo de segredos da Ilha dos Dois Irmãos, 1778.");
  }
  const st = state();
  const scene = st.scene ? game.scenes.get(st.scene) : null;
  if (!scene) throw new Error("Instale a carta antes de importar os segredos.");
  await deleteIfExists(game.journal, st.journalGM);

  const pages = json.locais.map((l, i) => ({
    name: `${l.letra} · ${l.nome}`, type: "text", sort: i * 1000,
    text: { content: l.html, format: HTML_FORMAT() }, flags: { [MOD]: { ref: l.id } }
  }));
  const atlas = {
    notas: json.locais.filter(l => l.nota).map(l => ({ ref: l.id, m: l.nota.m, texto: l.nota.texto })),
    extras: json.locais.filter(l => l.gm).map(l => ({ id: l.id, letra: l.letra, nome: l.nome, onde: l.onde, m: l.m }))
  };
  const gm = await JournalEntry.create({
    name: `${TITLE} · Mestre`, folder: st.folder ?? null, ownership: { default: OWN().NONE }, pages,
    flags: { [MOD]: { kind: "mestre", atlas } }
  });

  const old = scene.notes.filter(n => n.getFlag(MOD, "gm")).map(n => n.id);
  if (old.length) await scene.deleteEmbeddedDocuments("Note", old);
  const notes = json.locais.map(l => {
    const page = pageFor(gm, l.id);
    return {
      entryId: gm.id, pageId: page?.id ?? null, x: l.px_gm[0], y: l.px_gm[1],
      texture: { src: `${PATH}/assets/icons/${l.gm ? `ref-${l.letra}` : "segredo"}.svg` }, iconSize: l.gm ? 56 : 34,
      text: l.gm ? `${l.letra} · ${l.nome}` : `${l.letra} · segredos`, fontSize: 24, textAnchor: anchorBottom(),
      textColor: RED, global: true, flags: { [MOD]: { ref: l.id, gm: true } }
    };
  });
  await scene.createEmbeddedDocuments("Note", notes);

  st.journalGM = gm.id;
  await game.settings.set(MOD, "install", st);
  ui.notifications.info(`${TITLE}: segredos do Mestre importados. Só o Mestre vê o diário "${gm.name}" e as notas vermelhas.`);
}

async function readJsonFile(file) {
  if (!file) return null;
  try { return JSON.parse(await file.text()); }
  catch (err) { throw new Error("Não consegui ler o arquivo. Use o .json de segredos que veio do Claude, sem alterar."); }
}

async function installDialog() {
  if (!game.user.isGM) return;
  const st = state();
  const installed = !!(st.scene && game.scenes.get(st.scene));
  const content = `
    <p>${installed
      ? "A carta já está instalada neste mundo. Reinstalar apaga a cena, os diários e a macro desta carta e cria tudo de novo."
      : "Isso cria neste mundo a cena da carta de 1778, o diário dos locais com as Notas de Mapa e a macro que abre a carta interativa."}</p>
    <div class="form-group"><label for="g78-file">Segredos do Mestre (opcional)</label>
      <input id="g78-file" type="file" name="segredos" accept=".json,application/json"></div>
    <p class="hint">Sem o arquivo, só o conteúdo dos jogadores é instalado. Os segredos podem ser importados depois nas configurações do módulo.</p>`;
  const res = await foundry.applications.api.DialogV2.wait({
    window: { title: TITLE, icon: "fa-solid fa-map-location-dot" }, content, rejectClose: false,
    buttons: [
      { action: "install", label: installed ? "Reinstalar" : "Instalar", icon: "fa-solid fa-check", default: true,
        callback: (event, button) => ({ file: button.form?.elements?.segredos?.files?.[0] ?? null }) },
      { action: "later", label: "Agora não" }
    ]
  });
  if (!res || typeof res !== "object") {
    if (res === "later" && !installed) { st.dismissed = true; await game.settings.set(MOD, "install", st); }
    return;
  }
  try {
    const secrets = await readJsonFile(res.file);
    await install({ secrets });
  } catch (err) {
    console.error(err);
    ui.notifications.error(`${TITLE}: ${err.message}`);
  }
}

async function secretsDialog() {
  if (!game.user.isGM) return;
  const content = `
    <p>Escolha o arquivo <strong>ilha-1778-segredos-do-mestre.json</strong>. Ele cria um diário que só o Mestre vê e as notas vermelhas na cena.</p>
    <div class="form-group"><label for="g78-file2">Arquivo de segredos</label>
      <input id="g78-file2" type="file" name="segredos" accept=".json,application/json"></div>`;
  const res = await foundry.applications.api.DialogV2.wait({
    window: { title: "Segredos do Mestre", icon: "fa-solid fa-user-secret" }, content, rejectClose: false,
    buttons: [
      { action: "import", label: "Importar", icon: "fa-solid fa-file-import", default: true,
        callback: (event, button) => ({ file: button.form?.elements?.segredos?.files?.[0] ?? null }) },
      { action: "cancel", label: "Cancelar" }
    ]
  });
  if (!res || typeof res !== "object") return;
  try {
    if (!res.file) throw new Error("Nenhum arquivo escolhido.");
    await importSecrets(await readJsonFile(res.file));
  } catch (err) {
    console.error(err);
    ui.notifications.error(`${TITLE}: ${err.message}`);
  }
}

/* ------------------------------------------------------------------ carta interativa */

class AtlasApp extends foundry.applications.api.ApplicationV2 {
  static DEFAULT_OPTIONS = {
    id: "gfu-atlas-1778",
    classes: ["gfu-atlas"],
    tag: "div",
    window: { title: TITLE, icon: "fa-solid fa-map-location-dot", resizable: true },
    position: { width: 1180, height: 820 }
  };

  mode = "jog";
  current = null;

  async _renderHTML(context, options) {
    const [svg, d] = await Promise.all([loadSvg(), loadData()]);
    const isGM = game.user.isGM;
    const gm = isGM ? gmJournal() : null;
    const extras = gm?.getFlag(MOD, "atlas")?.extras ?? [];
    const refs = [...d.locais, ...extras.map(x => ({ ...x, gm: true }))];
    const el = document.createElement("div");
    el.className = "g78-wrap";
    el.innerHTML = `
      <div class="g78-stage">${svg}
        <div class="g78-zoom">
          <button type="button" data-z="in" aria-label="Aproximar">+</button>
          <button type="button" data-z="out" aria-label="Afastar">−</button>
          <button type="button" data-z="fit" class="wide" aria-label="Ver a carta inteira">Tudo</button>
        </div>
      </div>
      <aside class="g78-side">
        ${isGM ? `<div class="g78-mode" role="group" aria-label="Visão">
          <button type="button" data-mode="jog" aria-pressed="true">Jogadores</button>
          <button type="button" data-mode="mestre" aria-pressed="false">Mestre</button></div>` : ""}
        ${isGM && !gm ? `<p class="g78-empty">Os segredos do Mestre ainda não foram importados. Use as configurações do módulo.</p>` : ""}
        <section class="g78-card" aria-live="polite"><p class="g78-empty">Clique numa letra da carta, ou numa referência abaixo, para abrir a ficha do local.</p></section>
        <section><h3>Referências</h3><ul class="g78-refs">
          ${refs.map(r => `<li class="${r.gm ? "gm" : ""}"><button type="button" data-ref="${r.id}"><span class="l">${esc(r.letra)}</span><span>${esc(r.nome)}</span></button></li>`).join("")}
        </ul></section>
        <section><h3>Camadas</h3><div class="g78-layers">
          ${[["names", "Nomes"], ["refs", "Referências"], ["snd", "Sondagens"], ["rhumb", "Linhas de rumo"], ["relief", "Relevo"], ["woods", "Matas"], ["roads", "Caminhos"], ["water", "Linhas d’água"]]
            .map(([k, t]) => `<label><input type="checkbox" data-l="g78-lyr-${k}" checked> ${t}</label>`).join("")}
        </div></section>
      </aside>`;
    if (isGM && gm) this.#addGmLayer(el.querySelector("svg"), gm, extras);
    return el;
  }

  _replaceHTML(result, content, options) {
    content.replaceChildren(result);
    this.#wire(result);
  }

  #addGmLayer(svg, gm, extras) {
    const NS = "http://www.w3.org/2000/svg";
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "g78-gm");
    for (const n of gm.getFlag(MOD, "atlas")?.notas ?? []) {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", n.m[0]); t.setAttribute("y", n.m[1]); t.setAttribute("class", "gm-note");
      t.textContent = n.texto;
      g.appendChild(t);
    }
    for (const x of extras) {
      const r = document.createElementNS(NS, "g");
      r.setAttribute("class", "ref gm"); r.setAttribute("data-ref", x.id); r.setAttribute("tabindex", "0");
      r.setAttribute("transform", `translate(${x.m[0]} ${x.m[1]})`);
      r.innerHTML = `<circle r="330" class="ref-hit"/><circle r="190" class="ref-c"/><text y="78" class="ref-t" text-anchor="middle">${esc(x.letra)}</text>`;
      g.appendChild(r);
    }
    svg.appendChild(g);
  }

  #wire(root) {
    const svg = root.querySelector("svg");
    const stage = root.querySelector(".g78-stage");
    const v0 = svg.getAttribute("viewBox").split(/\s+/).map(Number);
    const HOME = { x: v0[0], y: v0[1], w: v0[2], h: v0[3] };
    let vb = { ...HOME };
    const apply = () => svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    const toSvg = (cx, cy) => { const p = svg.createSVGPoint(); p.x = cx; p.y = cy; return p.matrixTransform(svg.getScreenCTM().inverse()); };
    const zoomAt = (f, cx, cy) => {
      const p = toSvg(cx, cy); const nw = Math.min(HOME.w * 1.25, Math.max(1800, vb.w * f)); const k = nw / vb.w;
      vb = { x: p.x - (p.x - vb.x) * k, y: p.y - (p.y - vb.y) * k, w: nw, h: vb.h * k }; apply();
    };
    stage.addEventListener("wheel", e => { e.preventDefault(); e.stopPropagation(); zoomAt(Math.exp(e.deltaY * 0.0015), e.clientX, e.clientY); }, { passive: false });
    const ptrs = new Map(); let moved = 0, pinch0 = null;
    stage.addEventListener("pointerdown", e => {
      if (e.target.closest(".g78-zoom")) return;
      stage.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY }); moved = 0;
      if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch0 = { d: Math.hypot(a.x - b.x, a.y - b.y), w: vb.w }; }
      stage.classList.add("drag");
    });
    stage.addEventListener("pointermove", e => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId), cur = { x: e.clientX, y: e.clientY }; ptrs.set(e.pointerId, cur);
      if (ptrs.size === 2 && pinch0) { const [a, b] = [...ptrs.values()]; const d = Math.hypot(a.x - b.x, a.y - b.y);
        zoomAt((pinch0.w * pinch0.d / Math.max(1, d)) / vb.w, (a.x + b.x) / 2, (a.y + b.y) / 2); moved += 10; return; }
      const p0 = toSvg(prev.x, prev.y), p1 = toSvg(cur.x, cur.y);
      vb.x -= p1.x - p0.x; vb.y -= p1.y - p0.y; moved += Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y); apply();
    });
    const up = e => { ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch0 = null; if (!ptrs.size) stage.classList.remove("drag"); };
    stage.addEventListener("pointerup", e => {
      if (moved < 5) { const el = document.elementFromPoint(e.clientX, e.clientY); const g = el?.closest?.(".ref"); if (g) this.#select(root, g.dataset.ref, false); }
      up(e);
    });
    stage.addEventListener("pointercancel", up);
    root.querySelectorAll(".g78-zoom button").forEach(b => b.addEventListener("click", () => {
      const r = stage.getBoundingClientRect();
      if (b.dataset.z === "fit") { vb = { ...HOME }; apply(); }
      else zoomAt(b.dataset.z === "in" ? 1 / 1.6 : 1.6, r.left + r.width / 2, r.top + r.height / 2);
    }));
    root.querySelectorAll(".g78-layers input").forEach(inp => inp.addEventListener("change", () => svg.getElementById?.(inp.dataset.l)?.classList.toggle("off", !inp.checked) ?? root.querySelector(`#${inp.dataset.l}`)?.classList.toggle("off", !inp.checked)));
    root.querySelectorAll(".g78-refs button").forEach(b => b.addEventListener("click", () => {
      this.#select(root, b.dataset.ref, true);
      const d = root.querySelector(`.ref[data-ref="${b.dataset.ref}"]`);
      if (d) { const m = /translate\(([-\d.]+)[ ,]+([-\d.]+)\)/.exec(d.getAttribute("transform") ?? ""); if (m) { const w = 9000, k = stage.clientHeight / Math.max(1, stage.clientWidth); vb = { x: +m[1] - w / 2, y: +m[2] - w * k / 2, w, h: w * k }; apply(); } }
    }));
    root.querySelectorAll(".ref").forEach(g => g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.#select(root, g.dataset.ref, false); } }));
    root.querySelectorAll(".g78-mode button").forEach(b => b.addEventListener("click", () => this.#setMode(root, b.dataset.mode)));
    this.#setMode(root, this.mode);
    new ResizeObserver(apply).observe(stage);
    apply();
  }

  #setMode(root, mode) {
    this.mode = game.user.isGM ? mode : "jog";
    root.classList.toggle("mestre", this.mode === "mestre");
    root.querySelectorAll(".g78-mode button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === this.mode)));
    if (this.current) this.#select(root, this.current, false);
  }

  #select(root, id, fly) {
    const d = DATA?.locais.find(l => l.id === id);
    const gm = game.user.isGM ? gmJournal() : null;
    const extra = gm?.getFlag(MOD, "atlas")?.extras?.find(x => x.id === id);
    if (!d && !extra) return;
    if (extra && this.mode !== "mestre") {
      this.current = null;
      root.querySelectorAll(".ref.sel").forEach(g => g.classList.remove("sel"));
      root.querySelector(".g78-card").innerHTML = `<p class="g78-empty">Clique numa letra da carta, ou numa referência abaixo, para abrir a ficha do local.</p>`;
      return;
    }
    this.current = id;
    root.querySelectorAll(".ref.sel").forEach(g => g.classList.remove("sel"));
    root.querySelector(`.ref[data-ref="${id}"]`)?.classList.add("sel");
    root.querySelectorAll(".g78-refs button").forEach(b => b.setAttribute("aria-current", String(b.dataset.ref === id)));
    const info = d ?? extra;
    const pj = playerJournal(); const pPage = pageFor(pj, id);
    const gPage = this.mode === "mestre" ? pageFor(gm, id) : null;
    const pHtml = pPage?.text?.content ?? d?.html ?? "";
    const card = root.querySelector(".g78-card");
    card.innerHTML = `
      <div class="k"><span class="lt ${extra ? "gm" : ""}">${esc(info.letra)}</span><div><h2>${esc(pPage?.name?.replace(/^\w · /, "") ?? info.nome)}</h2><div class="onde">${esc(info.onde)}</div></div></div>
      ${pHtml ? `<div class="g78-text">${pHtml}</div>` : `<p class="g78-empty">Só o Mestre vê este local.</p>`}
      ${gPage ? `<div class="g78-secret"><div class="g78-secret-h">Mestre</div>${gPage.text?.content ?? ""}</div>` : ""}
      <div class="g78-actions">
        ${pPage ? `<button type="button" data-open="p">Abrir no diário</button>` : ""}
        ${gPage ? `<button type="button" data-open="g">Abrir a página do Mestre</button>` : ""}
      </div>`;
    card.querySelector('[data-open="p"]')?.addEventListener("click", () => pj.sheet.render(true, { pageId: pPage.id }));
    card.querySelector('[data-open="g"]')?.addEventListener("click", () => gm.sheet.render(true, { pageId: gPage.id }));
  }
}

let atlas = null;
async function openAtlas() {
  await loadData();
  if (!atlas) atlas = new AtlasApp();
  return atlas.render({ force: true });
}

/* ------------------------------------------------------------------ menus de configuração */

class InstallMenu extends foundry.applications.api.ApplicationV2 {
  async render() { installDialog(); return this; }
}
class SecretsMenu extends foundry.applications.api.ApplicationV2 {
  async render() { secretsDialog(); return this; }
}

/* ------------------------------------------------------------------ ganchos */

Hooks.once("init", () => {
  game.settings.register(MOD, "install", { scope: "world", config: false, type: Object, default: {} });
  game.settings.registerMenu(MOD, "installMenu", {
    name: "Instalar a carta no mundo", label: "Instalar ou reinstalar", icon: "fa-solid fa-map",
    hint: "Cria a cena da carta, o diário dos locais com as Notas de Mapa e a macro Carta de 1778.",
    type: InstallMenu, restricted: true
  });
  game.settings.registerMenu(MOD, "secretsMenu", {
    name: "Segredos do Mestre", label: "Importar arquivo de segredos", icon: "fa-solid fa-user-secret",
    hint: "Importa o arquivo .json com os segredos do Ato I. Só o Mestre vê o que ele cria.",
    type: SecretsMenu, restricted: true
  });
  const mod = game.modules.get(MOD);
  if (mod) mod.api = { openAtlas, install, importSecrets, installDialog, secretsDialog };
});

Hooks.on("getSceneControlButtons", controls => {
  const tool = {
    name: "gfu-atlas-1778", title: "Carta de 1778", icon: "fa-solid fa-map-location-dot",
    button: true, visible: true, order: 99, onChange: () => openAtlas(), onClick: () => openAtlas()
  };
  try {
    if (Array.isArray(controls)) controls.find(c => c.name === "notes")?.tools?.push(tool);
    else {
      const notes = controls.notes ?? controls.tokens;
      if (notes?.tools) notes.tools[tool.name] = tool;
    }
  } catch (err) { console.warn(`${MOD} | não consegui pôr o botão na barra`, err); }
});

Hooks.once("ready", async () => {
  if (!game.user.isGM) return;
  const st = state();
  const installed = !!(st.scene && game.scenes.get(st.scene));
  if (!installed && !st.dismissed) installDialog();
  log("pronto", installed ? "instalado" : "não instalado");
});

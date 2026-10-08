// The UI Design Reference tab: twelve common interface components, each one a card with
// its name, what it is for, and a working example. Every example is built here from plain
// elements and the kit's tokens, so each one can be read top to bottom and none of them
// leaves the page. Nothing a visitor types or clicks is sent or saved anywhere.

import {html} from "npm:htl";

let serial = 0;
const uid = (prefix) => `ui-${prefix}-${++serial}`;

const ZONES = [
  "Astoria",
  "Bushwick South",
  "Crown Heights North",
  "East Village",
  "JFK Airport",
  "LaGuardia Airport",
  "Midtown Center",
  "Park Slope",
  "Times Sq/Theatre District",
  "Upper East Side South",
  "Upper West Side South",
  "Williamsburg (North Side)"
];

const BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"];

// A panel anchored under the control that opens it. Escape or a click anywhere else
// closes it, and the document is only listened to while the panel is open.
function floating(trigger, panel) {
  const wrap = html`<span class="ui-anchor">${trigger}${panel}</span>`;
  panel.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  const onDown = (e) => {
    if (!wrap.contains(e.target)) close();
  };
  const onKey = (e) => {
    if (e.key !== "Escape") return;
    close();
    trigger.focus();
  };
  function open() {
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
  }
  function close() {
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", onDown);
    document.removeEventListener("keydown", onKey);
  }
  trigger.addEventListener("click", () => (panel.hidden ? open() : close()));
  return {wrap, open, close};
}

function accordion() {
  const items = [
    ["How is a trip counted?", "Each row TLC publishes is one trip, from pickup to drop off. A shared ride is still one row per rider."],
    ["Why is the data two months behind?", "TLC collects the records from the companies, checks them, and publishes a month at a time."],
    ["Which companies are included?", "Uber and Lyft, the two high volume for-hire services operating in New York City."]
  ];
  const root = html`<div class="ui-accordion">${items.map(
    ([question, answer], i) => html`<details class="ui-fold" open=${i === 0}><summary>${question}</summary><p>${answer}</p></details>`
  )}</div>`;
  // Opening one section closes the rest: that is what makes it an accordion.
  root.addEventListener(
    "toggle",
    (e) => {
      if (!e.target.open) return;
      for (const other of root.querySelectorAll("details[open]")) if (other !== e.target) other.open = false;
    },
    true
  );
  return root;
}

function carousel() {
  const slides = [
    ["Trips per day", "Volume across the year, with a seven day average."],
    ["Market share", "How the two companies split the city, month by month."],
    ["Wait for pickup", "Minutes from request to pickup, by hour of day."],
    ["Busiest zones", "Where the most trips begin."]
  ];
  let current = 0;
  const track = html`<div class="ui-carousel-track">${slides.map(
    ([title, text], n) => html`<div class="ui-slide" role="group" aria-roledescription="slide" aria-label=${`${n + 1} of ${slides.length}`}><strong>${title}</strong><span>${text}</span></div>`
  )}</div>`;
  const dots = slides.map((_, n) => {
    const dot = html`<button type="button" class="ui-dot" aria-label=${`Go to slide ${n + 1}`}></button>`;
    dot.addEventListener("click", () => go(n));
    return dot;
  });
  const previous = html`<button type="button" class="button ui-icon-button" aria-label="Previous slide">&lsaquo;</button>`;
  const next = html`<button type="button" class="button ui-icon-button" aria-label="Next slide">&rsaquo;</button>`;
  const count = html`<span class="ui-carousel-count" aria-live="polite"></span>`;
  function go(n) {
    current = (n + slides.length) % slides.length;
    track.style.transform = `translateX(${-100 * current}%)`;
    dots.forEach((dot, k) => dot.setAttribute("aria-current", String(k === current)));
    count.textContent = `${current + 1} of ${slides.length}`;
  }
  previous.addEventListener("click", () => go(current - 1));
  next.addEventListener("click", () => go(current + 1));
  go(0);
  return html`<div class="ui-carousel" role="group" aria-roledescription="carousel" aria-label="Charts on the Operations tab">
    <div class="ui-carousel-window">${track}</div>
    <div class="ui-carousel-bar">${previous}<span class="ui-dots">${dots}</span>${count}${next}</div>
  </div>`;
}

function combobox() {
  const listId = uid("listbox");
  const input = html`<input class="ui-input ui-combo-input" type="text" role="combobox" aria-label="Pickup zone" aria-autocomplete="list" aria-expanded="false" aria-controls=${listId} placeholder="Type a pickup zone" autocomplete="off" spellcheck="false">`;
  const list = html`<ul class="ui-float ui-listbox" role="listbox" id=${listId} aria-label="Pickup zones" aria-multiselectable="true" hidden></ul>`;
  const hint = html`<p class="ui-hint">Hold Ctrl (Cmd on a Mac) while you click or press Enter to choose more than one.</p>`;
  const result = html`<p class="ui-result">Nothing chosen yet.</p>`;
  const chosen = new Set();
  let shown = [];
  let active = -1;

  function render() {
    const query = input.value.trim().toLowerCase();
    shown = ZONES.filter((zone) => zone.toLowerCase().includes(query));
    active = Math.min(active, shown.length - 1);
    const options = shown.map((zone, n) => {
      const option = html`<li role="option" id=${`${listId}-${n}`} class=${n === active ? "ui-active" : null} aria-selected=${String(chosen.has(zone))}>${zone}</li>`;
      // pointerdown, not click: a click would land after the input has blurred and closed the list.
      option.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        if (e.ctrlKey || e.metaKey) toggle(zone);
        else choose(zone);
      });
      return option;
    });
    list.replaceChildren(...(options.length ? options : [html`<li class="ui-empty">No zone matches.</li>`]));
    if (active >= 0) input.setAttribute("aria-activedescendant", `${listId}-${active}`);
    else input.removeAttribute("aria-activedescendant");
    const row = options[active];
    if (row) list.scrollTop = Math.max(Math.min(list.scrollTop, row.offsetTop), row.offsetTop + row.offsetHeight - list.clientHeight);
  }
  function open() {
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    render();
  }
  function close() {
    list.hidden = true;
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
  function report() {
    result.textContent = chosen.size ? `Chosen: ${[...chosen].join(", ")}` : "Nothing chosen yet.";
  }
  function choose(zone) {
    chosen.clear();
    chosen.add(zone);
    input.value = zone;
    report();
    close();
  }
  // With Ctrl or Cmd held: add or remove one zone and leave the list open for the next.
  function toggle(zone) {
    if (!chosen.delete(zone)) chosen.add(zone);
    input.value = "";
    report();
    render();
  }
  input.addEventListener("input", () => {
    active = 0;
    open();
  });
  input.addEventListener("click", open);
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (list.hidden) open();
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = shown.length ? (active + step + shown.length) % shown.length : -1;
      render();
    } else if (e.key === "Enter" && !list.hidden && shown[active]) {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) toggle(shown[active]);
      else choose(shown[active]);
    } else if (e.key === "Escape" && !list.hidden) {
      close();
    }
  });
  return html`<div><span class="ui-anchor ui-combo">${input}${list}</span>${hint}${result}</div>`;
}

function datepicker() {
  const now = new Date();
  let value = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let view = new Date(value.getFullYear(), value.getMonth(), 1);
  // The day the arrow keys are on. It is the only day in the Tab order.
  let cursor = value;
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const label = html`<span></span>`;
  const field = html`<button type="button" class="ui-input ui-date-field" aria-haspopup="dialog">${label}<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg></button>`;
  const panel = html`<div class="ui-float ui-calendar" role="dialog" aria-label="Choose a date"></div>`;
  const result = html`<p class="ui-result"></p>`;
  const {wrap, close} = floating(field, panel);

  function show() {
    label.textContent = value.toLocaleDateString("en-US", {dateStyle: "medium"});
    result.textContent = `Chosen: ${value.toLocaleDateString("en-US", {dateStyle: "full"})}`;
  }
  function shift(months) {
    view = new Date(view.getFullYear(), view.getMonth() + months, 1);
    // Keep the day of the month where the new month has it, as in 31 January to 28 February.
    const last = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    cursor = new Date(view.getFullYear(), view.getMonth(), Math.min(cursor.getDate(), last));
    render();
  }
  function moveTo(date) {
    cursor = date;
    view = new Date(date.getFullYear(), date.getMonth(), 1);
    render();
    panel.querySelector(".ui-day[tabindex='0']").focus();
  }
  function render() {
    const previous = html`<button type="button" class="button ui-icon-button" aria-label="Previous month">&lsaquo;</button>`;
    const next = html`<button type="button" class="button ui-icon-button" aria-label="Next month">&rsaquo;</button>`;
    previous.addEventListener("click", () => shift(-1));
    next.addEventListener("click", () => shift(1));
    const days = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    const cells = Array.from({length: view.getDay()}, () => html`<span></span>`);
    for (let d = 1; d <= days; d++) {
      const date = new Date(view.getFullYear(), view.getMonth(), d);
      const day = html`<button type="button" class=${sameDay(date, now) ? "ui-day is-today" : "ui-day"} tabindex=${sameDay(date, cursor) ? "0" : "-1"} aria-pressed=${String(sameDay(date, value))} aria-label=${date.toLocaleDateString("en-US", {dateStyle: "long"})}>${d}</button>`;
      day.addEventListener("click", () => {
        value = date;
        show();
        render();
        close();
        field.focus();
      });
      cells.push(day);
    }
    panel.replaceChildren(
      html`<div class="ui-calendar-head">${previous}<strong aria-live="polite">${view.toLocaleDateString("en-US", {month: "long", year: "numeric"})}</strong>${next}</div>`,
      html`<div class="ui-calendar-grid ui-weekdays" aria-hidden="true">${["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => html`<span>${d}</span>`)}</div>`,
      html`<div class="ui-calendar-grid">${cells}</div>`
    );
  }
  // Arrows move by a day or a week, Home and End go to the ends of the week, Page Up and
  // Page Down change the month, and with Shift the year.
  panel.addEventListener("keydown", (e) => {
    if (!e.target.classList.contains("ui-day")) return;
    const day = (n) => new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + n);
    const month = (n) => {
      const last = new Date(cursor.getFullYear(), cursor.getMonth() + n + 1, 0).getDate();
      return new Date(cursor.getFullYear(), cursor.getMonth() + n, Math.min(cursor.getDate(), last));
    };
    const moves = {
      ArrowLeft: () => day(-1),
      ArrowRight: () => day(1),
      ArrowUp: () => day(-7),
      ArrowDown: () => day(7),
      Home: () => day(-cursor.getDay()),
      End: () => day(6 - cursor.getDay()),
      PageUp: () => month(e.shiftKey ? -12 : -1),
      PageDown: () => month(e.shiftKey ? 12 : 1)
    };
    if (!moves[e.key]) return;
    e.preventDefault();
    moveTo(moves[e.key]());
  });
  // Reopening always starts on the chosen date, with the keyboard already on it.
  field.addEventListener("click", () => {
    if (panel.hidden) return;
    moveTo(value);
  });
  show();
  render();
  return html`<div>${wrap}${result}</div>`;
}

function drawer() {
  const titleId = uid("drawer-title");
  const closeButton = html`<button type="button" class="button ui-icon-button" aria-label="Close">&times;</button>`;
  const cancel = html`<button type="button" class="button">Cancel</button>`;
  const apply = html`<button type="button" class="button ui-primary">Apply</button>`;
  const result = html`<p class="ui-result">The drawer is closed.</p>`;
  // The dialog element is the dimmed page; the panel inside it is the drawer. A native
  // modal dialog keeps the keyboard inside it and closes on Escape without any script.
  const dialog = html`<dialog class="ui-drawer" aria-labelledby=${titleId}>
    <div class="ui-drawer-panel">
      <header><h3 id=${titleId}>Trip filters</h3>${closeButton}</header>
      <div class="ui-drawer-body">
        <p>The page stays where it was underneath, so closing this puts you straight back.</p>
        <fieldset class="ui-checks">
          <legend>Pickup borough</legend>
          ${BOROUGHS.map((b) => html`<label><input type="checkbox" checked=${b !== "Staten Island"}> ${b}</label>`)}
        </fieldset>
      </div>
      <footer>${cancel}${apply}</footer>
    </div>
  </dialog>`;
  // One button per edge. The side is a data attribute the stylesheet reads.
  const openers = ["Left", "Right", "Bottom"].map((side) => {
    const button = html`<button type="button" class="button">${side} drawer</button>`;
    button.addEventListener("click", () => {
      dialog.dataset.side = side.toLowerCase();
      dialog.showModal();
    });
    return button;
  });
  // Escape and a click on the dimmed page close it too, and count as closing without a choice.
  let how = "";
  const closeWith = (choice) => {
    how = choice;
    dialog.close();
  };
  closeButton.addEventListener("click", () => closeWith(""));
  cancel.addEventListener("click", () => closeWith("Cancel"));
  apply.addEventListener("click", () => closeWith("Apply"));
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) closeWith("");
  });
  dialog.addEventListener("close", () => {
    result.textContent = how ? `Closed with ${how}.` : "Closed without a choice.";
    how = "";
  });
  return html`<div><div class="ui-actions" role="group" aria-label="Open the drawer from">${openers}</div>${dialog}${result}</div>`;
}

function expander() {
  return html`<details class="ui-fold ui-expander">
    <summary>Show the SQL behind this number</summary>
    <pre>SELECT count(*) AS trips
FROM trips
WHERE pickup_datetime &gt; dropoff_datetime;</pre>
  </details>`;
}

function form() {
  const fields = [
    {name: "name", label: "Full name", required: "Enter your name.", control: (id) => html`<input class="ui-input" id=${id} name="name" type="text" autocomplete="off" required>`},
    {name: "email", label: "Work email", required: "Enter your email address.", invalid: "That does not look like an email address.", control: (id) => html`<input class="ui-input" id=${id} name="email" type="email" autocomplete="off" required>`},
    {name: "borough", label: "Pickup borough", required: "Choose a borough.", control: (id) => html`<select class="ui-input" id=${id} name="borough" required><option value="">Choose one</option>${BOROUGHS.map((b) => html`<option>${b}</option>`)}</select>`}
  ].map((f) => {
    const id = uid(f.name);
    const control = f.control(id);
    const error = html`<span class="ui-error" id=${`${id}-error`} hidden></span>`;
    const row = html`<div class="ui-field"><label for=${id}>${f.label} <span class="ui-required" aria-hidden="true">*</span></label>${control}${error}</div>`;
    const check = () => {
      const message = control.validity.valueMissing ? f.required : control.validity.valid ? "" : f.invalid;
      error.textContent = message;
      error.hidden = !message;
      control.setAttribute("aria-invalid", String(Boolean(message)));
      if (message) control.setAttribute("aria-describedby", error.id);
      else control.removeAttribute("aria-describedby");
      return !message;
    };
    // Once a field has been flagged, clear the flag as soon as it is put right.
    control.addEventListener("input", () => !error.hidden && check());
    return {row, control, check};
  });
  const status = html`<p class="ui-result" role="status">Fields marked * are required.</p>`;
  const root = html`<form class="ui-form" novalidate>
    ${fields.map((f) => f.row)}
    <label class="ui-check"><input type="checkbox" name="summary"> Send me the monthly summary</label>
    <div class="ui-actions"><button type="submit" class="button ui-primary">Submit</button><button type="reset" class="button">Reset</button></div>
    ${status}
  </form>`;
  root.addEventListener("submit", (e) => {
    e.preventDefault();
    const failed = fields.filter((f) => !f.check());
    if (failed.length) {
      status.textContent = failed.length === 1 ? "One field needs attention." : `${failed.length} fields need attention.`;
      failed[0].control.focus();
    } else {
      status.textContent = "Submitted. This form is a demonstration, so nothing was sent.";
    }
  });
  root.addEventListener("reset", () => {
    for (const f of fields) {
      f.control.removeAttribute("aria-invalid");
      f.control.removeAttribute("aria-describedby");
      f.row.querySelector(".ui-error").hidden = true;
    }
    status.textContent = "Fields marked * are required.";
  });
  return root;
}

function popover() {
  const info = html`<button type="button" class="button" aria-haspopup="dialog">Trip details</button>`;
  const infoPanel = html`<div class="ui-float ui-popover" role="dialog" aria-label="Trip details">
    <strong>Midtown Center to JFK Airport</strong>
    <dl><dt>Distance</dt><dd>17.2 mi</dd><dt>Fare</dt><dd>$78.40</dd><dt>Driver pay</dt><dd>$54.10</dd></dl>
    <p>Click anywhere else, or press Escape, to close.</p>
  </div>`;
  const first = floating(info, infoPanel);

  const result = html`<p class="ui-result">The saved view is still here.</p>`;
  const remove = html`<button type="button" class="button ui-danger" aria-haspopup="dialog">Delete saved view</button>`;
  const cancel = html`<button type="button" class="button">Cancel</button>`;
  const confirm = html`<button type="button" class="button ui-danger-fill">Delete</button>`;
  const confirmPanel = html`<div class="ui-float ui-popover" role="alertdialog" aria-label="Confirm delete">
    <strong>Delete this saved view?</strong>
    <p>This cannot be undone.</p>
    <div class="ui-actions">${cancel}${confirm}</div>
  </div>`;
  const second = floating(remove, confirmPanel);
  cancel.addEventListener("click", () => {
    second.close();
    remove.focus();
    result.textContent = "Cancelled. The saved view is still here.";
  });
  confirm.addEventListener("click", () => {
    second.close();
    remove.focus();
    result.textContent = "Deleted (not really: this is a demonstration).";
  });
  return html`<div>
    <div class="ui-pair">
      <div><span class="ui-kind">Popover</span>${first.wrap}</div>
      <div><span class="ui-kind">Popconfirm</span>${second.wrap}</div>
    </div>
    ${result}
  </div>`;
}

function tabsDemo() {
  const panels = [
    ["Summary", "19.8 million trips in the month, up 3% on the month before."],
    ["By company", "Uber carried about three trips in four. Lyft carried the rest."],
    ["Notes", "Figures are for the selected month and include every borough."]
  ].map(([label, text], n) => {
    const id = uid("tab");
    const tab = html`<button type="button" class="ui-tab" role="tab" id=${id} aria-controls=${`${id}-panel`}>${label}</button>`;
    const panel = html`<div class="ui-tabpanel" role="tabpanel" id=${`${id}-panel`} aria-labelledby=${id} tabindex="0"><p>${text}</p></div>`;
    tab.addEventListener("click", () => select(n));
    return {tab, panel};
  });
  function select(n, focus = false) {
    panels.forEach(({tab, panel}, k) => {
      tab.setAttribute("aria-selected", String(k === n));
      tab.tabIndex = k === n ? 0 : -1;
      panel.hidden = k !== n;
    });
    if (focus) panels[n].tab.focus();
  }
  const list = html`<div class="ui-tablist" role="tablist" aria-label="Month summary">${panels.map((p) => p.tab)}</div>`;
  // Arrow keys move along the row; Tab leaves it for the panel.
  list.addEventListener("keydown", (e) => {
    const at = panels.findIndex((p) => p.tab === document.activeElement);
    const to = {ArrowRight: (at + 1) % panels.length, ArrowLeft: (at - 1 + panels.length) % panels.length, Home: 0, End: panels.length - 1}[e.key];
    if (to === undefined) return;
    e.preventDefault();
    select(to, true);
  });
  select(0);
  return html`<div class="ui-tabs">${list}${panels.map((p) => p.panel)}</div>`;
}

// One stack of toasts for the page, at the corner of the window, made on first use.
let toastStack;
// Icons from Lucide (lucide.dev, ISC licence): sun, moon and monitor, drawn inline so the
// page loads nothing extra.
const LUCIDE = {
  sun: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>`,
  moon: `<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>`,
  monitor: `<rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>`
};

function lucide(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "ui-lucide");
  svg.innerHTML = LUCIDE[name];
  return svg;
}

function themePicker() {
  const choices = [
    ["light", "Light", "sun"],
    ["dark", "Dark", "moon"],
    ["system", "System", "monitor"]
  ];
  const system = () => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  // The sample is a small stand-in for a page, so trying this does not fight the real
  // theme button in the header.
  const sample = html`<div class="ui-theme-sample"><strong>2,418 trips</strong><span>A sample card in the chosen theme.</span></div>`;
  const result = html`<p class="ui-result"></p>`;
  const buttons = choices.map(([value, label, icon]) => {
    const button = html`<button type="button" class="ui-seg" role="radio" aria-checked="false">${lucide(icon)}<span>${label}</span></button>`;
    button.addEventListener("click", () => choose(value));
    return button;
  });
  function choose(value) {
    const shown = value === "system" ? system() : value;
    sample.dataset.theme = shown;
    buttons.forEach((button, n) => {
      const on = choices[n][0] === value;
      button.setAttribute("aria-checked", String(on));
      button.tabIndex = on ? 0 : -1;
    });
    result.textContent = value === "system" ? `Following your device, which is set to ${shown}.` : `Chosen: ${choices.find(([v]) => v === value)[1]}`;
  }
  const group = html`<div class="ui-segmented" role="radiogroup" aria-label="Theme">${buttons}</div>`;
  group.addEventListener("keydown", (e) => {
    const step = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1}[e.key];
    if (!step) return;
    e.preventDefault();
    const at = buttons.indexOf(document.activeElement);
    const to = (at + step + buttons.length) % buttons.length;
    choose(choices[to][0]);
    buttons[to].focus();
  });
  choose("system");
  return html`<div>${group}${sample}${result}</div>`;
}

function toast(kind, message, life = 4000) {
  if (!toastStack?.isConnected) {
    toastStack = html`<div class="ui-toasts" role="region" aria-label="Notifications" aria-live="polite"></div>`;
    document.body.append(toastStack);
  }
  const dismiss = html`<button type="button" class="ui-toast-close" aria-label="Dismiss">&times;</button>`;
  const item = html`<div class=${`ui-toast is-${kind}`} role=${kind === "error" ? "alert" : "status"}><span>${message}</span>${dismiss}</div>`;
  const leave = () => {
    clearTimeout(timer);
    item.classList.add("is-leaving");
    setTimeout(() => item.remove(), 200);
  };
  let timer = setTimeout(leave, life);
  // A toast being read should not vanish from under the pointer.
  item.addEventListener("pointerenter", () => clearTimeout(timer));
  item.addEventListener("pointerleave", () => (timer = setTimeout(leave, life)));
  dismiss.addEventListener("click", leave);
  toastStack.append(item);
}

function toastDemo() {
  const save = html`<button type="button" class="button">Save changes</button>`;
  const copy = html`<button type="button" class="button">Copy link</button>`;
  const fail = html`<button type="button" class="button">Fail an upload</button>`;
  save.addEventListener("click", () => toast("success", "Changes saved."));
  copy.addEventListener("click", () => toast("info", "Link copied to the clipboard (not really)."));
  fail.addEventListener("click", () => toast("error", "The upload failed. Check the file and try again.", 6000));
  return html`<div><div class="ui-actions">${save}${copy}${fail}</div><p class="ui-result">Each toast appears at the bottom right of the window and leaves after a few seconds.</p></div>`;
}

function tree() {
  const data = {
    name: "New York City",
    children: [
      {name: "Brooklyn", children: [{name: "Bushwick South"}, {name: "Park Slope"}, {name: "Williamsburg (North Side)"}]},
      {name: "Manhattan", children: [{name: "East Village"}, {name: "Midtown Center"}, {name: "Upper East Side South"}]},
      {name: "Queens", children: [{name: "Airports", children: [{name: "JFK Airport"}, {name: "LaGuardia Airport"}]}, {name: "Astoria"}]}
    ]
  };
  const node = (n, level) => html`<li role="treeitem" aria-level=${level} aria-selected="false" aria-expanded=${n.children ? String(level === 1) : null} tabindex="-1">
    <span class="ui-tree-row"><span class=${n.children ? "ui-twist" : "ui-leaf"} aria-hidden="true"></span><span class="ui-tree-name">${n.name}</span></span>
    ${n.children ? html`<ul role="group">${n.children.map((c) => node(c, level + 1))}</ul>` : null}
  </li>`;
  const root = html`<ul class="ui-tree" role="tree" aria-label="Pickup zones by borough">${node(data, 1)}</ul>`;
  const result = html`<p class="ui-result">Nothing selected yet.</p>`;
  const items = () => [...root.querySelectorAll('[role="treeitem"]')];
  const parentOf = (item) => item.parentElement.closest('[role="treeitem"]');
  const visible = () => items().filter((item) => !item.parentElement.closest('[role="treeitem"][aria-expanded="false"]'));
  const isOpen = (item) => item.getAttribute("aria-expanded") === "true";
  const isParent = (item) => item.hasAttribute("aria-expanded");
  const setOpen = (item, open) => item.setAttribute("aria-expanded", String(open));

  // One item at a time is in the tab order, so Tab enters the tree once and the arrows move within it.
  function focus(item) {
    for (const other of items()) other.tabIndex = other === item ? 0 : -1;
    item.focus();
  }
  function select(item) {
    for (const other of items()) other.setAttribute("aria-selected", String(other === item));
    const path = [];
    for (let at = item; at; at = parentOf(at)) path.unshift(at.querySelector(".ui-tree-name").textContent);
    result.textContent = `Selected: ${path.join(" / ")}`;
  }
  root.addEventListener("click", (e) => {
    const item = e.target.closest(".ui-tree-row")?.parentElement;
    if (!item) return;
    if (isParent(item)) setOpen(item, !isOpen(item));
    select(item);
    focus(item);
  });
  root.addEventListener("keydown", (e) => {
    const item = e.target.closest('[role="treeitem"]');
    if (!item) return;
    const shown = visible();
    const at = shown.indexOf(item);
    const moves = {
      ArrowDown: () => shown[at + 1] && focus(shown[at + 1]),
      ArrowUp: () => shown[at - 1] && focus(shown[at - 1]),
      Home: () => focus(shown[0]),
      End: () => focus(shown.at(-1)),
      ArrowRight: () => (isParent(item) && !isOpen(item) ? setOpen(item, true) : isParent(item) && focus(shown[at + 1])),
      ArrowLeft: () => (isOpen(item) ? setOpen(item, false) : parentOf(item) && focus(parentOf(item))),
      Enter: () => {
        if (isParent(item)) setOpen(item, !isOpen(item));
        select(item);
      }
    };
    const move = moves[e.key === " " ? "Enter" : e.key];
    if (!move) return;
    e.preventDefault();
    e.stopPropagation();
    move();
  });
  items()[0].tabIndex = 0;
  return html`<div>${root}${result}</div>`;
}

// In the order the tab lists them. `demo` is a function so each card builds its own example.
export const entries = [
  {
    id: "accordion",
    name: "Accordion",
    aka: "collapsible sections, collapse",
    what: "A stack of headings that each open to show their own content. Opening one closes the others, so one section is in view at a time.",
    when: "Long content splits into sections a reader will pick between, such as frequent questions or groups of settings.",
    unlike: "An expander, which is a single section that opens and closes by itself.",
    demo: accordion
  },
  {
    id: "carousel",
    name: "Carousel",
    aka: "slider, slideshow",
    what: "A row of panels shown one at a time, moved with arrows, dots or a swipe.",
    when: "A few items of equal weight share one space, such as photos or featured cards. Most people never go past the first slide, so nothing essential belongs on the later ones.",
    unlike: "Tabs, where every panel has a visible label and is one click away.",
    demo: carousel
  },
  {
    id: "combobox",
    name: "Combobox",
    aka: "autocomplete, typeahead, searchable select",
    what: "A text box joined to a list of options. Typing narrows the list, and picking an option fills the box. This one also takes several options when Ctrl is held.",
    when: "The list is too long to scan by eye: countries, zones, customers.",
    unlike: "A dropdown (a select), which only lets you pick from the list and gives you nowhere to type.",
    demo: combobox
  },
  {
    id: "datepicker",
    name: "Datepicker",
    aka: "date picker, calendar picker",
    what: "A field that opens a small calendar, so a date is picked instead of typed.",
    when: "The date is close to today and the day of the week matters, as in a booking. For a date of birth, typing is faster.",
    unlike: "A date range picker, which chooses a start and an end together.",
    demo: datepicker
  },
  {
    id: "drawer",
    name: "Drawer",
    aka: "side drawer, side panel, sheet, off-canvas panel",
    what: "A panel that slides in from an edge of the screen and sits over the page. The page stays visible underneath, dimmed.",
    when: "A task needs more room than a popover but should keep the page in view: filters, the details of one row, the menu on a phone.",
    unlike: "A modal, which opens in the centre of the screen and wants an answer before anything else can happen.",
    demo: drawer
  },
  {
    id: "expander",
    name: "Expander",
    aka: "disclosure, collapsible, show and hide, details",
    what: "One heading that opens to reveal more, and closes again. The rule cards on the Data Quality tab are expanders.",
    when: "Detail that most readers can skip: an explanation, advanced options, the query behind a number.",
    unlike: "An accordion, which is several of these working as a group.",
    demo: expander
  },
  {
    id: "form",
    name: "Form",
    aka: "input form",
    what: "A set of labelled fields with a button that submits them together. A good form marks what is required and says plainly what is wrong. Submit this one empty to see that.",
    when: "Several pieces of information are collected in one go: a sign up, a checkout, a request.",
    unlike: "Filter controls, which act the moment they change and have no submit button.",
    demo: form
  },
  {
    id: "popover",
    name: "Popover and popconfirm",
    aka: "popup, flyout; a popconfirm is also an inline confirmation",
    what: "A popover is a small panel that opens beside the thing you clicked, holding extra detail or actions. A popconfirm is a popover that asks one question before a risky action goes ahead.",
    when: "Popover: a little more detail than fits on the page. Popconfirm: a delete, or anything else awkward to undo, that is too small for a modal.",
    unlike: "A tooltip, which shows on hover, holds a short label only, and has nothing in it to click.",
    demo: popover
  },
  {
    id: "tabs",
    name: "Tabs",
    aka: "tab bar, tabbed panel",
    what: "A row of labels that swap the content beneath them. All the labels stay visible and one is always selected.",
    when: "Content divides into a few parallel views of the same thing, and the reader wants one at a time.",
    unlike: "Navigation links that are drawn as tabs. The row at the top of this page goes to separate pages; the example below swaps a panel in place.",
    demo: tabsDemo
  },
  {
    id: "theme-picker",
    name: "Theme picker",
    aka: "light and dark mode switch, theme toggle, appearance setting",
    what: "A small control that switches the page between a light and a dark look. The icons here are from Lucide, a free open source icon set (lucide.dev): sun, moon and monitor.",
    when: "People use the page in different light, or for long stretches. It usually sits in the upper right corner of the page, where people look for settings. Offer System as well, so the page can follow the device, and remember the choice.",
    unlike: "A two-way toggle, which has no System choice and has to guess the first time. The button in this page's header is that simpler kind.",
    demo: themePicker
  },
  {
    id: "toast",
    name: "Toast",
    aka: "snackbar, toast notification",
    what: "A brief message that appears at the edge of the screen to confirm that something happened, then leaves by itself.",
    when: "Feedback that needs no decision: saved, copied, sent. Anything the reader must not miss belongs on the page instead.",
    unlike: "An alert or a banner, which stays put until it is dealt with.",
    demo: toastDemo
  },
  {
    id: "tree",
    name: "Tree",
    aka: "tree view, nested list, hierarchy",
    what: "A list whose items can hold other items. Each level opens and closes with a small arrow.",
    when: "The data really is nested: folders, an organisation chart, categories inside categories.",
    unlike: "An accordion, which has one level only.",
    demo: tree
  }
];

export function entry({id, name, aka, what, when, unlike, demo}) {
  return html`<section class="card ui-entry" id=${id}>
    <h2>${name}</h2>
    <p class="ui-aka">Also called: ${aka}</p>
    <p class="ui-what">${what}</p>
    <dl class="ui-facts">
      <dt>Use it when</dt><dd>${when}</dd>
      <dt>Not the same as</dt><dd>${unlike}</dd>
    </dl>
    <div class="ui-demo"><span class="ui-demo-label">Try it</span>${demo()}</div>
  </section>`;
}

// The row of links under the lede: one per component, in page order.
export function jumpIndex() {
  return html`<nav class="ui-index" aria-label="Components on this page">${entries.map((e) => html`<a href=${`#${e.id}`}>${e.name}</a>`)}</nav>`;
}

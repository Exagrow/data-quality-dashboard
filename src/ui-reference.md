---
title: UI Design Reference
---

```js
// The chrome is the kit's (src/kit/) and the tabs are this dashboard's. The examples are built in
// components/uiref.js and read no data.
import {masthead} from "./kit/index.js";
import {tabs} from "./components/tabs.js";
import {entries, entry, jumpIndex} from "./components/uiref.js";
```

<div>${masthead("UI Design Reference")}</div>

<div>${tabs("ui-reference")}</div>

<p class="lede">A short reference to ${entries.length} common interface components. Each has its name, the other names it goes by, what it is for, and a working example to try on this page. The examples borrow the dashboard's subject but their values are made up, and nothing typed or clicked here is sent or saved.</p>

<div>${jumpIndex()}</div>

<div class="ui-grid">${entries.map(entry)}</div>

<div class="notes">

**About this page**

- A short list, not a complete one. For a wider catalogue with examples from many design systems, see [The Component Gallery](https://component.gallery). For how each component should behave with a keyboard, see the W3C's [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/patterns/).
- Every example works with a keyboard: Tab moves between controls, the arrow keys move within the tabs, the tree, the combobox list and the calendar, and Escape closes anything that opened.
- Names vary between design systems. The "also called" line lists the ones worth recognising.

</div>

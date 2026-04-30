document.addEventListener('DOMContentLoaded', () => {
    const panel = document.querySelector('[data-search-panel]');
    if (!panel) return;

    const form       = panel.querySelector('#sp-form');
    const qInput     = panel.querySelector('#sp-q');
    const focusInput = panel.querySelector('#sp-focus');

    // ── Navigation tree ──────────────────────────────────────────────────
    const TREE = {
        root: {
            label: null,
            placeholder: 'What do you remember?',
            chips: [
                { id: 'character', label: 'Character', next: 'character' },
                { id: 'scene',     label: 'Scene',     next: 'scene'     },
                { id: 'plot',      label: 'Plot',      next: 'plot'      },
                { id: 'dialogue',  label: 'Dialogue',  next: 'dialogue'  },
                { id: 'visual',    label: 'Visual',    next: 'visual'    },
            ],
        },
        character: {
            label: 'Character',
            placeholder: 'Describe the character…',
            chips: [
                { id: 'actor',        label: 'Actor / Actress', next: 'actor'      },
                { id: 'role',         label: 'Role',            next: 'leaf'       },
                { id: 'charname',     label: 'Name',            next: 'leaf'       },
                { id: 'appearance',   label: 'Appearance',      next: 'appearance' },
                { id: 'relationship', label: 'Relationship',    next: 'leaf'       },
            ],
        },
        actor: {
            label: 'Actor / Actress',
            placeholder: 'Actor or actress…',
            chips: [
                { id: 'actor-name',   label: 'Name',       next: 'leaf' },
                { id: 'actor-gender', label: 'Gender',     next: 'leaf' },
                { id: 'actor-age',    label: 'Age range',  next: 'leaf' },
                { id: 'actor-hair',   label: 'Hair color', next: 'leaf' },
            ],
        },
        appearance: {
            label: 'Appearance',
            placeholder: 'Describe how they looked…',
            chips: [
                { id: 'hair',   label: 'Hairstyle', next: 'leaf' },
                { id: 'outfit', label: 'Outfit',    next: 'leaf' },
                { id: 'height', label: 'Height',    next: 'leaf' },
                { id: 'accent', label: 'Accent',    next: 'leaf' },
                { id: 'age',    label: 'Age',        next: 'leaf' },
            ],
        },
        scene: {
            label: 'Scene',
            placeholder: 'Describe the scene…',
            chips: [
                { id: 'location', label: 'Location',    next: 'leaf' },
                { id: 'time',     label: 'Time of day', next: 'leaf' },
                { id: 'weather',  label: 'Weather',     next: 'leaf' },
                { id: 'action',   label: 'Action',      next: 'leaf' },
                { id: 'objects',  label: 'Objects',     next: 'leaf' },
            ],
        },
        plot: {
            label: 'Plot',
            placeholder: 'Describe the plot…',
            chips: [
                { id: 'theme',    label: 'Theme',      next: 'leaf' },
                { id: 'twist',    label: 'Plot twist', next: 'leaf' },
                { id: 'ending',   label: 'Ending',     next: 'leaf' },
                { id: 'conflict', label: 'Conflict',   next: 'leaf' },
            ],
        },
        dialogue: {
            label: 'Dialogue',
            placeholder: 'What did they say?',
            chips: [
                { id: 'quote',  label: 'Exact quote', next: 'leaf' },
                { id: 'phrase', label: 'Phrase',      next: 'leaf' },
                { id: 'tone',   label: 'Tone',        next: 'leaf' },
                { id: 'lang',   label: 'Language',    next: 'leaf' },
            ],
        },
        visual: {
            label: 'Visual',
            placeholder: 'Describe the visuals…',
            chips: [
                { id: 'color',  label: 'Color palette', next: 'leaf' },
                { id: 'style',  label: 'Film style',    next: 'leaf' },
                { id: 'era',    label: 'Era / Decade',  next: 'leaf' },
                { id: 'camera', label: 'Camera style',  next: 'leaf' },
            ],
        },
    };

    // Leaf-level placeholder text
    const LEAF = {
        'actor-name':   { label: 'Name',          ph: 'Actor or actress name…' },
        'actor-gender': { label: 'Gender',         ph: 'e.g. male, female…'     },
        'actor-age':    { label: 'Age range',      ph: 'e.g. 30s, 50–60…'       },
        'actor-hair':   { label: 'Hair color',     ph: 'e.g. blonde, dark…'     },
        role:           { label: 'Role',           ph: 'e.g. a doctor…'          },
        charname:       { label: 'Name',           ph: 'Character name…'         },
        relationship:   { label: 'Relationship',   ph: 'e.g. brother and sister…'},
        hair:           { label: 'Hairstyle',      ph: 'e.g. curly, bald…'       },
        outfit:         { label: 'Outfit',         ph: 'e.g. red dress…'         },
        height:         { label: 'Height',         ph: 'e.g. tall, short…'       },
        accent:         { label: 'Accent',         ph: 'e.g. British…'           },
        age:            { label: 'Age',            ph: 'e.g. teenager…'          },
        location:       { label: 'Location',       ph: 'e.g. a rooftop…'         },
        time:           { label: 'Time of day',    ph: 'e.g. night…'             },
        weather:        { label: 'Weather',        ph: 'e.g. rainy…'             },
        action:         { label: 'Action',         ph: 'e.g. a chase…'           },
        objects:        { label: 'Objects',        ph: 'e.g. a red umbrella…'    },
        theme:          { label: 'Theme',          ph: 'e.g. redemption…'        },
        twist:          { label: 'Plot twist',     ph: 'Describe the twist…'     },
        ending:         { label: 'Ending',         ph: 'e.g. happy…'             },
        conflict:       { label: 'Conflict',       ph: 'e.g. man vs society…'    },
        quote:          { label: 'Exact quote',    ph: 'Type what you remember…' },
        phrase:         { label: 'Phrase',         ph: 'A word or phrase…'       },
        tone:           { label: 'Tone',           ph: 'e.g. sarcastic…'         },
        lang:           { label: 'Language',       ph: 'e.g. French…'            },
        color:          { label: 'Color palette',  ph: 'e.g. desaturated…'       },
        style:          { label: 'Film style',     ph: 'e.g. noir…'              },
        era:            { label: 'Era / Decade',   ph: 'e.g. 70s…'               },
        camera:         { label: 'Camera style',   ph: 'e.g. close-ups…'        },
    };

    // ── State ─────────────────────────────────────────────────────────────
    let stack   = ['root'];
    let leafId  = null;
    let pending = [];
    let groups  = [];

    // ── DOM refs ──────────────────────────────────────────────────────────
    const pillsZone    = document.getElementById('sp-pills-zone');
    const zoneDivider  = document.getElementById('sp-zone-divider');
    const bcPath       = document.getElementById('sp-bc-path');
    const input        = document.getElementById('sp-input');
    const semicolonBtn = document.getElementById('sp-semicolon-btn');
    const actionBtn    = document.getElementById('sp-action-btn');
    const actionLabel  = document.getElementById('sp-action-label');
    const hint         = document.getElementById('sp-hint');
    const chipsZone    = document.getElementById('sp-chips-zone');
    const groupsEl     = document.getElementById('sp-groups');

    // ── Helpers ───────────────────────────────────────────────────────────
    const curNode    = () => TREE[stack[stack.length - 1]];
    const buildCat   = () => { const p = stack.slice(1).map(k => TREE[k].label); if (leafId) p.push(LEAF[leafId].label); return p.join(' › ') || 'General'; };
    const topLabel   = () => stack.length < 2 ? 'General' : TREE[stack[1]].label;
    const shortLabel = () => leafId ? LEAF[leafId].label : (stack.length > 1 ? TREE[stack[stack.length - 1]].label : '');
    const usedLeafIds = () => new Set(pending.map(p => p.leafId).filter(Boolean));
    const isSearchMode = () => groups.length > 0 && pending.length === 0 && stack.length === 1 && !leafId;

    // ── Action button state ───────────────────────────────────────────────
    function updateActionBtn() {
        if (isSearchMode()) {
            actionBtn.className = 'sp-action-btn sp-action-btn--search';
            actionLabel.innerHTML =
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">' +
                '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>Search';
        } else {
            actionBtn.className = 'sp-action-btn sp-action-btn--add';
            actionLabel.textContent = 'Add';
        }
    }

    // ── Zone A: pending pills ─────────────────────────────────────────────
    function renderPillsZone() {
        pillsZone.innerHTML = '';
        const show = pending.length > 0;
        pillsZone.classList.toggle('sp-pills-zone--visible', show);
        zoneDivider.classList.toggle('sp-zone-divider--visible', show);
        if (!show) return;

        pending.forEach((p, i) => {
            if (i > 0) {
                const sep = document.createElement('span');
                sep.className = 'sp-pill-sep';
                sep.textContent = '·';
                pillsZone.appendChild(sep);
            }
            const pill = document.createElement('div');
            pill.className = 'sp-inline-pill';
            const ct = p.leafLabel || p.topLabel || '';
            pill.innerHTML =
                (ct ? `<span class="sp-pill-cat">${ct}</span>` : '') +
                `<span class="sp-pill-val">${p.val}</span>` +
                `<span class="sp-pill-x" data-idx="${i}">×</span>`;
            pill.querySelector('.sp-pill-x').addEventListener('click', () => removePending(i));
            pillsZone.appendChild(pill);
        });
    }

    // ── Zone B: breadcrumb path ───────────────────────────────────────────
    function renderPath() {
        bcPath.innerHTML = '';
        stack.slice(1).forEach((key, i) => {
            const isLast = i === stack.length - 2;
            const span = document.createElement('span');
            span.className = 'sp-bc-item' + (isLast && !leafId ? ' sp-bc-item--current' : '');
            span.textContent = TREE[key].label;
            span.addEventListener('click', () => jumpTo(i + 1));
            bcPath.appendChild(span);

            const sep = document.createElement('span');
            sep.className = 'sp-bc-sep';
            sep.textContent = ':';
            bcPath.appendChild(sep);
        });

        if (leafId) {
            const span = document.createElement('span');
            span.className = 'sp-bc-item sp-bc-item--current';
            span.textContent = LEAF[leafId].label;
            span.addEventListener('click', () => { leafId = null; renderAll('back'); });
            bcPath.appendChild(span);

            const sep = document.createElement('span');
            sep.className = 'sp-bc-sep';
            sep.textContent = ':';
            bcPath.appendChild(sep);
        }
    }

    function renderInput() {
        const leaf = leafId ? LEAF[leafId] : null;
        const atRoot = stack.length === 1;
        if (leaf)                input.placeholder = leaf.ph;
        else if (!atRoot)        input.placeholder = curNode().placeholder;
        else if (pending.length) input.placeholder = 'Add more…';
        else                     input.placeholder = 'What do you remember?';
    }

    function renderSemicolonBtn() {
        const show = stack.length > 1 || leafId || pending.length > 0;
        semicolonBtn.classList.toggle('sp-semicolon-btn--visible', show);
    }

    // ── Zone C: navigation chips ──────────────────────────────────────────
    function renderChips(dir) {
        chipsZone.innerHTML = '';
        const cls = dir === 'back' ? 'sp-ab' : 'sp-af';
        const used = usedLeafIds();

        if (stack.length > 1 || leafId) {
            const parentLabel = leafId
                ? (curNode().label || 'Back')
                : (TREE[stack[stack.length - 2]].label || 'Back');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `sp-chip sp-chip--back ${cls}`;
            btn.innerHTML =
                '<svg width="10" height="10" viewBox="0 0 12 12" fill="none">' +
                '<path d="M8 2L4 6l4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>' +
                `</svg>${parentLabel}`;
            btn.addEventListener('click', goBack);
            chipsZone.appendChild(btn);
        }

        curNode().chips.forEach(chip => {
            const btn = document.createElement('button');
            btn.type = 'button';
            const hasChildren = chip.next !== 'leaf';
            const isSel  = !hasChildren && leafId === chip.id;
            const isUsed = !hasChildren && used.has(chip.id);

            if (isUsed) {
                btn.className = `sp-chip sp-chip--used ${cls}`;
                btn.textContent = chip.label;
                btn.disabled = true;
            } else {
                btn.className = `sp-chip ${isSel ? 'sp-chip--sel' : 'sp-chip--nav'} ${cls}`;
                btn.textContent = hasChildren ? chip.label + ' →' : chip.label;
                btn.addEventListener('click', () => selectChip(chip));
            }
            chipsZone.appendChild(btn);
        });

        hint.classList.toggle('sp-hint--visible', stack.length > 1 || !!leafId || pending.length > 0);
    }

    function renderAll(dir) {
        renderPillsZone();
        renderPath();
        renderInput();
        renderSemicolonBtn();
        renderChips(dir);
        updateActionBtn();
    }

    // ── Interactions ──────────────────────────────────────────────────────
    function selectChip(chip) {
        if (chip.next === 'leaf') { leafId = chip.id; }
        else { leafId = null; stack.push(chip.next); }
        renderAll('forward');
        input.focus();
    }

    function goBack() {
        if (leafId) { leafId = null; }
        else if (stack.length > 1) { stack.pop(); leafId = null; }
        renderAll('back');
        input.focus();
    }

    function jumpTo(depth) {
        stack = stack.slice(0, depth + 1);
        leafId = null;
        renderAll('back');
        input.focus();
    }

    // ";" — commit current text as a pending pill, stay at same level
    function commitPending() {
        const val = input.value.trim();
        if (!val) { input.focus(); return; }
        pending.push({ cat: buildCat(), topLabel: topLabel(), leafLabel: shortLabel(), leafId, val });
        input.value = '';
        leafId = null;
        renderAll('forward');
        input.focus();
    }

    function removePending(i) {
        pending.splice(i, 1);
        renderAll('forward');
    }

    // Enter — commit all pending pills as a saved group
    function commitAll() {
        const val = input.value.trim();
        if (val) {
            pending.push({ cat: buildCat(), topLabel: topLabel(), leafLabel: shortLabel(), leafId, val });
            input.value = '';
        }
        if (!pending.length) { input.focus(); return; }
        const tops = [...new Set(pending.map(p => p.topLabel))];
        groups.push({ label: tops.length === 1 ? tops[0] : 'General', entries: [...pending] });
        pending = [];
        stack   = ['root'];
        leafId  = null;
        renderAll('back');
        renderGroups();
        input.focus();
    }

    // ── Saved groups ──────────────────────────────────────────────────────
    function renderGroups() {
        if (!groups.length) { groupsEl.innerHTML = ''; return; }
        groupsEl.innerHTML = groups.map((g, gi) => {
            const entriesHtml = g.entries.map((e, ei) => {
                const sc = e.leafLabel || (e.cat.includes('›') ? e.cat.split('›').slice(1).join('›').trim() : '');
                if (sc) {
                    return `<div class="sp-entry sp-pop">` +
                        `<span class="sp-entry-cat">${sc}</span>` +
                        `<span class="sp-entry-val">${e.val}</span>` +
                        `<span class="sp-entry-x" data-gi="${gi}" data-ei="${ei}">×</span>` +
                        `</div>`;
                }
                return `<div class="sp-entry-plain sp-pop">` +
                    `<span class="sp-entry-val">${e.val}</span>` +
                    `<span class="sp-entry-x" data-gi="${gi}" data-ei="${ei}">×</span>` +
                    `</div>`;
            }).join('');
            return `<div class="sp-group sp-pop">` +
                `<div class="sp-group-header">` +
                `<span class="sp-group-label">${g.label}</span>` +
                `<span class="sp-group-x" data-gi="${gi}">×</span>` +
                `</div>` +
                `<div class="sp-group-body">${entriesHtml}</div>` +
                `</div>`;
        }).join('');

        // Event delegation for × buttons
        groupsEl.querySelectorAll('.sp-entry-x').forEach(btn => {
            btn.addEventListener('click', () => {
                const gi = Number(btn.dataset.gi);
                const ei = Number(btn.dataset.ei);
                groups[gi].entries.splice(ei, 1);
                if (!groups[gi].entries.length) groups.splice(gi, 1);
                renderGroups();
                updateActionBtn();
            });
        });
        groupsEl.querySelectorAll('.sp-group-x').forEach(btn => {
            btn.addEventListener('click', () => {
                groups.splice(Number(btn.dataset.gi), 1);
                renderGroups();
                updateActionBtn();
            });
        });
    }

    // ── Search submission ─────────────────────────────────────────────────
    function doSearch() {
        const queryParts = groups.flatMap(g => g.entries.map(e => {
            const cat = e.leafLabel || e.topLabel || '';
            return cat ? `${cat}: ${e.val}` : e.val;
        }));
        qInput.value     = queryParts.join('; ');
        focusInput.value = groups[0]?.entries[0]?.topLabel || '';
        form.submit();
    }

    function handleAction() {
        if (isSearchMode()) { doSearch(); } else { commitAll(); }
    }

    // ── Event listeners ───────────────────────────────────────────────────
    actionBtn.addEventListener('click', handleAction);
    semicolonBtn.addEventListener('click', commitPending);

    input.addEventListener('keydown', e => {
        if (e.key === ';') {
            e.preventDefault();
            commitPending();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            isSearchMode() ? doSearch() : commitAll();
        } else if (e.key === 'Escape') {
            goBack();
        }
    });

    // ── Boot ──────────────────────────────────────────────────────────────
    renderAll('forward');
});

/* Filter dropdowns */
document.addEventListener('DOMContentLoaded', () => {
    const filters = document.querySelectorAll('.filter');
    if (!filters.length) return;
    const dropdowns = [];

    function closeAll(except = null) {
        dropdowns.forEach(dropdown => {
            if (dropdown.filter === except) return;
            dropdown.trigger.setAttribute('aria-expanded', 'false');
            dropdown.menu.hidden = true;
        });
    }

    function positionMenu(dropdown) {
        const { filter, menu } = dropdown;
        const gap = 8;
        const viewportGap = 12;
        const rect = filter.getBoundingClientRect();
        const maxMenuHeight = 248;
        const spaceBelow = window.innerHeight - rect.bottom - gap - viewportGap;
        const spaceAbove = rect.top - gap - viewportGap;
        const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
        const availableHeight = Math.max(132, openUp ? spaceAbove : spaceBelow);
        const menuHeight = Math.min(menu.scrollHeight, maxMenuHeight, availableHeight);
        const left = Math.min(
            Math.max(viewportGap, rect.left),
            window.innerWidth - rect.width - viewportGap
        );

        menu.style.width = `${rect.width}px`;
        menu.style.maxHeight = `${Math.min(maxMenuHeight, availableHeight)}px`;
        menu.style.left = `${left}px`;
        menu.style.top = openUp
            ? `${Math.max(viewportGap, rect.top - gap - menuHeight)}px`
            : `${Math.min(window.innerHeight - viewportGap - menuHeight, rect.bottom + gap)}px`;
    }

    function openDropdown(dropdown) {
        closeAll(dropdown.filter);
        dropdown.menu.hidden = false;
        dropdown.trigger.setAttribute('aria-expanded', 'true');
        positionMenu(dropdown);
    }

    filters.forEach((filter, index) => {
        const select = filter.querySelector('.filter__select');
        if (!select) return;

        filter.classList.add('is-enhanced');

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'filter__trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        trigger.setAttribute('aria-controls', `filter-menu-${index}`);
        trigger.innerHTML = '<span class="filter__value"></span>';

        const menu = document.createElement('div');
        menu.className = 'filter__menu';
        menu.id = `filter-menu-${index}`;
        menu.setAttribute('role', 'listbox');
        menu.hidden = true;
        document.body.appendChild(menu);

        const dropdown = { filter, trigger, menu };
        dropdowns.push(dropdown);

        function syncValue() {
            const selected = select.options[select.selectedIndex];
            trigger.querySelector('.filter__value').textContent = selected ? selected.textContent : '';
            menu.querySelectorAll('.filter__option').forEach(option => {
                const isSelected = option.dataset.value === select.value;
                option.classList.toggle('is-selected', isSelected);
                option.setAttribute('aria-selected', isSelected ? 'true' : 'false');
            });
        }

        Array.from(select.options).forEach(option => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'filter__option';
            item.dataset.value = option.value;
            item.textContent = option.textContent;
            item.setAttribute('role', 'option');
            item.addEventListener('click', () => {
                select.value = option.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                syncValue();
                closeAll();
                trigger.focus();
            });
            menu.appendChild(item);
        });

        trigger.addEventListener('click', e => {
            e.stopPropagation();
            filter.click();
        });

        filter.addEventListener('click', e => {
            if (e.target.closest('select')) return;
            const willOpen = menu.hidden;
            if (willOpen) {
                openDropdown(dropdown);
            } else {
                closeAll();
            }
        });

        trigger.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                closeAll();
                trigger.focus();
            }
        });

        select.insertAdjacentElement('afterend', trigger);
        syncValue();
    });

    document.addEventListener('click', e => {
        if (!e.target.closest('.filter') && !e.target.closest('.filter__menu')) closeAll();
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeAll();
    });

    window.addEventListener('resize', () => {
        dropdowns.forEach(dropdown => {
            if (!dropdown.menu.hidden) positionMenu(dropdown);
        });
    });

    window.addEventListener('scroll', () => {
        dropdowns.forEach(dropdown => {
            if (!dropdown.menu.hidden) positionMenu(dropdown);
        });
    }, true);
});

// ── Collapsible filter bar ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('filter-toggle');
    const grid   = document.getElementById('filter-grid');
    if (!toggle || !grid) return;

    toggle.addEventListener('click', () => {
        const opening = grid.hidden;
        grid.hidden = !opening;
        toggle.setAttribute('aria-expanded', String(opening));
    });
});

// ── Profile panel ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const avatarBtn    = document.getElementById('avatar-btn');
    const panel        = document.getElementById('profile-panel');
    const scrim        = document.getElementById('profile-scrim');
    const closeBtn     = document.getElementById('profile-close');
    const deleteDialog = document.getElementById('delete-dialog');
    const btnDelete    = document.getElementById('btn-delete-account');
    const btnCancel    = document.getElementById('btn-cancel-delete');

    if (!avatarBtn || !panel) return;

    // ── Open / close ────────────────────────────────────────────────────
    function openPanel() {
        panel.hidden = false;
        requestAnimationFrame(() => {
            panel.classList.add('is-open');
            scrim.classList.add('is-open');
        });
        avatarBtn.setAttribute('aria-expanded', 'true');
        closeBtn.focus();
    }

    function closePanel() {
        panel.classList.remove('is-open');
        scrim.classList.remove('is-open');
        panel.addEventListener('transitionend', () => { panel.hidden = true; }, { once: true });
        avatarBtn.setAttribute('aria-expanded', 'false');
        avatarBtn.focus();
    }

    avatarBtn.addEventListener('click', openPanel);
    closeBtn.addEventListener('click', closePanel);
    scrim.addEventListener('click', closePanel);

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            if (deleteDialog && !deleteDialog.hidden) {
                deleteDialog.hidden = true;
            } else if (!panel.hidden) {
                closePanel();
            }
        }
    });

    // ── Generic AJAX form submit ─────────────────────────────────────────
    function getCsrf(form) {
        return form.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    function setFeedback(el, msg, ok) {
        el.textContent = msg;
        el.className = 'pp-feedback ' + (ok ? 'is-ok' : 'is-err');
        setTimeout(() => { el.textContent = ''; el.className = 'pp-feedback'; }, 4000);
    }

    function wireForm(formId, feedbackId, onSuccess) {
        const form = document.getElementById(formId);
        const fb   = document.getElementById(feedbackId);
        if (!form || !fb) return;

        form.addEventListener('submit', async e => {
            e.preventDefault();
            const btn = form.querySelector('button[type=submit]');
            btn.disabled = true;

            try {
                const res = await fetch(form.dataset.url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrf(form),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: new FormData(form),
                });
                const data = await res.json();
                if (data.ok) {
                    setFeedback(fb, 'Saved.', true);
                    onSuccess && onSuccess(data);
                } else {
                    const msgs = Object.values(data.errors || {}).flat().join(' ');
                    setFeedback(fb, msgs || 'Something went wrong.', false);
                }
            } catch {
                setFeedback(fb, 'Network error — please try again.', false);
            } finally {
                btn.disabled = false;
            }
        });
    }

    // Display name — update avatar initials + panel heading on success
    wireForm('form-display-name', 'feedback-display-name', data => {
        const heading = document.getElementById('pp-display-name');
        if (heading) heading.textContent = data.display_name;
        if (avatarBtn && data.initials) avatarBtn.textContent = data.initials;
    });

    // Email
    wireForm('form-email', 'feedback-email');

    // Password — clear fields on success
    wireForm('form-password', 'feedback-password', () => {
        document.getElementById('form-password').reset();
    });

    // Delete account
    if (btnDelete) {
        btnDelete.addEventListener('click', () => { deleteDialog.hidden = false; });
    }
    if (btnCancel) {
        btnCancel.addEventListener('click', () => { deleteDialog.hidden = true; });
    }

    wireForm('form-delete', 'feedback-delete', () => {
        window.location.href = '/';
    });
});

/* ── Watchlist toggle ─────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    function getCsrfFromCookie() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    document.body.addEventListener('click', async e => {
        const btn = e.target.closest('.wl-btn[data-movie-id]');
        if (!btn) return;
        e.preventDefault();

        const url = btn.dataset.url;
        if (!url) return;

        btn.disabled = true;
        btn.classList.remove('wl-btn--pop');
        void btn.offsetWidth; // reflow to restart animation
        btn.classList.add('wl-btn--pop');

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfFromCookie(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await res.json();
            if (data.ok) {
                const inList = data.in_list;
                btn.classList.toggle('wl-btn--active', inList);
                btn.setAttribute('aria-label', inList ? 'Remove from watchlist' : 'Add to watchlist');
                btn.setAttribute('aria-pressed', inList ? 'true' : 'false');

                const icon = btn.querySelector('.wl-btn__icon');
                if (icon) icon.setAttribute('fill', inList ? 'currentColor' : 'none');

                const label = btn.querySelector('.wl-btn__label');
                if (label) {
                    label.textContent = inList
                        ? 'Added'
                        : (btn.classList.contains('wl-btn--watchlist') ? 'Add to Watchlist' : 'Watchlist');
                }
            }
        } catch { /* silent fail */ } finally {
            btn.disabled = false;
        }
    });
});

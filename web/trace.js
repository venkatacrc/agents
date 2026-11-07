// Step-through replays of agent runs (the ::: trace blocks of the lessons), shared by the web
// app and the Mac app. AgentTrace.html(section, key, forPrint) returns the markup; clicks are
// handled here and update the page in place, so the host app never has to re-render.
(() => {
    'use strict';

    const ROLE = {
        system: 'System', user: 'User', think: 'Thinks', call: 'Calls', tool: 'Tool result', answer: 'Answer',
        note: 'Harness', plan: 'Plan', approve: 'Needs approval', ask: 'Asks you', human: 'You',
    };
    const state = new Map();
    const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const traces = new Map();

    function get(key) {
        if (!state.has(key)) state.set(key, { shown: 1, branch: '' });
        return state.get(key);
    }
    // Steps in playback order for the chosen branch; before a choice, everything up to the approval.
    function visible(steps, branch) {
        return steps.map((s, i) => [s, i]).filter(([s]) => !s.branch || s.branch === branch);
    }
    const gate = (steps) => steps.findIndex((s) => s.role === 'approve');

    function html(section, key, forPrint) {
        traces.set(key, section);
        const steps = section.steps || [];
        const branched = steps.some((s) => s.branch);
        const items = steps.map((s, i) => {
            const tag = s.branch ? `<span class="ts-branch">${s.branch === 'approve' ? 'if approved' : 'if denied'}</span>` : '';
            const ctx = s.ctx != null ? `<span class="ts-ctx">${s.ctx.toLocaleString()} tok</span>` : '';
            const choose = branched && i === gate(steps) && !forPrint
                ? `<div class="ts-choose"><button type="button" class="btn good" data-trace="approve">✓ Approve</button>
                   <button type="button" class="btn bad" data-trace="deny">✗ Deny</button></div>` : '';
            return `<li class="ts role-${s.role}" data-i="${i}" data-branch="${s.branch || ''}">
                <span class="ts-role">${ROLE[s.role] || esc(s.role)}${tag}</span>
                <div class="ts-text">${s.text}</div>${ctx}${choose}</li>`;
        }).join('');
        const maxCtx = Math.max(0, ...steps.map((s) => s.ctx || 0));
        return `<div class="trace${forPrint ? ' print' : ''}" data-trace-key="${esc(key)}" data-max="${maxCtx}">
            ${section.title ? `<p class="trace-title">${section.title}</p>` : ''}
            ${maxCtx ? '<div class="trace-meter" aria-hidden="true"><i></i></div>' : ''}
            <ol class="trace-steps">${items}</ol>
            ${forPrint ? '' : `<div class="trace-ctl">
                <button type="button" class="btn" data-trace="reset" aria-label="Restart the replay">↺</button>
                <span class="trace-count"></span>
                <button type="button" class="btn" data-trace="all">Show all</button>
                <button type="button" class="btn primary" data-trace="next">Next step ›</button></div>`}
        </div>`;
    }

    function update(el) {
        const section = traces.get(el.dataset.traceKey);
        if (!section || el.classList.contains('print')) return;
        const steps = section.steps || [];
        const st = get(el.dataset.traceKey);
        const g = gate(steps);
        const order = visible(steps, st.branch);
        let limit = order.length;
        if (g >= 0 && !st.branch && steps.some((s) => s.branch)) limit = order.findIndex(([, i]) => i === g) + 1;
        st.shown = Math.max(1, Math.min(st.shown, limit));
        const on = new Set(order.slice(0, st.shown).map(([, i]) => i));
        let ctx = 0;
        el.querySelectorAll('.ts').forEach((li) => {
            const i = Number(li.dataset.i);
            li.hidden = !on.has(i);
            li.classList.toggle('latest', i === order[st.shown - 1][1]);
            if (on.has(i) && steps[i].ctx != null) ctx = steps[i].ctx;
            const choose = li.querySelector('.ts-choose');
            if (choose) choose.hidden = Boolean(st.branch);
        });
        const waiting = g >= 0 && !st.branch && on.has(g) && steps.some((s) => s.branch);
        const done = st.shown >= order.length && !waiting;
        const next = el.querySelector('[data-trace="next"]');
        if (next) {
            next.disabled = done || waiting;
            next.textContent = waiting ? 'Approve or deny ↑' : done ? 'Done' : 'Next step ›';
        }
        const all = el.querySelector('[data-trace="all"]');
        if (all) all.disabled = done;
        const count = el.querySelector('.trace-count');
        if (count) count.textContent = `${st.shown} / ${waiting ? '…' : order.length}`;
        const meter = el.querySelector('.trace-meter i');
        if (meter) {
            meter.style.width = `${(100 * ctx) / Number(el.dataset.max || 1)}%`;
            meter.parentElement.dataset.label = ctx ? `context ${ctx.toLocaleString()} tokens` : '';
        }
    }

    function act(button) {
        const el = button.closest('.trace');
        const key = el.dataset.traceKey;
        const st = get(key);
        const steps = (traces.get(key) || {}).steps || [];
        switch (button.dataset.trace) {
            case 'next': st.shown++; break;
            case 'all':
                if (!st.branch && steps.some((s) => s.branch)) st.branch = 'approve';
                st.shown = Infinity;
                break;
            case 'reset': st.shown = 1; st.branch = ''; break;
            case 'approve': case 'deny': st.branch = button.dataset.trace; st.shown++; break;
            default: return;
        }
        update(el);
        const latest = el.querySelector('.ts.latest');
        if (latest && button.dataset.trace !== 'reset' && latest.scrollIntoView) latest.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    document.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('[data-trace]');
        if (!b || b.disabled) return;
        e.stopPropagation();
        act(b);
    }, true);

    // Host apps replace their HTML freely; bring every new trace to its remembered step.
    const refresh = () => document.querySelectorAll('.trace[data-trace-key]').forEach(update);
    new MutationObserver((records) => {
        if (records.some((r) => [...r.addedNodes].some((n) => n.nodeType === 1 && (n.matches('.trace') || n.querySelector('.trace'))))) refresh();
    }).observe(document.documentElement, { childList: true, subtree: true });

    window.AgentTrace = { html, refresh };
})();

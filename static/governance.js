function actionPath(job, rule) {
    return '/actions/' + encodeURIComponent(job) + '/' + encodeURIComponent(rule);
}

async function renderActions() {
    const view = $('#view');
    view.innerHTML = '<div class="panel"><div class="panel-body">Loading corrective actions…</div></div>';
    try {
        const actions = await api('/actions');
        if (page !== 'actions') return;
        const canReview = ['reviewer', 'admin'].includes(user.role);
        const assigned = new Set(actions.map(action => action.job_id + '/' + action.rule_id));
        const findings = state.jobs.filter(job => job.status === 'approved').flatMap(job =>
            (job.result?.findings || []).filter(finding =>
                ['breach', 'missing'].includes(finding.status) && !assigned.has(job.id + '/' + finding.rule_id)
            ).map(finding => ({
                value: job.id + '/' + finding.rule_id,
                label: job.result.evidence.mine + ' · ' + finding.title
            }))
        );
        const assignment = canReview && findings.length ? `
            <section class="panel"><div class="panel-head"><h2>Assign a flagged finding</h2></div>
            <form class="panel-body governance-form" data-operation="assign">
                <label>Finding<select name="finding" required>${findings.map(f => `<option value="${esc(f.value)}">${esc(f.label)}</option>`).join('')}</select></label>
                <div class="form-grid"><label>Inspector username<input name="owner" required></label>
                <label>Due date<input name="due_date" type="date" required></label></div>
                <label>Corrective action<textarea name="description" required minlength="10" rows="3"></textarea></label>
                <button class="primary">Assign action</button>
            </form></section>` : '';
        view.innerHTML = assignment + `
            <section class="panel"><div class="panel-head"><h2>${esc(state.mine || 'All mines')}</h2>
            <small>${actions.filter(action => action.overdue).length} overdue · ${actions.length} total</small></div>
            ${actions.length ? actions.map(action => {
                const attributes = `data-job="${esc(action.job_id)}" data-rule="${esc(action.rule_id)}"`;
                const submitEvidence = user.username === action.owner && ['assigned', 'returned'].includes(action.status);
                const verify = canReview && action.status === 'submitted';
                return `<article class="rule-card">
                    ${badge(action.status)} ${action.overdue ? badge('overdue') : ''}
                    <h3>${esc(action.description)}</h3>
                    <p>${esc(action.mine)} · ${esc(action.rule_id)} · Owner: ${esc(action.owner)} · Due: ${esc(action.due_date)}</p>
                    ${action.evidence ? `<p><strong>Closure evidence</strong> ${esc(action.evidence)}</p>` : ''}
                    ${action.review_note ? `<p><strong>Review by ${esc(action.reviewer)}</strong> ${esc(action.review_note)}</p>` : ''}
                    ${submitEvidence ? `<form class="governance-form" data-operation="evidence" ${attributes}>
                        <label>Closure evidence<textarea name="evidence" rows="3" required minlength="10" placeholder="Describe the completed work and include a reference to supporting evidence"></textarea></label>
                        <label>Import a text report<input type="file" accept=".txt,text/plain" data-closure-file></label>
                        <button class="primary">Submit for verification</button></form>` : ''}
                    ${verify ? `<form class="governance-form" data-operation="verify" ${attributes}>
                        <label>Decision<select name="decision"><option value="verified">Verify closure</option><option value="returned">Return for more evidence</option></select></label>
                        <label>Review note<textarea name="note" required minlength="10" rows="2"></textarea></label>
                        <button class="primary">Record verification</button></form>` : ''}
                </article>`;
            }).join('') : empty('No corrective actions yet', 'Approve a flagged inspection to assign a corrective action.')}
            </section>`;
    } catch (error) {
        if (page === 'actions') view.innerHTML = empty('Unable to load actions', esc(error.message));
    }
}

function mineAccessForm() {
    if (user.role !== 'admin') return '';
    return `<section class="panel"><div class="panel-head"><h2>Assign mine access</h2></div>
        <form class="panel-body governance-form" data-operation="scope">
            <p>Limit an existing inspector, reviewer or viewer to one mine. Use the exact mine name from inspection records.</p>
            <div class="form-grid"><label>Username<input name="username" required></label>
            <label>Mine name<input name="mine" required maxlength="100" placeholder="Northfield Demo Mine"></label></div>
            <button class="primary">Save mine access</button>
        </form></section>`;
}

document.addEventListener('change', async event => {
    const input = event.target;
    if (!input.matches('[data-closure-file]') || !input.files.length) return;
    const file = input.files[0];
    try {
        if (file.size > 48000) throw new Error('Choose a smaller text report');
        const report = await file.text();
        if (report.length > 12000) throw new Error('Text reports are limited to 12,000 characters');
        input.form.elements.evidence.value = report;
    } catch (error) {
        notify(error.message);
    } finally {
        input.value = '';
    }
});

document.addEventListener('submit', async event => {
    const form = event.target;
    if (!form.matches('.governance-form')) return;
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    const data = Object.fromEntries(new FormData(form));
    const operation = form.dataset.operation;
    let path;
    let method = 'POST';
    if (operation === 'scope') {
        path = '/users/' + encodeURIComponent(data.username) + '/mine';
        delete data.username;
        method = 'PUT';
    } else if (operation === 'assign') {
        path = actionPath(...data.finding.split('/'));
        delete data.finding;
    } else {
        path = actionPath(form.dataset.job, form.dataset.rule) + '/' + operation;
    }
    try {
        await api(path, {method, body: JSON.stringify(data)});
        notify(operation === 'scope' ? 'Mine access saved' : 'Corrective action updated');
        if (operation === 'scope') form.reset();
        if (page === 'actions') await renderActions();
    } catch (error) {
        notify(error.message);
    } finally {
        button.disabled = false;
    }
});

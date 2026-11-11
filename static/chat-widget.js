(()=>{
  const design=document.createElement('link');design.rel='stylesheet';design.href='/static/chat-widget.css?v=20261110';document.head.append(design);
  const shell=document.querySelector('#shell');
  const toggle=document.querySelector('#quick-chat-toggle');
  const panel=document.querySelector('#quick-chat');
  const messages=document.querySelector('#quick-chat-messages');
  const form=document.querySelector('#quick-chat-form');
  const input=document.querySelector('#quick-chat-input');
  if(!shell||!toggle||!panel||!messages||!form)return;

  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeText=answer=>{
    const parts=[];
    if(answer?.message)parts.push(`<p>${escapeHtml(answer.message)}</p>`);
    if(Array.isArray(answer?.claims))for(const claim of answer.claims)parts.push(`<p>${escapeHtml(typeof claim==='string'?claim:claim.text||JSON.stringify(claim))}</p>`);
    if(Array.isArray(answer?.sources)&&answer.sources.length)parts.push(`<div class="quick-sources"><small>Retrieved policy sources</small>${answer.sources.map(s=>`<div><b>${escapeHtml(s.id)}</b> · ${escapeHtml(s.title)}</div>`).join('')}</div>`);
    if(Array.isArray(answer?.errors)&&answer.errors.length)parts.push(`<small class="quick-error">Provider issue: ${escapeHtml(answer.errors.join('; '))}</small>`);
    return parts.join('')||'<p>No validated policy answer was returned. Check the Rule Library or try again.</p>';
  };
  const addMessage=(kind,html)=>{const node=document.createElement('div');node.className=`quick-message ${kind}`;node.innerHTML=html;messages.append(node);messages.scrollTop=messages.scrollHeight;return node};
  const open=()=>{panel.hidden=false;toggle.hidden=true;input.focus()};
  const close=()=>{panel.hidden=true;toggle.hidden=shell.hidden;toggle.focus()};
  toggle.addEventListener('click',open);
  document.querySelector('#quick-chat-close').addEventListener('click',close);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)close()});
  document.querySelectorAll('[data-prompt]').forEach(button=>button.addEventListener('click',()=>{input.value=button.dataset.prompt;form.requestSubmit()}));
  const sync=()=>{const authenticated=!document.querySelector('#shell').hidden;toggle.hidden=!authenticated||!panel.hidden;if(!authenticated)panel.hidden=true};
  new MutationObserver(sync).observe(shell,{attributes:true,attributeFilter:['hidden']});
  sync();

  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const question=input.value.trim();
    if(question.length<3)return;
    addMessage('user',`<p>${escapeHtml(question)}</p>`);
    input.value='';
    const pending=addMessage('assistant','<p class="typing">Checking the configured policy library…</p>');
    const send=form.querySelector('button');send.disabled=true;
    try{
      const answer=await api('/chat',{method:'POST',body:JSON.stringify({question})});
      pending.innerHTML=safeText(answer);
    }catch(error){pending.innerHTML=`<p>${escapeHtml(error.message||'The assistant could not complete this request.')}</p>`;pending.classList.add('error')}
    finally{send.disabled=false;messages.scrollTop=messages.scrollHeight;input.focus()}
  });
})();

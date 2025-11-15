const chatBox = document.getElementById('chat');
const messageInput = document.getElementById('message');
const fileInput = document.getElementById('file');
const sendBtn = document.getElementById('send');
const clearBtn = document.getElementById('clear');
const clearKbBtn = document.getElementById('clear_knowledge');
// uploaded-list sidebar removed; composer list used instead
const attachBtn = document.getElementById('attach');
const composerUploadedList = document.getElementById('composer-uploaded-list');
const uploadResumeBtn = document.getElementById('upload_resume');
const resumeFileInput = document.getElementById('resume_file');

let currentUpload = null;
let streaming = false;

function fmtTime(){
  const d = new Date();
  return d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function appendBubble(text, who='ai'){
  const wrapper = document.createElement('div');
  const bubble = document.createElement('div');
  // support 'me', 'ai', and 'meta' (system/non-agent) message styles
  let cls = 'ai';
  if(who === 'me') cls = 'me';
  else if(who === 'meta') cls = 'meta';
  bubble.className = 'bubble ' + cls;

  // structured bubble: content + optional inline-meta + timestamp
  const content = document.createElement('div'); content.className = 'bubble-text';
  content.textContent = text;
  const ts = document.createElement('div'); ts.className='timestamp'; ts.textContent = fmtTime();

  bubble.appendChild(content);
  bubble.appendChild(ts);
  wrapper.appendChild(bubble);
  chatBox.appendChild(wrapper);
  chatBox.scrollTop = chatBox.scrollHeight;
  return bubble;
}

// Append or stream agent text into a single bubble. If a streaming bubble exists,
// append to it; otherwise create a new one and mark it as streaming.
function appendAgentChunk(text){
  const aiBubbles = chatBox.querySelectorAll('.bubble.ai');
  let last = aiBubbles.length ? aiBubbles[aiBubbles.length-1] : null;
  if(last && last.getAttribute('data-streaming') === '1'){
    const content = last.querySelector('.bubble-text');
    // append with two newlines to clearly separate paragraphs between chunks
    if(content.textContent && !content.textContent.endsWith('\n\n')){
      // if it ends with a single newline, add one more; otherwise add two
      if(content.textContent.endsWith('\n')) content.textContent += '\n';
      else content.textContent += '\n\n';
    }
    content.textContent += text;
    chatBox.scrollTop = chatBox.scrollHeight;
    return last;
  }
  // create new streaming bubble
  const bub = appendBubble(text, 'ai');
  bub.setAttribute('data-streaming', '1');
  return bub;
}

async function uploadFile(file){
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/upload', { method: 'POST', body: fd });
  return res.json();
}

async function uploadResumeFile(file){
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/upload_resume', { method: 'POST', body: fd });
  return res.json();
}

sendBtn.onclick = async () => {
  if (streaming) return; // prevent double sends
  const text = messageInput.value.trim();

  let file_paths = [];
  if (currentUpload) {
    file_paths.push(currentUpload.path);
  } else if (fileInput.files && fileInput.files[0]){
    // fallback: upload now
    appendBubble('Uploading file...', 'me');
    const r = await uploadFile(fileInput.files[0]);
    if(r.path){
      file_paths.push(r.path);
      // show in composer uploaded list
      const li = document.createElement('div'); li.className = 'file-chip'; li.textContent = r.filename || r.path; 
      const rem = document.createElement('span'); rem.className='remove'; rem.textContent='✕'; rem.title='Remove'; rem.onclick = ()=>{ li.remove(); currentUpload=null; };
      li.appendChild(rem);
      if(composerUploadedList) composerUploadedList.appendChild(li);
    } else {
      appendBubble('Upload error: ' + JSON.stringify(r), 'me');
    }
  }

  if(!text && file_paths.length===0){
    return;
  }

  appendBubble(text || '[file]', 'me');
  messageInput.value = '';
  // disable send while streaming
  streaming = true;
  sendBtn.disabled = true;

  // Start streaming response from server
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text, file_paths: file_paths })
  });

  if (!resp.body) {
    appendBubble('No streaming body in response', 'ai');
    streaming = false; sendBtn.disabled = false;
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let done = false;
  let buffer = '';
  // show typing indicator
  const typing = document.createElement('div'); typing.id = 'typing'; typing.className='bubble ai'; typing.textContent = '…'; chatBox.appendChild(typing);
  while(!done){
    const {value, done: d} = await reader.read();
    done = d;
    if(value){
      buffer += decoder.decode(value, {stream: true});
      const parts = buffer.split('\n\n');
      for(let i=0;i<parts.length-1;i++){
        const chunk = parts[i];
        const m = chunk.match(/^data:\s*(.*)$/s);
        if(m){
          try{
            const obj = JSON.parse(m[1]);
            if(obj.type === 'agent_message'){
              if(document.getElementById('typing')) document.getElementById('typing').remove();
              appendAgentChunk(obj.text);
            } else if(obj.type === 'error'){
              if(document.getElementById('typing')) document.getElementById('typing').remove();
              appendBubble('Agent error: ' + obj.text, 'ai');
            }
          }catch(e){
            if(document.getElementById('typing')) document.getElementById('typing').remove();
            appendBubble('Agent: ' + m[1], 'ai');
          }
        }
      }
      buffer = parts[parts.length-1];
    }
  }
  if(document.getElementById('typing')) document.getElementById('typing').remove();
  // Instead of a separate bubble, attach a small italic completion note inside
  // the last AI bubble if present. Otherwise fall back to a meta bubble.
  const aiBubbles = chatBox.querySelectorAll('.bubble.ai');
  const lastAi = aiBubbles.length ? aiBubbles[aiBubbles.length-1] : null;
  if(lastAi){
    // remove streaming mark and append inline meta note
    lastAi.removeAttribute('data-streaming');
    const note = document.createElement('div'); note.className = 'inline-meta';
    note.textContent = '--- Response complete ---';
    // insert before timestamp
    const ts = lastAi.querySelector('.timestamp');
    lastAi.insertBefore(note, ts);
    chatBox.scrollTop = chatBox.scrollHeight;
  } else {
    appendBubble('--- Response complete ---', 'meta');
  }
  streaming = false; sendBtn.disabled = false;
};

clearBtn.onclick = async () => {
  if(!confirm('Are you sure you want to clear chat history? This cannot be undone.')) return;
  const res = await fetch('/api/clear_chat', { method: 'POST' });
  const j = await res.json();
  appendBubble('Clear chat: ' + JSON.stringify(j), 'meta');
};

if(clearKbBtn){
  clearKbBtn.onclick = async () => {
    if(!confirm('Are you sure you want to clear the knowledge DB and remove resumes? This cannot be undone.')) return;
    const res = await fetch('/api/clear_knowledge', { method: 'POST' });
    const j = await res.json();
    appendBubble('Clear knowledge: ' + JSON.stringify(j), 'meta');
  };
}

// Sidebar dropzone removed; textarea/composer handles drag & drop now.

// file input change handler for browse
fileInput.addEventListener('change', async (e)=>{
  const f = e.target.files[0];
  if(!f) return;
  const res = await uploadFile(f);
  if(res.path){
    currentUpload = res;
    const chip = document.createElement('div'); chip.className='file-chip';
    if(f.type.startsWith('image/')){
      const img = document.createElement('img'); img.src = URL.createObjectURL(f); chip.appendChild(img);
    }
    const span = document.createElement('span'); span.textContent = res.filename || res.path; chip.appendChild(span);
    const rem = document.createElement('span'); rem.className='remove'; rem.textContent='✕'; rem.title='Remove'; rem.onclick = ()=>{ chip.remove(); currentUpload=null; };
    chip.appendChild(rem);
    if(composerUploadedList) composerUploadedList.appendChild(chip);
  } else {
    appendBubble('Upload error: ' + JSON.stringify(res), 'ai');
  }
});

// Attach button opens file picker
if(attachBtn){
  attachBtn.addEventListener('click', (e)=>{ e.preventDefault(); fileInput.click(); });
}

// Sidebar resume upload button
if(uploadResumeBtn && resumeFileInput){
  uploadResumeBtn.addEventListener('click', (e)=>{ e.preventDefault(); resumeFileInput.click(); });

  resumeFileInput.addEventListener('change', async (e)=>{
    const f = e.target.files[0];
    if(!f) return;
    appendBubble('Uploading resume...', 'meta');
    const r = await uploadResumeFile(f);
    if(r.path){
      appendBubble('Resume uploaded: ' + r.path, 'meta');
    } else {
      appendBubble('Resume upload error: ' + JSON.stringify(r), 'meta');
    }
  });
}

// Allow drag & drop directly onto the message input
if(messageInput){
  messageInput.addEventListener('dragover', (e)=>{ e.preventDefault(); messageInput.classList.add('drop-over'); });
  messageInput.addEventListener('dragleave', (e)=>{ e.preventDefault(); messageInput.classList.remove('drop-over'); });
  messageInput.addEventListener('drop', async (e)=>{
    e.preventDefault(); messageInput.classList.remove('drop-over');
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if(!f) return;
    const res = await uploadFile(f);
    if(res.path){
      currentUpload = res;
      const chip = document.createElement('div'); chip.className='file-chip';
      if(f.type.startsWith('image/')){
        const img = document.createElement('img'); img.src = URL.createObjectURL(f); chip.appendChild(img);
      }
      const span = document.createElement('span'); span.textContent = res.filename || res.path; chip.appendChild(span);
      const rem = document.createElement('span'); rem.className='remove'; rem.textContent='✕'; rem.title='Remove'; rem.onclick = ()=>{ chip.remove(); currentUpload=null; };
      chip.appendChild(rem);
      if(composerUploadedList) composerUploadedList.appendChild(chip);
    } else {
      appendBubble('Upload error: ' + JSON.stringify(res), 'ai');
    }
  });
}

// Send on Enter (without shift)
messageInput.addEventListener('keydown', (e)=>{
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault(); sendBtn.click();
  }
});
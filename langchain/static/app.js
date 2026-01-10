// Client-side JS for both index and chat pages

// Utility: speak text using browser SpeechSynthesis
function speakText(text, onend=null) {
  const synth = window.speechSynthesis;
  synth.cancel(); // stop any existing before starting new
  if (!text || !synth) return;
  const ut = new SpeechSynthesisUtterance(text);
  // optionally choose a voice
  // ut.voice = speechSynthesis.getVoices().find(v => v.lang.startsWith('en')) || null;
  ut.rate = 1;
  ut.pitch = 1;
  ut.onend = () => { if (onend) onend(); };
  synth.speak(ut);
  return ut;
}

// === INDEX page doesn't need special JS beyond maybe smooth scroll ===
document.addEventListener("DOMContentLoaded", function(){
  // smooth scroll for Start Now CTA
  document.querySelectorAll('a[href^="#"]').forEach(a=>{
    a.addEventListener('click', e=>{
      e.preventDefault();
      const t = document.querySelector(a.getAttribute('href'));
      if(t) t.scrollIntoView({behavior:'smooth'});
    });
  });

  // if on chat page (ACTIVE_DOC variable set), wire chat behavior
  if (typeof ACTIVE_DOC !== 'undefined' && ACTIVE_DOC) {
    initChatPage(ACTIVE_DOC);
  }
});

// === Chat page functionality ===
function initChatPage(filename) {
  // Read controls
  let synth = window.speechSynthesis;
  let currentUtterance = null;
  const readPlay = document.getElementById('readPlay');
  const readPause = document.getElementById('readPause');
  const readResume = document.getElementById('readResume');
  const readStop = document.getElementById('readStop');
  const historyDiv = document.getElementById('history');

  let docTextCache = ""; // full doc text
  let chunkIndex = 0;
  let chunks = [];
  const chunkSize = 800; // characters per chunk to speak

  // fetch document text when Play pressed (or prefetch)
  async function fetchDocText(){
    if(docTextCache) return docTextCache;
    const resp = await fetch(`/api/read?filename=${encodeURIComponent(filename)}`);
    if(!resp.ok){
      const data = await resp.json().catch(()=>({error:'unknown'}));
      alert("Error reading document: " + (data.error || resp.statusText));
      return "";
    }
    const data = await resp.json();
    docTextCache = data.text || "";
    // split into chunks (avoid too large utterances)
    chunks = [];
    for(let i=0;i<docTextCache.length;i+=chunkSize){
      chunks.push(docTextCache.slice(i,i+chunkSize));
    }
    chunkIndex = 0;
    return docTextCache;
  }

  function playNextChunk() {
    if(chunkIndex >= chunks.length) {
      currentUtterance = null;
      return;
    }
    const txt = chunks[chunkIndex++];
    currentUtterance = new SpeechSynthesisUtterance(txt);
    currentUtterance.rate = 1;
    currentUtterance.onend = () => {
      // auto-play next chunk if not paused
      if (!speechSynthesis.speaking && chunkIndex < chunks.length) {
        // small delay to allow state to settle
        setTimeout(()=>{
          playNextChunk();
        }, 60);
      } else {
        currentUtterance = null;
      }
    };
    speechSynthesis.speak(currentUtterance);
  }

  readPlay && readPlay.addEventListener('click', async ()=>{
    if(speechSynthesis.speaking) {
      // already speaking
      return;
    }
    await fetchDocText();
    if(chunks.length === 0){
      alert("Document is empty or couldn't be read.");
      return;
    }
    // If paused, resume; else start from chunkIndex
    if(speechSynthesis.paused) {
      speechSynthesis.resume();
    } else {
      // start from beginning if at end
      if(chunkIndex >= chunks.length) chunkIndex = 0;
      playNextChunk();
    }
  });

  readPause && readPause.addEventListener('click', ()=>{
    if(speechSynthesis.speaking) speechSynthesis.pause();
  });

  readResume && readResume.addEventListener('click', ()=>{
    if(speechSynthesis.paused) speechSynthesis.resume();
  });

  readStop && readStop.addEventListener('click', ()=>{
    speechSynthesis.cancel();
    chunkIndex = 0;
    currentUtterance = null;
  });

  // Ask question
  const askBtn = document.getElementById('askBtn');
  const questionInput = document.getElementById('question');

  askBtn && askBtn.addEventListener('click', async ()=>{
    const q = questionInput.value.trim();
    if(!q) return;
    askBtn.disabled = true;
    askBtn.innerText = 'Thinking...';
    try{
      const resp = await fetch('/api/ask', {
        method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({filename, question: q})
      });
      const data = await resp.json();
      if(!resp.ok){
        alert(data.error || 'Error from server');
        return;
      }
      const answer = data.answer || "(no answer)";
      appendQA(q, answer);
      questionInput.value = '';
      // auto-play answer TTS
      speakText(answer);
    }catch(e){
      alert("Error asking question: "+e);
    }finally{
      askBtn.disabled = false;
      askBtn.innerText = 'Ask';
    }
  });

  // add play button to existing answers and wire them
  function addPlayButtonsToHistory(){
    document.querySelectorAll('.play-answer').forEach(btn=>{
      if(btn._wired) return;
      btn._wired = true;
      btn.addEventListener('click', (ev)=>{
        // find nearest .answer-text
        const item = btn.closest('.a');
        const pre = item.querySelector('.answer-text');
        if(pre){
          speakText(pre.innerText);
        }
      });
    });
  }
  addPlayButtonsToHistory();

  function appendQA(q, a){
    const wrapper = document.createElement('div');
    wrapper.className = 'pair';
    wrapper.innerHTML = `<div class="q">Q: ${escapeHtml(q)}</div>
                         <div class="a">A: <pre class="answer-text">${escapeHtml(a)}</pre>
                         <button class="btn play-answer">🔊 Play</button>
                         </div>`;
    historyDiv.appendChild(wrapper);
    // scroll to bottom
    historyDiv.scrollTop = historyDiv.scrollHeight;
    addPlayButtonsToHistory();
  }

  function escapeHtml(txt){
    return (txt||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // If auto-fetch doc text on load, uncomment:
  // fetchDocText();
}

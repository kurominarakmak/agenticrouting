/* Controlled components: dynamic content becomes text nodes, never executable HTML. */
window.UI={
 node(tag,text,parent,cls){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;if(parent)parent.append(n);return n},
 badge(text,parent,color=''){return UI.node('span',text,parent,'badge '+color)},
 button(text,fn,parent,cls='button'){const b=UI.node('button',text,parent,cls);b.type='button';b.onclick=fn;return b},
 status(status,parent){const color=['done','completed'].includes(status)?'green':['running','planning','verifying'].includes(status)?'blue':['blocked','paused','awaiting_approval','review','waiting_dependency'].includes(status)?'amber':['failed','cancelled'].includes(status)?'red':'';return UI.badge(status.replaceAll('_',' '),parent,color)},
 inline(text,parent){
  const pattern=/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;let at=0;
  for(const match of text.matchAll(pattern)){parent.append(document.createTextNode(text.slice(at,match.index)));const token=match[0];if(token.startsWith('`'))UI.node('code',token.slice(1,-1),parent);else if(token.startsWith('**'))UI.node('strong',token.slice(2,-2),parent);else{const m=token.match(/^\[([^\]]+)\]\((.+)\)$/);const a=UI.node('a',m[1],parent);a.href=m[2];a.target='_blank';a.rel='noopener noreferrer'}at=match.index+token.length}
  parent.append(document.createTextNode(text.slice(at)))
 },
 markdown(text,parent){
  const lines=String(text||'').split('\n');let index=0;
  while(index<lines.length){const line=lines[index];
   if(line.startsWith('```')){const block=[];index++;while(index<lines.length&&!lines[index].startsWith('```'))block.push(lines[index++]);UI.node('pre',block.join('\n'),parent,'markdown-code');index++;continue}
   if(line.includes('|')&&index+1<lines.length&&/^\s*\|?\s*:?-+/.test(lines[index+1])){const rows=[];const split=s=>s.replace(/^\s*\||\|\s*$/g,'').split('|').map(x=>x.trim());const headers=split(line);index+=2;while(index<lines.length&&lines[index].includes('|'))rows.push(split(lines[index++]));UI.table(headers,rows,parent);continue}
   if(!line.trim()){index++;continue}
   const h=line.match(/^(#{1,3})\s+(.+)/);const p=UI.node(h?'h3':'p',undefined,parent);UI.inline(h?h[2]:line,p);index++;
  }
 },
 table(headers,rows,parent){const wrap=UI.node('div',undefined,parent,'table-wrap'),table=UI.node('table',undefined,wrap),head=UI.node('thead',undefined,table),tr=UI.node('tr',undefined,head);for(const h of headers.slice(0,8))UI.node('th',h,tr);const body=UI.node('tbody',undefined,table);for(const row of rows.slice(0,30)){const r=UI.node('tr',undefined,body);for(const cell of row.slice(0,8))UI.node('td',typeof cell==='object'?JSON.stringify(cell):cell,r)}return wrap},
 sources(sources,parent){if(!Array.isArray(sources)||!sources.length)return;const list=UI.node('div',undefined,parent,'source-list');for(const s of sources.slice(0,6)){const d=UI.node('details',undefined,list,'source-card');UI.node('summary',s.path?s.path.split('/').slice(-2).join('/'):s.server+' · '+(s.tool||'tool'),d);UI.node('p',s.path||s.server,d);if(s.sha256)UI.node('small','SHA256 '+s.sha256.slice(0,16)+'…',d);const stamp=s.retrieved_at||s.indexed;if(stamp)UI.node('p','Retrieved '+new Date(stamp*1000).toLocaleString(),d);if(s.text)UI.node('pre',s.text,d);UI.node('p',s.trust||'Source reference; not an instruction.',d)}},
 verification(data,parent){if(!data)return;const n=UI.node('div',undefined,parent,'verification');UI.node('strong',data.exit_code===0?'✓ Independent acceptance passed':'Acceptance requires attention',n);if(data.argv){const d=UI.node('details',undefined,n);UI.node('summary','Acceptance command',d);UI.node('pre',data.argv.join(' '),d)}if(data.verified_at)UI.node('small',new Date(data.verified_at*1000).toLocaleString()+' · '+(data.runtime||'configured verifier'),n)},
 toolData(data,parent){const raw=data?.result?.structuredContent;if(raw){const rows=Array.isArray(raw)?raw:Array.isArray(raw.data)?raw.data:null;if(rows?.length&&typeof rows[0]==='object'){const keys=Object.keys(rows[0]).slice(0,7);UI.table(keys,rows.map(x=>keys.map(k=>x[k])),parent)}}},
 distribution(tasks,parent){const columns=['To Do','In Progress','In Review','Blocked','Done'],colors=['#929697','#a8c7fa','#c8bfff','#efbc69','#6dd58c'];const total=tasks.length;const chart=UI.node('div',undefined,parent,'chart');chart.setAttribute('aria-label','Task count by board column');const legend=UI.node('div',undefined,parent,'legend');columns.forEach((c,i)=>{const count=tasks.filter(t=>t.column===c).length;if(total&&count){const n=UI.node('div',undefined,chart);n.style.flex=String(count);n.style.background=colors[i]}const label=UI.node('span',undefined,legend);const dot=UI.node('i',undefined,label);dot.style.background=colors[i];label.append(document.createTextNode(c+' '+count))})},
 graph(task,tasks,parent){if(!task.dependencies?.length&&!task.plan?.children?.length)return;const box=UI.node('div',undefined,parent,'card');UI.node('small','DEPENDENCY HANDOFFS',box);for(const id of new Set([...(task.dependencies||[]),...(task.plan?.children||[])])){const t=tasks.find(t=>t.id===id);const line=UI.node('p',undefined,box);UI.status(t?.status||'unknown',line);line.append(document.createTextNode(' '+(t?.title||id)+' → '+task.id))}}
};

(function() {
  'use strict';
  const M=ValuationModel, model=JSON.parse(document.getElementById('model-data').textContent);
  const $=id=>document.getElementById(id), fmt=(v,d=2)=>Number.isFinite(v)?v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const signed=v=>Number.isFinite(v)?`${v>=0?'+':''}${fmt(v)}`:'—';
  const C={ink:'#1b303b', muted:'#6b7a83', grid:'#e8eeee', teal:'#14796e', red:'#b55d50', blue:'#305e82', gold:'#b08b54'};
  const scale=[[0,'#ceaaa1'],[.5,'#f6f7f3'],[1,'#76a69b']];
  const initial=M.evaluate(model,'gordon',model.base.rate,model.base.gordon);
  const state={method:'gordon',rate:model.base.rate,terminal:model.base.gordon,
    target:model.market ?? initial?.price ?? 0,pins:[],nextPin:1};
  let rateSolutions=[],terminalSolution=null,dirty=false,running=false,initialized=false;
  const grids={},defaultBounds=JSON.parse(JSON.stringify(model.bounds));
  const invalidInputs=new Set();
  const terminalLabel=()=>state.method==='gordon'?'Terminal growth (%)':'Exit EV/EBITDA (×)';
  const terminalScale=()=>state.method==='gordon'?100:1;
  const within=(v,b)=>Number.isFinite(v)&&v>=b[0]&&v<=b[1];
  const baseResult=method=>M.evaluate(model,method,model.base.rate,model.base[method]);
  const camera={eye:{x:1.5,y:-1.6,z:1.05},projection:{type:'orthographic'}};
  const config={displaylogo:false,responsive:true,scrollZoom:false,modeBarButtonsToRemove:['select2d','lasso2d'],toImageButtonOptions:{format:'png',scale:3}};
  function layout(extra={}) {
    return {paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{family:'Arial, sans-serif',size:12,color:C.muted},
      margin:{l:50,r:16,t:14,b:45},showlegend:false,hovermode:'closest',uirevision:state.method,
      hoverlabel:{bgcolor:C.ink,font:{color:'#fff',size:12}},
      xaxis:{showgrid:false,zeroline:false,automargin:true},
      yaxis:{gridcolor:C.grid,zeroline:false,automargin:true,nticks:5},...extra};
  }
  function getGrid() {
    if (grids[state.method]) return grids[state.method];
    const xs=M.linspace(...model.bounds.rate,51,model.base.rate);
    const ys=M.linspace(...model.bounds[state.method],51,model.base[state.method]);
    const z=ys.map(y=>xs.map(x=>M.evaluate(model,state.method,x,y)?.price ?? null));
    const finite=z.flat().filter(Number.isFinite);
    const grid={xs,ys,z,low:finite.length?Math.min(...finite):0,high:finite.length?Math.max(...finite):1};
    grids[state.method]=grid;return grid;
  }
  function syncControls() {
    invalidInputs.clear();
    for (const id of ['rate','terminal','target','rate-range','terminal-range']) $(id).setCustomValidity('');
    const rb=model.bounds.rate,tb=model.bounds[state.method],factor=terminalScale();
    for(const id of ['rate','rate-range']) {$(id).min=rb[0]*100;$(id).max=rb[1]*100;$(id).value=Number((state.rate*100).toFixed(6));}
    for(const id of ['terminal','terminal-range']) {$(id).min=tb[0]*factor;$(id).max=tb[1]*factor;$(id).value=Number((state.terminal*factor).toFixed(6));}
    $('rate-range').step='any';$('terminal-range').step='any';
    $('rate-min').textContent=fmt(rb[0]*100)+'%';$('rate-max').textContent=fmt(rb[1]*100)+'%';
    $('terminal-min').textContent=fmt(tb[0]*factor)+(factor===100?'%':'×');$('terminal-max').textContent=fmt(tb[1]*factor)+(factor===100?'%':'×');
    $('terminal-label').textContent=terminalLabel();$('terminal-range').setAttribute('aria-label',terminalLabel());
    $('target').value=Number(state.target.toFixed(6));
    $('gordon').setAttribute('aria-pressed',String(state.method==='gordon'));$('exit').setAttribute('aria-pressed',String(state.method==='exit'));
    $('market').disabled=model.market===null;
  }
  function updateAnswers(value) {
    $('price').textContent=fmt(value?.price);const base=baseResult(state.method);
    $('base-delta').textContent=`${model.currency} · ${value&&base?signed(value.price-base.price)+' versus base':'undefined at these inputs'}`;
    const gap=value?value.price-state.target:null;
    $('upside').textContent=signed(gap);$('upside').className=gap===null?'':gap>=0?'positive':'negative';
    $('target-caption').textContent=`Target ${fmt(state.target)}${gap!==null&&state.target>0?' · '+signed(gap/state.target*100)+'%':''}`;
    $('explicit').textContent=fmt(value?.explicitPerShare);
    $('terminal-share').textContent=value&&Number.isFinite(value.terminalShare)?fmt(value.terminalShare*100,1)+'%':'—';
    $('terminal-caption').textContent=value?`Terminal PV / share ${fmt(value.terminalPerShare)}`:'No valid terminal value';
    $('pin').disabled=!value||state.pins.length>=6||invalidInputs.size>0;
    $('status').textContent=!value?'Undefined: Gordon growth must be below WACC. Adjust either input.':state.pins.length>=6?'Six scenarios pinned. Remove one to add another.':'';
    rateSolutions=M.roots(rate=>M.evaluate(model,state.method,rate,state.terminal)?.price,state.target,model.bounds.rate);
    rateSolutions.sort((a,b)=>Math.abs(a-state.rate)-Math.abs(b-state.rate));
    const implied=M.targetTerminal(model,state.method,state.rate,state.target);
    terminalSolution=within(implied,model.bounds[state.method])?implied:null;
    $('solve-rate').textContent=rateSolutions.length?fmt(rateSolutions[0]*100,3)+'%':'No crossing found';
    $('solve-rate-note').textContent=rateSolutions.length>1?'Multiple solutions; nearest shown':`Holding terminal input at ${fmt(state.terminal*terminalScale())}${terminalScale()===100?'%':'×'}`;
    $('apply-rate').disabled=!rateSolutions.length;
    $('solve-terminal-label').textContent=state.method==='gordon'?'Implied growth':'Implied exit multiple';
    $('solve-terminal').textContent=terminalSolution!==null?fmt(terminalSolution*terminalScale(),3)+(terminalScale()===100?'%':'×'):(implied===null?'Not determined':'Not in range');
    $('solve-terminal-note').textContent=implied===null?'No unique valid solution at the selected WACC.':Number.isFinite(implied)&&terminalSolution===null?`Requires ${fmt(implied*terminalScale(),3)}${terminalScale()===100?'%':'×'} outside the displayed range`:`Holding WACC at ${fmt(state.rate*100)}%`;
    $('apply-terminal').disabled=terminalSolution===null;
    const rStep=.0025,tStep=state.method==='gordon'?.0025:.5;
    const rTrial=M.evaluate(model,state.method,state.rate+rStep,state.terminal);
    const tTrial=M.evaluate(model,state.method,state.rate,state.terminal+tStep);
    $('insight').textContent=value?`At this selection, +25 bp of WACC changes value by ${rTrial?signed(rTrial.price-value.price):'an undefined amount'} per share. ${state.method==='gordon'?'+25 bp of terminal growth':'+0.5× on the exit multiple'} changes it by ${tTrial?signed(tTrial.price-value.price):'an undefined amount'}. These are recalculated scenarios, not linear estimates.`:'This selection has no finite Gordon valuation. The blank region is a model boundary, not a zero valuation.';
    $('rate-slice-caption').textContent=`Holding ${state.method==='gordon'?'growth':'exit multiple'} at ${fmt(state.terminal*terminalScale())}${terminalScale()===100?'%':'×'} · red rule = target`;
    $('terminal-slice-title').textContent=state.method==='gordon'?'Growth sensitivity':'Exit-multiple sensitivity';
    $('terminal-slice-caption').textContent=`Holding WACC at ${fmt(state.rate*100)}% · red rule = target`;
    $('decomposition').textContent=value?`Per-share bridge: forecast PV ${fmt(value.explicitPerShare)} + terminal PV ${fmt(value.terminalPerShare)} − net debt ${fmt(value.debtPerShare)} = equity value ${fmt(value.price)}. Net cash appears as negative net debt.`:'The valuation bridge is unavailable for an undefined scenario.';
  }
  function marker3(x,y,z,name,color,symbol='circle') {
    return {type:'scatter3d',x,y,z,name,mode:'markers',marker:{color,size:5,symbol,line:{color:'#fff',width:1}},
      hovertemplate:'%{fullData.name}<br>WACC %{x:.3f}%<br>Terminal %{y:.3f}<br>Value %{z:,.2f}<extra></extra>'};
  }
  function sliceFigure(xs,values,input,label,value,range) {
    const traces=[{type:'scatter',x:xs,y:values,mode:'lines',line:{color:C.teal,width:2.5},connectgaps:false,
      hovertemplate:label+': %{x:.3f}<br>Value %{y:,.2f}<extra></extra>'}];
    if(value)traces.push({type:'scatter',x:[input],y:[value.price],mode:'markers',marker:{color:C.teal,size:8},hoverinfo:'skip'});
    const separation = value ? Math.abs(value.price-state.target)/(range[1]-range[0]) : 1;
    const annotations=[{xref:'paper',x:1,y:state.target,xanchor:'right',yanchor:'bottom',
      yshift:4,showarrow:false,text:'Target '+fmt(state.target),font:{color:C.red,size:10},bgcolor:'rgba(255,255,255,.88)'}];
    if(value)annotations.push({x:input,y:value.price,text:fmt(value.price),showarrow:true,arrowhead:0,
      arrowwidth:1,arrowcolor:C.teal,ax:input>(xs[0]+xs.at(-1))/2?-25:25,
      ay:separation<.15?28:-25,font:{color:C.teal,size:11},bgcolor:'rgba(255,255,255,.94)',borderpad:3});
    return {traces,layout:layout({annotations,xaxis:{title:{text:label,font:{size:10}},showgrid:false,zeroline:false},
      yaxis:{title:{text:'Value / share',font:{size:10}},gridcolor:C.grid,zeroline:false,range,nticks:5,autorange:false},
      shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:state.target,y1:state.target,line:{color:C.red,width:1.2,dash:'dash'}}]})};
  }
  async function render() {
    const value=M.evaluate(model,state.method,state.rate,state.terminal),g=getGrid(),factor=terminalScale();
    updateAnswers(value);
    const x=g.xs.map(v=>v*100),y=g.ys.map(v=>v*factor),mx=state.rate*100,my=state.terminal*factor;
    const sx=g.xs.map(v=>M.evaluate(model,state.method,v,state.terminal)?.price??null);
    const sy=g.ys.map(v=>M.evaluate(model,state.method,state.rate,v)?.price??null);
    const frontierX=[],frontierY=[],frontierZ=[];
    for(const rate of g.xs) {
      const terminal=M.targetTerminal(model,state.method,rate,state.target),valid=within(terminal,model.bounds[state.method]);
      frontierX.push(valid?rate*100:null);frontierY.push(valid?terminal*factor:null);frontierZ.push(valid?state.target:null);
    }
    const crossing=frontierX.some(Number.isFinite);
    $('frontier-note').textContent=crossing?'The red frontier shows combinations that exactly reach the target. Teal regions exceed it; rust regions fall short.':'No target-price frontier appears within the displayed assumptions. Change the target or use the inverse answers to inspect the gap.';
    const delta=g.z.map(row=>row.map(v=>v===null?null:v-state.target));
    const limit=Math.max(Math.abs(g.low-state.target),Math.abs(g.high-state.target),.01);
    const surface=[{type:'surface',x,y,z:g.z,surfacecolor:delta,colorscale:scale,cmin:-limit,cmax:limit,showscale:false,
      opacity:1,connectgaps:false,lighting:{ambient:.7,diffuse:.8,roughness:.85,specular:.12},
      lightposition:{x:-100,y:-120,z:200},
      hovertemplate:'WACC %{x:.3f}%<br>'+terminalLabel()+': %{y:.3f}<br>Value %{z:,.2f}<extra></extra>'},
      {type:'scatter3d',x,y:Array(x.length).fill(my),z:sx,mode:'lines',line:{color:C.blue,width:3},hoverinfo:'skip'},
      {type:'scatter3d',x:Array(y.length).fill(mx),y,z:sy,mode:'lines',line:{color:C.gold,width:3},hoverinfo:'skip'},
      {type:'scatter3d',x:frontierX,y:frontierY,z:frontierZ,mode:'lines',connectgaps:false,line:{color:C.red,width:6},name:'Target frontier',hoverinfo:'skip'}];
    const base=baseResult(state.method);
    if(base)surface.push(marker3([model.base.rate*100],[model.base[state.method]*factor],[base.price],'Entered base',C.ink,'diamond'));
    if(value)surface.push(marker3([mx],[my],[value.price],'Selected scenario',C.teal));
    const pins=state.pins.filter(p=>p.method===state.method);
    if(pins.length)surface.push({...marker3(pins.map(p=>p.rate*100),pins.map(p=>p.terminal*factor),pins.map(p=>p.result.price),'Pinned scenarios',C.gold),text:pins.map(p=>p.name),hovertemplate:'%{text}<br>Value %{z:,.2f}<extra></extra>'});
    const axis=title=>({title:{text:title,font:{size:10}},tickfont:{size:9},nticks:4,gridcolor:'#e8eded',backgroundcolor:'#fff',showbackground:false,zeroline:false});
    const span=Math.max(g.high-g.low,1);
    const scene={xaxis:axis('WACC (%)'),yaxis:axis(terminalLabel()),zaxis:{...axis('Value / share'),range:[g.low-.08*span,g.high+.08*span]},
      camera,aspectmode:'manual',aspectratio:{x:1.15,y:1,z:.8}};
    const map=[{type:'contour',x,y,z:g.z,customdata:delta,colorscale:scale,zmin:state.target-limit,zmax:state.target+limit,
      connectgaps:false,hoverongaps:false,ncontours:9,line:{width:.6,color:'rgba(70,90,96,.35)'},
      contours:{showlabels:true,labelfont:{size:10,color:C.ink}},showscale:true,
      colorbar:{title:{text:'Value / share',side:'right',font:{size:10}},thickness:8,len:.8,outlinewidth:0,tickfont:{size:9},nticks:4,x:1.02},
      hovertemplate:'WACC %{x:.3f}%<br>'+terminalLabel()+': %{y:.3f}<br>Value %{z:,.2f}<br>Target gap %{customdata:+,.2f}<extra></extra>'},
      {type:'scatter',x:frontierX,y:frontierY,mode:'lines',connectgaps:false,line:{color:C.red,width:2.5},hoverinfo:'skip'},
      {type:'scatter',x:[mx],y:[my],mode:'markers',marker:{color:C.teal,size:11,line:{color:'white',width:2}},name:'Selection',hoverinfo:'skip'}];
    if(base)map.push({type:'scatter',x:[model.base.rate*100],y:[model.base[state.method]*factor],mode:'markers',marker:{color:C.ink,symbol:'diamond-open',size:10,line:{width:2}},hoverinfo:'skip'});
    // A shared scale prevents the two inputs from appearing equally sensitive by autoscaling.
    const comparable=[...sx,...sy,state.target,value?.price].filter(Number.isFinite);
    const minimum=Math.min(...comparable),maximum=Math.max(...comparable);
    const pad=Math.max(maximum-minimum,Math.abs(maximum)*.01,1)*.13;
    const range=[minimum-pad,maximum+pad];
    const xs=sliceFigure(x,sx,mx,'WACC (%)',value,range),ys=sliceFigure(y,sy,my,terminalLabel(),value,range);
    const jobs=[
      Plotly.react($('surface'),surface,layout({margin:{l:0,r:0,t:5,b:0},scene}),config),
      Plotly.react($('map'),map,layout({margin:{l:55,r:55,t:14,b:45},xaxis:{title:{text:'WACC (%)',font:{size:10}},range:[x[0],x.at(-1)],zeroline:false},
        yaxis:{title:{text:terminalLabel(),font:{size:10}},range:[y[0],y.at(-1)],zeroline:false},
        shapes:[{type:'line',x0:mx,x1:mx,y0:y[0],y1:y.at(-1),line:{color:C.teal,width:1,dash:'dot'}},
          {type:'line',x0:x[0],x1:x.at(-1),y0:my,y1:my,line:{color:C.teal,width:1,dash:'dot'}}]}),config),
      Plotly.react($('rate-slice'),xs.traces,xs.layout,config),Plotly.react($('terminal-slice'),ys.traces,ys.layout,config)];
    const results=await Promise.allSettled(jobs);
    if(invalidInputs.size){$('pin').disabled=true;$('apply-rate').disabled=true;$('apply-terminal').disabled=true;$('status').textContent='Correct the highlighted input. Charts show the last valid selection.';}
    $('webgl-note').textContent=results[0].status==='rejected'?'3D rendering is unavailable. Use the target map and sensitivity charts; calculations remain available.':'';
    if(results.slice(1).some(r=>r.status==='rejected'))$('status').textContent='A chart could not render. The numerical results above remain available.';
    if(!initialized && typeof $('map').on==='function') {
      initialized=true;
      $('map').on('plotly_click',event=>{
        const p=event.points?.[0];if(!p)return;
        const rate=p.x/100,terminal=p.y/terminalScale();
        if(!within(rate,model.bounds.rate)||!within(terminal,model.bounds[state.method]))return;
        state.rate=rate;state.terminal=terminal;syncControls();schedule();
      });
      if(typeof $('surface').on==='function') $('surface').on('plotly_webglcontextlost',()=>{$('webgl-note').textContent='The 3D context was lost. The map and numerical controls remain usable.';});
    }
  }
  async function schedule() {
    dirty=true;if(running)return;running=true;
    try {while(dirty){dirty=false;await render();}}catch(error){$('status').textContent='Unable to update this view: '+error.message;}
    finally{running=false;}
  }
  function clearInvalid(ids) {for(const id of ids){invalidInputs.delete(id);$(id).setCustomValidity('');}}
  function invalidate(input,id,message) {
    invalidInputs.add(id);input.setCustomValidity(message);input.reportValidity();
    $('pin').disabled=true;$('apply-rate').disabled=true;$('apply-terminal').disabled=true;
    $('status').textContent='Correct the highlighted input. Charts show the last valid selection.';
  }
  function setNumeric(id,field,factor=1,bounds=null) {
    $(id).addEventListener('input',()=>{
      const input=$(id),v=input.value.trim()===''?NaN:Number(input.value)/factor;
      if(!Number.isFinite(v)||(bounds&&!within(v,bounds()))) {invalidate(input,id,'Enter a finite value within the displayed range.');return;}
      clearInvalid(field==='rate'?['rate','rate-range']:[id]);state[field]=v;
      if(id==='rate'||id==='rate-range'){$('rate').value=v*factor;$('rate-range').value=v*factor;}
      if(id==='terminal'||id==='terminal-range'){$('terminal').value=v*factor;$('terminal-range').value=v*factor;}
      schedule();
    });
  }
  function renderPins() {
    $('pins').replaceChildren();$('empty-pins').hidden=state.pins.length>0;$('scenarios').hidden=!state.pins.length;$('export').disabled=!state.pins.length;
    for(const p of state.pins) {
      const row=document.createElement('tr'),factor=p.method==='gordon'?100:1;
      const values=[p.name,fmt(p.rate*100)+'%',fmt(p.terminal*factor)+(factor===100?'% growth':'× exit'),fmt(p.result.price),fmt(p.target),signed(p.result.price-p.target),Number.isFinite(p.result.terminalShare)?fmt(p.result.terminalShare*100,1)+'%':'—'];
      for(const text of values){const td=document.createElement('td');td.textContent=text;row.append(td);}
      const actions=document.createElement('td');
      for(const [label,action] of [['Recall',()=>{state.method=p.method;setDomain(p.domain);state.rate=p.rate;state.terminal=p.terminal;state.target=p.target;bindTerminal();syncControls();schedule();}],['Remove',()=>{state.pins=state.pins.filter(v=>v!==p);renderPins();schedule();}]]){
        const b=document.createElement('button');b.textContent=label;b.className='secondary';b.setAttribute('aria-label',label+' '+p.name);b.addEventListener('click',action);actions.append(b);
      }
      row.append(actions);$('pins').append(row);
    }
  }
  function bindTerminal() {
    // Factor changes by method, so the two handlers read it at interaction time.
    for(const id of ['terminal','terminal-range'])$(id).oninput=()=>{
      const input=$(id),v=input.value.trim()===''?NaN:Number(input.value)/terminalScale();
      if(!within(v,model.bounds[state.method])){invalidate(input,id,'Enter a value within the displayed range.');return;}
      clearInvalid(['terminal','terminal-range']);state.terminal=v;$('terminal').value=v*terminalScale();$('terminal-range').value=v*terminalScale();schedule();
    };
  }
  for(const method of ['gordon','exit'])$(method).addEventListener('click',()=>{state.method=method;state.terminal=model.base[method];bindTerminal();syncControls();schedule();});
  setNumeric('rate','rate',100,()=>model.bounds.rate);setNumeric('rate-range','rate',100,()=>model.bounds.rate);setNumeric('target','target');bindTerminal();
  function setDomain(mode) {
    $('domain').value=mode;
    const multiplier=mode==='wide'?2:1;
    for(const key of ['rate','gordon','exit']) {
      const center=key==='rate'?model.base.rate:model.base[key];
      model.bounds[key]=defaultBounds[key].map(v=>center+(v-center)*multiplier);
    }
    model.bounds.rate[0]=Math.max(-.999,model.bounds.rate[0]);
    state.rate=Math.max(model.bounds.rate[0],Math.min(model.bounds.rate[1],state.rate));
    const bounds=model.bounds[state.method];state.terminal=Math.max(bounds[0],Math.min(bounds[1],state.terminal));
    delete grids.gordon;delete grids.exit;
  }
  $('domain').addEventListener('change',()=>{setDomain($('domain').value);syncControls();schedule();});
  $('reset').addEventListener('click',()=>{state.rate=model.base.rate;state.terminal=model.base[state.method];syncControls();schedule();});
  $('market').addEventListener('click',()=>{if(model.market!==null){state.target=model.market;syncControls();schedule();}});
  $('apply-rate').addEventListener('click',()=>{if(rateSolutions.length){state.rate=rateSolutions[0];syncControls();schedule();}});
  $('apply-terminal').addEventListener('click',()=>{if(terminalSolution!==null){state.terminal=terminalSolution;syncControls();schedule();}});
  $('camera').addEventListener('click',()=>Plotly.relayout($('surface'),{'scene.camera':camera}));
  $('pin').addEventListener('click',()=>{const item=M.scenario(model,state.method,state.rate,state.terminal,state.target);if(item.result&&state.pins.length<6){item.name='Scenario '+state.nextPin++;item.domain=$('domain').value||'focus';state.pins.push(item);renderPins();schedule();}});
  $('export').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([M.csv(state.pins)],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='valuation-scenarios.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  $('company').textContent=model.name;$('model-note').textContent=`${model.currency} / share · ${model.flows.length}-year forecast · ${model.midYear?'mid-year':'year-end'} discounting`;
  $('model-explanation').textContent=`Operating inputs in ${model.unit}; ${fmt(model.shares)} shares in the same unit scale. Net debt ${fmt(model.netDebt)}. Final-year EBITDA ${fmt(model.finalEbitda)}. ${model.midYear?'Mid-year':'Year-end'} convention applies to forecast and terminal discount factors.`;
  model.flows.forEach((flow,i)=>{const row=document.createElement('tr');for(const value of [model.years[i],fmt(flow)]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}$('flows').append(row);});
  syncControls();renderPins();schedule();
})();

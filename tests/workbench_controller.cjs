/* Exercise real controller logic with a minimal DOM and a recorded Plotly interface. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=JSON.parse(fs.readFileSync(0,'utf8'));
const M=require('../valuation/assets/dcf_model.js');
class Element {
 constructor(id){this.id=id;this.children=[];this.events={};this._value='';this.textContent='';this.disabled=false;this.attrs={};}
 set value(v){this._value=String(v)} get value(){return this._value}
 setAttribute(k,v){this.attrs[k]=v} addEventListener(k,fn){this.events[k]=fn} on(k,fn){this.events[k]=fn}
 append(...children){this.children.push(...children)} replaceChildren(){this.children=[]}
 setCustomValidity(v){this.validation=v} reportValidity(){} remove(){} click(){if(!this.disabled)this.events.click?.()}
 input(v){this.value=v;this.oninput?this.oninput():this.events.input?.()}
}
const elements={};const $=id=>elements[id]??=(new Element(id));
$('model-data').textContent=JSON.stringify(model);
const document={getElementById:$,createElement:tag=>new Element(tag),body:new Element('body')};
const charts={};let downloadCount=0;
const Plotly={react:(el,data,layout)=>{charts[el.id]={data,layout};return Promise.resolve();},relayout:()=>Promise.resolve()};
vm.runInNewContext(fs.readFileSync('valuation/assets/dcf_workbench.js','utf8'),{
 document,ValuationModel:M,Plotly,console,Blob,URL:{createObjectURL:()=>{downloadCount++;return'blob:test'},revokeObjectURL:()=>{}},setTimeout:fn=>fn()
});
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(setImmediate)};
const selected=()=>charts.surface.data.find(t=>t.name==='Selected scenario');
(async()=>{
 await settle();assert.equal(Object.keys(charts).length,4);
 assert.equal(selected().z[0],M.evaluate(model,'gordon',model.base.rate,model.base.gordon).price);
 $('map').events.plotly_click({points:[{x:9,y:3}]});await settle();
 assert.equal(selected().x[0],9);assert.equal(selected().y[0],3);
 const chosen=M.evaluate(model,'gordon',.09,.03).price;
 assert.equal(selected().z[0],chosen);assert.equal(charts['rate-slice'].data[1].y[0],chosen);
 assert.deepEqual(charts['rate-slice'].layout.yaxis.range,charts['terminal-slice'].layout.yaxis.range);
 assert.equal(charts['rate-slice'].layout.yaxis.autorange,false);
 assert.equal(charts['rate-slice'].layout.annotations[1].y,chosen);
 assert.equal(charts['map'].data[0].colorbar.title.text,'Value / share');
 assert.equal(charts['terminal-slice'].data[1].x[0],3);
 $('target').input(25);await settle();assert.equal(charts['rate-slice'].layout.shapes[0].y0,25);
 assert.equal($('apply-rate').disabled,false);$('apply-rate').click();await settle();
 assert.ok(Math.abs(selected().z[0]-25)<1e-5);
 $('pin').click();await settle();assert.equal($('pins').children.length,1);
 const savedRate=selected().x[0];
 $('exit').click();await settle();assert.equal($('exit').attrs['aria-pressed'],'true');
 assert.equal(selected().y[0],model.base.exit);
 const row=$('pins').children[0];row.children.at(-1).children[0].click();await settle();
 assert.equal($('gordon').attrs['aria-pressed'],'true');assert.equal(selected().x[0],savedRate);
 $('export').click();assert.equal(downloadCount,1);
 for(let i=0;i<7;i++){$('pin').click();await settle()}
 assert.equal($('pins').children.length,6);assert.equal($('pin').disabled,true);
 $('pins').children[0].children.at(-1).children[1].click();await settle();assert.equal($('pins').children.length,5);
 $('rate').input('');assert.ok($('rate').validation);await settle();assert.equal(selected().x[0],savedRate);
 // Invalid Gordon selections remain undefined; stress-range pins restore their domain.
 $('rate-range').input(model.base.rate*100);await settle();
 assert.equal($('rate').validation,'');
 $('domain').value='wide';$('domain').events.change();await settle();
 $('rate').input(5);$('terminal').input(6);await settle();
 assert.equal(selected(),undefined);assert.equal($('pin').disabled,true);
 assert.ok($('status').textContent.includes('Undefined'));
 $('terminal').input(1);await settle();assert.ok(selected());
 $('pin').click();await settle();assert.equal($('pins').children.length,6);
 $('domain').value='focus';$('domain').events.change();await settle();
 assert.ok(selected().x[0]>=model.bounds.rate[0]*100);
 $('pins').children.at(-1).children.at(-1).children[0].click();await settle();
 assert.equal($('domain').value,'wide');assert.equal(selected().x[0],5);
 console.log('Controller selection, inverse target, method switching, pin/recall/remove and CSV export passed.');
})().catch(e=>{console.error(e);process.exitCode=1});

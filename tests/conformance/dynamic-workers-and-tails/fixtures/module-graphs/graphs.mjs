// Handwritten finite graphs; helpers package modules, never generate case IDs.
export const DATE='2026-09-04';
export const SUPPORT=`
export const events=[];
const gates=new Map();
export function note(value){if(events.length>=48)throw new Error('event bound');events.push(value);}
export function snapshot(){return {events:[...events],pending:[...gates.keys()].sort()};}
export function hold(key){
 if(gates.has(key)||gates.size>=2)throw new Error('gate bound');note('hold:'+key);
 return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{gates.delete(key);reject(new Error('gate-expired:'+key));},3000);gates.set(key,{resolve,reject,timer});});
}
export function release(key){const gate=gates.get(key);if(!gate)throw new Error('gate not pending:'+key);gates.delete(key);clearTimeout(gate.timer);note('release:'+key);gate.resolve();}
export function stop(){for(const [key,gate] of gates){clearTimeout(gate.timer);gate.reject(new Error('cleanup:'+key));}gates.clear();return snapshot();}
`;
export function main(imports,body){return `import {WorkerEntrypoint} from 'cloudflare:workers';\nimport {snapshot,release,stop} from './support.js';\n${imports}\nconst calls=[];const active=new Set();\nexport default class extends WorkerEntrypoint { state(){return {...snapshot(),calls:[...calls],active:[...active].sort()};} release(key){release(key);return this.state();} stop(){stop();return this.state();} async invoke(op,id,args){if(calls.length>=48||active.has(id))throw new Error('invocation bound');calls.push({id,op,phase:'enter'});active.add(id);try{return await this[op](...args);}finally{active.delete(id);calls.push({id,op,phase:'settle'});}} ${body} }`;}
export function graph(modules,mainModule='main.js') {return {compatibilityDate:DATE,mainModule,modules:{'support.js':SUPPORT,...modules},globalOutbound:null,env:{}};}
export const GRAPHS={
 control:graph({'main.js':main('',`probe(){return 'graph-control';}`)}),
 M001:graph({
  'main.js':main(`import {left} from './left.js';import {right} from './right.js';import {note} from './support.js';note('main');`,`probe(){return {left:left(),right:right(),state:snapshot()};}`),
  'leaf.js':`import {note} from './support.js';note('leaf');const object={value:41};export {object};`,
  'left.js':`import {object} from './leaf.js';import {note} from './support.js';note('left');export function left(){return object.value++;}`,
  'right.js':`import {object} from './leaf.js';import {note} from './support.js';note('right');export function right(){return object.value;}`
 }),
 M002:graph({
  'main.js':main(`import {value,set} from './barrel.js';import * as observer from './observer.js';import {hold,note} from './support.js';`,`async write(){await hold('write');set(9);note('written');return value;} read(){return [value,observer.read()];}`),
  'state.js':`export let value=1;export function set(v){value=v;}`,
  'barrel.js':`export {value,set} from './state.js';`,
  'observer.js':`import {value} from './state.js';export function read(){return value;}`
 }),
 M003:graph({
  'main.js':main(`import original,{current,replace} from './state.js';import {read} from './observer.js';`,`probe(){return {original:original.value,current:current.value,seen:read(),same:original===current};} replace(){replace();return this.probe();}`),
  'state.js':`export let current={value:1};export default current;export function replace(){current={value:2};}`,
  'observer.js':`import {current} from './state.js';export function read(){return current.value;}`
 }),
 M004:graph({
  'main.js':main(`import {read,add} from './left/view.js';import {read as right} from './right/view.js';import {read as direct} from './left/state.js';`,`probe(){return [read(),right(),direct()];} add(){add();return this.probe();}`),
  'left/view.js':`import {n,add} from './state.js';export {add};export function read(){return n;}`,
  'right/view.js':`import {n} from './state.js';export function read(){return n;}`,
  'left/state.js':`export let n=1;export function read(){return n;}export function add(){n++;}`,
  'right/state.js':`export const n=10;`
 }),
 M005:graph({
  'main.js':main(`import {readA,setA} from './a.js';import {readB} from './b.js';`,`probe(){return [readA(),readB()];} change(){setA(7);return this.probe();}`),
  'a.js':`import {valueB} from './b.js';export let valueA=2;export function setA(v){valueA=v;}export function readA(){return valueB;}`,
  'b.js':`import {valueA} from './a.js';export const valueB=3;export function readB(){return valueA;}`
 }),
 M006:graph({
  'main.js':main(`import {a} from './a.js';`,`probe(){return a;}`),
  'a.js':`import {b} from './b.js';export const a=b+1;`,
  'b.js':`import {a} from './a.js';export const b=a+1;`
 }),
 M007:graph({
  'main.js':main('',`async lazy(){const x=await import('./lazy.js');return {value:x.value,events:snapshot().events};}`),
  'lazy.js':`import {note,hold} from './support.js';note('lazy-start');await hold('lazy');note('lazy-ready');export const value=17;`
 }),
 M008:graph({
  'main.js':main(`import * as staticState from './state.js';`,`async mutate(){const dynamicState=await import('./state.js');dynamicState.add();return {same:dynamicState===staticState,n:staticState.n};} read(){return staticState.n;}`),
  'state.js':`export let n=0;export function add(){n++;}`
 }),
 M009:graph({
  'main.js':main(`import {read} from './leaf.js';`,`async broken(){return (await import('./broken.js')).value;} async good(){return (await import('./good.js')).read();} read(){return read();}`),
  'leaf.js':`let n=0;export function add(){n++;}export function read(){return n;}`,
  'broken.js':`import {add} from './leaf.js';add();throw new Error('planned:M009:after-leaf');export const value=0;`,
  'good.js':`export {read} from './leaf.js';`
 }),
 M010:graph({
  'main.js':main('',`async broken(){return (await import('./consumer.js')).read();} async good(){return (await import('./left.js')).value;}`),
  'left.js':`export const value=4;`,
  'right.js':`export const value=8;`,
  'barrel.js':`export * from './left.js';export * from './right.js';`,
  'consumer.js':`import {value} from './barrel.js';export function read(){return value;}`
 }),
 M011:graph({
  'main.js':main('',`async lazy(){return (await import('./lazy.js')).value;}`),
  'lazy.js':`import {note,hold} from './support.js';note('failing-start');await hold('failure');note('failing-throw');throw new Error('planned:M011:lazy');export const value=0;`
 }),
 M012:graph({
  'main.js':main('',`async left(){return (await import('./left.js')).read();} async right(){return (await import('./right.js')).read();}`),
  'leaf.js':`import {note,hold} from './support.js';note('shared-start');await hold('shared');note('shared-ready');export const object={n:0};`,
  'left.js':`import {object} from './leaf.js';import {note} from './support.js';note('left-ready');export function read(){object.n++;return {side:'left',n:object.n};}`,
  'right.js':`import {object} from './leaf.js';import {note} from './support.js';note('right-ready');export function read(){object.n++;return {side:'right',n:object.n};}`
 }),
 M013:graph({
  'main.js':main('',`async left(){return (await import('./left.js')).value;} async right(){return (await import('./right.js')).value;}`),
  'left.js':`import {hold,note} from './support.js';await hold('left');note('left-ready');export const value='left';`,
  'right.js':`import {hold,note} from './support.js';await hold('right');note('right-ready');export const value='right';`
 }),
 M014left:graph({
  'main.js':main('',`async lazy(){const x=await import('./lazy.js');return x.value;} async read(){return (await import('./state.js')).n;}`),
  'lazy.js':`import {hold} from './support.js';import {n,add} from './state.js';await hold('same');add();export const value=n;`,
  'state.js':`export let n=1;export function add(){n++;}`
 }),
 M014right:graph({
  'main.js':main('',`async lazy(){const x=await import('./lazy.js');return x.value;} async read(){return (await import('./state.js')).n;}`),
  'lazy.js':`import {hold} from './support.js';import {n,add} from './state.js';await hold('same');add();export const value=n;`,
  'state.js':`export let n=10;export function add(){n++;}`
 }),
 M015bad:graph({
  'main.js':main('',`async lazy(){return (await import('./lazy.js')).value;}`),
  'lazy.js':`import {hold,note} from './support.js';await hold('same');note('bad-throw');throw new Error('planned:M015:bad');export const value=0;`
 }),
 M015good:graph({
  'main.js':main('',`async lazy(){return (await import('./lazy.js')).value;}`),
  'lazy.js':`import {hold,note} from './support.js';await hold('same');note('good-ready');export const value=77;`
 }),
 M016:graph({
  'main.js':main(`import {inside} from './nested/importer.js';`,`async probe(){const [a,b]=await Promise.all([inside(),import('./state.js')]);return {same:a===b,n:a.n};} async add(){const a=await inside();a.add();return this.probe();}`),
  'nested/importer.js':`export function inside(){return import('../nested/../state.js');}`,
  'state.js':`export let n=2;export function add(){n++;}`
 }),
 M017:graph({
  'main.js':main('',`async lazy(){return (await import('./recoverer.js')).value;}`),
  'bad.js':`import {hold,note} from './support.js';await hold('recover');note('bad-throw');throw new Error('planned:M017:handled');`,
  'recoverer.js':`import {note} from './support.js';let value;try{await import('./bad.js');value='wrong';}catch(error){if(!String(error).includes('planned:M017:handled'))throw error;note('caught');value='fallback';}export {value};`
 }),
 M018:graph({
  'main.js':main(`import {hold} from './support.js';`,`async lazy(){const lazy=await import('./return-main.js');return lazy.sameClass(this.constructor);} probe(){return 'main-live';}`),
  'return-main.js':`const main=await import('./main.js');export function sameClass(cls){return cls===main.default;}`
 }),
 M019:graph({
  'main.js':main(`import {value,set} from './state.js';`,`async lazy(){return (await import('./reader.js')).captured;} set(v){set(v);return value;}`),
  'state.js':`export let value=1;export function set(v){value=v;}`,
  'reader.js':`import {value} from './state.js';import {hold,note} from './support.js';await hold('read');note('read:'+value);export const captured=value;`
 }),
 M020:graph({
  'main.js':main(`import {read} from './consumer.js';import {set} from './right.js';`,`probe(){return read();} change(){set(12);return read();}`),
  'left.js':`export const value=4;`,
  'right.js':`export let value=8;export function set(v){value=v;}`,
  'barrel.js':`export * from './left.js';export * from './right.js';export {value} from './right.js';`,
  'consumer.js':`import {value} from './barrel.js';export function read(){return value;}`
 }),
 M021:graph({
  'main.js':main(`import {value} from './selected.js';`,`probe(){return {value,events:snapshot().events};} async optional(){await import('./optional.js');return 'unreachable';}`),
  'selected.js':`import {note} from './support.js';note('selected');export const value='selected';`,
  'optional.js':`import {note} from './support.js';note('optional');throw new Error('planned:M021:optional');`
 })
};

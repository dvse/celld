import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
let next=0;
class Value extends RpcTarget {constructor(){super();this.identity=++next;} id(){return this.identity;}}
function shape(cap){const array=new Array(5);array[0]=cap;array.extra=cap;
 const graph={a:cap,b:cap,array,map:new Map([[cap,cap]])};graph.self=graph;
 Object.defineProperty(graph,'__proto__',{value:{sentinel:7},enumerable:true});return graph;}
function inspect(g){return {ownProto:Object.hasOwn(g,'__proto__'),proto:g.__proto__.sentinel??null,
 length:g.array.length,holes:[1,2,3,4].every(k=>!(k in g.array)),extra:g.array.extra===g.a,
 alias:g.a===g.b&&g.a===g.array[0]&&g.map.get(g.a)===g.a,cycle:g.self===g};}
class Shape extends RpcTarget {constructor(g){super();this.g=g;} read(){return inspect(this.g);}}
export class Actor extends DurableObject {
 [restore](p){return p.graph?new Shape(p.graph):new Value();}
 async check(){const cap=await this.ctx.restore({id:'value'});const graph=shape(cap);
 await this.ctx.storage.put('graph',graph);const stored=await this.ctx.storage.get('graph');
 const x=await stored.a.id(),y=await stored.b.id();
 const restored=await this.ctx.restore({graph});const params=await restored.read();
 const plain=shape('plain');await this.ctx.storage.put('plain',plain);
 return {stored:inspect(stored),sameTarget:x===y,params,plain:inspect(await this.ctx.storage.get('plain'))};}
}
export default {async fetch(req,env){return Response.json(await env.ACTOR.getByName('test').check());}};

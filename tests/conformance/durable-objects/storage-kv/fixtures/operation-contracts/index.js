import upstream from './upstream.js';
export * from './upstream.js';
export default {async fetch(r,env,ctx){try{await upstream.test(null,env,ctx);return Response.json({ok:true});}catch(e){return Response.json({ok:false,name:e.name,message:e.message},{status:500});}}};

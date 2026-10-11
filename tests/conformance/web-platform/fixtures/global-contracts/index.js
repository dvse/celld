export * from './upstream.js';
import * as checks from './upstream.js';
export default {async fetch(request,env,ctx){const name=new URL(request.url).pathname.slice(1);try {if(!checks[name]?.test)throw new Error('unknown check '+name);await checks[name].test(null,env,ctx);return Response.json({check:name,ok:true});}catch(e){return Response.json({check:name,ok:false,name:e.name,message:e.message},{status:500});}}};

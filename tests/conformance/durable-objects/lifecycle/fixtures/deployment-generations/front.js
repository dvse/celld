// Static service bindings only. No Loader and no capability retained across requests.
export default {async fetch(request,env) {
 if(new URL(request.url).pathname==='/health')return Response.json({profile:'deployment-recovery',build:'front'});
 try {const input=await request.json();if(!['identity','snapshot','apply','prepare','seed','status','release'].includes(input.method))throw new Error('bounded front method');const answer=await env.BACKEND.call(input);return Response.json(answer);}
 catch(error){return Response.json({error:String(error)},{status:500});}
}};

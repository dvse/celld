import {DurableObject, WorkerEntrypoint} from 'cloudflare:workers';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chunks = prefix => new ReadableStream({async start(c) {
  const enc = new TextEncoder();
  for (let i = 0; i < 3; i++) { c.enqueue(enc.encode(prefix + i + ';')); await sleep(20); }
  c.close();
}});
// A route owner on another node (Durable Object placement), like the Git
// Server or a Planet: it answers with a streamed body.
export class Owner extends DurableObject {
  fetch(req) {
    if (new URL(req.url).pathname.endsWith('/unauth'))
      return new Response('auth required', {status: 401, headers: {'www-authenticate': 'Basic realm="c7"'}});
    return new Response(chunks('owner'));
  }
}
const route = async (env, path) => {
  let result;
  if (path === '/nosuch') result = new Response('Published application not found.', {status: 404});
  else if (path === '/stream') result = new Response(chunks('local'));
  else if (path.startsWith('/owner')) result = await env.OWNER.getByName('owner').fetch(new Request('http://owner' + path));
  else return null;
  // As the Publication gatekeeper does: re-wrap the body before returning it.
  const answer = new Response(result.body, result);
  answer.headers.set('x-robots-tag', 'noindex');
  return answer;
};
export class Routes extends DurableObject {
  route(path) { return route(this.env, path); }
}
export default class Gatekeeper extends WorkerEntrypoint {
  fetch(req) { return new Response('gatekeeper'); }
  route(request) { return route(this.env, new URL(request.url).pathname.replace(/^\/p/, '')); }
}

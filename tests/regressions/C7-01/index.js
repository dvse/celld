// The origin router, shaped like a published-route ingress: the response to a
// /p/ request is the Response that the gatekeeper's route() RPC returned, so
// its body stream is a capability this stateless handler received over RPC
// and the node pumps it after the handler has returned.
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname.startsWith('/p/')) {
      const published = await env.PUB.route(req);
      return published instanceof Response ? published : new Response('router 404', {status: 404});
    }
    // The same through a Durable Object's RPC method.
    if (url.pathname.startsWith('/do/')) return env.ROUTES.getByName('routes').route(url.pathname.slice(3));
    // Control: the body is consumed inside the handler.
    if (url.pathname === '/read') {
      const r = await env.PUB.route(new Request('http://x' + url.searchParams.get('path')));
      return Response.json({status: r.status, text: await r.text()});
    }
    return new Response('router');
  },
};

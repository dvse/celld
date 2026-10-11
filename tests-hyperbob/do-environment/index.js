// A Durable Object binding with Wrangler's `environment` must be refused at deploy, not ignored.
export default { fetch() { return new Response("deployed"); } };

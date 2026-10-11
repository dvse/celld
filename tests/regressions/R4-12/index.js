import { WorkerEntrypoint } from 'cloudflare:workers';
export class Counter extends WorkerEntrypoint {
  value = 0;
  next() { return ++this.value; }
}
export default { async fetch(req, env, ctx) {
  const plain = ctx.exports.Counter;
  const empty = ctx.exports.Counter({props: {}});
  const props = ctx.exports.Counter({props: {tag: 'x'}});
  return Response.json({plain: [await plain.next(), await plain.next()],
    empty: [await empty.next(), await empty.next()],
    props: [await props.next(), await props.next()],
    concurrent: await Promise.all([props.next(), props.next()])});
}};

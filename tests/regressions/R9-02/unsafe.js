import {WorkerEntrypoint} from 'cloudflare:workers';
export class Inner extends WorkerEntrypoint {ping(){return 42;}}
export default class extends WorkerEntrypoint {get(){return this.ctx.exports.Inner({});}}

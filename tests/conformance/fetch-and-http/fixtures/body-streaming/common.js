export const PROFILE = 'http-stream-stress-frozen-v1';
export const LIMITS = Object.freeze({ wallMs: 24000, payloadBytes: 4194304, operationBytes: 131072, operations: 24, networkRequests: 6, events: 512, readOperations: 262144 });
export class Blocked extends Error { constructor(message) { super(message); this.name='Blocked'; this.code='BLOCKED_PREREQUISITE'; } }
export const requireReady = (ok, message) => { if (!ok) throw new Blocked(message); };
export const check = (ok, message) => { if (!ok) throw new Error(message); };
export const ident = value => { check(typeof value === 'string' && /^[a-zA-Z0-9_-]{1,100}$/.test(value), 'bounded identifier required'); return value; };
export function privateOrigin(value) {
  const u = new URL(value); const parts = u.hostname.split('.').map(Number);
  check(u.protocol === 'http:' && !u.username && !u.password && !u.search && !u.hash && u.pathname === '/' && parts.length === 4 && parts.every(x => Number.isInteger(x) && x >= 0 && x <= 255), 'literal private HTTP origin required');
  check(parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168) || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31), 'private destination required');
  check(u.port === '18080', 'fixture HTTP port required'); return u.origin;
}
export function bytes(label, n = 32768) {
  ident(label); check(Number.isSafeInteger(n) && n >= 0 && n <= LIMITS.operationBytes, 'payload bound');
  const out = new Uint8Array(n); let seed = 0;
  for (const char of label) seed = (seed * 33 + char.charCodeAt(0)) >>> 0;
  for (let i = 0; i < n; i++) out[i] = (seed + 29 * i + (i >>> 7)) & 255;
  return out;
}
export const join = chunks => { const total = chunks.reduce((n,c) => n+c.byteLength,0); check(total <= LIMITS.operationBytes, 'body exceeds per-operation bound'); const result = new Uint8Array(total); let pos=0; for (const c of chunks) { result.set(c,pos); pos+=c.byteLength; } return result; };
export function equal(actual, expected, context='bytes') { check(actual.byteLength === expected.byteLength, context+': length mismatch'); for(let i=0;i<actual.byteLength;i++) check(actual[i]===expected[i],context+': byte mismatch at '+i); }
export const hex = value => [...new Uint8Array(value)].map(v=>v.toString(16).padStart(2,'0')).join('');
export const hash = async value => hex(await crypto.subtle.digest('SHA-256', value));
export function gate() { let resolve; const promise=new Promise(r=>{resolve=r;}); return {promise,resolve,open:false}; }
export async function bounded(promise, ms, label) { let timer; try { return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label+' deadline')),ms);})]); } finally { clearTimeout(timer); } }

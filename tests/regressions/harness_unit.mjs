import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
export const source = readFileSync(process.env.CELLD_SOURCE
  ?? fileURLToPath(new URL('../../crates/celld/js/harness.js', import.meta.url)), 'utf8');
export function section(start, end) {
  const a=source.indexOf(start), b=source.indexOf(end,a+start.length);
  if(a<0||b<a) throw new Error('Harness section not found: '+start);
  return source.slice(a,b);
}
export function evaluate(code, globals={}) {
  return vm.runInNewContext(code, {console, setTimeout, clearTimeout, ...globals});
}

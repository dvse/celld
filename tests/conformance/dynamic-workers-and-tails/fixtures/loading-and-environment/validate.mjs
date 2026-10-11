// Static-only: materialize hand-authored source strings and invoke node's parser.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawnSync} from 'node:child_process';
import * as sources from './sources.mjs';
const here=path.dirname(new URL(import.meta.url).pathname);
const manifest=JSON.parse(fs.readFileSync(path.join(here,'manifest.json'),'utf8'));
const text=fs.readFileSync(path.join(here,'cases.js'),'utf8');
const implemented=[...text.matchAll(/^  async (L\d{3})\(s\)/gm)].map(x=>x[1]);
const listed=manifest.map(x=>x.id);
if(JSON.stringify(implemented)!==JSON.stringify(listed) || new Set(listed).size!==listed.length)throw new Error('manifest/implementation mismatch');
for(const row of manifest)for(const key of ['intent','failure_hypothesis','preconditions','trace','stress','oracle','cleanup','implementation','qualification','profile'])if(!row[key]?.length)throw new Error(row.id+' missing '+key);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'loader-props-static-'));
try {
  const checks=[['index.js',fs.readFileSync(path.join(here,'index.js'),'utf8')],['cases.js',text]];
  for(const [name,value] of Object.entries(sources))if(typeof value==='string')checks.push([name+'.mjs',value]);
  checks.push(['facet-materialized.mjs',sources.facetSource('static-check')]);
  for(const [name,source] of checks){const file=path.join(temp,name.replace(/\.js$/,'.mjs'));fs.writeFileSync(file,source);const r=spawnSync(process.execPath,['--check',file],{encoding:'utf8'});if(r.status!==0)throw new Error(name+': '+r.stderr);}
  console.log(JSON.stringify({kind:'static-only',manifestCases:listed.length,implementedCases:implemented.length,parsedModules:checks.length,runtimeLaunches:0,reviewed:0,run:0,passed:0}));
} finally {fs.rmSync(temp,{recursive:true,force:true});}

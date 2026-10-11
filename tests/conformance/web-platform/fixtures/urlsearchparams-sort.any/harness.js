export const results=[];
 globalThis.test=(fn,name)=>{try{fn();results.push({name,status:'pass'});}catch(e){results.push({name,status:'fail',message:e.message});}};
 globalThis.assert_equals=(a,b,why='')=>{if(!Object.is(a,b))throw new Error(why+': '+JSON.stringify(a)+' != '+JSON.stringify(b));};
 globalThis.assert_array_equals=(a,b,why='')=>{if(a.length!==b.length || a.some((x,i)=>!Object.is(x,b[i])))throw new Error(why+': '+JSON.stringify(a)+' != '+JSON.stringify(b));};
 
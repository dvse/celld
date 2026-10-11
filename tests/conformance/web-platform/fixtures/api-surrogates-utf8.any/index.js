import {results} from './harness.js';
import './upstream.js';
export default {fetch(){return Response.json({tests:results.length,results},{status:results.length && results.every(x=>x.status==='pass')?200:500});}};

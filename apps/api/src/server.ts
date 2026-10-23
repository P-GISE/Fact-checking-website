import {createClient} from 'redis';
import {createApp} from './app.js';
import {migrate,pool} from './db.js';
import {authConfiguration} from './auth-config.js';
import {config} from './config.js';
import {cleanup} from './cleanup.js';
const auth=authConfiguration(process.env);
if(process.env.FACTLENS_AUTO_MIGRATE!=='false')await migrate();
const redis=createClient({url:process.env.REDIS_URL??'redis://127.0.0.1:6379'});
redis.on('error',()=>console.error('Redis connection unavailable; queued jobs remain durable.'));
await redis.connect();
await cleanup(config.mediaRoot);
const timer=setInterval(()=>cleanup(config.mediaRoot).catch(()=>console.error('Cleanup failed')),30000);
const server=createApp({...auth,trustProxy:process.env.FACTLENS_TRUST_PROXY==='true',mediaRoot:config.mediaRoot,enqueue:async(id)=>{await redis.lPush('factlens:jobs',id);}}).listen(config.port,process.env.API_HOST??'127.0.0.1',()=>console.log(`FactLens API listening on ${config.port}`));
async function stop(){clearInterval(timer);server.close();await redis.quit();await pool.end();}
process.on('SIGTERM',stop);process.on('SIGINT',stop);

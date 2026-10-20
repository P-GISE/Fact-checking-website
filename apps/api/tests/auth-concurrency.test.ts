import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createServer,request as httpRequest,type ClientRequest,type Server} from 'node:http';
import {once} from 'node:events';
import request from 'supertest';
import {createApp} from '../src/app.js';

const db=vi.hoisted(()=>({query:vi.fn(),connect:vi.fn()}));
vi.mock('../src/db.js',()=>({pool:db}));

const password='correct-horse-927!';
const routes=[
 {method:'POST',path:'/api/auth/register',body:{username:'alice',password},status:409},
 {method:'POST',path:'/api/auth/login',body:{username:'alice',password},status:401},
 {method:'PATCH',path:'/api/auth/account',body:{username:'alice',currentPassword:password},status:401},
 {method:'DELETE',path:'/api/auth/account',body:{currentPassword:password,confirmation:'DELETE'},status:401},
] as const;
const cookie='factlens_session='+'a'.repeat(64);
type Route=typeof routes[number];
let server:Server;
let origin:string;
let closed:number;
let hold:boolean;
let rejectWork:boolean;
let activeTransactions:number;
let releases:Array<()=>void>;
let clients:ClientRequest[];

beforeEach(async()=>{
 closed=0;hold=false;rejectWork=false;activeTransactions=0;releases=[];clients=[];
 db.query.mockReset();
 db.connect.mockReset();
 db.query.mockImplementation(async(sql:string)=>{
  if(sql.startsWith('SELECT u.id,u.username,u.role FROM app_sessions')){
   return {rows:[{id:'00000000-0000-4000-8000-000000000001',username:'alice',role:'user'}],rowCount:1};
  }
  if(sql.startsWith('INSERT INTO app_users')||sql.includes('FROM app_users WHERE')){
   if(hold)await new Promise<void>(resolve=>releases.push(resolve));
   if(rejectWork)throw new Error('controlled database failure');
   return {rows:[],rowCount:0};
  }
  if(sql==='BEGIN'||sql==='ROLLBACK'||sql==='SELECT pg_advisory_xact_lock(548871631)'||
     sql.startsWith('SELECT 1 FROM app_sessions'))return {rows:[],rowCount:0};
  throw new Error('Unexpected query: '+sql);
 });
 db.connect.mockImplementation(async()=>{
  activeTransactions++;
  return {query:db.query,release:()=>{activeTransactions--;}};
 });
 const app=createApp({mediaRoot:'.',enqueue:async()=>{},authMode:'accounts'});
 server=createServer((req,res)=>{res.once('close',()=>closed++);app(req,res);});
 server.listen(0,'127.0.0.1');
 await once(server,'listening');
 const address=server.address();
 if(!address||typeof address==='string')throw new Error('Missing HTTP listener');
 origin=`http://127.0.0.1:${address.port}`;
});

afterEach(async()=>{
 hold=false;
 releases.forEach(resolve=>resolve());
 clients.forEach(client=>client.destroy());
 await vi.waitFor(()=>expect(activeTransactions).toBe(0));
 server.closeAllConnections();
 await new Promise<void>((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
});

function send(route:Route,body:unknown=route.body){
 return request(origin)[route.method.toLowerCase() as 'post'|'patch'|'delete'](route.path)
  .set('Cookie',cookie).send(body).timeout(3000);
}

async function fillSlots(route:Route){
 hold=true;
 const start=releases.length;
 const pending=Array.from({length:4},()=>send(route).then(response=>response));
 await vi.waitFor(()=>expect(releases.length).toBe(start+4),{timeout:3000});
 const blocked=await send(route,{});
 expect(blocked.status).toBe(429);
 expect(blocked.body.error.code).toBe('AUTH_RATE_LIMITED');
 hold=false;
 releases.slice(start).forEach(resolve=>resolve());
 const responses=await Promise.all(pending);
 expect(responses.map(response=>response.status)).toEqual(Array(4).fill(route.status));
}

it.each(routes)('$method $path retains all four slots after disconnect until handler work settles',async route=>{
 hold=true;
 const body=JSON.stringify(route.body);
 for(let i=0;i<4;i++){
  const client=httpRequest(origin+route.path,{
   method:route.method,headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body),Cookie:cookie},agent:false,
  });
  client.on('error',()=>{});
  client.end(body);
  clients.push(client);
 }
 // The database barrier proves all four real handlers started before any socket is aborted.
 await vi.waitFor(()=>expect(releases).toHaveLength(4),{timeout:3000});
 clients.forEach(client=>client.destroy());
 await vi.waitFor(()=>expect(closed).toBe(4));
 try{
  const blocked=await send(route,{});
  expect(blocked.status).toBe(429);
  expect(blocked.body.error.code).toBe('AUTH_RATE_LIMITED');
 }finally{
  hold=false;
  releases.forEach(resolve=>resolve());
 }
 // A completed response proves admission after the abandoned handlers finish (including scrypt).
 await vi.waitFor(async()=>expect((await send(route)).status).toBe(route.status),{timeout:3000});
 await fillSlots(route);
});

it.each(routes)('$method $path releases slots on validation throws and early returns',async route=>{
 for(let i=0;i<5;i++){
  expect((await send(route,{})).status).toBe(400);
  expect((await send(route)).status).toBe(route.status);
 }
 await fillSlots(route);
});

it.each(routes)('$method $path releases slots when asynchronous database work throws',async route=>{
 rejectWork=true;
 for(let i=0;i<5;i++){
  const response=await send(route);
  expect(response.status).toBe(500);
  expect(response.body.error.code).toBe('INTERNAL_ERROR');
 }
 rejectWork=false;
 await fillSlots(route);
});

it('keeps the twenty-attempt limit after completed handlers release their slots',async()=>{
 for(let i=0;i<20;i++)expect((await send(routes[1],{})).status).toBe(400);
 const blocked=await send(routes[1],{});
 expect(blocked.status).toBe(429);
 expect(blocked.body.error.code).toBe('AUTH_RATE_LIMITED');
});

import {it,expect} from 'vitest';
import request from 'supertest';
import {createApp} from '../src/app.js';
const app=createApp({mediaRoot:'/tmp/factlens-security-unused',enqueue:async()=>{}});
it.each([
 ['/api/not-found',{},404],
 ['/api/media/not-an-id',{},400],
 ['/api/analyses',{Origin:'https://untrusted.example'},403],
] as const)('protects API response %s including errors',async(url,headers,status)=>{
 const response=await request(app).get(url).set(headers);
 expect(response.status).toBe(status);
 expect(response.headers['x-frame-options']).toBe('DENY');
 expect(response.headers['content-security-policy']).toBe("default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
 expect(response.headers['cross-origin-resource-policy']).toBe('same-origin');
 expect(response.headers['referrer-policy']).toBe('no-referrer');
 expect(response.headers['x-content-type-options']).toBe('nosniff');
 expect(response.headers['cache-control']).toBe('no-store');
 expect(response.headers['x-powered-by']).toBeUndefined();
});

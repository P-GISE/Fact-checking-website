import path from 'node:path';
export const config={mediaRoot:path.resolve(process.env.MEDIA_ROOT??'.data/media'),maxBytes:100*1024*1024,port:Number(process.env.PORT??3000)};

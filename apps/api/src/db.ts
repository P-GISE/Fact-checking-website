import pg from 'pg';
import { readFile } from 'node:fs/promises';
const databaseUrl=process.env.DATABASE_URL;
if(!databaseUrl)throw new Error('DATABASE_URL_REQUIRED');
export const pool=new pg.Pool({connectionString:databaseUrl});
// PostgreSQL maintenance can drop idle sockets. Let the pool reconnect on demand.
pool.on('error',()=>console.error('Database connection interrupted; pending requests may be retried.'));

export async function migrate(){for(const name of ['001_initial.sql','002_accounts.sql','003_upload_limits.sql'])await pool.query(await readFile(new URL('../migrations/'+name,import.meta.url),'utf8'));}

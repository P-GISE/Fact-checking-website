import pg from 'pg';
import { readFile } from 'node:fs/promises';
export const pool=new pg.Pool({connectionString:process.env.DATABASE_URL??'postgresql://factlens:development@127.0.0.1:5432/factlens'});
export async function migrate(){await pool.query(await readFile(new URL('../migrations/001_initial.sql',import.meta.url),'utf8'));}

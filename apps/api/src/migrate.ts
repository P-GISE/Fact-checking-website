import {migrate,pool} from './db.js';
try { await migrate(); } finally { await pool.end(); }

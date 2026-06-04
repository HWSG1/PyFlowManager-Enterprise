import { Router } from 'express';
import { getPool } from '../db/sql';

const router = Router();

router.get('/', async (_req, res) => {
  try {
    const pool = await getPool();
    await pool.request().query('SELECT 1 AS ok');
    res.json({ ok: true, database: 'connected', timestamp: new Date().toISOString() });
  } catch (error: any) {
    res.status(500).json({ ok: false, database: 'error', error: error.message });
  }
});

export default router;

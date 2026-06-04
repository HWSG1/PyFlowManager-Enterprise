import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { requireAuth } from '../services/security.service';
const router = Router();
const defaultThemes = [
'dark-blue','light','corporate-gray','banking-blue','navy','emerald','purple','crimson','ocean','aurora','matrix','cyberpunk','dracula','nord','monokai','github-dark','vscode-dark','gold','titanium','obsidian'
];
router.get('/', async (_req,res,next)=>{ try { const pool=await getPool(); const r=await pool.request().query(`SELECT theme_key,theme_name,is_dark FROM dbo.Themes ORDER BY theme_name`); res.json(r.recordset.length?r.recordset:defaultThemes.map(x=>({theme_key:x,theme_name:x.replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase()),is_dark:x!=='light'}))); } catch(err){ next(err); }});
router.post('/me', requireAuth, async(req,res,next)=>{ try{ const pool=await getPool(); await pool.request().input('id',sql.Int,(req as any).user.id).input('theme_key',sql.NVarChar(80),req.body?.theme_key).query(`UPDATE dbo.Users SET theme_key=@theme_key WHERE id=@id`); res.json({ok:true}); }catch(err){next(err);} });
export default router;

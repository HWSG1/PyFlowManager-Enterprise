import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import fs from 'fs';
import { env } from './config/env';
import healthRoutes from './routes/health.routes';
import scriptsRoutes from './routes/scripts.routes';
import executionsRoutes from './routes/executions.routes';
import schedulesRoutes from './routes/schedules.routes';
import settingsRoutes from './routes/settings.routes';
import authRoutes from './routes/auth.routes';
import usersRoutes from './routes/users.routes';
import themesRoutes from './routes/themes.routes';
import { startScheduler } from './services/schedulerService';
import dashboardRoutes from "./routes/dashboard.routes";
import governanceRoutes from './routes/governance.routes';
import { processExecutionQueue } from './services/executionQueue.service';

fs.mkdirSync(env.runtime.scriptsDir, { recursive: true });
fs.mkdirSync(env.runtime.logsDir, { recursive: true });
fs.mkdirSync(env.runtime.exportsDir, { recursive: true });

const app = express();

app.use(helmet());
const allowedOrigins = process.env.CORS_ORIGINS?.split(',') || [];

app.use(cors({
  origin: allowedOrigins,
  credentials: true
}));
app.use(express.json({ limit: '10mb' }));

app.use('/api/health', healthRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/scripts', scriptsRoutes);
app.use('/api/executions', executionsRoutes);
app.use('/api/schedules', schedulesRoutes);
app.use('/api/settings', settingsRoutes);
app.use('/api/users', usersRoutes);
app.use('/api/themes', themesRoutes);
app.use("/api/dashboard", dashboardRoutes);
app.use('/api/governance', governanceRoutes);

app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err);
  res.status(500).json({
    error: true,
    message: err.message || 'Error interno'
  });
});

app.listen(env.port, () => {
  console.log(`PyFlow backend listening on http://localhost:${env.port}`);

  startScheduler();

  const queueInterval = Number(process.env.QUEUE_PROCESS_INTERVAL_MS || 30000);
  setInterval(() => {
    processExecutionQueue();
  }, queueInterval);

  console.log(`Execution queue processor started. Interval: ${queueInterval}ms`);
});

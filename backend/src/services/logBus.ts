import { EventEmitter } from 'events';

export const logBus = new EventEmitter();
logBus.setMaxListeners(500);

export function emitExecutionLog(executionId: number, payload: any) {
  logBus.emit(`execution:${executionId}`, payload);
}

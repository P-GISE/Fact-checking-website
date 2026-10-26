import { createConnection } from 'node:net';

export function confirmLoopbackRefused(port, connect = createConnection) {
  return new Promise((accept, reject) => {
    const socket = connect({ host: '127.0.0.1', port });
    const finish = (error) => { socket.destroy(); error ? reject(error) : accept(true); };
    socket.once('connect', () => finish(new Error('listener_still_accepts_tcp')));
    socket.once('error', (error) => finish(error.code === 'ECONNREFUSED' ? undefined : new Error('tcp_close_unverified')));
    socket.setTimeout(1000, () => finish(new Error('tcp_close_timeout_unverified')));
  });
}

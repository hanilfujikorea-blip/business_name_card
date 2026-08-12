const { spawn } = require('node:child_process');

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const options = { stdio: 'inherit', shell: process.platform === 'win32' };
const api = spawn(npmCommand, ['run', 'dev:api'], options);
const web = spawn(npmCommand, ['run', 'dev:web'], options);
let stopping = false;

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  if (!api.killed) api.kill();
  if (!web.killed) web.kill();
  process.exitCode = exitCode;
}

api.on('exit', code => stop(code || 0));
web.on('exit', code => stop(code || 0));
process.on('SIGINT', () => stop(0));
process.on('SIGTERM', () => stop(0));

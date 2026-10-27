const path = require('node:path')

/** This local CommonJS module is shared with Electron. Vite's dependency cache
 * does not otherwise invalidate when its source changes without a lockfile edit. */
function shortcutDependencies(filename) {
  const modulePath = path.resolve(filename)
  const key = filename => process.platform === 'win32' ? path.resolve(filename).toLowerCase() : path.resolve(filename)
  return {
    name: 'nova-shortcut-dependencies',
    config() {
      return {
        resolve: { alias: { '@nova/keyboard-shortcuts': modulePath } },
        optimizeDeps: { include: ['@nova/keyboard-shortcuts'], force: true },
      }
    },
    configureServer(server) {
      let timer
      const changed = filename => {
        if (key(filename) !== key(modulePath)) return
        clearTimeout(timer)
        timer = setTimeout(() => {
          timer = undefined
          void server.restart(true).catch(error => server.config.logger.error(String(error)))
        }, 100)
      }
      const dispose = () => { clearTimeout(timer); server.watcher.off('change', changed) }
      server.watcher.add(modulePath)
      server.watcher.on('change', changed)
      server.httpServer?.once('close', dispose)
    },
  }
}

module.exports = { shortcutDependencies }

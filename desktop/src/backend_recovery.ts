/** Restart only a disconnected host. A readiness refresh never replays a turn. */
export async function recheckBackend(connected: boolean, api: {
  restartBackend: () => Promise<{ success: boolean }>
  refreshReadiness: () => Promise<unknown>
}): Promise<void> {
  if (!connected) {
    const receipt = await api.restartBackend()
    if (!receipt.success) throw new Error('BACKEND_RESTART_FAILED')
  }
  await api.refreshReadiness()
}

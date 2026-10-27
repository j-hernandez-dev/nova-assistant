// Desktop-owned chrome only. This module never translates model or tool content.
const messages = {
  en: {
    cancel: 'Cancel', allow: 'Allow', workspace: 'Workspace',
    memoryTitle: 'Nova — sensitive memory',
    memoryWrite: 'Allow this exact sensitive memory write?',
    memoryReveal: 'Reveal sensitive content for this memory inspection/export?',
    memoryNotice: 'Local storage is not process isolation or encryption. Forget does not erase audit, logs, source conversations or backups.',
    forwardingTitle: 'Nova — document forwarding',
    forwardingMessage: 'Allow this source in remote chat context?',
    forwardingNotice: 'Document data may leave this device. This does not grant tool or security permissions. Future forwarding can be revoked; already transmitted data cannot be recalled.',
    chooseDocument: 'Select a document', select: 'Select',
    refreshDocument: 'Select the source document again',
    exportDocument: 'Export source document', save: 'Save',
    chooseProject: 'Select a project folder',
    authFailed: 'Login failed', authInvalid: 'Invalid request', authSuccess: 'Login successful',
    authClose: 'You can close this window.', authReturn: 'You can close this window and return to Nova.',
  },
  es: {
    cancel: 'Cancelar', allow: 'Permitir', workspace: 'Proyecto',
    memoryTitle: 'Nova — memoria sensible',
    memoryWrite: '¿Permitir esta escritura exacta de memoria sensible?',
    memoryReveal: '¿Mostrar contenido sensible para esta consulta o exportación de memoria?',
    memoryNotice: 'El almacenamiento local no ofrece aislamiento de procesos ni cifrado. Olvidar no elimina auditorías, registros, conversaciones de origen ni copias de seguridad.',
    forwardingTitle: 'Nova — envío de documentos',
    forwardingMessage: '¿Permitir esta fuente en el contexto del chat remoto?',
    forwardingNotice: 'Los datos del documento pueden salir de este dispositivo. Esto no concede permisos de herramientas o seguridad. El envío futuro puede revocarse; los datos ya transmitidos no pueden recuperarse.',
    chooseDocument: 'Seleccionar un documento', select: 'Seleccionar',
    refreshDocument: 'Seleccionar de nuevo el documento de origen',
    exportDocument: 'Exportar documento de origen', save: 'Guardar',
    chooseProject: 'Seleccionar una carpeta de proyecto',
    authFailed: 'No se pudo iniciar sesión', authInvalid: 'Solicitud no válida', authSuccess: 'Sesión iniciada',
    authClose: 'Puedes cerrar esta ventana.', authReturn: 'Puedes cerrar esta ventana y volver a Nova.',
  },
}

function desktopHostMessages(locale) { return messages[locale === 'en' ? 'en' : 'es'] }

function memoryDialogOptions(locale, request) {
  const t = desktopHostMessages(locale)
  return { type: 'warning', title: t.memoryTitle,
    message: request.write ? t.memoryWrite : t.memoryReveal,
    detail: request.name + '\n' + t.workspace + ': ' + (request.workspace || '—') + '\n' + t.memoryNotice,
    buttons: [t.cancel, t.allow], defaultId: 0, cancelId: 0, noLink: true }
}

function forwardingDialogOptions(locale) {
  const t = desktopHostMessages(locale)
  return { type: 'warning', title: t.forwardingTitle, message: t.forwardingMessage,
    detail: t.forwardingNotice, buttons: [t.cancel, t.allow], defaultId: 0, cancelId: 0, noLink: true }
}

function pickerDialogOptions(locale, kind) {
  const t = desktopHostMessages(locale)
  if (kind === 'export') return { title: t.exportDocument, buttonLabel: t.save, defaultPath: 'nova-source-export.bin' }
  return { title: kind === 'project' ? t.chooseProject : kind === 'refresh' ? t.refreshDocument : t.chooseDocument,
    buttonLabel: t.select, properties: [kind === 'project' ? 'openDirectory' : 'openFile'] }
}


module.exports = { desktopHostMessages, memoryDialogOptions, forwardingDialogOptions, pickerDialogOptions }

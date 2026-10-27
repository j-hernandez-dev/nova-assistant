import type {AttachmentRef} from '../shared/application'
import type {SourceFile} from '../shared/storage'
export const sourceIcon=(source:Pick<SourceFile,'kind'>)=>source.kind==='url'?'globe':'file-read'
export const usableSource=(ref:AttachmentRef)=>!!ref.revisionId&&['READY','PARTIAL'].includes(ref.state)

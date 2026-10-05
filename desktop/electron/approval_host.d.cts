export function stableJson(value: unknown): string
export function signApproval(key: string, command: Record<string, unknown>): string
export function validFrame(value: unknown): boolean
export function confirmApproval(client: any, payload: Record<string, unknown>, commandId: string | undefined,
  showDialog: (request: any) => Promise<{ response: number }>): Promise<any>

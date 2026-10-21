const base = import.meta.env.VITE_API_BASE ?? '/api/v1'
const key = 'campuscomp.session'
export const sessionToken = {
  get: () => sessionStorage.getItem(key),
  set: (value: string) => sessionStorage.setItem(key, value),
  clear: () => sessionStorage.removeItem(key),
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  const token = sessionToken.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${base}${path}`, { ...init, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: '服务暂时不可用' }))
    const message = Array.isArray(payload.detail)
      ? payload.detail.map((item: { msg: string }) => item.msg).join('；')
      : payload.detail
    throw new Error(typeof message === 'string' ? message : `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

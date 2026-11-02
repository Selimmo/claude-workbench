// Comment threads as the server returns them (see plan_review/threads.py).

export interface Message {
  author: 'owner' | 'claude'
  text: string
  at: string
}

export interface Thread {
  id: string
  anchor: string
  messages: Message[]
  resolved: boolean
  orphaned: boolean
}

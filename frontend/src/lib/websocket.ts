import { useEffect, useRef, useState, useCallback } from 'react'

type MessageHandler = (data: any) => void

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Map<string, MessageHandler[]>>(new Map())

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        console.log('[WS] Connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
          
          const handlers = handlersRef.current.get(data.type) || []
          handlers.forEach(handler => handler(data))
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        console.log('[WS] Disconnected, reconnecting in 3s...')
        setTimeout(connect, 3000)
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }
    } catch (e) {
      console.error('[WS] Connection failed:', e)
      setTimeout(connect, 3000)
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  const subscribe = useCallback((type: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(type)) {
      handlersRef.current.set(type, [])
    }
    handlersRef.current.get(type)!.push(handler)
    
    return () => {
      const handlers = handlersRef.current.get(type) || []
      const idx = handlers.indexOf(handler)
      if (idx > -1) handlers.splice(idx, 1)
    }
  }, [])

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { isConnected, lastMessage, subscribe, send }
}
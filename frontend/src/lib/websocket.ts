import { useEffect, useRef, useState, useCallback } from 'react'

type MessageHandler = (data: any) => void

export function useWebSocket(url: string | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Map<string, MessageHandler[]>>(new Map())
  const retryCountRef = useRef(0)

  const connect = useCallback(() => {
    if (!url) return;
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        retryCountRef.current = 0
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
        const delay = Math.min(1000 * (2 ** retryCountRef.current), 30000)
        retryCountRef.current++
        console.log(`[WS] Disconnected, reconnecting in ${delay / 1000}s...`)
        setTimeout(connect, delay)
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }
    } catch (e) {
      console.error('[WS] Connection failed:', e)
      const delay = Math.min(1000 * (2 ** retryCountRef.current), 30000)
      retryCountRef.current++
      setTimeout(connect, delay)
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
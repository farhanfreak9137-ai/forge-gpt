import { ActivityEvent } from '../types';

type EventListener = (event: ActivityEvent) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Set<EventListener> = new Set();
  private reconnectTimeout: any = null;
  private isConnecting: boolean = false;
  private lastSequenceNumber: number = 0;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // Connect directly to backend loopback port 8000 or through Vite proxy
    const wsUrl = `${protocol}//${host}/api/v1/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected to ForgeAgent event bus.');
        this.isConnecting = false;
      };

      this.ws.onmessage = (event) => {
        try {
          const parsed: ActivityEvent = JSON.parse(event.data);
          if (parsed.sequence_number) {
            this.lastSequenceNumber = Math.max(this.lastSequenceNumber, parsed.sequence_number);
          }
          this.listeners.forEach((listener) => listener(parsed));
        } catch (e) {
          console.warn('[WebSocket] Non-JSON message received:', event.data);
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn('[WebSocket] Connection error:', err);
        if (this.ws) this.ws.close();
      };
    } catch (e) {
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.reconnectTimeout = setTimeout(() => {
      console.log('[WebSocket] Attempting to reconnect...');
      this.connect();
    }, 2000);
  }

  subscribe(listener: EventListener): () => void {
    this.listeners.add(listener);
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect();
    }
    return () => {
      this.listeners.delete(listener);
    };
  }

  getLastSequenceNumber(): number {
    return this.lastSequenceNumber;
  }
}

export const wsClient = new WebSocketClient();


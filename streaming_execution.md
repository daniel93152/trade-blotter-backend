# WebSocket Streaming Execution Plan

## Stage 1: Backend — WebSocket Infrastructure
**Goal:** Add streaming endpoint in FastAPI backend without breaking existing REST APIs.

**Actions:**
1. Install dependencies:
   ```bash
   pip install fastapi[all]
   ```
2. Create `app/ws_stream.py`:
   ```python
   from fastapi import APIRouter, WebSocket, WebSocketDisconnect
   from app.simulator import get_current_data
   import asyncio

   router = APIRouter()
   clients = set()

   @router.websocket("/ws/stream")
   async def stream_data(ws: WebSocket):
       await ws.accept()
       clients.add(ws)
       try:
           while True:
               data = get_current_data()  # {curve, positions, pnl_summary}
               await ws.send_json(data)
               await asyncio.sleep(2)
       except WebSocketDisconnect:
           clients.remove(ws)
   ```
3. Integrate with `main.py`:
   ```python
   from app.ws_stream import router as ws_router
   app.include_router(ws_router)
   ```

**Output Deliverables:**
- New WebSocket endpoint `/ws/stream`.

**Validation Criteria:**
- `wscat -c ws://localhost:5000/ws/stream` receives continuous JSON every 2s.

---

## Stage 2: Backend — Shared State for Simulation
**Goal:** Ensure curve and PnL simulation data are shared between REST and WebSocket endpoints.

**Actions:**
1. Add global state manager in `app/state.py`:
   ```python
   class MarketState:
       def __init__(self):
           self.curve = {}
           self.positions = []
           self.pnl_summary = {}

   market_state = MarketState()
   ```
2. Update simulator to modify `market_state` during drift loop.
3. Update REST `/curve` and `/pnl` endpoints to read from `market_state`.

**Output Deliverables:**
- Shared in-memory state accessible by both streaming and REST.

**Validation Criteria:**
- `/pnl` and `/ws/stream` return consistent data.

---

## Stage 3: Frontend — WebSocket Integration
**Goal:** Replace Axios polling with WebSocket live streaming (toggleable).

**Actions:**
1. Install optional helper:
   ```bash
   npm install reconnecting-websocket
   ```
2. Create `src/utils/ws.js`:
   ```js
   import ReconnectingWebSocket from 'reconnecting-websocket';

   export const initStream = (onData, onError) => {
     const ws = new ReconnectingWebSocket('ws://localhost:5000/ws/stream');
     ws.onmessage = (event) => onData(JSON.parse(event.data));
     ws.onerror = onError;
     return ws;
   };
   ```
3. Modify `useBlotterData.js`:
   ```js
   const [paused, setPaused] = useState(false);
   useEffect(() => {
     if (paused) return;
     const ws = initStream((data) => {
       setCurve(data.curve);
       setPositions(data.positions);
     });
     return () => ws.close();
   }, [paused]);
   ```

**Output Deliverables:**
- Live WebSocket data replacing polling.

**Validation Criteria:**
- Network tab shows WebSocket connection, not repeated HTTP requests.

---

## Stage 4: Frontend — User Controls and Connection State
**Goal:** Give user control over WebSocket connection.

**Actions:**
1. Extend `SummaryBar.js` with:
   - Pause/Resume toggle (sets `paused`).
   - Connection indicator (🟢 connected / 🔴 disconnected).
2. Display reconnect notification in console or toast.

**Output Deliverables:**
- User-visible control over streaming.

**Validation Criteria:**
- Toggling pause stops updates.
- Connection loss automatically reconnects.

---

## Stage 5: Optimization
**Goal:** Maintain performance and smooth visuals.

**Actions:**
1. Use `React.memo` and `useCallback` to prevent re-renders of unchanged rows.
2. Implement incremental animation updates only for changed tenors and PnL cells.
3. Gracefully handle socket close events (free resources).

**Output Deliverables:**
- Optimized, smooth event-driven UI.

**Validation Criteria:**
- CPU and memory usage stay low.
- Animations remain fluid under streaming load.

---

## Stage 6: End-to-End Validation
**Goal:** Verify the full WebSocket streaming pipeline.

**Actions:**
1. Run backend container and React app.
2. Validate data refreshes every 2s without polling.
3. Toggle pause/resume and observe updates stopping/continuing.
4. Simulate connection drop — auto reconnect should restore stream.

**Output Deliverables:**
- Fully functional WebSocket streaming environment.

**Validation Criteria:**
- Live updates continuous and accurate.
- No unused polling or dead code remaining.

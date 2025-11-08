import React from "react";
import { createRoot } from "react-dom/client";
import io from "socket.io-client";
import axios from "axios";

const socket = io("http://localhost:8000"); // optional, or use redis->socket bridge in prod

function App(){
  const [inside, setInside] = React.useState(0);
  const [events, setEvents] = React.useState([]);

  React.useEffect(()=>{
    // Poll recent logs every 3s (demo)
    const id = setInterval(async ()=>{
      const res = await axios.get("http://localhost:8000/recent");
      setEvents(res.data || []);
      // compute inside count naive
      const users = new Set();
      res.data.forEach(e => { if(e.matched) users.add(e.user_id) });
      setInside(users.size);
    },3000);
    return ()=>clearInterval(id);
  },[]);

  return (
    <div style={{padding:20, fontFamily:"system-ui"}}>
      <h1>GateKeeper Dashboard</h1>
      <h2>Users inside: {inside}</h2>
      <h3>Recent events</h3>
      <ul>
        {events.map(ev => <li key={ev.id}>{ev.ts} - {ev.name || ev.user_id || 'unknown'} - {ev.camera_id} - {ev.matched ? 'IN' : 'FAIL'}</li>)}
      </ul>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);

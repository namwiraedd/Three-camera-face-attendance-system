require('dotenv').config();
const express = require('express');
const axios = require('axios');
const { Pool } = require('pg');
const { createClient } = require('redis');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const r = createClient({ url: process.env.REDIS_URL });
r.connect();

app.get('/health', (req,res)=>res.json({ok:true}));

// enroll proxy -> face-service
app.post('/enroll', async (req,res)=>{
  // expect multipart form from kiosk; simplified for demo
  res.status(501).json({error:"use direct /face-service/enroll in demo"});
});

// QR token validation endpoint
app.post('/qr/validate', async (req,res)=>{
  const { token } = req.body;
  try {
    const jwt = require('jsonwebtoken');
    const payload = jwt.verify(token, process.env.QR_JWT_SECRET || 'devsecret');
    // Log entry and publish
    const { user_id, action, camera_id } = payload;
    await pool.query("INSERT INTO logs (user_id, name, camera_id, matched, score, ts) VALUES ($1,$2,$3,$4,$5,now())", [user_id, payload.name || null, payload.camera_id || 'qr', true, 0]);
    await r.publish('events', JSON.stringify({event:'recognized', user_id, name: payload.name, camera_id: payload.camera_id || 'qr'}));
    return res.json({ ok: true, user_id });
  } catch (e) {
    return res.status(401).json({ error: 'invalid' });
  }
});

// fingerprint fallback (kiosk posts successful fingerprint verify)
app.post('/fingerprint/verify', async (req,res)=>{
  const { user_id, scanner_id } = req.body;
  // validate scanner permissions in prod
  await pool.query("INSERT INTO logs (user_id, name, camera_id, matched, score, ts) VALUES ($1,$2,$3,$4,$5,now())", [user_id, null, scanner_id || 'fp', true, 0]);
  await r.publish('events', JSON.stringify({event:'recognized', user_id, name:null, camera_id: scanner_id || 'fp'}));
  return res.json({ ok: true });
});

app.listen(process.env.API_PORT || 8000, ()=>console.log("API listening"));

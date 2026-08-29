"""Public-ready chat with server-side accounts and private conversations."""
import html, json, os, re, sqlite3
from pathlib import Path
from urllib.parse import quote
import requests
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app=Flask(__name__); app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY","replace-before-public-deployment"),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
DB=Path(os.environ.get("DATABASE_PATH","data/local_chat.db")); DB.parent.mkdir(parents=True,exist_ok=True)
web=requests.Session(); web.headers["User-Agent"]="PublicLocalChat/1.0"
def con():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
with con() as c:c.executescript("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT);CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY,user_id INTEGER,title TEXT);CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,chat_id INTEGER,role TEXT,text TEXT,sources TEXT DEFAULT '[]');")
def uid():return session.get("uid")
def need():return (jsonify(error="Sign in required."),401) if not uid() else None
def research(q):
 try:
  r=web.get("https://en.wikipedia.org/w/api.php",params={"action":"query","list":"search","srsearch":q,"srlimit":3,"format":"json"},timeout=8);r.raise_for_status()
  return [{"title":x["title"],"url":f"https://en.wikipedia.org/wiki/{quote(x['title'].replace(' ','_'))}","snippet":re.sub("<.*?>","",html.unescape(x.get("snippet","")))} for x in r.json()["query"]["search"]]
 except (requests.RequestException,KeyError):return []
def respond(q,web_on):
 basic={"hi":"Hi! What’s on your mind?","hello":"Hello! How can I help?","help":"I can chat, brainstorm, help you write, explain ideas, and research facts with web search.","thank you":"You’re welcome!","bye":"Bye for now.","tell me a joke":"Why did the computer go to the doctor? It had a virus."}
 if q.lower().strip() in basic and not web_on:return basic[q.lower().strip()],[]
 if not web_on and not any(w in q.lower() for w in ("what is","who is","where","when","capital","history","search","wiki")):return "I’m here to help. Tell me more, or turn on Search the web for researched sources.",[]
 s=research(q);return (f"Based on the available sources: {s[0]['snippet']}" if s else "I couldn’t reach a research source right now."),s
@app.get("/")
def home():return render_template("index.html")
@app.post("/api/register")
def register():
 d=request.get_json()or{};name=d.get("username","").strip();pw=d.get("password","")
 if not re.fullmatch(r"[\w -]{2,40}",name)or len(pw)<8:return jsonify(error="Use a 2–40 character name and an 8+ character password."),400
 try:
  with con()as c:cur=c.execute("INSERT INTO users(username,password_hash)VALUES(?,?)",(name,generate_password_hash(pw)));i=cur.lastrowid
 except sqlite3.IntegrityError:return jsonify(error="That username is already taken."),409
 session.clear();session.update(uid=i,username=name);return jsonify(username=name)
@app.post("/api/login")
def login():
 d=request.get_json()or{};r=con().execute("SELECT * FROM users WHERE username=?",(d.get("username","").strip(),)).fetchone()
 if not r or not check_password_hash(r["password_hash"],d.get("password","")):return jsonify(error="Incorrect username or password."),401
 session.clear();session.update(uid=r["id"],username=r["username"]);return jsonify(username=r["username"])
@app.post("/api/logout")
def logout():session.clear();return jsonify(ok=True)
@app.get("/api/me")
def me():return jsonify(username=session.get("username"))
@app.get("/api/chats")
def chats():
 if(x:=need()):return x
 return jsonify([dict(r)for r in con().execute("SELECT id,title FROM chats WHERE user_id=? ORDER BY id DESC",(uid(),))])
@app.post("/api/chats")
def new():
 if(x:=need()):return x
 with con()as c:cur=c.execute("INSERT INTO chats(user_id,title)VALUES(?,?)",(uid(),"New chat"));return jsonify(id=cur.lastrowid,title="New chat")
@app.post("/api/chats/<int:chat_id>/ask")
def ask(chat_id):
 if(x:=need()):return x
 d=request.get_json()or{};q=d.get("question","").strip()
 if not q:return jsonify(error="Enter a message."),400
 with con()as c:
  if not c.execute("SELECT 1 FROM chats WHERE id=? AND user_id=?",(chat_id,uid())).fetchone():return jsonify(error="Not found"),404
  a,s=respond(q,d.get("research",False));c.execute("INSERT INTO messages(chat_id,role,text)VALUES(?,?,?)",(chat_id,"user",q));c.execute("INSERT INTO messages(chat_id,role,text,sources)VALUES(?,?,?,?)",(chat_id,"assistant",a,json.dumps(s)));c.execute("UPDATE chats SET title=? WHERE id=? AND title='New chat'",(q[:34],chat_id))
 return jsonify(answer=a,sources=s)
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))

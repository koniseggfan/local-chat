"""Public-ready chat with server-side accounts and private conversations."""
import html, json, os, re, sqlite3
from pathlib import Path
from urllib.parse import quote
import requests
from openai import APIError, OpenAI
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app=Flask(__name__); app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY","replace-before-public-deployment"),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE","false").lower()=="true")
DB=Path(os.environ.get("DATABASE_PATH","data/local_chat.db")); DB.parent.mkdir(parents=True,exist_ok=True)
web=requests.Session(); web.headers["User-Agent"]="PublicLocalChat/1.0"
OPENAI_MODEL=os.environ.get("OPENAI_MODEL","gpt-6-luna")
OPENAI_CLIENT=OpenAI(timeout=25.0,max_retries=1) if os.environ.get("OPENAI_API_KEY") else None
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
def respond(q,web_on,history=()):
 if OPENAI_CLIENT:
  messages=[{"role":m["role"],"content":m["text"]} for m in history[-12:] if m["role"] in ("user","assistant")]
  messages.append({"role":"user","content":q})
  params={"model":OPENAI_MODEL,"input":messages,"instructions":"You are Vortex AI, a helpful and accurate assistant. Give clear, direct answers, use recent conversation context, and ask a short clarifying question only when needed. Keep ordinary replies concise while giving enough detail to be useful. When web search is enabled, use the search results to support current factual claims and cite sources.","reasoning":{"effort":"none"},"max_output_tokens":500,"store":False}
  if web_on:params.update(tools=[{"type":"web_search","search_context_size":"low"}],tool_choice="required")
  try:
   response=OPENAI_CLIENT.responses.create(**params)
  except APIError as exc:
   app.logger.warning("OpenAI request failed: %s",type(exc).__name__)
   return "Vortex AI could not reach its model just now. Please try again.",[]
  sources=[]
  for item in response.output:
   for content in getattr(item,"content",[]):
    for annotation in getattr(content,"annotations",[]):
     citation=getattr(annotation,"url_citation",None)
     url=getattr(citation,"url",None) if citation else None
     if url and not any(s["url"]==url for s in sources):sources.append({"title":getattr(citation,"title",None) or url,"url":url})
  return response.output_text.strip() or "I couldn't prepare a reply just now.",sources
 basic={"hi":"Hi! What’s on your mind?","hello":"Hello! How can I help?","help":"I can chat, brainstorm, help you write, explain ideas, and research facts with web search.","thank you":"You’re welcome!","bye":"Bye for now.","tell me a joke":"Why did the computer go to the doctor? It had a virus."}
 if q.lower().strip() in basic:return basic[q.lower().strip()],[]
 if not web_on:return "Vortex AI's model is not configured yet. Add an OpenAI API key in the service settings to enable full AI replies.",[]
 s=research(q);return (f"Based on the available sources: {s[0]['snippet']}" if s else "I couldn’t reach a research source right now."),s
@app.get("/")
def home():return redirect(url_for("chat_page") if uid() else url_for("login_page"))
@app.get("/login")
def login_page():return redirect(url_for("chat_page")) if uid() else render_template("index.html")
@app.get("/chat")
def chat_page():return render_template("chat.html") if uid() else redirect(url_for("login_page"))
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
@app.get("/api/chats/<int:chat_id>")
def get_chat(chat_id):
 if(x:=need()):return x
 with con()as c:
  if not c.execute("SELECT 1 FROM chats WHERE id=? AND user_id=?",(chat_id,uid())).fetchone():return jsonify(error="Not found"),404
  return jsonify(messages=[dict(r,sources=json.loads(r["sources"])) for r in c.execute("SELECT role,text,sources FROM messages WHERE chat_id=? ORDER BY id",(chat_id,))])
@app.post("/api/chats/<int:chat_id>/ask")
def ask(chat_id):
 if(x:=need()):return x
 d=request.get_json()or{};q=d.get("question","").strip()
 if not q:return jsonify(error="Enter a message."),400
 with con()as c:
  if not c.execute("SELECT 1 FROM chats WHERE id=? AND user_id=?",(chat_id,uid())).fetchone():return jsonify(error="Not found"),404
  history=[dict(r) for r in c.execute("SELECT role,text FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 12",(chat_id,))][::-1]
  a,s=respond(q,d.get("research",False),history)
  c.execute("INSERT INTO messages(chat_id,role,text)VALUES(?,?,?)",(chat_id,"user",q))
  c.execute("INSERT INTO messages(chat_id,role,text,sources)VALUES(?,?,?,?)",(chat_id,"assistant",a,json.dumps(s)))
  c.execute("UPDATE chats SET title=? WHERE id=? AND title='New chat'",(q[:34],chat_id))
 return jsonify(answer=a,sources=s)
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))

import sys
import os
import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
from pymongo import MongoClient
from PyPDF2 import PdfReader
import chardet

# optional langchain-style imports (if installed)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import CharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
except Exception:
    FAISS = None
    CharacterTextSplitter = None
    HuggingFaceEmbeddings = None
    ChatGoogleGenerativeAI = None
    ChatPromptTemplate = None
    RunnablePassthrough = None

# ---- Config ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
VSTORE_FOLDER = os.path.join(BASE_DIR, "vectorstores")

# Inserted API key as requested (you may replace or use env var)
# Note: storing keys in code is not recommended for production.
API_KEY = "AIzaSyC_IJw4N10A_Dk1ZYGpOUD42_KEDI6EEz4"

# Alternative (safer) - uncomment to read from env:
# API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

app = Flask(__name__, static_folder="static", template_folder="templates")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VSTORE_FOLDER, exist_ok=True)

# --- MongoDB (ensure MongoDB is running or change URI) ---
client = MongoClient("mongodb://localhost:27017/")
mongo = client["langchain_chat"]

# --- embeddings setup (if available) ---
if HuggingFaceEmbeddings:
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception:
        embeddings = None
else:
    embeddings = None

# ---------------- HOME / UPLOAD ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "No file provided", 400
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # read file contents
        docs = []
        if filename.lower().endswith(".pdf"):
            text = ""
            reader = PdfReader(filepath)
            for page in reader.pages:
                p = page.extract_text()
                if p:
                    text += p + "\n"
            if text.strip() == "":
                return "ERROR: PDF has no readable text!", 400
            docs.append(text)
        else:
            raw = open(filepath, "rb").read()
            result = chardet.detect(raw)
            encoding = result.get("encoding") or "utf-8"
            with open(filepath, "r", encoding=encoding, errors="ignore") as f:
                data = f.read()
            if data.strip() == "":
                return "ERROR: Text file is empty!", 400
            docs.append(data)

        # create vectorstore if deps present
        vs_path = None
        if FAISS and CharacterTextSplitter and embeddings:
            splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            texts = splitter.create_documents(docs)
            if len(texts) == 0:
                return "ERROR: Could not split file into chunks!", 400
            vector_db = FAISS.from_documents(texts, embeddings)
            vs_path = os.path.join(VSTORE_FOLDER, filename)
            os.makedirs(vs_path, exist_ok=True)
            vector_db.save_local(vs_path)

        # save metadata
        mongo.documents.insert_one({
            "filename": filename,
            "vectorstore_path": vs_path,
            "uploaded_at": datetime.datetime.utcnow()
        })

        return redirect(url_for("chat", filename=filename))

    docs = [d["filename"] for d in mongo.documents.find({})]
    return render_template("index.html", docs=docs)

# ---------------- Read document text endpoint ----------------
@app.route("/api/read", methods=["GET"])
def api_read():
    filename = request.args.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    doc = mongo.documents.find_one({"filename": filename})
    if not doc:
        return jsonify({"error": "document not found"}), 404
    path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(path):
        return jsonify({"error": "file missing on disk"}), 404

    # read text
    text = ""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(path)
        for page in reader.pages:
            p = page.extract_text()
            if p:
                text += p + "\n"
    else:
        raw = open(path, "rb").read()
        enc = chardet.detect(raw)["encoding"] or "utf-8"
        text = open(path, "r", encoding=enc, errors="ignore").read()

    return jsonify({"text": text})

# ---------------- Answer endpoint (JSON) ----------------
@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json() or {}
    filename = data.get("filename")
    question = data.get("question", "").strip()
    if not filename or question == "":
        return jsonify({"error": "filename and question required"}), 400

    doc = mongo.documents.find_one({"filename": filename})
    if not doc:
        return jsonify({"error": "document not found"}), 404

    answer_text = ""
    try:
        if FAISS and embeddings and ChatGoogleGenerativeAI and ChatPromptTemplate and RunnablePassthrough and doc.get("vectorstore_path"):
            vector_db = FAISS.load_local(
                doc["vectorstore_path"],
                embeddings,
                allow_dangerous_deserialization=True
            )
            retriever = vector_db.as_retriever()
            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=API_KEY)

            template = """Answer the question based ONLY on the context below.

Context:
{context}

Question: {question}

Answer:"""

            prompt = ChatPromptTemplate.from_template(template)

            chain = (
                {"context": retriever, "question": RunnablePassthrough()}
                | prompt
                | llm
            )

            result = chain.invoke(question)
            answer_text = result.content if hasattr(result, "content") else str(result)
        else:
            # fallback: return snippet and explain LLM not available
            path = os.path.join(UPLOAD_FOLDER, filename)
            raw = open(path, "rb").read()
            enc = chardet.detect(raw)["encoding"] or "utf-8"
            full_text = open(path, "r", encoding=enc, errors="ignore").read()
            snippet = full_text[:1500]
            answer_text = "(Fallback answer — LLM chain not configured or vectorstore missing)\n\n" \
                          "Here's a document excerpt to help answer your question:\n\n" + snippet
    except Exception as e:
        # send the error back so the client can show it (useful for debugging)
        answer_text = f"Error while answering: {e}"

    # Save chat history
    mongo.chats.insert_one({
        "doc_filename": filename,
        "question": question,
        "answer": answer_text,
        "timestamp": datetime.datetime.utcnow()
    })

    return jsonify({"answer": answer_text})

# ---------------- Chat page ----------------
@app.route("/chat/<filename>", methods=["GET"])
def chat(filename):
    docs = [d["filename"] for d in mongo.documents.find({})]
    history_docs = mongo.chats.find({"doc_filename": filename}).sort("timestamp", 1)
    history = [{"q": h["question"], "a": h["answer"], "ts": h["timestamp"].isoformat()} for h in history_docs]
    return render_template("chat.html", active_doc=filename, docs=docs, history=history)

# favicon route (optional)
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)

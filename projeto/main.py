"""
IoT Estoque — Backend FastAPI
Recebe movimentações do ESP32 e serve o frontend com histórico.

Instalar:
    pip install fastapi uvicorn

Rodar:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Para expor ao Wokwi use ngrok:
    ngrok http 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import json, os

app = FastAPI(title="IoT Estoque API", version="1.0.0")

# ── CORS (permite o Wokwi e o front chamar a API) ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Banco de dados simulado (arquivo JSON) ─────────────────
DB_FILE = "movimentacoes.json"

def carregar_db() -> list:
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_db(dados: list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=str)

# ── Tabelas locais (espelham o ESP32) ──────────────────────
FUNCIONARIOS = {
    1: "Ana Lima",
    2: "Bruno Costa",
    3: "Carla Dias",
    4: "Diego Nunes",
    5: "Eva Rocha",
}

PRODUTOS = {
    1: {"nome": "Parafuso M6",   "unidade": "pcs"},
    2: {"nome": "Cimento CP-II", "unidade": "sac"},
    3: {"nome": "Cabo Elétrico", "unidade": "mts"},
    4: {"nome": "Tinta Látex",   "unidade": "lts"},
    5: {"nome": "Tubo PVC 1/2",  "unidade": "pcs"},
    6: {"nome": "Rolo de Lixa",  "unidade": "pcs"},
    7: {"nome": "Fio Terra 2.5", "unidade": "mts"},
    8: {"nome": "Disjuntor 20A", "unidade": "pcs"},
}

# ── Schemas ────────────────────────────────────────────────
class MovimentacaoEntrada(BaseModel):
    funcionario_id: int = Field(..., ge=1, le=5)
    acao: str           = Field(..., pattern="^(entrada|saida)$")
    produto_id: int     = Field(..., ge=1, le=8)
    quantidade: int     = Field(..., ge=1, le=999)

class MovimentacaoSaida(BaseModel):
    id: int
    funcionario_id: int
    funcionario_nome: str
    acao: str
    produto_id: int
    produto_nome: str
    produto_unidade: str
    quantidade: int
    data_hora: str

# ── Rotas ──────────────────────────────────────────────────

@app.post("/movimentacoes", response_model=MovimentacaoSaida, status_code=201)
def registrar_movimentacao(payload: MovimentacaoEntrada):
    """Recebe dados do ESP32 e registra a movimentação."""

    if payload.funcionario_id not in FUNCIONARIOS:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    if payload.produto_id not in PRODUTOS:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    db = carregar_db()

    novo_id = (db[-1]["id"] + 1) if db else 1
    produto  = PRODUTOS[payload.produto_id]

    registro = {
        "id":               novo_id,
        "funcionario_id":   payload.funcionario_id,
        "funcionario_nome": FUNCIONARIOS[payload.funcionario_id],
        "acao":             payload.acao,
        "produto_id":       payload.produto_id,
        "produto_nome":     produto["nome"],
        "produto_unidade":  produto["unidade"],
        "quantidade":       payload.quantidade,
        "data_hora":        datetime.now().isoformat(timespec="seconds"),
    }

    db.append(registro)
    salvar_db(db)

    print(f"[{registro['data_hora']}] {registro['funcionario_nome']} — "
          f"{registro['acao'].upper()} {registro['quantidade']}x {registro['produto_nome']}")

    return registro


@app.get("/movimentacoes", response_model=list[MovimentacaoSaida])
def listar_movimentacoes(limite: int = 100):
    """Retorna o histórico de movimentações (mais recentes primeiro)."""
    db = carregar_db()
    return list(reversed(db))[-limite:]


@app.get("/movimentacoes/{mov_id}", response_model=MovimentacaoSaida)
def buscar_movimentacao(mov_id: int):
    db = carregar_db()
    for m in db:
        if m["id"] == mov_id:
            return m
    raise HTTPException(status_code=404, detail="Movimentação não encontrada")


@app.delete("/movimentacoes", status_code=204)
def limpar_historico():
    """Apaga todo o histórico (útil para testes)."""
    salvar_db([])


@app.get("/status")
def status():
    db = carregar_db()
    return {
        "status": "online",
        "total_movimentacoes": len(db),
        "ultima_movimentacao": db[-1]["data_hora"] if db else None,
    }


# ── Serve o frontend estático ──────────────────────────────
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")

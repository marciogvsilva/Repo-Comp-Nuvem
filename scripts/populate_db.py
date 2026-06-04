#!/usr/bin/env python3
"""Script para popular a base de dados com produtos artificiais"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/app/data/products.db"
NUM_PRODUCTS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

categorias = ["Eletrônicos", "Livros", "Roupas", "Alimentos", "Móveis", "Esportes", "Beleza", "Brinquedos"]

db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create table if not exists
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT NOT NULL,
        preco REAL NOT NULL,
        estoque INTEGER NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )
    """
)

# Insert products
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

for i in range(1, NUM_PRODUCTS + 1):
    nome = f"Produto {i}"
    categoria = categorias[(i - 1) % len(categorias)]
    preco = round(10.0 + (i % 1000) * 0.5, 2)
    estoque = (i % 500) + 1
    
    cursor.execute(
        """
        INSERT INTO produtos (nome, categoria, preco, estoque, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (nome, categoria, preco, estoque, now, now),
    )

conn.commit()
count = cursor.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
conn.close()

print(f"✅ Banco populado com {count} produtos em {DB_PATH}")

# loto_plus_pronosticos.py
# ------------------------------------------------------------
# Pronósticos Loto Plus (Argentina) usando:
#  - Estadística (frecuencia + "antigüedad"/recency)
#  - (Opcional) IA: Transformer (PyTorch) multi-label
#
# ✅ Corre SIN argumentos (usa defaults):
#    IN : loto_plus_incremental.xlsx
#    OUT: pronosticos.xlsx
#
# Ejemplos:
#   python loto_plus_pronosticos.py
#   python loto_plus_pronosticos.py --use_transformer --epochs 40 --seq 30
#   python loto_plus_pronosticos.py --in "loto_plus_incremental.xlsx" --out "pronosticos.xlsx"
# ------------------------------------------------------------

from __future__ import annotations

import argparse
import os
import sys
import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# IA opcional
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_OK = True
except Exception:
    TORCH_OK = False


# =========================
# UTILIDADES
# =========================

def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def resolve_path(p: str) -> str:
    """
    Si el archivo no existe en cwd, intenta en el directorio del script.
    """
    if os.path.exists(p):
        return p
    alt = os.path.join(_script_dir(), p)
    if os.path.exists(alt):
        return alt
    return p  # devolvemos igual para que el error sea claro


def safe_int(x: str) -> Optional[int]:
    try:
        return int(str(x).strip())
    except Exception:
        return None


def parse_six_numbers(s: str) -> List[int]:
    """
    Convierte '11-12-17-27-35-41' o '11 12 17 27 35 41' a [11,12,17,27,35,41].
    Admite '00' => 0.
    """
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return []
    txt = str(s).strip()
    if not txt:
        return []
    # unificamos separadores
    txt = txt.replace(",", "-").replace(" ", "-").replace("–", "-").replace("—", "-")
    parts = [p for p in txt.split("-") if p != ""]
    nums: List[int] = []
    for p in parts:
        v = safe_int(p)
        if v is not None:
            nums.append(v)
    return nums


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if TORCH_OK:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


# =========================
# CARGA Y LIMPIEZA
# =========================

REQUIRED_COLS = ["sorteo", "fecha", "numero_plus", "tradicional", "match", "desquite", "sale_o_sale"]
MODALITIES = ["tradicional", "match", "desquite", "sale_o_sale"]


def load_data(in_path: str) -> pd.DataFrame:
    in_path = resolve_path(in_path)
    if not os.path.exists(in_path):
        raise FileNotFoundError(
            f"No se encuentra el archivo de entrada: {in_path}\n"
            f"Tip: colocalo en la misma carpeta del script o pasá --in con la ruta completa."
        )

    ext = os.path.splitext(in_path)[1].lower()
    if ext in [".xlsx", ".xlsm", ".xls"]:
        df = pd.read_excel(in_path)
    elif ext in [".csv", ".txt"]:
        df = pd.read_csv(in_path)
    else:
        raise ValueError(f"Formato no soportado: {ext}. Usá .xlsx o .csv")

    # Normalizamos nombres de columnas
    df.columns = [str(c).strip().lower() for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas en el archivo: {missing}\n"
            f"Se esperan: {REQUIRED_COLS}"
        )

    # Orden por sorteo ascendente (importante para series)
    df = df.copy()
    df["sorteo"] = pd.to_numeric(df["sorteo"], errors="coerce")
    df = df.dropna(subset=["sorteo"]).sort_values("sorteo").reset_index(drop=True)

    # Fecha (la dejamos como texto si viene raro, pero intentamos parsear)
    # No es crítica para el modelo.
    df["fecha_str"] = df["fecha"].astype(str)

    # número plus
    df["numero_plus"] = pd.to_numeric(df["numero_plus"], errors="coerce").fillna(-1).astype(int)

    # columnas de 6 números
    for m in MODALITIES:
        df[m] = df[m].apply(parse_six_numbers)

    return df


# =========================
# ESTADÍSTICA: FRECUENCIA + RECENCIA
# =========================

@dataclass
class StatsResult:
    freq: np.ndarray        # (n_numbers,)
    recency: np.ndarray     # (n_numbers,) 0=salió recién, mayor=más "atrasado"
    score: np.ndarray       # (n_numbers,) combinación normalizada


def compute_freq_recency(draws: List[List[int]], n_numbers: int, recent_k: int = 200) -> StatsResult:
    """
    draws: lista cronológica ASCENDENTE
    freq: conteo en las últimas recent_k tiradas
    recency: cuántos sorteos desde la última aparición (en todo el histórico disponible)
    score: mezcla simple freq_norm + recency_norm
    """
    if len(draws) == 0:
        raise ValueError("No hay tiradas para calcular stats.")

    # frecuencia en ventana
    window = draws[-recent_k:] if recent_k > 0 else draws
    freq = np.zeros(n_numbers, dtype=np.float64)
    for d in window:
        for x in d:
            if 0 <= x < n_numbers:
                freq[x] += 1.0

    # recencia: desde el final hacia atrás
    recency = np.full(n_numbers, fill_value=len(draws), dtype=np.float64)
    last_seen = {i: None for i in range(n_numbers)}
    for idx in range(len(draws) - 1, -1, -1):
        for x in draws[idx]:
            if 0 <= x < n_numbers and last_seen[x] is None:
                last_seen[x] = idx
    last_index = len(draws) - 1
    for i in range(n_numbers):
        if last_seen[i] is not None:
            recency[i] = float(last_index - last_seen[i])
        else:
            recency[i] = float(len(draws))  # nunca salió (en tus datos)

    # normalizaciones suaves
    freq_norm = (freq - freq.min()) / (freq.max() - freq.min() + 1e-9)
    rec_norm = (recency - recency.min()) / (recency.max() - recency.min() + 1e-9)

    # score base: balancea calientes (freq) y atrasados (recency)
    score = 0.55 * freq_norm + 0.45 * rec_norm

    return StatsResult(freq=freq, recency=recency, score=score)


def weighted_sample_without_replacement(weights: np.ndarray, k: int, rng: np.random.Generator) -> List[int]:
    """
    Elige k índices sin reemplazo proporcional a weights (si hay pesos 0, pueden salir igual si todo es 0).
    """
    w = np.array(weights, dtype=np.float64)
    w = np.clip(w, 0.0, None)

    if w.sum() <= 0:
        # todo cero -> uniforme
        p = np.ones_like(w) / len(w)
    else:
        p = w / w.sum()

    # Muestreo sin reemplazo
    choices = rng.choice(len(w), size=k, replace=False, p=p)
    return sorted([int(x) for x in choices])


# =========================
# IA: TRANSFORMER (multi-label)
# =========================

class DrawSeqDataset(Dataset):
    def __init__(self, X: np.ndarray, Y: np.ndarray):
        self.X = X.astype(np.float32)
        self.Y = Y.astype(np.float32)

    def __len__(self) -> int:
        return self.X.shape[0]

    def __getitem__(self, idx: int):
        return self.X[idx], self.Y[idx]


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D)
        T = x.size(1)
        return x + self.pe[:, :T, :]


class TransformerPredictor(nn.Module):
    def __init__(self, n_numbers: int, d_model: int = 128, nhead: int = 8, nlayers: int = 3, dropout: float = 0.1, max_len: int = 256):
        super().__init__()
        self.in_proj = nn.Linear(n_numbers, d_model)
        self.pos = PositionalEncoding(d_model, max_len=max_len)
        enc_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=d_model * 4, dropout=dropout, batch_first=True)
        self.enc = nn.TransformerEncoder(enc_layer, num_layers=nlayers)
        self.out = nn.Linear(d_model, n_numbers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, n_numbers)
        h = self.in_proj(x)
        h = self.pos(h)
        h = self.enc(h)
        # usamos el último paso
        last = h[:, -1, :]
        logits = self.out(last)
        return logits


def draws_to_multi_hot(draws: List[List[int]], n_numbers: int) -> np.ndarray:
    X = np.zeros((len(draws), n_numbers), dtype=np.float32)
    for i, d in enumerate(draws):
        for x in d:
            if 0 <= x < n_numbers:
                X[i, x] = 1.0
    return X


def make_sequences(draws: List[List[int]], n_numbers: int, seq_len: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve X: (N, seq_len, n_numbers), Y: (N, n_numbers)
    donde Y es la próxima tirada (multi-hot).
    """
    mh = draws_to_multi_hot(draws, n_numbers)
    if len(draws) <= seq_len:
        raise ValueError(f"Histórico insuficiente: necesitas > seq_len. len={len(draws)}, seq_len={seq_len}")

    Xs, Ys = [], []
    for i in range(seq_len, len(draws)):
        Xs.append(mh[i - seq_len:i, :])
        Ys.append(mh[i, :])
    return np.stack(Xs, axis=0), np.stack(Ys, axis=0)


def train_transformer(draws: List[List[int]], n_numbers: int, seq_len: int, epochs: int, batch: int, lr: float,
                      d_model: int, nhead: int, nlayers: int, dropout: float, seed: int) -> Tuple[TransformerPredictor, np.ndarray]:
    if not TORCH_OK:
        raise RuntimeError("PyTorch no está instalado/importable. Instalá torch o ejecutá sin --use_transformer.")

    set_all_seeds(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    X, Y = make_sequences(draws, n_numbers, seq_len)
    # split simple train/val (último 15% para validar)
    n = X.shape[0]
    cut = max(1, int(n * 0.85))
    Xtr, Ytr = X[:cut], Y[:cut]
    Xva, Yva = X[cut:], Y[cut:]

    ds_tr = DrawSeqDataset(Xtr, Ytr)
    ds_va = DrawSeqDataset(Xva, Yva)

    dl_tr = DataLoader(ds_tr, batch_size=batch, shuffle=True, drop_last=False)
    dl_va = DataLoader(ds_va, batch_size=batch, shuffle=False, drop_last=False)

    model = TransformerPredictor(n_numbers=n_numbers, d_model=d_model, nhead=nhead, nlayers=nlayers, dropout=dropout, max_len=max(256, seq_len + 5))
    model.to(device)

    crit = nn.BCEWithLogitsLoss()
    opt = torch.optim.AdamW(model.parameters(), lr=lr)

    best_val = float("inf")
    best_state = None

    for ep in range(1, epochs + 1):
        model.train()
        tr_loss = 0.0
        for xb, yb in dl_tr:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tr_loss += float(loss.item()) * xb.size(0)
        tr_loss /= max(1, len(ds_tr))

        model.eval()
        va_loss = 0.0
        with torch.no_grad():
            for xb, yb in dl_va:
                xb = xb.to(device)
                yb = yb.to(device)
                logits = model(xb)
                loss = crit(logits, yb)
                va_loss += float(loss.item()) * xb.size(0)
        va_loss /= max(1, len(ds_va))

        # print corto (sin “cháchara”)
        print(f"[Transformer] epoch {ep}/{epochs} - train {tr_loss:.4f} - val {va_loss:.4f} - device {device}")

        if va_loss < best_val:
            best_val = va_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    # Probabilidades del próximo sorteo, usando la última ventana real
    last_seq = draws_to_multi_hot(draws[-seq_len:], n_numbers)[None, :, :]  # (1, T, n_numbers)
    model.eval()
    with torch.no_grad():
        xb = torch.from_numpy(last_seq.astype(np.float32)).to(device)
        logits = model(xb)
        probs = torch.sigmoid(logits).detach().cpu().numpy().reshape(-1)

    return model, probs


# =========================
# PRONÓSTICOS
# =========================

def suggest_plus(df: pd.DataFrame, recent_k: int, seed: int) -> int:
    """
    Sugiere numero_plus (0..9) por frecuencia reciente + recency.
    """
    rng = np.random.default_rng(seed)
    plus = df["numero_plus"].to_numpy()
    plus = plus[plus >= 0]
    if len(plus) == 0:
        return int(rng.integers(0, 10))

    window = plus[-recent_k:] if recent_k > 0 else plus
    freq = np.zeros(10, dtype=np.float64)
    for p in window:
        if 0 <= int(p) <= 9:
            freq[int(p)] += 1.0

    # recency
    rec = np.full(10, fill_value=len(plus), dtype=np.float64)
    last_seen = [None] * 10
    for i in range(len(plus) - 1, -1, -1):
        p = int(plus[i])
        if 0 <= p <= 9 and last_seen[p] is None:
            last_seen[p] = i
    last_idx = len(plus) - 1
    for d in range(10):
        if last_seen[d] is not None:
            rec[d] = float(last_idx - last_seen[d])

    freq_n = (freq - freq.min()) / (freq.max() - freq.min() + 1e-9)
    rec_n = (rec - rec.min()) / (rec.max() - rec.min() + 1e-9)
    score = 0.6 * freq_n + 0.4 * rec_n

    # elegimos top con un toque aleatorio
    probs = score + 1e-6
    probs = probs / probs.sum()
    return int(rng.choice(np.arange(10), p=probs))


def build_pronosticos_for_modality(
    draws: List[List[int]],
    n_numbers: int,
    recent_k: int,
    n_preds: int,
    seed: int,
    stats_only: bool,
    transformer_probs: Optional[np.ndarray],
    alpha: float,
) -> List[List[int]]:
    """
    alpha: peso del transformer (0..1). score_final = (1-alpha)*score_stats + alpha*probs_transformer
    """
    rng = np.random.default_rng(seed)

    st = compute_freq_recency(draws, n_numbers=n_numbers, recent_k=recent_k)
    score_stats = st.score

    if (not stats_only) and transformer_probs is not None:
        # normalizamos probs para que escale parecido
        pt = np.array(transformer_probs, dtype=np.float64)
        pt = np.clip(pt, 0.0, 1.0)
        pt = (pt - pt.min()) / (pt.max() - pt.min() + 1e-9)
        score = (1.0 - alpha) * score_stats + alpha * pt
    else:
        score = score_stats

    pronos: List[List[int]] = []
    for i in range(n_preds):
        # Le damos un poquito de ruido para no repetir igual
        noise = rng.normal(loc=0.0, scale=0.03, size=score.shape[0])
        w = np.clip(score + noise, 0.0, None)
        pick = weighted_sample_without_replacement(w, k=6, rng=rng)
        pronos.append(pick)
    return pronos


# =========================
# EXPORT EXCEL
# =========================

def export_excel(
    out_path: str,
    df: pd.DataFrame,
    stats_by_mod: Dict[str, StatsResult],
    probs_by_mod: Dict[str, Optional[np.ndarray]],
    pronos_by_mod: Dict[str, List[List[int]]],
    plus_suggested: int,
) -> str:
    out_path = resolve_path(out_path)
    out_dir = os.path.dirname(out_path) or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)

    # Tablas para exportar
    base = df[["sorteo", "fecha_str", "numero_plus"] + MODALITIES].copy()

    with pd.ExcelWriter(out_path, engine="openpyxl") as wr:
        base.to_excel(wr, index=False, sheet_name="Datos_Limpios")

        for m in MODALITIES:
            st = stats_by_mod[m]
            tab = pd.DataFrame({
                "numero": np.arange(len(st.freq)),
                "freq_recent": st.freq,
                "recency": st.recency,
                "score_stats": st.score,
            })
            tab.to_excel(wr, index=False, sheet_name=f"Stats_{m[:25]}")

            p = probs_by_mod.get(m)
            if p is not None:
                tabp = pd.DataFrame({"numero": np.arange(len(p)), "prob_transformer": p})
                tabp.to_excel(wr, index=False, sheet_name=f"Probs_{m[:25]}")

        # Pronósticos
        rows = []
        for m in MODALITIES:
            for idx, comb in enumerate(pronos_by_mod[m], start=1):
                rows.append({
                    "modalidad": m,
                    "nro_pronostico": idx,
                    "combinacion": "-".join(f"{x:02d}" for x in comb),
                })
        pr = pd.DataFrame(rows)
        pr.to_excel(wr, index=False, sheet_name="Pronosticos")

        # Plus
        pd.DataFrame([{"numero_plus_sugerido": plus_suggested}]).to_excel(wr, index=False, sheet_name="Numero_Plus")

    return out_path


# =========================
# MAIN
# =========================

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Pronósticos Loto Plus (stats + Transformer opcional)")

    # ✅ Defaults adentro del programa (tu pedido)
    ap.add_argument("--in", dest="in_path", default="loto_plus_incremental.xlsx",
                    help="Archivo de entrada (default: loto_plus_incremental.xlsx)")
    ap.add_argument("--out", dest="out_path", default="pronosticos.xlsx",
                    help="Archivo de salida (default: pronosticos.xlsx)")

    ap.add_argument("--recent", dest="recent_k", type=int, default=200,
                    help="Ventana reciente para frecuencia (default: 200)")
    ap.add_argument("--preds", dest="n_preds", type=int, default=12,
                    help="Cantidad de pronósticos por modalidad (default: 12)")
    ap.add_argument("--seed", dest="seed", type=int, default=42, help="Seed (default: 42)")

    ap.add_argument("--min", dest="n_min", type=int, default=0, help="Mínimo número (default: 0)")
    ap.add_argument("--max", dest="n_max", type=int, default=45, help="Máximo número (default: 45)")

    ap.add_argument("--use_transformer", action="store_true", help="Activa IA Transformer (PyTorch)")

    ap.add_argument("--seq", dest="seq_len", type=int, default=30, help="Largo de secuencia (default: 30)")
    ap.add_argument("--epochs", dest="epochs", type=int, default=35, help="Epochs (default: 35)")
    ap.add_argument("--batch", dest="batch", type=int, default=64, help="Batch (default: 64)")
    ap.add_argument("--lr", dest="lr", type=float, default=2e-3, help="Learning rate (default: 2e-3)")

    ap.add_argument("--dmodel", dest="d_model", type=int, default=128, help="Dim modelo (default: 128)")
    ap.add_argument("--heads", dest="nhead", type=int, default=8, help="Heads (default: 8)")
    ap.add_argument("--layers", dest="layers", type=int, default=3, help="Layers (default: 3)")
    ap.add_argument("--dropout", dest="dropout", type=float, default=0.10, help="Dropout (default: 0.10)")

    ap.add_argument("--alpha", dest="alpha", type=float, default=0.55,
                    help="Peso del transformer vs stats (0..1). default: 0.55")

    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)

    args.n_min = int(args.n_min)
    args.n_max = int(args.n_max)
    if args.n_min > args.n_max:
        args.n_min, args.n_max = args.n_max, args.n_min

    # n_numbers = max+1 (incluye 0..45)
    n_numbers = args.n_max + 1
    if args.n_min != 0:
        print("Nota: este script asume universo 0..max. Si querés recortar, lo ajustamos, pero no lo recomiendo.", file=sys.stderr)

    args.alpha = float(args.alpha)
    args.alpha = max(0.0, min(1.0, args.alpha))

    set_all_seeds(int(args.seed))

    df = load_data(args.in_path)

    # Preparamos draws por modalidad
    draws_by_mod: Dict[str, List[List[int]]] = {}
    for m in MODALITIES:
        draws = df[m].tolist()
        # filtramos a rango 0..max y tamaño 6
        clean_draws = []
        for d in draws:
            dd = [clamp(int(x), 0, args.n_max) for x in d if x is not None]
            dd = sorted(list(dict.fromkeys(dd)))  # únicos conservando orden
            # Si por datos raros quedan !=6, intentamos arreglar conservador
            if len(dd) >= 6:
                dd = dd[:6]
            # si quedan menos (dato faltante), lo ignoramos (para no ensuciar el modelo)
            if len(dd) == 6:
                clean_draws.append(dd)
        if len(clean_draws) < 60:
            raise ValueError(f"Pocos datos válidos para {m}: {len(clean_draws)} (necesito al menos ~60).")
        draws_by_mod[m] = clean_draws

    # Stats
    stats_by_mod: Dict[str, StatsResult] = {}
    for m in MODALITIES:
        stats_by_mod[m] = compute_freq_recency(draws_by_mod[m], n_numbers=n_numbers, recent_k=int(args.recent_k))

    # IA Transformer (opcional)
    probs_by_mod: Dict[str, Optional[np.ndarray]] = {m: None for m in MODALITIES}
    if args.use_transformer:
        if not TORCH_OK:
            raise RuntimeError("Pediste --use_transformer pero PyTorch no está disponible. Instalá torch o quitá el flag.")

        for m in MODALITIES:
            print(f"\n=== Entrenando Transformer para: {m} ===")
            _, probs = train_transformer(
                draws=draws_by_mod[m],
                n_numbers=n_numbers,
                seq_len=int(args.seq_len),
                epochs=int(args.epochs),
                batch=int(args.batch),
                lr=float(args.lr),
                d_model=int(args.d_model),
                nhead=int(args.nhead),
                nlayers=int(args.layers),
                dropout=float(args.dropout),
                seed=int(args.seed),
            )
            probs_by_mod[m] = probs

    # Pronósticos
    pronos_by_mod: Dict[str, List[List[int]]] = {}
    for m in MODALITIES:
        pronos_by_mod[m] = build_pronosticos_for_modality(
            draws=draws_by_mod[m],
            n_numbers=n_numbers,
            recent_k=int(args.recent_k),
            n_preds=int(args.n_preds),
            seed=int(args.seed) + 7,  # seed distinta para que no “claven” igual
            stats_only=(not args.use_transformer),
            transformer_probs=probs_by_mod[m],
            alpha=float(args.alpha),
        )

    plus = suggest_plus(df, recent_k=int(args.recent_k), seed=int(args.seed) + 99)

    out_path = export_excel(
        out_path=args.out_path,
        df=df,
        stats_by_mod=stats_by_mod,
        probs_by_mod=probs_by_mod,
        pronos_by_mod=pronos_by_mod,
        plus_suggested=plus,
    )

    print("\nOK ✅ Exportado:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

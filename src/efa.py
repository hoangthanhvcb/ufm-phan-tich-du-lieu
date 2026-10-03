"""Phân tích nhân tố khám phá (EFA) - KMO, Bartlett, ma trận nhân tố xoay.

Lưu ý tương thích: thư viện `factor_analyzer` gọi
`sklearn.utils.check_array(force_all_finite=..., estimator=...)`.
Hai tham số này đã bị XOÁ ở scikit-learn >= 1.7, nên trên môi trường
(Streamlit Cloud, Python 3.14) `fa.fit()` ném TypeError.

Vì vậy module này có engine dự phòng thuần NumPy (principal axis + xoay
varimax). Nếu thư viện lỗi, tự động chuyển sang engine dự phòng nên phần
"Độ tin cậy & EFA" không bao giờ bị đổ vỡ.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats

try:
    from factor_analyzer import FactorAnalyzer

    HAS_FACTOR_ANALYZER = True
except Exception:  # noqa: BLE001
    FactorAnalyzer = None
    HAS_FACTOR_ANALYZER = False


# ---------------------------------------------------------------------------
# Làm sạch dữ liệu trước khi phân tích
# ---------------------------------------------------------------------------
def prepare(df: pd.DataFrame, min_items: int = 3) -> pd.DataFrame:
    """Chỉ giữ biến số, bỏ NaN/inf và biến không biến thiên.

    Ma trận tương quan bị khoái đại nếu cột có phương sai = 0 nên phải loại.
    """
    out = df.copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan).dropna()
    keep = [c for c in out.columns if out[c].nunique() > 1]
    out = out[keep]
    if out.shape[1] < min_items or out.shape[0] < out.shape[1]:
        raise ValueError(
            f"Cần ít nhất {min_items} biến có biến thiên và số dòng ≥ số biến "
            f"(hiện có {out.shape[1]} biến, {out.shape[0]} dòng hợp lệ)."
        )
    return out


def _corr(df: pd.DataFrame) -> np.ndarray:
    r = df.corr().to_numpy(dtype=float)
    if not np.all(np.isfinite(r)):
        r = np.nan_to_num(r, nan=0.0)
    return np.nan_to_num(r, nan=0.0)


# ---------------------------------------------------------------------------
# KMO & Bartlett (tự tính để không phụ thuộc thư viện)
# ---------------------------------------------------------------------------
def run_kmo_bartlett(df: pd.DataFrame) -> dict:
    """Tính chỉ số KMO toàn phần và kiểm định Bartlett."""
    df = prepare(df, min_items=2)
    n_obs, p = df.shape
    r = _corr(df)
    r_inv = np.linalg.pinv(r)

    if p > 1 and n_obs > p:
        diag = np.sqrt(np.outer(np.diag(r_inv), np.diag(r_inv)))
        partial = np.where(diag != 0, -r_inv / np.where(diag == 0, 1, diag), 0.0)
        np.fill_diagonal(partial, 0.0)
        num = r**2
        np.fill_diagonal(num, 0.0)
        den = num + partial**2
        total_num, total_den = num.sum(), den.sum()
        kmo = float(total_num / total_den) if total_den > 0 else 0.0
    else:
        kmo = 0.0

    det = float(np.linalg.det(r))
    dof = int(p * (p - 1) / 2)
    if det > 0 and n_obs > p:
        chi2 = -((n_obs - 1) - (2 * p + 5) / 6) * np.log(det)
        p_value = float(stats.chi2.sf(chi2, dof)) if dof > 0 else 0.0
    else:
        chi2, p_value = 0.0, 1.0

    return {
        "kmo": kmo,
        "bartlett_chi2": float(chi2),
        "bartlett_p": p_value,
        "dof": dof,
        "kmo_ok": kmo >= 0.5,
        "bartlett_ok": p_value < 0.05,
    }


# ---------------------------------------------------------------------------
# Engine dự phòng: principal axis + xoay varimax (thuần NumPy)
# ---------------------------------------------------------------------------
def _varimax_value(L: np.ndarray) -> float:
    """V = Σ_j [Σ_i λ⁴ − (1/p)(Σ_i λ²)²]."""
    p = L.shape[0]
    col_ss = (L**2).sum(axis=1)
    return float((L**4).sum() - (col_ss**2).sum() / p)


def _varimax(loadings: np.ndarray, max_sweeps: int = 100) -> np.ndarray:
    """Xoay varimax bằng thuật toán quét đôi Kaiser (1958).

    Với mỗi cặp cột (j, m) ta giải đúng góc θ tối đa hoá V, nên mỗi vòng quét
    luôn làm V không giảm -> hội tụ ổn định (khác với lặp SVD đơn thuần hay
    dao động vì bước quá lớn). Áp dụng sau khi chuẩn hoá Kaiser.
    """
    L = np.asarray(loadings, dtype=float).copy()
    k = L.shape[1]
    if k < 2:
        return L

    for _ in range(max_sweeps):
        max_change = 0.0
        for j in range(k - 1):
            for m in range(j + 1, k):
                u = L[:, j].copy()
                v = L[:, m].copy()
                A, B, C = u**2, v**2, u * v
                # f(θ) = (3/4)K + cos4θ·(K/4 − M) + ½·sin4θ·N  ->  θ* = ¼·atan2(N/2, K/4 − M)
                K = float((A**2).sum() + (B**2).sum())
                M = float((C**2).sum())
                N = float((A * C).sum() - (B * C).sum())
                theta = 0.25 * np.arctan2(N / 2.0, K / 4.0 - M)
                if abs(theta) < 1e-12:
                    continue
                cos_t, sin_t = np.cos(theta), np.sin(theta)
                L[:, j] = cos_t * u + sin_t * v
                L[:, m] = -sin_t * u + cos_t * v
                max_change = max(max_change, abs(theta))
        if max_change < 1e-9:
            break
    return L


def _kaiser_normalize(L: np.ndarray) -> np.ndarray:
    h2 = (L**2).sum(axis=1)
    h2 = np.where(h2 > 0, h2, 1.0)
    Ln = L / np.sqrt(h2)[:, None]
    Ln[np.isnan(Ln)] = 0.0
    return Ln


def _extract_loadings(r: np.ndarray, n_factors: int) -> np.ndarray:
    """Trích nhân tố bằng phân tích trục chính (PCA trên ma trận tương quan)."""
    eigvals, eigvecs = np.linalg.eigh(r)
    order = np.argsort(eigvals)[::-1][:n_factors]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    loadings = eigvecs * np.sqrt(np.maximum(eigvals, 0.0))[None, :]
    loadings = np.nan_to_num(loadings)
    # dời dấu cho cột dương để ổn định giữa các lần chạy
    for j in range(loadings.shape[1]):
        k = int(np.argmax(np.abs(loadings[:, j])))
        if loadings[k, j] < 0:
            loadings[:, j] = -loadings[:, j]
    return loadings


def _run_efa_numpy(df: pd.DataFrame, n_factors: int, rotation: str | None):
    r = _corr(df)
    loadings = _extract_loadings(r, n_factors)

    if rotation:
        h2 = np.maximum((loadings**2).sum(axis=1), 1e-12)
        rotated = _varimax(_kaiser_normalize(loadings))
        # Trả về dạng không chuẩn hoá để communalities đọc được
        loadings = rotated * np.sqrt(h2)[:, None]

    # Sắp xếp nhân tố theo phương sai giải thích giảm dần, dời dấu cho dễ đọc
    order = np.argsort((loadings**2).sum(axis=0))[::-1]
    loadings = loadings[:, order]
    for j in range(loadings.shape[1]):
        k = int(np.argmax(np.abs(loadings[:, j])))
        if loadings[k, j] < 0:
            loadings[:, j] = -loadings[:, j]

    # "Giá trị riêng" = tổng bình phương hệ số tải của nhân tố (đúng như
    # factor_analyzer), tương đương eigenvalue của R khi không xoay.
    eigenvalues = (loadings**2).sum(axis=0)
    return loadings, eigenvalues


# ---------------------------------------------------------------------------
# Hàm chính
# ---------------------------------------------------------------------------
def run_efa(
    df: pd.DataFrame,
    n_factors: int,
    rotation: str = "varimax",
    method: str = "principal",
) -> dict:
    """Chạy EFA và trả về hệ số tải nhân tố, phương sai giải thích, cộng đồng.

    rotation: 'varimax' (mặc định), 'promax', 'oblimin', hoặc None.
    method: 'principal' (mặc định), 'ml', 'minres'.
    """
    df = prepare(df, min_items=2)
    n_factors = max(1, min(int(n_factors), df.shape[1]))

    loadings = eigenvalues = None
    engine = ""

    if HAS_FACTOR_ANALYZER:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fa = FactorAnalyzer(
                    n_factors=n_factors, rotation=rotation, method=method
                )
                fa.fit(df)
            loadings = np.asarray(fa.loadings_, dtype=float)
            communalities = np.asarray(fa.get_communalities(), dtype=float)
            eigenvalues, variance, _ = fa.get_factor_variance()
            eigenvalues = np.asarray(eigenvalues, dtype=float)
            variance = np.asarray(variance, dtype=float)
            engine = "factor_analyzer"
        except Exception:  # noqa: BLE001
            # Thư viện lệch phiên bản (vd. sklearn đã bỏ force_all_finite)
            loadings = None

    if loadings is None:
        loadings, eigenvalues = _run_efa_numpy(df, n_factors, rotation)
        communalities = (loadings**2).sum(axis=1)
        variance = eigenvalues / df.shape[1]
        engine = "numpy"

    cols = [f"Nhân tố {i + 1}" for i in range(loadings.shape[1])]
    loadings_df = pd.DataFrame(loadings, index=df.columns, columns=cols).round(4)

    communalities_df = pd.DataFrame(
        {"Cộng đồng (Communality)": np.round(communalities, 4)}, index=df.columns
    )

    total_var = float(np.trace(_corr(df))) or 1.0
    share = eigenvalues / total_var
    variance_table = pd.DataFrame(
        {
            "Giá trị riêng (Eigenvalue)": np.round(eigenvalues, 4),
            "Phương sai giải thích (%)": np.round(share * 100, 4),
            "Phương sai tích lũy (%)": np.round(np.cumsum(share) * 100, 4),
        },
        index=cols,
    )

    return {
        "loadings": loadings_df,
        "communalities": communalities_df,
        "variance_table": variance_table,
        "n_factors": n_factors,
        "rotation": rotation,
        "method": method,
        "engine": engine,
    }


def assign_items_to_factors(loadings: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Gán mỗi biến vào nhân tố có hệ số tải lớn nhất (>= threshold)."""
    rows = []
    for item in loadings.index:
        row = loadings.loc[item]
        best = row.abs().idxmax()
        best_val = row[best]
        rows.append(
            {
                "Biến quan sát": item,
                "Nhân tố": best,
                "Hệ số tải": best_val,
                "Đạt ngưỡng (>= {:.2f})".format(threshold): abs(best_val) >= threshold,
            }
        )
    return pd.DataFrame(rows)
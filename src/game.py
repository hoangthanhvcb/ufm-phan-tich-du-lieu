"""Trò chơi câu đố tích hợp với từng bước quy trình phân tích dữ liệu.

Mỗi bước có 2 nguồn câu hỏi:
  - Câu hỏi lý thuyết (cố định).
  - Câu hỏi tự sinh từ dữ liệu/kết quả thực tế của bước đó.

Cơ chế: trả lời đúng +1 điểm, tích lũy qua các bước.
"""
from __future__ import annotations

import random

import streamlit as st

# ---------------------------------------------------------------------------
# Ngân hàng câu hỏi lý thuyết
# ---------------------------------------------------------------------------
THEORY: dict[str, list[dict]] = {
    "descriptive": [
        {
            "question": "Giá trị trung bình (Mean) cho biết điều gì?",
            "options": [
                "Mức độ đánh giá chung của dữ liệu",
                "Số lần xuất hiện nhiều nhất",
                "Giá trị ở chính giữa dãy số",
                "Mức độ phân tán của dữ liệu",
            ],
            "answer": 0,
            "explanation": "Mean là mức đánh giá chung; giá trị nhiều nhất là Mode, ở giữa là Median, phân tán là SD.",
        },
        {
            "question": "Nếu độ lệch chuẩn (SD) lớn thì dữ liệu như thế nào?",
            "options": [
                "Tập trung quanh giá trị trung bình",
                "Phân tán mạnh",
                "Bị sai lệch",
                "Không đáng tin cậy",
            ],
            "answer": 1,
            "explanation": "SD lớn → dữ liệu phân tán mạnh; SD nhỏ → dữ liệu tập trung.",
        },
        {
            "question": "Bảng tần suất và tỷ lệ (%) thường dùng cho loại biến nào?",
            "options": [
                "Biến định lượng",
                "Biến phân loại",
                "Biến phụ thuộc",
                "Biến độc lập",
            ],
            "answer": 1,
            "explanation": "Tần suất và tỷ lệ % dùng để mô tả biến phân loại (giới tính, nhóm...).",
        },
    ],
    "cronbach": [
        {
            "question": "Cronbach's Alpha dùng để đánh giá điều gì?",
            "options": [
                "Độ tin cậy (nhất quán nội tại) của thang đo",
                "Mức độ phù hợp của mô hình hồi quy",
                "Tính phân phối chuẩn của dữ liệu",
                "Mối quan hệ nhân quả giữa các biến",
            ],
            "answer": 0,
            "explanation": "Cronbach's Alpha đo mức độ nhất quán nội tại giữa các biến quan sát trong cùng nhân tố.",
        },
        {
            "question": "Hệ số Alpha tối thiểu bao nhiêu được xem là chấp nhận được?",
            "options": ["0.5", "0.6", "0.7", "0.9"],
            "answer": 2,
            "explanation": "Ngưỡng chấp nhận phổ biến là Alpha >= 0.7 (0.6 vẫn dùng được trong nghiên cứu khám phá).",
        },
        {
            "question": "Biến có tương quan biến - tổng nhỏ hơn bao nhiêu thì nên loại?",
            "options": ["0.3", "0.5", "0.7", "0.9"],
            "answer": 0,
            "explanation": "Tương quan biến - tổng < 0.3 bị xem là yếu và nên loại bỏ khỏi thang đo.",
        },
    ],
    "efa": [
        {
            "question": "Chỉ số KMO cần đạt tối thiểu bao nhiêu để dữ liệu phù hợp phân tích nhân tố?",
            "options": ["0.3", "0.5", "0.7", "0.9"],
            "answer": 1,
            "explanation": "KMO > 0.5 → dữ liệu phù hợp phân tích nhân tố khám phá.",
        },
        {
            "question": "Kiểm định Bartlett có ý nghĩa thống kê khi p-value?",
            "options": ["> 0.05", "= 0.5", "< 0.05", "> 0.1"],
            "answer": 2,
            "explanation": "Bartlett Sig < 0.05 → ma trận tương quan phù hợp cho EFA.",
        },
        {
            "question": "Tổng phương sai trích nên giải thích được bao nhiêu % biến thiên?",
            "options": [">= 20%", ">= 30%", ">= 50%", ">= 90%"],
            "answer": 2,
            "explanation": "Tổng phương sai trích khuyến nghị >= 50%.",
        },
    ],
    "correlation": [
        {
            "question": "Hệ số tương quan Pearson nhận giá trị trong khoảng nào?",
            "options": ["[0; 1]", "[-1; 1]", "[-∞; +∞]", "[0; 100]"],
            "answer": 1,
            "explanation": "Pearson r nằm trong khoảng [-1; 1], càng gần ±1 tương quan càng mạnh.",
        },
        {
            "question": "r ≈ 0.6 cho thấy mối tương quan ở mức nào?",
            "options": ["Yếu", "Trung bình", "Mạnh", "Không có tương quan"],
            "answer": 2,
            "explanation": "|r| >= 0.6 thường được xem là tương quan mạnh.",
        },
    ],
    "regression": [
        {
            "question": "p-value < 0.05 của một biến độc lập thường có nghĩa là gì?",
            "options": [
                "Biến không quan trọng",
                "Biến có ảnh hưởng ý nghĩa thống kê",
                "Dữ liệu sai",
                "Mô hình không dùng được",
            ],
            "answer": 1,
            "explanation": "p < 0.05 → biến có ảnh hưởng ý nghĩa thống kê đến biến phụ thuộc.",
        },
        {
            "question": "Chỉ số VIF dùng để kiểm tra hiện tượng gì?",
            "options": ["Tự tương quan", "Đa cộng tuyến", "Phương sai sai số thay đổi", "Ngoại lai"],
            "answer": 1,
            "explanation": "VIF (Variance Inflation Factor) phát hiện đa cộng tuyến giữa các biến độc lập.",
        },
        {
            "question": "VIF từ bao nhiêu trở lên được xem là đa cộng tuyến nghiêm trọng?",
            "options": ["2", "5", "10", "100"],
            "answer": 2,
            "explanation": "VIF >= 10 → đa cộng tuyến nghiêm trọng, nên xử lý.",
        },
        {
            "question": "Hệ số R² cho biết điều gì?",
            "options": [
                "Mức độ giải thích của mô hình",
                "Độ tin cậy của thang đo",
                "Mức độ đa cộng tuyến",
                "Tính phân phối chuẩn",
            ],
            "answer": 0,
            "explanation": "R² là tỷ lệ biến thiên của biến phụ thuộc được mô hình giải thích.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Ngân hàng câu hỏi trắc nghiệm chính thức
# Nguồn: Cau_hoi_trac_nghiem_Xu_ly_va_Phan_tich_du_lieu_dinh_luong.docx
# 18 câu · 6 nội dung · mỗi câu 4 lựa chọn A, B, C, D
# Đây là nguồn câu hỏi DUY NHẤT dùng cho QUIZZ trên web.
# ---------------------------------------------------------------------------
EXAM_QUESTIONS: dict[str, list[dict]] = {
    # --- PHẦN 1. TỔNG QUAN VỀ DỮ LIỆU ĐỊNH LƯỢNG ---
    "overview": [
        {
            "question": "Dữ liệu định lượng là loại dữ liệu như thế nào?",
            "options": [
                "Chỉ mô tả bằng chữ",
                "Được biểu diễn bằng số hoặc có thể chuyển thành giá trị số",
                "Chỉ dùng để phỏng vấn",
                "Không thể phân tích thống kê",
            ],
            "answer": 1,
            "explanation": "Dữ liệu định lượng được biểu diễn bằng số hoặc quy đổi được về số để đo lường và phân tích thống kê.",
        },
        {
            "question": "Có bao nhiêu cấp độ đo lường cơ bản?",
            "options": ["2", "3", "4", "5"],
            "answer": 2,
            "explanation": "Có 4 cấp độ: định danh, thứ bậc, khoảng và tỷ lệ.",
        },
        {
            "question": "Một câu hỏi Likert đơn lẻ từ 1–5 thường được xem là thang đo nào?",
            "options": ["Định danh", "Thứ bậc", "Khoảng", "Tỷ lệ"],
            "answer": 1,
            "explanation": "Câu hỏi Likert đơn lẻ có thứ tự rõ ràng nên là thang đo thứ bậc (ordinal).",
        },
    ],
    # --- PHẦN 2. THU THẬP, MÃ HÓA VÀ LÀM SẠCH DỮ LIỆU ---
    "cleaning": [
        {
            "question": "Dữ liệu sơ cấp là dữ liệu:",
            "options": [
                "Do nhà nghiên cứu trực tiếp thu thập",
                "Lấy từ báo cáo của tổ chức khác",
                "Lấy từ niên giám thống kê",
                "Lấy từ các nghiên cứu trước",
            ],
            "answer": 0,
            "explanation": "Dữ liệu sơ cấp do chính nhà nghiên cứu thu thập; các loại còn lại là dữ liệu thứ cấp.",
        },
        {
            "question": "Trong quá trình làm sạch dữ liệu, vấn đề nào sau đây cần được kiểm tra?",
            "options": [
                "Dữ liệu thiếu (Missing)",
                "Bản ghi trùng lặp (Duplicate)",
                "Giá trị ngoại lại (Outlier)",
                "Cả A, B và C",
            ],
            "answer": 3,
            "explanation": "Cả ba vấn đề — thiếu, trùng lặp và giá trị ngoại lại — đều phải được kiểm tra khi làm sạch.",
        },
        {
            "question": "Mục đích chính của việc làm sạch dữ liệu là gì?",
            "options": [
                "Làm tăng số lượng mẫu",
                "Làm dữ liệu đẹp hơn",
                "Đảm bảo dữ liệu hợp lệ, nhất quán và sẵn sàng cho phân tích",
                "Loại bỏ toàn bộ dữ liệu thiếu",
            ],
            "answer": 2,
            "explanation": "Mục tiêu là dữ liệu hợp lệ, nhất quán và sẵn sàng phân tích — không phải làm đẹp hay loại bỏ mọi giá trị thiếu.",
        },
    ],
    # --- PHẦN 3. THỐNG KÊ MÔ TẢ VÀ PHÂN TÍCH TƯƠNG QUAN ---
    "descriptive": [
        {
            "question": "Mean dùng để biểu thị:",
            "options": [
                "Giá trị xuất hiện nhiều nhất",
                "Giá trị nằm giữa",
                "Giá trị trung bình",
                "Giá trị lớn nhất",
            ],
            "answer": 2,
            "explanation": "Mean là giá trị trung bình; xuất hiện nhiều nhất là Mode, nằm giữa là Median.",
        },
        {
            "question": "Nếu độ lệch chuẩn (SD) càng nhỏ thì dữ liệu có xu hướng:",
            "options": [
                "Càng phân tán",
                "Càng tập trung",
                "Càng nhiều giá trị ngoại lại",
                "Không thể xác định",
            ],
            "answer": 1,
            "explanation": "SD nhỏ → các quan sát dồn quanh trung bình, dữ liệu càng tập trung.",
        },
        {
            "question": "Hệ số tương quan Pearson (r) có giá trị trong khoảng nào?",
            "options": ["0 đến 1", "-1 đến 0", "-1 đến +1", "1 đến 100"],
            "answer": 2,
            "explanation": "r chạy từ -1 (tương quan hoàn hảo đảo chiều) đến +1 (tương quan hoàn hảo cùng chiều).",
        },
    ],
    # --- PHẦN 4. KIỂM ĐỊNH ĐỘ TIN CẬY THANG ĐO VÀ EFA ---
    "reliability": [
        {
            "question": "Cronbach's Alpha được sử dụng chủ yếu để:",
            "options": [
                "Kiểm tra độ tin cậy của thang đo",
                "Kiểm tra dữ liệu thiếu",
                "Tính giá trị trung bình",
                "Kiểm tra đa cộng tuyến",
            ],
            "answer": 0,
            "explanation": "Cronbach's Alpha đo độ tin cậy nội bộ của một thang đo.",
        },
        {
            "question": "Theo tài liệu, Corrected Item-Total Correlation nhỏ hơn mức nào thì cần xem xét loại biến?",
            "options": ["0,1", "0,2", "0,3", "0,5"],
            "answer": 2,
            "explanation": "Dưới 0,3 biến đó có đóng góp thấp cho thang đo và cần được xem xét loại.",
        },
        {
            "question": "Điều kiện nào phù hợp để thực hiện phân tích nhân tố EFA?",
            "options": [
                "KMO < 0,5 và Bartlett > 0,05",
                "KMO ≥ 0,5 và Sig. Bartlett < 0,05",
                "KMO = 0 và Bartlett = 1",
                "KMO < 0,3 và Sig. Bartlett > 0,05",
            ],
            "answer": 1,
            "explanation": "Cần KMO ≥ 0,5 (dữ liệu đủ tương quan) và Bartlett có ý nghĩa (Sig. < 0,05).",
        },
    ],
    # --- PHẦN 5. THIẾT LẬP VÀ ƯỚC LƯỢNG MÔ HÌNH HỒI QUY ---
    "ols_setup": [
        {
            "question": "Trong mô hình hồi quy, biến phụ thuộc thường được ký hiệu là:",
            "options": ["X", "Y", "β", "α"],
            "answer": 1,
            "explanation": "Y là biến phụ thuộc; X là biến độc lập, β là hệ số hồi quy và α là hệ số chặn.",
        },
        {
            "question": "Hệ số góc trong mô hình hồi quy cho biết:",
            "options": [
                "Số lượng mẫu nghiên cứu",
                "Mức độ và xu hướng thay đổi của Y khi X thay đổi 1 đơn vị",
                "Giá trị lớn nhất của Y",
                "Số biến độc lập trong mô hình",
            ],
            "answer": 1,
            "explanation": "Hệ số góc cho biết Y thay đổi bao nhiêu đơn vị (theo chiều và dấu) khi X tăng 1 đơn vị.",
        },
        {
            "question": "Phương pháp OLS được sử dụng để:",
            "options": [
                "Thu thập dữ liệu",
                "Mã hóa dữ liệu",
                "Ước lượng các hệ số của mô hình hồi quy",
                "Tính tần suất",
            ],
            "answer": 2,
            "explanation": "OLS (bình phương nhỏ nhất) dùng để ước lượng các hệ số của mô hình hồi quy.",
        },
    ],
    # --- PHẦN 6. ĐÁNH GIÁ MÔ HÌNH HỒI QUY ---
    "ols_eval": [
        {
            "question": "R² trong mô hình hồi quy cho biết:",
            "options": [
                "Tỷ lệ biến thiên của Y được giải thích bởi các biến X",
                "Số lượng biến độc lập",
                "Số lượng mẫu",
                "Giá trị trung bình của Y",
            ],
            "answer": 0,
            "explanation": "R² là tỷ lệ phần biến thiên của Y được mô hình giải thích.",
        },
        {
            "question": "Kiểm định F trong hồi quy dùng để:",
            "options": [
                "Kiểm tra dữ liệu thiếu",
                "Kiểm tra độ tin cậy thang đo",
                "Kiểm tra sự phù hợp của mô hình tổng thể",
                "Tính trung bình mẫu",
            ],
            "answer": 2,
            "explanation": "Kiểm định F kiểm tra giả thuyết các hệ số hồi quy đều bằng 0, tức mô hình có ý nghĩa tổng thể.",
        },
        {
            "question": "VIF được sử dụng để kiểm tra:",
            "options": [
                "Tương quan Pearson",
                "Độ tin cậy Cronbach's Alpha",
                "Đa cộng tuyến giữa các biến độc lập",
                "Dữ liệu thiếu",
            ],
            "answer": 2,
            "explanation": "VIF (Variance Inflation Factor) đo mức độ đa cộng tuyến giữa các biến độc lập.",
        },
    ],
}


def questions_for_section(section: str) -> list[dict]:
    """3 câu trắc nghiệm của phần, lấy từ ngân hàng câu hỏi chính thức."""
    return [
        {
            "question": q["question"],
            "options": list(q["options"]),
            "answer": int(q["answer"]),
            "explanation": q.get("explanation", ""),
        }
        for q in EXAM_QUESTIONS.get(section, [])
    ]


# ---------------------------------------------------------------------------
# Bộ sinh câu hỏi từ dữ liệu thực tế
# ---------------------------------------------------------------------------
def _numeric_options(correct: float, decimals: int = 2) -> tuple[list, int]:
    """Tạo 4 lựa chọn cho một đáp án số, trả về (options, chỉ số đáp án đúng)."""
    r = round(float(correct), decimals)
    if decimals == 0:
        step = 1
    else:
        step = max(round(abs(r) * 0.15, decimals), 10 ** (-decimals))

    opts = [r]
    for k in range(1, 8):
        if len(opts) >= 4:
            break
        for sign in (1, -1):
            if len(opts) >= 4:
                break
            v = round(r + sign * k * step, decimals)
            if v not in opts:
                opts.append(v)
    extra = 0
    while len(opts) < 4:
        extra += 1
        v = round(r + extra, decimals)
        if v not in opts:
            opts.append(v)

    opts_str = [f"{v:.{decimals}f}" for v in opts]
    random.shuffle(opts_str)
    answer = opts_str.index(f"{r:.{decimals}f}")
    return opts_str, answer


def _tf_question(q: str, statement: bool, explanation: str) -> dict:
    return {
        "question": q,
        "options": ["Đúng", "Sai"],
        "answer": 0 if statement else 1,
        "explanation": explanation,
    }


def questions_overview(summary: dict) -> list[dict]:
    """Câu hỏi cho phần Tổng quan về dữ liệu định lượng."""
    qs = []
    n_num = len(summary.get("numeric_cols", []))
    n_cat = len(summary.get("categorical_cols", []))
    if n_num + n_cat:
        qs.append(
            {
                "question": (
                    f"Bộ dữ liệu có bao nhiêu biến định lượng và phân loại?\n"
                    f"A. {n_num} – {n_cat}\n"
                    f"B. {n_cat} – {n_num}\n"
                    f"C. {n_num} – 0\n"
                    f"D. 0 – {n_cat}"
                ),
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "explanation": f"Dữ liệu có {n_num} biến định lượng và {n_cat} biến phân loại.",
            }
        )
    qs += [
        _tf_question(
            "Dữ liệu định lượng (định lượng) là dữ liệu có thể đo lường bằng số.",
            True,
            "Dữ liệu định lượng biểu diễn bằng số và có ý nghĩa toán học.",
        ),
        _tf_question(
            "Biến phân loại chỉ có thể là biến chuỗi hoặc logic.",
            True,
            "Biến phân loại chia nhóm: giới tính, học vấn, tỉnh thành...",
        ),
    ]
    return qs


def questions_cleaning(completeness: dict, consistency: dict) -> list[dict]:
    """Câu hỏi cho phần Thu thập, mã hoá và làm sạch dữ liệu."""
    qs = []
    missing = completeness.get("missing_cells", 0)
    qs.append(
        {
            "question": (
                "Dữ liệu hiện có bao nhiêu ô bị thiếu giá trị?\n"
                f"A. {missing}\n"
                f"B. 0\n"
                f"C. {completeness.get('rows_with_missing', 0)}\n"
                "D. Không xác định"
            ),
            "options": ["A", "B", "C", "D"],
            "answer": 0,
            "explanation": f"Tổng số ô trống là {missing}.",
        }
    )
    if consistency.get("constant_cols"):
        cols = ", ".join(consistency["constant_cols"][:3])
        qs.append(
            {
                "question": (
                    f"Cột nào không có biến động (giá trị không đổi)?\nA. {cols}\n"
                    "B. Không có cột nào\nC. Tất cả các cột\nD. Cột đầu tiên"
                ),
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "explanation": f"Cột giá trị không đổi: {cols}.",
            }
        )
    qs += [
        _tf_question(
            "Mã hoá biến phân loại thành số làm mất thông tin bản chất của biến.",
            True,
            "Nên dùng mã hoá nhân với biến giả (dummy) thay vì gán số tuần tự.",
        ),
        _tf_question(
            "Giá trị vô hạn (∞, -∞) hoặc NaN đều làm hỏng kết quả phân tích.",
            True,
            "Cần xử lý giá trị khuyết trước khi chạy mô hình.",
        ),
    ]
    return qs


def questions_ols_eval(fit: dict) -> list[dict]:
    """Câu hỏi cho phần Đánh giá mô hình hồi quy."""
    qs = []
    if fit:
        qs += [
            _tf_question(
                "Hệ số R² càng gần 1 thì mô hình giải thích dữ liệu càng tốt.",
                True,
                "R² đo mức độ phù hợp của mô hình với dữ liệu quan sát.",
            ),
            _tf_question(
                "VIF ≥ 10 là dấu hiệu đa cộng tuyến nghiêm trọng giữa các biến độc lập.",
                True,
                "VIF cao cho thấy biến độc lập bị trùng lặp thông tin với nhau.",
            ),
            _tf_question(
                "Kiểm định F của mô hình OLS cho biết mô hình có ý nghĩa thống kê hay không.",
                True,
                "F (ANOVA) kiểm tra giả thuyết H0: tất cả hệ số bằng 0.",
            ),
        ]
    else:
        qs += [_tf_question("OLS là phương pháp hồi quy tuyến tính.", True, "OLS = Ordinary Least Squares.")]
    return qs


def questions_descriptive(numeric_desc, cat_freq, cat_col) -> list[dict]:
    """Câu hỏi cho bước thống kê mô tả."""
    qs = []
    if numeric_desc is not None and not numeric_desc.empty:
        col = random.choice(list(numeric_desc.index))
        mean = numeric_desc.loc[col, "Giá trị trung bình (Mean)"]
        opts, ans = _numeric_options(mean, 2)
        qs.append(
            {
                "question": f"Dựa vào kết quả vừa tính, giá trị trung bình (Mean) của biến '{col}' là bao nhiêu?",
                "options": opts,
                "answer": ans,
                "explanation": f"Mean của '{col}' = {mean:.2f}.",
            }
        )
    if cat_freq is not None and not cat_freq.empty and cat_col:
        mode = cat_freq["Tần suất (n)"].idxmax()
        cats = list(cat_freq.index)
        others = [c for c in cats if c != mode]
        opts = [mode] + random.sample(others, min(3, len(others)))
        while len(opts) < 4:
            opts.append("Không có")
        random.shuffle(opts)
        ans = opts.index(mode)
        qs.append(
            {
                "question": f"Ở biến phân loại '{cat_col}', nhóm nào có tần suất cao nhất?",
                "options": [str(o) for o in opts],
                "answer": ans,
                "explanation": f"Nhóm '{mode}' có tần suất cao nhất ({cat_freq.loc[mode, 'Tần suất (n)']}).",
            }
        )
    return qs


def questions_cronbach(alpha, drop_items, verdict) -> list[dict]:
    """Câu hỏi cho bước Cronbach's Alpha."""
    qs = []
    if alpha is not None and not (isinstance(alpha, float) and alpha != alpha):  # not NaN
        opts, ans = _numeric_options(alpha, 3)
        qs.append(
            {
                "question": "Hệ số Cronbach's Alpha của thang đo vừa kiểm định là bao nhiêu?",
                "options": opts,
                "answer": ans,
                "explanation": f"Alpha = {alpha:.3f}. {verdict}",
            }
        )
    if len(drop_items) == 1:
        others = list(THEORY["cronbach"][0]["options"])[:3]
        opts = [drop_items[0]] + others
        random.shuffle(opts)
        ans = opts.index(drop_items[0])
        qs.append(
            {
                "question": "Biến nào bị đề xuất loại vì tương quan biến - tổng < 0.3?",
                "options": opts,
                "answer": ans,
                "explanation": f"Biến '{drop_items[0]}' có tương quan biến - tổng < 0.3.",
            }
        )
    return qs


def questions_efa(kmo, variance_table, n_factors) -> list[dict]:
    """Câu hỏi cho bước EFA."""
    qs = []
    if kmo is not None:
        opts, ans = _numeric_options(kmo["kmo"], 3)
        qs.append(
            {
                "question": "Chỉ số KMO của dữ liệu vừa tính là bao nhiêu?",
                "options": opts,
                "answer": ans,
                "explanation": f"KMO = {kmo['kmo']:.3f}.",
            }
        )
    if variance_table is not None and not variance_table.empty:
        cum = variance_table["Phương sai tích lũy (%)"].iloc[-1]
        qs.append(
            _tf_question(
                f"Tổng phương sai trích ({cum:.2f}%) có đạt ngưỡng khuyến nghị >= 50% không?",
                cum >= 50,
                f"Tổng phương sai trích = {cum:.2f}%.",
            )
        )
    if n_factors:
        opts, ans = _numeric_options(n_factors, 0)
        qs.append(
            {
                "question": "Mô hình EFA vừa trích được bao nhiêu nhân tố?",
                "options": opts,
                "answer": ans,
                "explanation": f"Số nhân tố = {n_factors}.",
            }
        )
    return qs


def questions_correlation(pairs) -> list[dict]:
    """Câu hỏi cho bước tương quan Pearson."""
    qs = []
    if pairs is not None and not pairs.empty:
        top = pairs.iloc[0]
        others = list(pairs["Biến A"]) + list(pairs["Biến B"])
        others = [o for o in others if o not in (top["Biến A"], top["Biến B"])]
        pair_ans = f"{top['Biến A']} – {top['Biến B']}"
        opts = [pair_ans] + [f"{top['Biến A']} – {o}" for o in others[:3]]
        while len(opts) < 4:
            opts.append(f"{top['Biến B']} – {top['Biến B']}")
        random.shuffle(opts)
        ans = opts.index(pair_ans)
        qs.append(
            {
                "question": "Cặp biến nào có hệ số tương quan Pearson lớn nhất (về trị tuyệt đối)?",
                "options": opts,
                "answer": ans,
                "explanation": f"Cặp {pair_ans} có r = {top['Hệ số r']:.4f} ({top['Mức độ']}).",
            }
        )
    return qs


def questions_regression(fit) -> list[dict]:
    """Câu hỏi cho bước hồi quy."""
    qs = []
    if fit is not None:
        opts, ans = _numeric_options(fit["r2"], 3)
        qs.append(
            {
                "question": "Hệ số xác định R² của mô hình vừa ước lượng là bao nhiêu?",
                "options": opts,
                "answer": ans,
                "explanation": f"R² = {fit['r2']:.3f}.",
            }
        )
        qs.append(
            _tf_question(
                f"Kiểm định F (p-value = {fit['f_pvalue']:.4f}) có ý nghĩa thống kê không?",
                fit["f_pvalue"] < 0.05,
                f"F p-value = {fit['f_pvalue']:.4f} (ngưỡng < 0.05).",
            )
        )
        # Biến có Beta chuẩn hóa lớn nhất
        coefs = fit["coefficients"].drop(index="Hằng số (β0)", errors="ignore")
        if not coefs.empty:
            beta = coefs["Beta chuẩn hóa"].abs()
            best = beta.idxmax()
            opts = [best] + [c for c in coefs.index if c != best][:3]
            while len(opts) < 4:
                opts.append("Hằng số")
            random.shuffle(opts)
            ans = opts.index(best)
            qs.append(
                {
                    "question": "Biến độc lập nào có hệ số Beta chuẩn hóa (ảnh hưởng) lớn nhất?",
                    "options": opts,
                    "answer": ans,
                    "explanation": f"Biến '{best}' có |Beta| = {abs(coefs.loc[best, 'Beta chuẩn hóa']):.3f}.",
                }
            )
    return qs


# ---------------------------------------------------------------------------
# Kết hợp câu hỏi lý thuyết + dữ liệu
# ---------------------------------------------------------------------------
def build_questions(step: str, data_questions: list[dict], theory_limit: int = 2) -> list[dict]:
    """Trộn câu hỏi lý thuyết (lấy ngẫu nhiên) với câu hỏi dữ liệu."""
    theory = random.sample(THEORY.get(step, []), min(theory_limit, len(THEORY.get(step, []))))
    combined = theory + list(data_questions)
    random.shuffle(combined)
    return combined


# ---------------------------------------------------------------------------
# Hiển thị trò chơi
# ---------------------------------------------------------------------------
def render_quiz(step_name: str, questions: list[dict], session_key: str) -> None:
    """Nhúng câu đố ngay sau mỗi bước, tính điểm tích lũy."""
    if not questions:
        return
    if "game_total" not in st.session_state:
        st.session_state["game_total"] = 0

    # Lưu câu hỏi ở lần đầu để giữ ổn định giữa các lần render lại.
    if session_key not in st.session_state:
        st.session_state[session_key] = {
            "questions": questions,
            "answered": False,
            "gained": 0,
        }
    state = st.session_state[session_key]
    qs = state["questions"]

    st.markdown("---")
    st.markdown(f"### 🎮 Câu đố · {step_name}")
    st.markdown("Mỗi câu trả lời đúng +1 điểm.")

    user = []
    for i, q in enumerate(qs):
        user.append(
            st.radio(
                f"**Câu {i + 1}.** {q['question']}",
                list(range(len(q["options"]))),
                format_func=lambda idx, q=q: q["options"][idx],
                key=f"{session_key}_q{i}",
                disabled=state["answered"],
            )
        )

    if not state["answered"]:
        if st.button("Nộp câu trả lời", key=f"{session_key}_submit"):
            score = sum(1 for i, q in enumerate(qs) if user[i] == q["answer"])
            st.session_state["game_total"] += score
            st.session_state[session_key] = {
                "questions": qs,
                "answered": True,
                "gained": score,
            }
            st.rerun()
    else:
        for i, q in enumerate(qs):
            chosen = user[i]
            correct = chosen == q["answer"]
            icon = "✅" if correct else "❌"
            st.markdown(
                f"{icon} **Câu {i + 1}:** Bạn chọn *{q['options'][chosen]}* — Đáp án đúng: **{q['options'][q['answer']]}**"
            )
            st.markdown(f"💡 {q['explanation']}")
        st.success(f"Điểm màn này: {state['gained']}/{len(qs)}")


def show_scoreboard() -> None:
    """Hiển thị tổng điểm ở sidebar."""
    total = st.session_state.get("game_total", 0)
    st.sidebar.metric("🏆 Tổng điểm trò chơi", total)

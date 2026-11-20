"""소개서용 통계 그래프를 만든다. 숫자는 모두 아래 DATA에 출처와 함께 적혀 있다(출처.md 참고).
실행: python make_charts.py  → 같은 폴더에 PNG 8장."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).parent
SURFACE, INK, SUB, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#b9b8b2"   # 계열 1·2는 검사기를 통과한 조합, 회색은 강조하지 않는 막대
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "text.color": INK,
                     "axes.labelcolor": SUB, "xtick.color": SUB, "ytick.color": SUB})

# ── 숫자 (출처는 출처.md) ─────────────────────────────────────────────
RELIEF = {2021: 2406, 2022: 2654, 2023: 3165, 2024: 3412}          # 헬스장 피해구제 신청, 한국소비자원
PILATES = {2021: 662, 2022: 804, 2023: 1021}                         # 필라테스 피해구제 신청, 한국소비자원
REASONS = [("계약해지\n(환급 거부·위약금)", 92.0), ("계약불이행", 5.0), ("기타", 2.3), ("부당행위", 0.7)]  # 2022~2025.3, 10,104건
GYMS = {2013: 6991, 2014: 7363, 2015: 7931, 2017: 8942, 2018: 9046, 2019: 9469, 2020: 9574,
        2021: 11144, 2022: 12669, 2023: 14773, 2024: 15548}          # 체력단련장업 개소, 문체부(2016년 값은 못 찾음)
TOP2023 = [("헬스장", 15718), ("이동전화서비스", 11414), ("기타 의류·섬유", 9916),
           ("항공여객운송서비스", 8733), ("세탁서비스", 8360)]        # 1372 상담 다발 품목, 2023년
SURVEY_WHY = [("전화가 부담돼서", 5), ("환불 규정을 몰라서", 5), ("뭐라고 말할지 몰라서", 3), ("거절당할까 봐", 3)]
SURVEY_LOSS = [("없음", 2), ("5만 원 미만", 2), ("5~10만 원", 2), ("10~30만 원", 2), ("30만 원 이상", 1)]


def frame(title, sub, source, size=(8, 4.5)):
    fig = plt.figure(figsize=size, dpi=200)
    fig.text(0.06, 0.93, title, fontsize=15, fontweight="bold", va="top")
    fig.text(0.06, 0.855, sub, fontsize=9.5, color=SUB, va="top")
    fig.text(0.06, 0.035, source, fontsize=7.5, color=SUB, va="bottom")
    return fig


def clean(ax, grid="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, labelsize=9)
    ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / name)
    plt.close(fig)
    print(name)


def pct(a, b):
    return (b / a - 1) * 100


# 1. 헬스장 피해구제 신청 건수
g = pct(RELIEF[2021], RELIEF[2024])
fig = frame(f"헬스장 피해구제 신청은 3년 새 {g:.0f}% 늘었다", "한국소비자원에 접수된 헬스장 피해구제 신청 건수",
            "자료: 한국소비자원 보도자료(2024.12.11., 2025.5.15.). 2025년 1분기는 873건(전년 동기 741건).")
ax = fig.add_axes([0.08, 0.14, 0.86, 0.62])
xs = [str(y) for y in RELIEF]
bars = ax.bar(xs, RELIEF.values(), width=0.5, color=BLUE)
for b, v in zip(bars, RELIEF.values()):
    ax.text(b.get_x() + b.get_width() / 2, v + 60, f"{v:,}건", ha="center", fontsize=10.5, fontweight="bold")
ax.set_ylim(0, 4000); ax.set_yticks([0, 1000, 2000, 3000, 4000]); ax.set_yticklabels(["0", "1,000", "2,000", "3,000", "4,000"])
clean(ax); save(fig, "1_헬스장_피해구제_연도별.png")

# 2. 신청 이유
fig = frame("헬스장 분쟁 10건 중 9건은 계약해지 문제다", "헬스장 피해구제 신청 이유별 비율 (2022년~2025년 3월, 10,104건)",
            "자료: 한국소비자원 보도자료(2025.5.15.). 계약해지 관련은 9,290건.")
ax = fig.add_axes([0.25, 0.14, 0.66, 0.62])
names = [n for n, _ in REASONS][::-1]; vals = [v for _, v in REASONS][::-1]
bars = ax.barh(names, vals, height=0.5, color=[GRAY, GRAY, GRAY, BLUE])
for b, v in zip(bars, vals):
    ax.text(v + 1.2, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=10.5, fontweight="bold")
ax.set_xlim(0, 105); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
clean(ax, "x"); ax.spines["bottom"].set_visible(False); ax.tick_params(axis="y", labelsize=10)
save(fig, "2_헬스장_분쟁_이유.png")

# 3. 헬스장 수
g = pct(GYMS[2019], GYMS[2024])
fig = frame(f"헬스장은 5년 새 {g:.0f}% 늘어 1만 5천 곳을 넘었다", "전국 체력단련장업 신고 업소 수 (각 연도 말 기준)",
            "자료: 문화체육관광부 「전국 등록·신고 체육시설업 현황」(e-나라지표, 2025년판). 2016년 값은 확인하지 못해 비웠다.")
ax = fig.add_axes([0.09, 0.14, 0.85, 0.62])
a = [y for y in GYMS if y <= 2015]; b = [y for y in GYMS if y >= 2017]
for seg in (a, b):
    ax.plot(seg, [GYMS[y] for y in seg], color=BLUE, linewidth=2, marker="o", markersize=5.5,
            markerfacecolor=BLUE, markeredgecolor=SURFACE, markeredgewidth=1.5)
ax.plot([2015, 2017], [GYMS[2015], GYMS[2017]], color=BLUE, linewidth=1.2, linestyle=(0, (2, 3)))
for y, dy in ((2013, 550), (2019, 600), (2024, 550)):
    ax.text(y, GYMS[y] + dy, f"{GYMS[y]:,}", ha="center", fontsize=10.5, fontweight="bold")
ax.set_xlim(2012.4, 2024.8); ax.set_xticks(range(2013, 2025)); ax.set_xticklabels([f"'{str(y)[2:]}" for y in range(2013, 2025)])
ax.set_ylim(0, 18000); ax.set_yticks(range(0, 18001, 6000)); ax.set_yticklabels(["0", "6,000", "12,000", "18,000"])
clean(ax); save(fig, "3_헬스장_수.png")

# 4. 1372 상담 다발 품목
fig = frame("헬스장은 소비자상담이 가장 많은 품목이다", "1372 소비자상담센터 상담 다발 품목 상위 5개 (2023년, 건)",
            "자료: 한국소비자원 「2023년 연간 소비자상담 빅데이터 트렌드」. 2022년도 헬스장이 1위(15,346건).")
ax = fig.add_axes([0.25, 0.14, 0.66, 0.62])
names = [n for n, _ in TOP2023][::-1]; vals = [v for _, v in TOP2023][::-1]
bars = ax.barh(names, vals, height=0.5, color=[GRAY] * 4 + [BLUE])
for b, v in zip(bars, vals):
    ax.text(v + 250, b.get_y() + b.get_height() / 2, f"{v:,}", va="center", fontsize=10.5, fontweight="bold")
ax.set_xlim(0, 18500); ax.set_xticks([0, 5000, 10000, 15000]); ax.set_xticklabels(["0", "5,000", "10,000", "15,000"])
clean(ax, "x"); ax.spines["bottom"].set_visible(False); ax.tick_params(axis="y", labelsize=10)
save(fig, "4_소비자상담_상위_품목.png")

# 5. 헬스장과 필라테스
fig = frame(f"필라테스 분쟁은 2년 새 {pct(PILATES[2021], PILATES[2023]):.0f}% 늘어 헬스장({pct(RELIEF[2021], RELIEF[2023]):.0f}%)보다 빠르다",
            "피해구제 신청 건수. 필라테스도 계약해지 관련이 91.4%다(2021~2023년, 2,487건)",
            "자료: 한국소비자원 보도자료(헬스장 2024.12.11., 필라테스 2024.7.26.).")
ax = fig.add_axes([0.08, 0.14, 0.86, 0.60])
years = [2021, 2022, 2023]; w = 0.34
for i, (name, src, color) in enumerate((("헬스장", RELIEF, BLUE), ("필라테스", PILATES, ORANGE))):
    xs = [j + (i - 0.5) * (w + 0.03) for j in range(3)]
    bars = ax.bar(xs, [src[y] for y in years], width=w, color=color, label=name)
    for x, y in zip(xs, years):
        ax.text(x, src[y] + 60, f"{src[y]:,}", ha="center", fontsize=10, fontweight="bold")
ax.set_xticks(range(3)); ax.set_xticklabels([str(y) for y in years])
ax.set_ylim(0, 3800); ax.set_yticks([0, 1000, 2000, 3000]); ax.set_yticklabels(["0", "1,000", "2,000", "3,000"])
ax.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=2, handlelength=1, handleheight=1, borderaxespad=0)
clean(ax); save(fig, "5_헬스장과_필라테스.png")

# 6. 상담에서 피해구제까지
c, r = TOP2023[0][1], RELIEF[2023]
fig = frame("피해구제 신청은 상담 건수의 5분의 1이다", "2023년 헬스장 관련 1372 상담 건수와 피해구제 신청 건수",
            "자료: 한국소비자원(상담: 2023년 연간 소비자상담 트렌드, 피해구제: 2024.12.11. 보도자료). 비율은 두 건수를 나눈 값으로,\n"
            "같은 사람을 추적한 수치가 아니다. 피해구제를 신청해도 49.7%는 환급·배상을 받지 못했다(2022년~2025년 3월).")
ax = fig.add_axes([0.25, 0.20, 0.66, 0.54])
bars = ax.barh(["피해구제 신청", "1372 상담"], [r, c], height=0.45, color=[BLUE, GRAY])
ax.text(c + 250, 1, f"{c:,}건", va="center", fontsize=11, fontweight="bold")
ax.text(r + 250, 0, f"{r:,}건 (상담의 {r / c * 100:.0f}%)", va="center", fontsize=11, fontweight="bold")
ax.set_xlim(0, 19500); ax.set_xticks([0, 5000, 10000, 15000]); ax.set_xticklabels(["0", "5,000", "10,000", "15,000"])
clean(ax, "x"); ax.spines["bottom"].set_visible(False); ax.tick_params(axis="y", labelsize=10.5)
save(fig, "6_상담에서_피해구제까지.png")

# 7. 자체 설문 (작은 표본)
fig = frame("미룬 이유는 전화 부담과 규정을 모른다는 것이었다", "팀 자체 설문 17건 중 중도해지를 하려 한 적이 있는 9건의 답 (건)",
            "자료: 팀 자체 간이 설문(2026.11.15.~16., 응답 17건). 대표 표본이 아니며 왼쪽은 여러 개를 고를 수 있었다.")
for k, (title, rows, box) in enumerate((("해지 연락을 미룬 이유", SURVEY_WHY, [0.22, 0.14, 0.27, 0.56]),
                                         ("포기했거나 덜 받은 금액", SURVEY_LOSS, [0.68, 0.14, 0.27, 0.56]))):
    ax = fig.add_axes(box)
    names = [n for n, _ in rows][::-1]; vals = [v for _, v in rows][::-1]
    bars = ax.barh(names, vals, height=0.5, color=BLUE)
    for b, v in zip(bars, vals):
        ax.text(v + 0.15, b.get_y() + b.get_height() / 2, str(v), va="center", fontsize=10.5, fontweight="bold")
    ax.set_xlim(0, 6.2); ax.set_xticks([]); ax.set_title(title, fontsize=10.5, loc="left", color=INK, pad=8)
    clean(ax, "x"); ax.grid(False); ax.spines["bottom"].set_visible(False); ax.tick_params(axis="y", labelsize=9.5)
save(fig, "7_자체_설문.png")

# 8. 핵심 숫자
fig = frame("한눈에 보는 헬스장 환불 분쟁", "공식 통계에서 뽑은 다섯 가지 숫자",
            "자료: 한국소비자원 보도자료(2025.5.15.)와 그 보도, 문화체육관광부 「전국 등록·신고 체육시설업 현황」(2024년 말 기준).\n"
            "평균 계약 금액은 보도에 따라 약 120만 원 또는 약 132만 원으로 전해졌다.")
tiles = [(f"{RELIEF[2024]:,}건", "2024년 헬스장\n피해구제 신청"), ("92.0%", "계약해지 관련 분쟁\n('22~'25.3 신청 건)"),
         ("49.7%", "환급·배상을 못 받은\n신청 ('22~'25.3)"), ("약 120만 원", "피해구제 사건의\n평균 계약 금액"),
         (f"{GYMS[2024]:,}곳", "전국 헬스장 수\n(2024년 말)")]
ax = fig.add_axes([0.05, 0.16, 0.90, 0.60]); ax.axis("off"); ax.set_xlim(0, 5); ax.set_ylim(0, 1)
for i, (num, label) in enumerate(tiles):
    ax.add_patch(FancyBboxPatch((i + 0.06, 0.08), 0.88, 0.84, boxstyle="round,pad=0,rounding_size=0.05",
                                facecolor="#ffffff", edgecolor=GRID, linewidth=1))
    ax.text(i + 0.5, 0.62, num, ha="center", va="center", fontsize=15.5 if len(num) < 8 else 13.5, fontweight="bold", color=BLUE)
    ax.text(i + 0.5, 0.30, label, ha="center", va="center", fontsize=8.5, color=SUB, linespacing=1.5)
save(fig, "8_핵심_숫자.png")

# 계산한 값 (출처.md의 표와 같아야 한다)
print(f"피해구제 2021→2024: +{pct(RELIEF[2021], RELIEF[2024]):.1f}%, 연평균 {((RELIEF[2024] / RELIEF[2021]) ** (1 / 3) - 1) * 100:.1f}%")
print(f"필라테스 2021→2023: +{pct(PILATES[2021], PILATES[2023]):.1f}%, 연평균 {((PILATES[2023] / PILATES[2021]) ** (1 / 2) - 1) * 100:.1f}%")
print(f"헬스장 수 2019→2024: +{pct(GYMS[2019], GYMS[2024]):.1f}%, 연평균 {((GYMS[2024] / GYMS[2019]) ** (1 / 5) - 1) * 100:.1f}%")
print(f"헬스장 1곳당 피해구제 2021: {RELIEF[2021] / GYMS[2021]:.3f}, 2024: {RELIEF[2024] / GYMS[2024]:.3f}")
print(f"상담 대비 피해구제 2023: {RELIEF[2023] / TOP2023[0][1] * 100:.1f}%")
print(f"2024 피해구제 계약 금액 합(120만 원 가정): {RELIEF[2024] * 120 / 10000:.1f}억 원")
assert sum(RELIEF[y] for y in (2022, 2023, 2024)) + 873 == 10104   # 소비자원이 밝힌 2022~2025.3 합계와 맞는지

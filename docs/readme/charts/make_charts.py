"""The README's charts, from the measured numbers quoted in README.md.

    python docs/readme/charts/make_charts.py --fonts DIR   # DIR holds Onest.ttf, Golos.ttf, GeistMono.ttf

Every chart says in its subtitle what it was measured on. Colours and type
follow DESIGN.md: warm ground, one ink, speaker colours for series.
"""

import argparse
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

OUT = Path(__file__).parent
GROUND, PANEL, HAIR = "#f7f6f3", "#ffffff", "#eae6df"
INK, INK2, INK3 = "#101010", "#5b544b", "#6f685f"
S1, S2, S3, S4, S5 = "#b73f74", "#c27544", "#0093a5", "#6450a1", "#1a7444"
MUTED = "#cfc9bf"


def setup(fonts: Path):
    for f in ("Onest.ttf", "Golos.ttf", "GeistMono.ttf"):
        fm.fontManager.addfont(str(fonts / f))
    plt.rcParams.update({
        "font.family": "Golos Text", "font.size": 12, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": INK3, "ytick.color": INK2, "axes.edgecolor": HAIR, "axes.facecolor": GROUND,
        "figure.facecolor": GROUND, "savefig.facecolor": GROUND, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": False, "figure.dpi": 100,
    })


def frame(title: str, subtitle: str, size=(12, 5.2)):
    fig, ax = plt.subplots(figsize=size)
    sub = textwrap.fill(subtitle, 125)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.8 - 0.045 * sub.count("\n"), bottom=0.14)
    fig.text(0.08, 0.93, title, fontsize=20, fontfamily="Onest", fontweight="medium", color=INK)
    fig.text(0.08, 0.885, sub, fontsize=11.5, color=INK2, va="top", linespacing=1.4)
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)


def hbars(ax, labels, values, colors, fmt="{:.1f}%", xmax=100):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=colors, height=0.58)
    ax.set_yticks(list(y), labels)
    ax.set_xlim(0, xmax)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.01, yi, fmt.format(v), va="center", fontsize=12, fontfamily="Geist Mono", color=INK)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)


def speakers():
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=0.2, right=0.97, top=0.74, bottom=0.12, wspace=0.55)
    fig.text(0.03, 0.92, "Who spoke when: accuracy (100 − DER), strict scoring", fontsize=20, fontfamily="Onest",
             fontweight="medium")
    fig.text(0.03, 0.855, "Left: AMI, one far table microphone (paid and open numbers: all 16 test meetings; ours: 4 of them, 92 min). "
             "Right: our close-mic test sets.", fontsize=11, color=INK2)
    hbars(a, ["pyannoteAI Precision-2\n(paid, cloud or H100)", "pyannote community-1\n(open, GPU)", "Liminal\n(2017 laptop CPU, live)"],
          [84.4, 80.1, 66.5], [MUTED, MUTED, S1])
    a.set_title("Far microphone", loc="left", fontsize=13, color=INK2, pad=8)
    hbars(b, ["Mixed RO/RU/EN,\n18 meetings, 65 min", "11 to 14 people,\n4 × 30 min"], [93.0, 93.6], [S3, S3])
    b.set_title("Close microphone (no paid number)", loc="left", fontsize=13, color=INK2, pad=8)
    save(fig, "speakers")


def minutes_models():
    rows = [("qwen3:8b", 7.2, 100, 93, S1), ("mistral-small3.2:24b", 19.5, 100, 100, INK3),
            ("qwen3:14b", 11.0, 93, 93, INK3), ("gpt-oss:20b", 13.2, 80, 100, INK3), ("phi4:14b", 25.7, 80, 93, INK3),
            ("gemma3:12b", 19.4, 80, 100, INK3), ("EuroLLM-22B", 16.9, 53, 87, INK3), ("gemma3:4b", 4.1, 67, 67, INK3)]
    fig, ax = frame("Minutes model: what it finds vs the GPU memory it needs",
                    "14 local models on Kaggle T4s, 6 scripted RO/RU/EN meetings (16.4 min, 15 decisions, 15 actions, 6 traps); no model fell "
                    "for a trap. Memory is round 1's peak across two T4s; round 2 measures each model alone.")
    ax.axvspan(0, 16, color="#efece6", zorder=0)
    ax.text(0.4, 55, "fits the reference 16 GB GPU", fontsize=11, color=INK3)
    for name, gb, dec, act, c in rows:
        score = (dec + act) / 2
        ax.scatter(gb, score, s=160 if c == S1 else 90, color=c, zorder=3)
        ax.annotate(name, (gb, score), xytext=(8, 6), textcoords="offset points", fontsize=11,
                    color=INK if c == S1 else INK2, fontweight="bold" if c == S1 else "normal")
    ax.set_xlim(0, 28)
    ax.set_ylim(50, 104)
    ax.set_xlabel("peak GPU memory, GB (lower is cheaper)")
    ax.set_ylabel("decisions and actions found, %")
    save(fig, "minutes_models")


def hallucination():
    fig, ax = frame("Adds content that is not in the source: lower is better",
                    "Vectara hallucination leaderboard, 22 Sep 2026: every model summarises the same documents, HHEM judges each summary. "
                    "Liminal then checks every fact against the transcript in code.")
    hbars(ax, ["qwen3-8b (Liminal, local, 7.2 GB)", "Gemini 2.5 Pro (cloud)", "GPT-5.4 Pro (cloud)",
               "Claude Sonnet 4 (cloud)", "Claude Opus 4.5 (cloud)"], [4.8, 7.0, 8.3, 10.3, 10.9],
          [S5, MUTED, MUTED, MUTED, MUTED], xmax=12.5)
    fig.subplots_adjust(left=0.27)
    save(fig, "hallucination")


def meeting_type():
    fig, ax = frame("Meeting type detected correctly, by type",
                    "8 meetings (6 scripted, one of 60 min, our 10-min mock board), each as the full transcript and its first 3 minutes: "
                    "16 variants. The local model's one miss was a timeout.")
    cats = ["Medical (8)", "Executive (4)", "Administrative (4)"]
    laya = [100, 50, 0]
    llm = [87.5, 100, 100]
    x = range(len(cats))
    ax.bar([i - 0.18 for i in x], llm, width=0.34, color=S3, label="local model Liminal already runs (qwen3:8b, CPU): 15 / 16")
    ax.bar([i + 0.18 for i in x], laya, width=0.34, color=MUTED, label="Laya zero-shot classifier: 10 / 16")
    for i, (a, b) in enumerate(zip(llm, laya)):
        ax.text(i - 0.18, a + 2, f"{a:.0f}%", ha="center", fontfamily="Geist Mono", fontsize=11)
        ax.text(i + 0.18, b + 2, f"{b:.0f}%", ha="center", fontfamily="Geist Mono", fontsize=11)
    ax.set_xticks(list(x), cats)
    ax.set_ylim(0, 135)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=11, ncol=2)
    save(fig, "meeting_type")


def training_gains():
    fig, ax = frame("Where the speaker accuracy came from",
                    "Mixed RO/RU/EN meetings, 18 scored (65 min, 497 turns, 61 voices never trained on). "
                    "The biggest step cost no GPU time.")
    steps = ["one setting for every room", "settings chosen by\nmicrophone distance", "+ segmentation fine-tuned\non RO/RU (69 min on 2× T4)"]
    vals = [80.0, 90.1, 93.0]
    ax.bar(range(3), vals, color=[MUTED, S3, S1], width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{'about ' if i == 0 else ''}{v:.1f}%", ha="center", fontfamily="Geist Mono", fontsize=12)
    ax.set_xticks(range(3), steps)
    ax.set_ylim(60, 100)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    save(fig, "training_gains")


def training_data():
    fig, ax = frame("Speech the speaker models trained on: 166 hours, about 5,900 speakers",
                    "Public data only, on Kaggle T4s (3.3 h of training). Hospital audio was never uploaded. "
                    "Plus 300 synthetic RO/RU meetings with room echo.")
    labels = ["AMI meetings (EN, near and far mics)", "Common Voice 22, Russian", "VoxConverse (broadcast)",
              "Common Voice 22, Romanian", "VoxPopuli, Romanian", "AliMeeting (far-field meetings)"]
    hours = [40.1, 46.3, 33.5, 24.6, 19.6, 2.0]
    order = sorted(zip(hours, labels), reverse=True)
    hbars(ax, [l for _, l in order], [h for h, _ in order], [S4] * 6, fmt="{:.1f} h", xmax=55)
    fig.subplots_adjust(left=0.3)
    save(fig, "training_data")


def cost():
    seats = list(range(10, 201, 10))
    otter = [s * 19.99 * 36 for s in seats]
    fireflies = [s * 19 * 36 for s in seats]
    server = 2500
    fig, ax = frame("Three-year cost by number of people who run meetings",
                    "Cloud: list prices per user per month (Otter.ai Business \\$19.99, Fireflies Business \\$19, before AI credits). "
                    "Liminal: one 16 GB GPU workstation, assumed \\$2,500.")
    ax.plot(seats, otter, color=MUTED, lw=2.5, label="Otter.ai Business (no Romanian or Russian)")
    ax.plot(seats, fireflies, color=INK3, lw=2.5, label="Fireflies.ai Business")
    ax.plot(seats, [server] * len(seats), color=S5, lw=3, label="Liminal on one server, any number of users")
    ax.set_xlabel("people who run meetings")
    ax.set_ylabel("USD over 3 years")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
    ax.legend(frameon=False, loc="upper left", fontsize=11)
    ax.text(203, fireflies[-1], f"${fireflies[-1] / 1000:.0f}k", va="center", fontfamily="Geist Mono", fontsize=11)
    ax.text(203, server, f"${server / 1000:.1f}k", va="center", fontfamily="Geist Mono", fontsize=11, color=S5)
    ax.set_xlim(0, 218)
    save(fig, "cost")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fonts", type=Path, required=True)
    setup(p.parse_args().fonts)
    for chart in (speakers, minutes_models, hallucination, meeting_type, training_gains, training_data, cost):
        chart()
        print("wrote", chart.__name__)

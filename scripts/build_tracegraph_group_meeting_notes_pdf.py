"""Create a concise two-page Chinese group-meeting note for TraceGraph TG6-TG8."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "paper/acl2027/reports/TRACEGRAPH_TG6_TG8_GROUP_MEETING_NOTES_20260917_ZH.pdf"
FONT = Path("C:/Windows/Fonts/simhei.ttf")

NAVY = colors.HexColor("#244A73")
TEAL = colors.HexColor("#2B6F6D")
INK = colors.HexColor("#202A33")
MUTED = colors.HexColor("#65717D")
PALE_BLUE = colors.HexColor("#EAF1F7")
PALE_TEAL = colors.HexColor("#E9F3F1")
PALE_YELLOW = colors.HexColor("#FFF5D8")
GRID = colors.HexColor("#CED6DE")


def register_fonts():
    if not FONT.is_file():
        raise FileNotFoundError(FONT)
    pdfmetrics.registerFont(TTFont("SimHei", str(FONT)))


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="SimHei", fontSize=21,
            leading=27, textColor=NAVY, alignment=TA_CENTER, spaceAfter=5 * mm,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="SimHei", fontSize=10,
            leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=5 * mm,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="SimHei", fontSize=14,
            leading=19, textColor=NAVY, spaceBefore=3 * mm, spaceAfter=2 * mm,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="SimHei", fontSize=11.5,
            leading=16, textColor=TEAL, spaceBefore=2 * mm, spaceAfter=1.5 * mm,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="SimHei", fontSize=9.4,
            leading=14.2, textColor=INK, alignment=TA_LEFT, spaceAfter=1.6 * mm,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="SimHei", fontSize=8.1,
            leading=11.5, textColor=INK,
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["BodyText"], fontName="SimHei", fontSize=11,
            leading=17, textColor=NAVY, alignment=TA_LEFT, spaceAfter=0,
        ),
        "foot": ParagraphStyle(
            "foot", parent=base["BodyText"], fontName="SimHei", fontSize=7.2,
            leading=10, textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def p(text, style):
    return Paragraph(text, style)


def callout(text, style, background=PALE_BLUE):
    table = Table([[p(text, style)]], colWidths=[172 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def result_table(s):
    data = [
        [p("条件", s["small"]), p("成功", s["small"]), p("完成率", s["small"]), p("二周期回合", s["small"])],
        [p("词面贪心", s["small"]), "0/90", "0.00%", "90/90"],
        [p("词面防循环", s["small"]), "0/90", "0.00%", "81/90"],
        [p("子目标贪心", s["small"]), "3/90", "3.33%", "87/90"],
        [p("子目标 + 防循环", s["small"]), "42/90", "46.67%", "45/90"],
    ]
    table = Table(data, colWidths=[58 * mm, 28 * mm, 34 * mm, 38 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "SimHei"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 4), (-1, 4), PALE_TEAL),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def add_bullet(story, text, style, marker="·"):
    table = Table([[p(marker, style), p(text, style)]], colWidths=[6 * mm, 166 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story.append(table)


def header_footer(canvas, document):
    canvas.saveState()
    canvas.setFont("SimHei", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(19 * mm, 12 * mm, "TraceGraph TG6–TG8 组会速记 | 2026-09-17")
    canvas.drawRightString(191 * mm, 12 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def build():
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing notes: {OUTPUT}")
    register_fonts()
    s = styles()
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm, title="TraceGraph TG6–TG8 组会速记",
        author="SummerSkillOpt Research Project",
    )
    story = []
    story.append(p("TraceGraph TG6–TG8 组会速记", s["title"]))
    story.append(p("核心问题：为什么智能体动作合法、轨迹可审计，却长期无法完成任务？", s["subtitle"]))
    story.append(callout(
        "<b>一句话结论：</b>合法动作、动作多样性和目标词命中都不足以形成任务完成；"
        "在当前 ALFWorld 开发试验中，<b>可观测子目标表示 × 防循环控制</b>出现明显的组合收益。",
        s["callout"],
    ))

    story.append(p("1. 研究链条", s["h1"]))
    add_bullet(story, "<b>TG6：</b>先检验“减少循环、增加探索”是否足够。轨迹变得更多样，但三组仍全部失败，说明新动作/新状态不等于目标进展。", s["body"])
    add_bullet(story, "<b>TG7：</b>加入任务锚点和进度记忆。目标相关动作命中增加，但成功仍为 0，说明记住关键词不等于知道当前应完成哪个子目标。", s["body"])
    add_bullet(story, "<b>TG8：</b>将“进度表示”和“防循环控制”拆成 2×2 因子实验，检验表示主效应、控制器主效应和交互效应。", s["body"])

    story.append(p("2. TG8 设计与结果", s["h1"]))
    story.append(p("30 个任务 × 3 个重复 × 4 个条件 = 360 条；运行时仅使用 observation、historical_actions、admissible_actions。", s["body"]))
    story.append(result_table(s))
    story.append(Spacer(1, 2 * mm))
    add_bullet(story, "任务聚类 bootstrap（30 个任务，10,000 次）：完成率表示效应 <b>+25.00 pp</b>，控制器效应 <b>+21.67 pp</b>，交互效应 <b>+43.33 pp</b>；边际 95% 区间均未跨 0。", s["body"])
    add_bullet(story, "解释：表示负责确定“当前应该推进什么”，防循环负责避免“沿着正确方向反复卡住”；最大的信号来自二者组合。", s["body"])

    story.append(p("3. 组会上必须主动说的边界", s["h1"]))
    limits = [
        "独立单位是 <b>30 个任务</b>，不是 360 条；同一任务—条件的三次轨迹完全一致。",
        "所有失败回合都在第 50 步结束，原计划的 75 步敏感性没有真正实现。",
        "组合组在简单放置和清洗任务上有效，但双物体放置为 <b>0/10 个任务</b>。",
        "当前只是开发试验 signal：未做多重比较校正，也没有跨数据集或确认集证明。",
    ]
    for item in limits:
        add_bullet(story, item, s["body"], marker="—")

    story.append(PageBreak())
    story.append(p("后续研究：我建议优先推进 TG9 机制验证", s["title"]))
    story.append(callout(
        "<b>优先研究问题：</b>为什么当前方法可以完成单物体和清洗任务，却无法完成双物体任务？"
        "这个边界比继续扩大总体样本更容易形成清晰、可反驳的论文贡献。",
        s["callout"], PALE_YELLOW,
    ))

    story.append(p("A. 先做零执行的失败机制分解", s["h1"]))
    hypotheses = [
        "<b>H1 对象身份塌缩：</b>账本只记住“目标物体类型”，不能稳定区分第一个和第二个实例。",
        "<b>H2 子目标重入失败：</b>第一个物体放置后，没有正确回到第二轮 search → pickup → put。",
        "<b>H3 错误完成：</b>第一轮的证据被错误复用于第二轮，导致账本提前完成或停在错误阶段。",
        "<b>H4 候选技能缺口：</b>第二轮存在合法动作，但 SkillBank 匹配或排序不能把它提到前面。",
    ]
    for item in hypotheses:
        add_bullet(story, item, s["body"])
    story.append(p("预期交付：每个失败任务的“首次偏离步骤—账本状态—候选动作—排序原因”矩阵，并把四个假设逐条标为支持/反驳/证据不足。", s["body"]))

    story.append(p("B. TG9 最小可识别实验", s["h1"]))
    tg9 = [
        [p("因素", s["small"]), p("水平 0", s["small"]), p("水平 1", s["small"])],
        [p("对象表示", s["small"]), p("当前类型级账本", s["small"]), p("对象索引/已完成实例绑定", s["small"])],
        [p("重入控制", s["small"]), p("当前流程", s["small"]), p("完成后强制进入下一实例子目标", s["small"])],
    ]
    table = Table(tg9, colWidths=[42 * mm, 63 * mm, 67 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "SimHei"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, -1), PALE_TEAL),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 2 * mm))
    add_bullet(story, "保持防循环、候选技能和其他排序规则固定，只改变对象绑定与重入机制；这样可以直接检验双物体失败的来源。", s["body"])
    add_bullet(story, "使用未被 TG8 诊断消费的新双物体任务；primary endpoint 为第 50 步完成率，机制指标为“第一物体完成后成功进入第二实例流程”的比例。", s["body"])
    add_bullet(story, "先做 readiness 与合成反例测试，再申请正式授权。75 步扩展应作为另一项独立敏感性实验，不能和机制修改混在一起。", s["body"])

    story.append(p("C. 3 分钟口头讲法", s["h1"]))
    script = (
        "“我们研究的不是动作是否合法，而是合法动作为什么不能形成任务进展。TG6 发现，减少循环和增加探索能改变轨迹，"
        "但不能带来成功；TG7 发现，记住目标关键词也不够。于是 TG8 将进度表示与防循环控制拆成 2×2 实验。"
        "结果只有子目标表示与防循环组合出现明显成功，42/90，而其余三组为 0、0、3。任务聚类分析也显示明显交互信号。"
        "但我们不把它写成通用结论：只有 30 个任务，重复轨迹完全一致，75 步没有实现，双物体任务仍全部失败。"
        "下一步我建议集中研究双物体失败，检验对象身份绑定和第二轮子目标重入，而不是马上扩大数据集。”"
    )
    story.append(callout(script, s["body"], PALE_BLUE))

    story.append(p("D. 可以问导师的三个问题", s["h1"]))
    questions = [
        "论文主线是否聚焦“合法性 ≠ 目标进展”，把 TG8 作为机制证据，而不是单纯追求更高成功率？",
        "下一步是否同意先做双物体任务的对象绑定 × 重入控制因子实验？",
        "确认性实验应优先扩大新任务身份，还是先跨环境/跨数据集验证？",
    ]
    for index, item in enumerate(questions, 1):
        add_bullet(story, item, s["body"], marker=str(index))

    story.append(Spacer(1, 2 * mm))
    story.append(p("备注：当前没有新实验授权。TG9 只是研究方案建议，需完成离线诊断、冻结设计和新任务隔离后再执行。", s["foot"]))
    document.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()

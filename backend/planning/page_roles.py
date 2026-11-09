"""第五至第七步共用的页面用途规则。

辅助页仍保存来源，但不成为教学单元；范围只是外包络，实际教学页
需要扣除文档级辅助页。这里不按标题关键词自动推断页面用途。
"""

AUXILIARY_ROLES = frozenset({
    "document_intro", "document_outline", "document_recap",
})

PAGE_USAGE_RULES = """
PAGE PURPOSES

Whole-document covers or orientation, agendas and outlines, and final
Key Takeaways or whole-document recaps are document-level auxiliary material.
They inform structure and coverage checks, but are not standalone learning
units or independent practice scopes. Retain their original pages and sources.

Classify actual function, not title keywords or page position. A page called
Summary, Introduction or Agenda may contain new substantive teaching.
Do not mark a mixed teaching page wholly auxiliary. Preserve its teaching
in an appropriate scope. Missing text is not proof of auxiliary content.

A section-introduction page belongs with the teaching it introduces.
A local example, result, question or recap belongs with the teaching it
develops or consolidates. Neither creates a standalone learning unit merely
because it has its own heading. A question can introduce new teaching;
determine its actual role from the surrounding content.

Do not attach whole-document auxiliary material to unrelated teaching just
to satisfy page coverage. Do not mislabel it administrative or attribution.
An auxiliary-page decision needs evidence from that page and a concise reason.
""".strip()


def auxiliary_page_numbers(plan):
    """已校验计划中的辅助页编号；旧报告缺少字段时按空列表读取。"""
    return {item["page_number"] for item in plan.get("auxiliary_pages", [])}


def scope_page_numbers(scope, plan):
    """返回实际教学页，不能把范围内的辅助页当作教学证据。"""
    auxiliary = auxiliary_page_numbers(plan)
    return [page for page in range(scope["start_page"], scope["end_page"] + 1)
            if page not in auxiliary]

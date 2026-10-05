"""M0 端到端验收（真实走 LLM）：找小米手机 → 加购 → 购物车有图。

运行：.venv\\Scripts\\python scripts/smoke_m0_e2e.py
前置：mall-portal 已在 8081 运行；DEEPSEEK_API_KEY 已配置。

与 smoke_m0.py 的区别：那个只验工具层（不经 LLM）；本脚本让 LLM 自己决定调哪个工具，
验证「ReAct 编排 + 工具层 + mall-v2」整条链路。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage  # noqa: E402

from app.agent import build_agent  # noqa: E402
from app.tools import mall_client  # noqa: E402
from app.tools.order_tools import current_session, current_token, fetch_cart  # noqa: E402

PHONE = "13900007777"
PASSWORD = "Test123456"
SESSION = "smoke-m0-e2e"

ok = 0
fail = 0


def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {label} {extra}")
    else:
        fail += 1
        print(f"  [FAIL] {label} {extra}")


def run(agent, history, text):
    """跑一轮，打印工具调用轨迹，返回本轮新增消息。"""
    print(f"\n[用户] {text}")
    before = len(history)
    result = agent.invoke({"messages": history + [HumanMessage(content=text)]})
    msgs = result["messages"]
    for m in msgs[before:]:
        for tc in (getattr(m, "tool_calls", None) or []):
            print(f"  -> 工具调用 {tc.get('name')}({tc.get('args')})")
        if type(m).__name__ == "ToolMessage":
            content = str(getattr(m, "content", ""))
            print(f"  <- 工具返回 {getattr(m, 'name', '?')}: {content[:120]}")
    print(f"[小M] {getattr(msgs[-1], 'content', '')}")
    return msgs


def main():
    print("=== M0 端到端验收（LLM 驱动）===")

    try:
        mall_client.api_post(mall_client.config.PORTAL_BASE_URL, "/member/register",
                             params={"phone": PHONE, "password": PASSWORD})
    except Exception:  # noqa: BLE001
        pass
    login = mall_client.api_post(mall_client.config.PORTAL_BASE_URL, "/member/login",
                                 params={"phone": PHONE, "password": PASSWORD})
    token = (login.get("data") or {}).get("token")
    check("登录拿到 token", bool(token))
    if not token:
        sys.exit(1)

    current_token.set(token)
    current_session.set(SESSION)

    # 可重复运行：先清空购物车（幽灵缓存条目见缺陷 B1，删不掉就忽略）
    for it in fetch_cart(token):
        try:
            mall_client.api_delete(mall_client.config.PORTAL_BASE_URL, "/cart/delete",
                                   params={"cartItemId": it["cartItemId"]}, token=token)
        except Exception:  # noqa: BLE001
            pass

    agent = build_agent()
    history = []
    history = run(agent, history, "帮我找手机")
    check("第一轮调用了 search_products",
          any("search_products" in str(getattr(m, "tool_calls", "")) for m in history))

    history = run(agent, history, "把第一款加入购物车，1 件")
    added = any("add_to_cart" in str(getattr(m, "tool_calls", "")) for m in history)
    check("第二轮调用了 add_to_cart", added)

    cart = fetch_cart(token)
    mine = [c for c in cart if c.get("productName")]
    check("购物车有商品", len(cart) > 0, f"共 {len(cart)} 条")
    check("购物车条目带图（取图口径未踩坑）",
          any(c.get("pic") for c in cart),
          f"样例pic={((mine[0].get('pic') if mine else '') or '')[:52]}")

    print(f"\n=== 结果：{ok} 通过 / {fail} 失败 ===")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()

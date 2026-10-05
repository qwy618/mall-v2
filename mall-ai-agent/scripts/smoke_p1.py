"""P1 验收脚本（非交互）：跑一次完整 ReAct 循环并打印全过程。

运行：.venv\\Scripts\\python scripts/smoke_p1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import build_agent  # noqa: E402

QUESTION = "帮我找2000元以下的小米手机"


def main():
    agent = build_agent()
    print(f"你: {QUESTION}\n")
    result = agent.invoke({"messages": [("user", QUESTION)]})
    for m in result["messages"]:
        name = type(m).__name__
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                print(f"[{name}] 工具调用: {tc.get('name')}({tc.get('args')})")
        content = getattr(m, "content", "")
        if content:
            label = "你" if name == "HumanMessage" else "小M"
            print(f"[{name}] {label}: {content[:600]}")
        else:
            print(f"[{name}] (空内容)")
        print("-" * 70)


if __name__ == "__main__":
    main()

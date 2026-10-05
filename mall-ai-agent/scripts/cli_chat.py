"""P1 验收入口：命令行和 agent 对话，观察工具调用全过程。

运行：.venv\\Scripts\\python scripts/cli_chat.py
验收标准：问「帮我找2000元以下的小米手机」，能看到
  [工具调用] search_products(...) → 真实商品列表 → 按价格筛选后的推荐
带会话记忆：后续提问能记住上文（「给我推荐充电宝」→「200元左右」不会失忆）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 让 app 包可导入

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from app.agent import build_agent  # noqa: E402


def main():
    print("=== mall AI 助手（命令行版，带会话记忆）===")
    print("试试：帮我找2000元以下的小米手机")
    print("输入 quit 退出\n")
    try:
        agent = build_agent()
    except RuntimeError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    history = []  # 会话历史：每轮的用户消息和助手回复都记下来
    while True:
        try:
            text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not text:
            continue
        if text in ("quit", "exit", "退出"):
            print("再见！")
            break

        history.append(HumanMessage(content=text))
        print("小M: ", end="", flush=True)
        reply = ""
        for chunk in agent.stream({"messages": list(history)}, stream_mode="messages"):
            if isinstance(chunk, tuple):   # 兼容不同版本的返回形态
                chunk = chunk[0]
            tool_calls = getattr(chunk, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    print(f"\n  [工具调用] {tc.get('name')}({tc.get('args')})")
            content = getattr(chunk, "content", "")
            if content:
                reply += content
                print(content, end="", flush=True)
        history.append(AIMessage(content=reply))
        print()


if __name__ == "__main__":
    main()

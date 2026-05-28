#!/usr/bin/env python3
"""
启动团队协作 Web UI

用法:
    python run_team_ui.py [--port 8080] [--host 0.0.0.0]

演示模式 (无需 LLM API Key):
    python run_team_ui.py

带 LLM:
    OPENAI_API_KEY=sk-xxx python run_team_ui.py --llm openai
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Team Collaboration Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--llm", choices=["openai", "anthropic", "none"], default="none",
                        help="LLM provider (default: none = demo mode)")
    parser.add_argument("--model", default=None, help="Default model name")
    args = parser.parse_args()

    # 配置 LLM
    llm = None
    if args.llm == "openai":
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=args.model or "gpt-4o", temperature=0.7)
            print(f"✅ Using OpenAI: {args.model or 'gpt-4o'}")
        except Exception as e:
            print(f"⚠️  OpenAI setup failed: {e}, falling back to demo mode")
    elif args.llm == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=args.model or "claude-sonnet-4-20250514", temperature=0.7)
            print(f"✅ Using Anthropic: {args.model or 'claude-sonnet-4-20250514'}")
        except Exception as e:
            print(f"⚠️  Anthropic setup failed: {e}, falling back to demo mode")

    if llm is None:
        print("🎭 Running in DEMO mode (mock responses, no API key needed)")
        print("   Use --llm openai|anthropic to enable real LLM calls")

    print(f"\n🚀 Starting Team Collaboration UI...")
    print(f"   URL: http://localhost:{args.port}")
    print(f"   Press Ctrl+C to stop\n")

    from agent.web.server import run_team_server
    run_team_server(host=args.host, port=args.port, llm=llm)


if __name__ == "__main__":
    main()

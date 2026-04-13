#!/usr/bin/env python3
"""Test each auxiliary model with a simple prompt."""

import asyncio
import sys
import time
sys.path.insert(0, '/home/butterfly443/.hermes/hermes-agent')

from agent.auxiliary_client import async_call_llm


async def test_vision():
    print("\n=== Vision ===")
    try:
        result = await async_call_llm(
            task="vision",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_74x24dp.png"}}
                ]
            }],
            timeout=30,
        )
        print(f"✓ Vision OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Vision FAILED: {e}")
        return False


async def test_compression():
    print("\n=== Compression ===")
    try:
        long_text = "Hello world. " * 200
        result = await async_call_llm(
            task="compression",
            messages=[{"role": "user", "content": f"Summarize this: {long_text}"}],
            timeout=30,
        )
        print(f"✓ Compression OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Compression FAILED: {e}")
        return False


async def test_session_search():
    print("\n=== Session Search ===")
    try:
        result = await async_call_llm(
            task="session_search",
            messages=[{"role": "user", "content": "What did we discuss about Python?"}],
            timeout=30,
        )
        print(f"✓ Session Search OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Session Search FAILED: {e}")
        return False


async def test_flush_memories():
    print("\n=== Flush Memories ===")
    try:
        result = await async_call_llm(
            task="flush_memories",
            messages=[{"role": "user", "content": "Remember this: The capital of France is Paris."}],
            timeout=30,
        )
        print(f"✓ Flush Memories OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Flush Memories FAILED: {e}")
        return False


async def test_skills_hub():
    print("\n=== Skills Hub ===")
    try:
        result = await async_call_llm(
            task="skills_hub",
            messages=[{"role": "user", "content": "Find a skill for web scraping"}],
            timeout=30,
        )
        print(f"✓ Skills Hub OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Skills Hub FAILED: {e}")
        return False


async def test_web_extract():
    print("\n=== Web Extract ===")
    try:
        result = await async_call_llm(
            task="web_extract",
            messages=[{"role": "user", "content": "Extract the title from https://example.com"}],
            timeout=30,
        )
        print(f"✓ Web Extract OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Web Extract FAILED: {e}")
        return False


async def test_approval():
    print("\n=== Approval ===")
    try:
        result = await async_call_llm(
            task="approval",
            messages=[{"role": "user", "content": "Should I approve deleting this file?"}],
            timeout=30,
        )
        print(f"✓ Approval OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Approval FAILED: {e}")
        return False


async def test_mcp():
    print("\n=== MCP ===")
    try:
        result = await async_call_llm(
            task="mcp",
            messages=[{"role": "user", "content": "List available MCP tools"}],
            timeout=30,
        )
        print(f"✓ MCP OK: {result.choices[0].message.content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ MCP FAILED: {e}")
        return False


def show_current_config():
    print("\n=== Current Auxiliary Config ===")
    import yaml
    with open('/home/butterfly443/.hermes/config.yaml') as f:
        config = yaml.safe_load(f)
    
    aux = config.get('auxiliary', {})
    for task, cfg in aux.items():
        if isinstance(cfg, dict):
            provider = cfg.get('provider', 'auto')
            model = cfg.get('model', '')
            print(f"  {task}: provider={provider}, model={model or '(default)'}")
        else:
            print(f"  {task}: {cfg}")


async def run_tests():
    show_current_config()
    
    tests = [
        ("Vision", test_vision),
        ("Compression", test_compression),
        ("Session Search", test_session_search),
        ("Flush Memories", test_flush_memories),
        ("Skills Hub", test_skills_hub),
        ("Web Extract", test_web_extract),
        ("Approval", test_approval),
        ("MCP", test_mcp),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            ok = await test_fn()
            results.append((name, ok))
        except Exception as e:
            print(f"✗ {name} CRASHED: {e}")
            results.append((name, False))
        await asyncio.sleep(1)
    
    print("\n=== Summary ===")
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}: {name}")


if __name__ == "__main__":
    asyncio.run(run_tests())

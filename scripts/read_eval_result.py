import json

with open('C:/project/hermes-agent/scripts/qwen235b_agent_eval_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for turn in data['conversation_turns']:
    print(f"=== 第{turn['turn']}轮 ===")
    print(f"用户消息: {turn['user_message'][:200]}...")
    print(f"模型响应长度: {len(turn['model_response'])} 字符")
    print(f"模型响应前1000字符:")
    print(turn['model_response'][:1000])
    print()

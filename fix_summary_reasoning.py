#!/usr/bin/env python3
path = '/Users/lierdong/.hermes/hermes-agent/run_agent.py'
with open(path, 'r') as f:
    content = f.read()

old = '''            summary_extra_body = {}
            _is_nous = "nousresearch" in self._base_url_lower
            if self._supports_reasoning_extra_body():
                if self.reasoning_config is not None:
                    summary_extra_body["reasoning"] = self.reasoning_config
                else:
                    summary_extra_body["reasoning"] = {
                        "enabled": True,
                        "effort": "medium"
                    }
            if _is_nous:
                summary_extra_body["tags"] = ["product=hermes-agent"]'''

new = '''            summary_extra_body = {}
            _is_nous = "nousresearch" in self._base_url_lower
            if self._supports_reasoning_extra_body():
                if self.reasoning_config is not None:
                    rc = dict(self.reasoning_config)
                    if self.thinking_budget is not None:
                        rc["budget"] = self.thinking_budget
                    summary_extra_body["reasoning"] = rc
                else:
                    summary_extra_body["reasoning"] = {
                        "enabled": True,
                        "effort": "medium"
                    }
            if _is_nous:
                summary_extra_body["tags"] = ["product=hermes-agent"]'''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(content)
    print("SUCCESS: replacement done")
else:
    print("ERROR: pattern not found")

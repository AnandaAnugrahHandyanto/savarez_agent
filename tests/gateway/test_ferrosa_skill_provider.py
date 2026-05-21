import json

from plugins.memory.ferrosa import FerrosaSkillProvider
from agent.skill_providers import SkillMetadata, SkillPayload, clear_skill_providers, register_skill_provider


class FakeClient:
    def __init__(self):
        self.calls = []

    def call(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        if tool_name == "retrieve_skills_for_context":
            return {
                "results": [
                    {
                        "skill_name": "blueprint",
                        "description": "Generates a complete project blueprint.",
                        "category": "task-level",
                        "version": "2026050185",
                    }
                ]
            }
        if tool_name == "invoke_skill":
            assert arguments == {"skill_name": "blueprint"}
            return {
                "skill_name": "blueprint",
                "description": "Generates a complete project blueprint.",
                "category": "task-level",
                "version": "2026050185",
                "first_step_prompt": "Follow the Spec Root Resolution guidance.",
                "steps": [
                    {"phase": "Spec Root Resolution", "instruction": "Resolve spec root."},
                    {"phase": "Phase 0", "instruction": "Run reconnaissance."},
                ],
                "completion_criteria": "Blueprint artifacts are complete.",
                "output_artifacts": ["specs/architecture.md"],
            }
        raise AssertionError(tool_name)


def test_ferrosa_skill_provider_lists_blueprint_from_fmem():
    provider = FerrosaSkillProvider(client=FakeClient())

    skills = provider.list_skills()

    assert len(skills) == 1
    assert skills[0].name == "blueprint"
    assert skills[0].description == "Generates a complete project blueprint."
    assert skills[0].category == "task-level"


def test_ferrosa_skill_provider_resolves_blueprint_as_virtual_skill_payload():
    provider = FerrosaSkillProvider(client=FakeClient())

    payload = provider.resolve_skill("blueprint")

    assert isinstance(payload, SkillPayload)
    assert payload.name == "blueprint"
    assert payload.description == "Generates a complete project blueprint."
    assert "# blueprint" in payload.content
    assert "Resolve spec root." in payload.content
    assert "Blueprint artifacts are complete." in payload.content


class FakeRegisteredProvider:
    def list_skills(self):
        return [
            SkillMetadata(
                name="blueprint",
                description="Generates a complete project blueprint.",
                category="task-level",
            )
        ]

    def resolve_skill(self, name):
        if name != "blueprint":
            return None
        return SkillPayload(
            name="blueprint",
            description="Generates a complete project blueprint.",
            content="---\nname: blueprint\ndescription: Generates a complete project blueprint.\n---\n\n# blueprint\n\nFrom fmem.\n",
        )


def test_skills_list_and_view_load_active_memory_skill_provider(monkeypatch):
    from tools import skills_tool
    import plugins.memory

    clear_skill_providers()

    def fake_register_active_memory_skill_providers():
        register_skill_provider(FakeRegisteredProvider(), namespace="fmem")

    monkeypatch.setattr(
        plugins.memory,
        "register_active_memory_skill_providers",
        fake_register_active_memory_skill_providers,
    )

    listed = json.loads(skills_tool.skills_list())
    assert any(skill["name"] == "fmem:blueprint" for skill in listed["skills"])

    viewed = json.loads(skills_tool.skill_view("fmem:blueprint"))
    assert viewed["success"] is True
    assert viewed["name"] == "fmem:blueprint"
    assert viewed["provider"] == "fmem"
    assert "From fmem." in viewed["content"]

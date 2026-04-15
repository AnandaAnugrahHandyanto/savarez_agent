"""
hermes CLI용 cron 하위 명령.

list, create, edit, pause/resume/run/remove, status, tick 같은
독립형 cron 관리 명령을 처리합니다.
"""

import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from hermes_cli.colors import Colors, color


def _normalize_skills(single_skill=None, skills: Optional[Iterable[str]] = None) -> Optional[List[str]]:
    if skills is None:
        if single_skill is None:
            return None
        raw_items = [single_skill]
    else:
        raw_items = list(skills)

    normalized: List[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _cron_api(**kwargs):
    from tools.cronjob_tools import cronjob as cronjob_tool

    return json.loads(cronjob_tool(**kwargs))


def cron_list(show_all: bool = False):
    """List all scheduled jobs."""
    from cron.jobs import list_jobs

    jobs = list_jobs(include_disabled=show_all)

    if not jobs:
        print(color("예약된 작업이 없어요.", Colors.DIM))
        print(color("'hermes cron create ...' 또는 채팅의 /cron 명령으로 만들어 보세요.", Colors.DIM))
        return

    print()
    print(color("┌─────────────────────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│                           예약 작업 목록                                 │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    for job in jobs:
        job_id = job.get("id", "?")
        name = job.get("name", "(unnamed)")
        schedule = job.get("schedule_display", job.get("schedule", {}).get("value", "?"))
        state = job.get("state", "scheduled" if job.get("enabled", True) else "paused")
        next_run = job.get("next_run_at", "?")

        repeat_info = job.get("repeat", {})
        repeat_times = repeat_info.get("times")
        repeat_completed = repeat_info.get("completed", 0)
        repeat_str = f"{repeat_completed}/{repeat_times}" if repeat_times else "∞"

        deliver = job.get("deliver", ["local"])
        if isinstance(deliver, str):
            deliver = [deliver]
        deliver_str = ", ".join(deliver)

        skills = job.get("skills") or ([job["skill"]] if job.get("skill") else [])
        if state == "paused":
            status = color("[paused]", Colors.YELLOW)
        elif state == "completed":
            status = color("[completed]", Colors.BLUE)
        elif job.get("enabled", True):
            status = color("[active]", Colors.GREEN)
        else:
            status = color("[disabled]", Colors.RED)

        print(f"  {color(job_id, Colors.YELLOW)} {status}")
        print(f"    이름:      {name}")
        print(f"    일정:      {schedule}")
        print(f"    반복:      {repeat_str}")
        print(f"    다음 실행: {next_run}")
        print(f"    전달:      {deliver_str}")
        if skills:
            print(f"    스킬:      {', '.join(skills)}")
        script = job.get("script")
        if script:
            print(f"    스크립트:  {script}")

        # Execution history
        last_status = job.get("last_status")
        if last_status:
            last_run = job.get("last_run_at", "?")
            if last_status == "ok":
                status_display = color("ok", Colors.GREEN)
            else:
                status_display = color(f"{last_status}: {job.get('last_error', '?')}", Colors.RED)
            print(f"    마지막 실행: {last_run}  {status_display}")

        delivery_err = job.get("last_delivery_error")
        if delivery_err:
            print(f"    {color('⚠ 전달 실패:', Colors.YELLOW)} {delivery_err}")

        print()

    from hermes_cli.gateway import find_gateway_pids
    if not find_gateway_pids():
        print(color("  ⚠  게이트웨이가 실행 중이 아니어서 작업이 자동 실행되지 않아요.", Colors.YELLOW))
        print(color("     시작 명령: hermes gateway install", Colors.DIM))
        print(color("                sudo hermes gateway install --system  # Linux 서버", Colors.DIM))
        print()


def cron_tick():
    """Run due jobs once and exit."""
    from cron.scheduler import tick
    tick(verbose=True)


def cron_status():
    """Show cron execution status."""
    from cron.jobs import list_jobs
    from hermes_cli.gateway import find_gateway_pids

    print()

    pids = find_gateway_pids()
    if pids:
        print(color("✓ 게이트웨이가 실행 중이어서 cron 작업이 자동으로 실행돼요", Colors.GREEN))
        print(f"  PID: {', '.join(map(str, pids))}")
    else:
        print(color("✗ 게이트웨이가 실행 중이 아니어서 cron 작업이 자동 실행되지 않아요", Colors.RED))
        print()
        print("  자동 실행을 켜려면:")
        print("    hermes gateway install    # 사용자 서비스로 설치")
        print("    sudo hermes gateway install --system  # Linux 서버: 부팅 시 시작되는 시스템 서비스")
        print("    hermes gateway            # 또는 포그라운드 실행")

    print()

    jobs = list_jobs(include_disabled=False)
    if jobs:
        next_runs = [j.get("next_run_at") for j in jobs if j.get("next_run_at")]
        print(f"  활성 작업 {len(jobs)}개")
        if next_runs:
            print(f"  다음 실행: {min(next_runs)}")
    else:
        print("  활성 작업이 없어요")

    print()


def cron_create(args):
    result = _cron_api(
        action="create",
        schedule=args.schedule,
        prompt=args.prompt,
        name=getattr(args, "name", None),
        deliver=getattr(args, "deliver", None),
        repeat=getattr(args, "repeat", None),
        skill=getattr(args, "skill", None),
        skills=_normalize_skills(getattr(args, "skill", None), getattr(args, "skills", None)),
        script=getattr(args, "script", None),
    )
    if not result.get("success"):
        print(color(f"작업을 만들지 못했어요: {result.get('error', '알 수 없는 오류')}", Colors.RED))
        return 1
    print(color(f"작업을 만들었어요: {result['job_id']}", Colors.GREEN))
    print(f"  이름: {result['name']}")
    print(f"  일정: {result['schedule']}")
    if result.get("skills"):
        print(f"  스킬: {', '.join(result['skills'])}")
    job_data = result.get("job", {})
    if job_data.get("script"):
        print(f"  스크립트: {job_data['script']}")
    print(f"  다음 실행: {result['next_run_at']}")
    return 0


def cron_edit(args):
    from cron.jobs import get_job

    job = get_job(args.job_id)
    if not job:
        print(color(f"작업을 찾지 못했어요: {args.job_id}", Colors.RED))
        return 1

    existing_skills = list(job.get("skills") or ([] if not job.get("skill") else [job.get("skill")]))
    replacement_skills = _normalize_skills(getattr(args, "skill", None), getattr(args, "skills", None))
    add_skills = _normalize_skills(None, getattr(args, "add_skills", None)) or []
    remove_skills = set(_normalize_skills(None, getattr(args, "remove_skills", None)) or [])

    final_skills = None
    if getattr(args, "clear_skills", False):
        final_skills = []
    elif replacement_skills is not None:
        final_skills = replacement_skills
    elif add_skills or remove_skills:
        final_skills = [skill for skill in existing_skills if skill not in remove_skills]
        for skill in add_skills:
            if skill not in final_skills:
                final_skills.append(skill)

    result = _cron_api(
        action="update",
        job_id=args.job_id,
        schedule=getattr(args, "schedule", None),
        prompt=getattr(args, "prompt", None),
        name=getattr(args, "name", None),
        deliver=getattr(args, "deliver", None),
        repeat=getattr(args, "repeat", None),
        skills=final_skills,
        script=getattr(args, "script", None),
    )
    if not result.get("success"):
        print(color(f"작업을 업데이트하지 못했어요: {result.get('error', '알 수 없는 오류')}", Colors.RED))
        return 1

    updated = result["job"]
    print(color(f"작업을 업데이트했어요: {updated['job_id']}", Colors.GREEN))
    print(f"  이름: {updated['name']}")
    print(f"  일정: {updated['schedule']}")
    if updated.get("skills"):
        print(f"  스킬: {', '.join(updated['skills'])}")
    else:
        print("  스킬: 없음")
    if updated.get("script"):
        print(f"  스크립트: {updated['script']}")
    return 0


def _job_action(action: str, job_id: str, success_verb: str) -> int:
    result = _cron_api(action=action, job_id=job_id)
    if not result.get("success"):
        print(color(f"작업 {action}에 실패했어요: {result.get('error', '알 수 없는 오류')}", Colors.RED))
        return 1
    job = result.get("job") or result.get("removed_job") or {}
    print(color(f"{success_verb} job: {job.get('name', job_id)} ({job_id})", Colors.GREEN))
    if action in {"resume", "run"} and result.get("job", {}).get("next_run_at"):
        print(f"  다음 실행: {result['job']['next_run_at']}")
    if action == "run":
        print("  다음 scheduler tick에서 실행돼요.")
    return 0


def cron_command(args):
    """Handle cron subcommands."""
    subcmd = getattr(args, 'cron_command', None)

    if subcmd is None or subcmd == "list":
        show_all = getattr(args, 'all', False)
        cron_list(show_all)
        return 0

    if subcmd == "status":
        cron_status()
        return 0

    if subcmd == "tick":
        cron_tick()
        return 0

    if subcmd in {"create", "add"}:
        return cron_create(args)

    if subcmd == "edit":
        return cron_edit(args)

    if subcmd == "pause":
        return _job_action("pause", args.job_id, "일시중지한")

    if subcmd == "resume":
        return _job_action("resume", args.job_id, "재개한")

    if subcmd == "run":
        return _job_action("run", args.job_id, "실행 예약한")

    if subcmd in {"remove", "rm", "delete"}:
        return _job_action("remove", args.job_id, "제거한")

    print(f"알 수 없는 cron 명령어예요: {subcmd}")
    print("사용법: hermes cron [list|create|edit|pause|resume|run|remove|status|tick]")
    sys.exit(1)

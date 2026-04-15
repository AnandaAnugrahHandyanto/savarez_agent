"""
DM 페어링 시스템용 CLI 명령.

사용 예:
    hermes pairing list                    # 대기 중 + 승인된 사용자 모두 표시
    hermes pairing approve <platform> <code>   # 페어링 코드 승인
    hermes pairing revoke <platform> <user_id> # 사용자 접근 권한 철회
    hermes pairing clear-pending           # 만료/대기 코드를 모두 비우기
"""

def pairing_command(args):
    """Handle hermes pairing subcommands."""
    from gateway.pairing import PairingStore

    store = PairingStore()
    action = getattr(args, "pairing_action", None)

    if action == "list":
        _cmd_list(store)
    elif action == "approve":
        _cmd_approve(store, args.platform, args.code)
    elif action == "revoke":
        _cmd_revoke(store, args.platform, args.user_id)
    elif action == "clear-pending":
        _cmd_clear_pending(store)
    else:
        print("사용법: hermes pairing {list|approve|revoke|clear-pending}")
        print("자세한 내용은 'hermes pairing --help'를 실행하세요.")


def _cmd_list(store):
    """대기 중인 사용자와 승인된 사용자를 모두 표시."""
    pending = store.list_pending()
    approved = store.list_approved()

    if not pending and not approved:
        print("페어링 데이터가 없어요. 아직 아무도 페어링을 시도하지 않았어요~")
        return

    if pending:
        print(f"\n  대기 중인 페어링 요청 ({len(pending)}):")
        print(f"  {'플랫폼':<12} {'코드':<10} {'사용자 ID':<20} {'이름':<20} {'경과 시간'}")
        print(f"  {'------':<12} {'----':<10} {'---------':<20} {'----':<20} {'---------'}")
        for p in pending:
            print(
                f"  {p['platform']:<12} {p['code']:<10} {p['user_id']:<20} "
                f"{p.get('user_name', ''):<20} {p['age_minutes']}분 전"
            )
    else:
        print("\n  대기 중인 페어링 요청이 없어요.")

    if approved:
        print(f"\n  승인된 사용자 ({len(approved)}):")
        print(f"  {'플랫폼':<12} {'사용자 ID':<20} {'이름':<20}")
        print(f"  {'------':<12} {'---------':<20} {'----':<20}")
        for a in approved:
            print(f"  {a['platform']:<12} {a['user_id']:<20} {a.get('user_name', ''):<20}")
    else:
        print("\n  승인된 사용자가 없어요.")

    print()


def _cmd_approve(store, platform: str, code: str):
    """페어링 코드를 승인."""
    platform = platform.lower().strip()
    code = code.upper().strip()

    result = store.approve_code(platform, code)
    if result:
        uid = result["user_id"]
        name = result.get("user_name", "")
        display = f"{name} ({uid})" if name else uid
        print(f"\n  승인 완료! 이제 {platform}의 사용자 {display} 가 봇을 사용할 수 있어요~")
        print("  다음 메시지부터 자동으로 인식돼요.\n")
    else:
        print(f"\n  플랫폼 '{platform}'에서 코드 '{code}'를 찾지 못했거나 이미 만료되었어요.")
        print("  대기 중인 코드를 보려면 'hermes pairing list'를 실행하세요.\n")


def _cmd_revoke(store, platform: str, user_id: str):
    """사용자 접근 권한을 철회."""
    platform = platform.lower().strip()

    if store.revoke(platform, user_id):
        print(f"\n  {platform}의 사용자 {user_id} 접근 권한을 철회했어요.\n")
    else:
        print(f"\n  {platform}의 승인 목록에서 사용자 {user_id}를 찾지 못했어요.\n")


def _cmd_clear_pending(store):
    """대기 중인 페어링 코드를 모두 비움."""
    count = store.clear_pending()
    if count:
        print(f"\n  대기 중인 페어링 요청 {count}개를 비웠어요.\n")
    else:
        print("\n  비울 대기 요청이 없어요.\n")
